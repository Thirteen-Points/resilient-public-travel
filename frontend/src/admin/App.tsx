import { useCallback, useEffect, useState } from 'react'
import type { Event, Network, Signal } from '../api/types'
import { ReviewConsole } from '../components/ReviewConsole'
import { SignalInbox } from '../components/SignalInbox'
import { call, network, reviewApi, saveReview, setSession } from './client'
import { LLMSettings } from './LLMSettings'
import type { Activity, Overview, Session, Settings, SourceConfig, SourceResult } from './client'
const titles = { overview: 'Overview', review: 'Reports & Review', settings: 'API Settings', activity: 'Activity' }
type Page = keyof typeof titles
const errorText = (error: unknown) => error instanceof Error ? error.message : 'The request could not be completed.'
const time = (at: string) => new Date(at).toLocaleString('en-HK', { timeZone: 'Asia/Hong_Kong', hour12: false }) + ' HKT'
function Result({ value }: { value: SourceResult | null }) {
  if (!value) return <p className="muted">Not run yet. No scheduled collection.</p>
  return <div className="run-result"><span className={`pill ${value.failures ? 'warning' : ''}`}>{value.status.replaceAll('_', ' ')}</span><p>{value.added} new · {value.duplicate} duplicates · {value.failures} failures</p>
    {value.details.consecutive_polls !== undefined && <p>Consecutive observations: {String(value.details.consecutive_polls)} · usable stations: {String(value.details.observations)}. An anomaly report needs the saved detection threshold.</p>}
    {value.details.active_codes !== undefined && <p>Active warning codes: {(value.details.active_codes as string[]).join(', ') || 'None'}</p>}
    {!value.added && !value.failures && <p className="muted">No new reports. Collection never publishes events automatically.</p>}<small>{time(value.at)}</small></div>
}
function Login({ onLogin, configured, expired }: { onLogin: (session: Session) => void; configured: boolean; expired: boolean }) {
  const [username, setUsername] = useState('admin'), [password, setPassword] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  return <section className={expired ? 'login-overlay' : 'login-screen'}><form className="login-card" onSubmit={async e => {
    e.preventDefault(); setBusy(true); setError('')
    try { const s = await call<Session>('/login', { username, password }); setPassword(''); onLogin(s) }
    catch (cause) { setError(errorText(cause)) } finally { setBusy(false) }
  }}><span className="eyebrow">RESILIENTROUTE / ADMINISTRATION</span><h1>A clearer signal.</h1><p className="muted">Review the evidence. Keep the network informed.</p>
    {configured ? <>{expired && <p role="alert">Your session expired. Sign in to continue; this page keeps your unsaved work.</p>}<label>Username<input autoComplete="username" required value={username} onChange={e => setUsername(e.target.value)} /></label><label>Password<input autoComplete="current-password" type="password" required maxLength={1024} value={password} onChange={e => setPassword(e.target.value)} /></label><button className="primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in →'}</button></> : <p role="alert">Administrator access is not configured. Ask the service owner to configure the Render administrator variables.</p>}
    {error && <p className="alert error" role="alert">{error}</p>}<a href="https://resilient-public-travel.pages.dev">Open public website ↗</a>
  </form></section>
}
function SettingsPanel({ onDirty }: { onDirty: (dirty: boolean) => void }) {
  const [settings, setSettings] = useState<Settings | null>(null), [baseline, setBaseline] = useState(''), [busy, setBusy] = useState(''), [notice, setNotice] = useState(''), [error, setError] = useState('')
  const [results, setResults] = useState<Partial<Record<'mtr' | 'hko', SourceResult>>>({})
  const accept = (s: Settings) => { setSettings(s); setBaseline(JSON.stringify(s)) }
  useEffect(() => { call<Settings>('/settings').then(accept).catch(e => setError(errorText(e))) }, [])
  const dirty = settings !== null && JSON.stringify(settings) !== baseline
  useEffect(() => { onDirty(dirty); return () => onDirty(false) }, [dirty, onDirty])
  const operate = async (id: string, fn: () => Promise<void>) => { if (busy) return; setBusy(id); setError(''); setNotice(''); try { await fn() } catch (e) { setError(errorText(e)) } finally { setBusy('') } }
  if (!settings) return <section className="card"><p>{error || 'Loading API settings…'}</p><button className="secondary" onClick={() => { setError(''); call<Settings>('/settings').then(accept).catch(e => setError(errorText(e))) }}>Retry</button></section>
  const updateSource = (name: 'mtr' | 'hko', patch: Partial<SourceConfig>) => setSettings({ ...settings, sources: { ...settings.sources, [name]: { ...settings.sources[name], ...patch } } })
  const names = settings.ai.order
  return <form className="settings-layout" onSubmit={e => { e.preventDefault(); void operate('save', async () => {
    const providers = Object.fromEntries(names.map(name => { const p = settings.ai.providers[name]; return [name, { name:p.name, model:p.model, base_url:p.base_url, enabled:p.enabled, keys:p.keys.map(k=>({id:k.id,label:k.label,value:k.value?.trim() || null})) }] }))
    accept(await call<Settings>('/settings', { ...settings, ai: { ...settings.ai, providers } })); setNotice('Settings saved. New structuring requests use this configuration immediately.')
  }) }}>
    <div className="settings-bar card"><div><strong>{dirty ? 'Unsaved changes' : `Configuration revision ${settings.revision}`}</strong><p className="muted">Saved on the persistent disk. Tests use saved settings.</p></div><button className="primary" disabled={!dirty || Boolean(busy)}>{busy === 'save' ? 'Saving…' : 'Save settings'}</button></div>
    {error && <p className="alert error" role="alert">{error}</p>}{notice && <p className="alert" role="status">{notice}</p>}
    <fieldset disabled={Boolean(busy)}><LLMSettings ai={settings.ai} change={ai => setSettings({ ...settings, ai })} dirty={dirty} busy={busy} test={(provider, key_id) => {
      if (!window.confirm('Send one request with this key? It may incur a charge. No user reports are sent.')) return
      void operate(`test-${provider}-${key_id}`, async () => { const result = await call<{ok:boolean;message:string;ai:Settings['ai']}>('/test/ai',{provider,key_id,confirm_external_request:true}); accept({...settings,ai:result.ai}); if (result.ok) setNotice(result.message); else setError(result.message) })
    }} />
    <section className="card"><span className="eyebrow">OFFICIAL DATA SOURCES</span><h2>Collect evidence on demand.</h2><p className="muted">External requests run only when you press Test or Collect. New signals await human review. There are no scheduled jobs.</p>
      <div className="source-grid">{(['mtr', 'hko'] as const).map(name => { const cfg = settings.sources[name]; return <section className="provider" key={name}><div className="row"><h3>{name === 'mtr' ? 'MTR · East Rail' : 'Hong Kong Observatory'}</h3><span className="pill">{cfg.enabled ? 'Enabled' : 'Disabled'}</span></div><p className="muted">{name === 'mtr' ? 'TAW · KOT · MKK · HUH · EXC · ADM. Anomalies are project heuristics, not official delay notices.' : 'Active weather warnings and cleared warnings. Unchanged warning sets produce no new reports.'}</p>
        <label className="toggle"><input type="checkbox" checked={cfg.enabled} onChange={e => updateSource(name, { enabled: e.target.checked })} />Enable manual collection</label>
        <div className="field-grid"><label>Request timeout · seconds<input type="number" min="2" max="15" required value={cfg.timeout_s} onChange={e => updateSource(name, { timeout_s: Number(e.target.value) })} /></label><label>Minimum interval · seconds<input type="number" min="60" max={name === 'hko' ? 120 : 600} required value={cfg.poll_interval_seconds} onChange={e => updateSource(name, { poll_interval_seconds: Number(e.target.value) })} /></label></div>
        {name === 'mtr' ? <div className="field-grid">{([{ key: 'ttnt_threshold_minutes', label: 'Arrival threshold · minutes', min: 1, max: 60 },{key:'min_adjacent_stations',label:'Adjacent anomalous stations',min:2,max:6},{key:'min_consecutive_polls',label:'Consecutive observations',min:1,max:10},{key:'min_usable_stations',label:'Minimum usable stations',min:2,max:6}] as const).map(f => <label key={f.key}>{f.label}<input type="number" min={f.min} max={f.max} required value={cfg[f.key]} onChange={e => updateSource(name, { [f.key]: Number(e.target.value) })} /></label>)}</div> : <label>Language<select value={cfg.lang} onChange={e => updateSource(name, { lang: e.target.value as 'tc' | 'sc' | 'en' })}><option value="tc">Traditional Chinese</option><option value="sc">Simplified Chinese</option><option value="en">English</option></select></label>}
        <div className="actions">{(['test','collect'] as const).map(operation => <button key={operation} type="button" className={operation === 'collect' ? 'primary' : 'secondary'} disabled={dirty || (operation === 'collect' && !cfg.enabled)} onClick={() => void operate(`${name}-${operation}`, async () => { const result = await call<SourceResult>(`/sources/${name}/${operation}`, {}); setResults(previous => ({ ...previous, [name]: result })); setNotice(operation === 'test' ? 'Connection test complete. Reports and detection state were not changed.' : `Collection complete: ${result.added} new reports. Review remains required.`) })}>{busy === `${name}-${operation}` ? 'Running…' : operation === 'test' ? 'Test connection' : 'Collect now'}</button>)}</div>
        <Result value={results[name] ?? null} />
      </section> })}</div>
      <div className="not-connected"><strong>KMB/LWB & Citybus arrivals</strong><span className="pill">Connected</span><p className="muted">Official arrivals are available on public bus journey pages. Arrival observations do not automatically publish disruption reports.</p><a href="/api/buses/status" target="_blank" rel="noreferrer">Bus data coverage →</a></div>
    </section></fieldset>
  </form>
}
function ActivityPanel() {
  const [rows, setRows] = useState<Activity[]>([]), [error, setError] = useState(''), [busy, setBusy] = useState(false), [more, setMore] = useState(true)
  const load = async (append = false) => { setBusy(true); setError(''); try { const values = await call<Activity[]>(`/activity${append && rows.length ? `?before=${rows.at(-1)!.id}` : ''}`); setRows(previous => append ? [...previous,...values] : values); setMore(values.length === 100) } catch (e) { setError(errorText(e)) } finally { setBusy(false) } }
  useEffect(() => { void load() }, [])
  return <section className="card"><div className="row"><div><span className="eyebrow">DURABLE OPERATION HISTORY</span><h2>A record of every decision.</h2></div><button className="secondary" disabled={busy} onClick={() => void load()}>Refresh</button></div>{error && <p className="alert error" role="alert">{error}</p>}<div className="table-scroll"><table><thead><tr><th>Time</th><th>Actor / action</th><th>Target</th><th>Result</th><th>Detail</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><td>{time(row.at)}</td><td><strong>{row.actor}</strong><br/>{row.action.replaceAll('_',' ')}</td><td>{row.target}</td><td><span className="pill">{row.result}</span></td><td>{row.detail || '—'}</td></tr>)}</tbody></table></div>{!rows.length && <p className="muted">{busy ? 'Loading activity…' : 'No activity yet.'}</p>}{more && rows.length > 0 && <button className="secondary" disabled={busy} onClick={() => void load(true)}>Load earlier activity</button>}</section>
}
export function AdminApp() {
  const [session, setUser] = useState<Session | null>(null), [configured, setConfigured] = useState(false), [loading, setLoading] = useState(true), [expired, setExpired] = useState(false)
  const [page, setPage] = useState<Page>('overview'), [overview, setOverview] = useState<Overview | null>(null), [error, setError] = useState(''), [notice, setNotice] = useState('')
  const [data, setData] = useState<{events: Event[]; signals: Signal[]; network: Network} | null>(null)
  const [reviewDirty, setReviewDirty] = useState(false), [inboxDirty, setInboxDirty] = useState(false), [settingsDirty, setSettingsDirty] = useState(false)
  const markReview = useCallback((v: boolean) => setReviewDirty(v), []), markInbox = useCallback((v: boolean) => setInboxDirty(v), []), markSettings = useCallback((v: boolean) => setSettingsDirty(v), [])
  const dirty = reviewDirty || inboxDirty || settingsDirty
  const refreshReview = async () => { const [events, signals, graph] = await Promise.all([call<Event[]>('/events'),call<Signal[]>('/signals'),network()]); setData({ events, signals, network: graph }) }
  const loadOverview = () => call<Overview>('/overview').then(setOverview)
  useEffect(() => {
    let active = true
    void (async () => { try { const status = await call<{configured: boolean}>('/status'); if (!active) return; setConfigured(status.configured); if (status.configured) { try { const s = await call<Session>('/session'); if (active) { setSession(s);setUser(s) } } catch { /* Show login. */ } } } catch (e) { if (active) setError(errorText(e)) } finally { if (active) setLoading(false) } })()
    return () => { active=false }
  }, [])
  useEffect(() => { const listener = () => setExpired(true); window.addEventListener('admin-session-expired',listener); return () => window.removeEventListener('admin-session-expired',listener) }, [])
  useEffect(() => { if (!dirty) return; const listener = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue='' }; window.addEventListener('beforeunload',listener); return () => window.removeEventListener('beforeunload',listener) }, [dirty])
  useEffect(() => { if (!session || expired) return; setError(''); const promise=page==='overview' ? loadOverview() : page==='review' ? refreshReview() : Promise.resolve(); promise.catch(e => setError(errorText(e))) }, [session, page, expired])
  const loggedIn = (s: Session) => { setSession(s); setUser(s); setExpired(false); setError('') }
  if (loading) return <div className="login-screen"><p role="status">Loading administrator access…</p></div>
  if (!session) return <>{error && <p className="alert error" role="alert">{error}</p>}<Login configured={configured} expired={false} onLogin={loggedIn} /></>
  const changePage = (next: Page) => { if (next === page) return; if (dirty && !window.confirm('Discard unsaved changes and leave this page?')) return; setPage(next); setError(''); setNotice('') }
  return <><div className="admin-shell" inert={expired}><aside className="sidebar"><a className="brand" href="/admin/">Resilient<span>Route</span><small>OPERATIONS CONSOLE</small></a><nav aria-label="Administration">{(Object.keys(titles) as Page[]).map((id,index) => <button key={id} aria-current={page===id ? 'page' : undefined} onClick={() => changePage(id)}><span className="nav-number">0{index+1}</span>{titles[id]}</button>)}</nav><div className="sidebar-footer"><span className="pill">{session.username}</span><p>One network.<br/>Human decisions.</p><a href="https://resilient-public-travel.pages.dev" target="_blank" rel="noreferrer">Public website ↗</a><button className="text-button" onClick={async () => { if (dirty && !window.confirm('Discard unsaved changes and sign out?')) return; try { await call('/logout',{});setSession(null);setUser(null);setData(null) } catch (e) { setError(errorText(e)) } }}>Sign out</button></div></aside>
    <main className="admin-main"><header className="page-header"><div><span className="eyebrow">RESILIENTROUTE / ADMINISTRATION</span><h1>{titles[page]}</h1></div><a className="docs-link" href="/docs" target="_blank" rel="noreferrer">API docs ↗</a></header>{error && <p className="alert error" role="alert">{error}</p>}{notice && <p className="alert" role="status">{notice}</p>}
      {page==='overview' && <>{!overview ? <section className="card"><p>{error ? 'Overview unavailable.' : 'Loading service overview…'}</p><button className="secondary" onClick={() => loadOverview().catch(e=>setError(errorText(e)))}>Retry</button></section> : <><section className="overview-intro card"><div><span className="eyebrow">NETWORK OPERATIONS</span><h2>Every report deserves<br/>a considered decision.</h2><p className="muted">Your workspace for evidence, review and service connections.</p></div><div className="health-status"><span className="status-dot"/><strong>{overview.health.ok ? 'Service healthy' : 'Service degraded'}</strong><small>Route engine · seed data · {overview.health.mode}</small><a href="/api/health/deep" target="_blank" rel="noreferrer">Deep health ↗</a></div></section><div className="metrics">{[{label:'Unlinked reports',value:overview.unlinked_reports},{label:'Awaiting review',value:overview.pending_review},{label:'Published events',value:overview.published},{label:'Reports received',value:overview.reports}].map(item=><section className="card metric" key={item.label}><span className="eyebrow">{item.label}</span><strong>{String(item.value).padStart(2,'0')}</strong></section>)}</div><div className="overview-grid"><section className="card"><span className="eyebrow">HUMAN REVIEW</span><h2>Clear the queue.</h2><p className="muted">Original reports remain unverified until corroborated and reviewed. Only approved events affect routes.</p><button className="primary" onClick={()=>changePage('review')}>Open reports & review →</button></section><section className="card"><span className="eyebrow">AI STRUCTURING</span><h2>{overview.ai.enabled ? 'Enabled' : 'Rules first.'}</h2><p className="muted">{overview.ai.enabled ? `${overview.ai.provider} assists draft extraction.` : 'AI is off. Deterministic extraction remains available.'} Route chat uses deterministic tools.</p><button className="secondary" onClick={()=>changePage('settings')}>Manage connections →</button></section></div><div className="source-grid">{(['mtr','hko'] as const).map(name=><section className="card" key={name}><span className="eyebrow">LATEST COLLECTION</span><h3>{name==='mtr' ? 'MTR · East Rail' : 'Hong Kong Observatory'}</h3><Result value={overview.sources[name]} /></section>)}</div></>}</>}
      {page==='review' && <>{!data ? <section className="card"><p>Loading reports and network…</p><button className="secondary" onClick={()=>refreshReview().catch(e=>setError(errorText(e)))}>Retry</button></section> : <><SignalInbox network={data.network} api={reviewApi} onDirty={markInbox} onChanged={refreshReview}/><ReviewConsole live compact reasonSaved events={data.events} signals={data.signals} network={data.network} logs={[]} onDirty={markReview} onReplay={()=>void refreshReview().catch(e=>setError(errorText(e)))} onSave={async (event,action,reason) => {
        const saved=await saveReview(event,action,reason);setData(previous=>previous ? {...previous,events:previous.events.map(e=>e.event_id===saved.event_id ? saved : e)} : previous)
        setNotice('Review saved on the server.');try { await refreshReview() } catch { setNotice('Review saved. The queue could not refresh; refresh it manually.') }
      }}/></>}</>}
      {page==='settings' && <SettingsPanel onDirty={markSettings}/>}{page==='activity' && <ActivityPanel/>}<footer className="main-footer">ResilientRoute · Evidence before action · All times shown in HKT</footer>
    </main></div>{expired && <Login configured={configured} expired onLogin={loggedIn}/>}</>
}
