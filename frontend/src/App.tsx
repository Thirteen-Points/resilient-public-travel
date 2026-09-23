import { useEffect, useMemo, useRef, useState } from 'react'
import { MapView } from './MapView'
import { activePublishedEvents, seedDataSource } from './api/seedDataSource'
import { DeparturePicker, hktDeparture } from './components/DeparturePicker'
import { AgentAvatar } from './components/AgentAvatar'
import { AgentPanel } from './components/AgentPanel'
import { ReviewConsole, type ReviewLog } from './components/ReviewConsole'
import { gsap, useGSAP, usePageMotion, useSuccessMotion } from './lib/motion'
import { lineGradient, lineStyle, resolveLine } from './lib/lineColors'
import type { DemoMeta, Event, Network, Preset, RouteCandidate, Signal } from './api/types'
import { CORRIDOR_IDS, formatHkt, formatRange, modeSummary, nearestAccessPoint, nodeIndex } from './data'
import css from './App.module.css'

type Screen = 'journey' | 'results' | 'updates' | 'detail' | 'sources' | 'agent' | 'review'
type Field = 'origin' | 'destination'
type Bundle = { network: Network; events: Event[]; signals: Signal[]; published: Event[]; meta: DemoMeta }
const PRESETS: { id: Preset; label: string }[] = [
  { id: 'fastest', label: 'Fastest' },
  { id: 'most_stable', label: 'Most stable' },
  { id: 'fewest_transfers', label: 'Fewer transfers' },
  { id: 'least_walking', label: 'Less walking' },
]

function ProvenanceBadge({ value }: { value: string }) {
  return <span className={css.provenance}>{value === 'real' ? 'Real station record' : value === 'real-derived' ? 'Derived estimate' : 'Simulated seed'}</span>
}

function StationField({ id, label, value, network, active, onFocus, onSelect, onPickMap, invalid }: {
  id: string; label: string; value: string; network: Network; active: boolean
  onFocus: () => void; onSelect: (id: string) => void; onPickMap: () => void; invalid?: boolean
}) {
  const nodes = nodeIndex(network)
  const [query, setQuery] = useState('')
  const [index, setIndex] = useState(0)
  const choices = CORRIDOR_IDS.map(id => nodes.get(id)!).filter(node =>
    node.name_en.toLowerCase().includes(query.toLowerCase()) || node.name_zh.includes(query) || node.id.toLowerCase().includes(query.toLowerCase()),
  )
  return <div className={css.fieldWrap}>
    <label htmlFor={id} className={css.fieldLabel}>{label}</label>
    <input id={id} className={`${css.input} ${invalid ? css.invalid : ''}`} role="combobox"
      aria-expanded={active} aria-controls={`${id}-options`} aria-autocomplete="list" aria-invalid={Boolean(invalid)}
      placeholder={label === 'TO' ? 'Choose a destination' : 'Search a station'}
      value={active ? query : nodes.get(value)?.name_en ?? ''}
      onFocus={() => { setQuery(''); setIndex(0); onFocus() }}
      onChange={event => { setQuery(event.target.value); setIndex(0) }}
      onKeyDown={event => {
        if (event.key === 'ArrowDown') { event.preventDefault(); setIndex(i => Math.min(i + 1, choices.length - 1)) }
        if (event.key === 'ArrowUp') { event.preventDefault(); setIndex(i => Math.max(0, i - 1)) }
        if (event.key === 'Enter' && active && choices[index]) { event.preventDefault(); onSelect(choices[index].id); setQuery('') }
        if (event.key === 'Escape') { onSelect(value); setQuery('') }
      }} />
    {active && <div className={css.suggestions} id={`${id}-options`} role="listbox">
      <span className={css.suggestionLabel}>STATIONS · SEARCH OR SELECT</span>
      {choices.map((node, i) => <button key={node.id} type="button" role="option" aria-selected={index === i}
        className={`${css.suggestion} ${index === i ? css.highlighted : ''}`} onMouseDown={event => event.preventDefault()}
        onClick={() => { onSelect(node.id); setQuery('') }}>{node.name_en}<small>{node.name_zh}</small></button>)}
      {!choices.length && <p className={css.small}>No matching seed station. Map selection is available.</p>}
      <button type="button" className={css.mapChoice} onMouseDown={event => event.preventDefault()} onClick={onPickMap}>◎ Select a point on the map</button>
    </div>}
  </div>
}

function RouteCard({ route, letter, network, selected, onSelect, onDetail }: {
  route: RouteCandidate; letter: string; network: Network; selected: boolean
  onSelect: () => void; onDetail: () => void
}) {
  const card = useRef<HTMLElement>(null)
  useGSAP(() => {
    const media = gsap.matchMedia()
    media.add('(prefers-reduced-motion: no-preference)', () => {
      if (selected) gsap.fromTo(card.current, { scale: .985 }, { scale: 1, duration: .35, ease: 'back.out(2)', clearProps: 'transform' })
    })
    return () => media.revert()
  }, { dependencies: [selected], revertOnUpdate: true })
  return <article ref={card} data-enter className={`${css.routeCard} ${selected ? css.selectedRoute : ''}`}>
    <button type="button" className={css.routeSelect} onClick={onSelect} aria-pressed={selected}>
      <span className={css.routeTop}><span className={css.routeLetter}>{letter}</span><span className={css.routeName}>Option {letter}<small>{modeSummary(route, network)}</small></span><strong>{formatRange(route.total.time_range_s)}</strong></span>
      <span className={css.routeMetrics}><span>{route.total.transfers} transfer{route.total.transfers === 1 ? '' : 's'}</span><span>{route.total.walk_m} m walk</span><span>HK${route.total.fare_hkd.toFixed(2)}</span></span>
    </button>
    <div className={css.routeFooter}><span>Score {Math.round(route.score * 100)}/100 · Estimated</span><button type="button" onClick={onDetail}>View steps →</button></div>
    <div className={css.scoreTrack} aria-label={`Route score ${Math.round(route.score * 100)} out of 100`}><span style={{ width: `${route.score * 100}%` }} /></div>
    <div className={css.routeCaveat}><ProvenanceBadge value={route.provenance} /><span>{route.warnings[0] ?? 'No specific warning in fixture; verify service.'}</span></div>
    <p className={css.routeFreshness}>{route.notes[0] ?? 'Illustrative candidate'} · Seed age at snapshot {route.total.freshness_s}s</p>
    <div className={css.lineChips}>{Array.from(new Set(route.legs.filter(leg => leg.line).map(leg => leg.line!))).map(id => {
      const style = lineStyle(resolveLine(network, id), id)
      return <span key={id} title={style.label}><i style={{ background: lineGradient(style.colors) }} />{id.replace('BUS_', '')}{style.colors.length > 1 ? ' · joint' : ''}</span>
    })}</div>
    <details className={css.routeEvidence}><summary>Score, preferences & sources</summary>
      {route.score_breakdown?.length ? route.score_breakdown.map(factor => <div className={css.factor} key={factor.criterion}><span>{factor.criterion}</span><span>{Math.round(factor.weight * 100)}% weight · {factor.contribution.toFixed(3)}</span></div>) : <p>No factor breakdown supplied in this seed.</p>}
      <p>{route.explain}</p><strong>Risks</strong>{route.warnings.length ? route.warnings.map(note => <p key={note}>{note}</p>) : <p>No specific seed warning; verify current service.</p>}<strong>Preference notes</strong>{route.notes.map(note => <p key={note}>{note}</p>)}<p>Source: routes.seed.json · {route.provenance}. Freshness is measured at the seed snapshot, not now.</p>
    </details>
    <p className={css.routeDisclaimer}>Academic estimate · not official travel advice.</p>
  </article>
}

function EventCard({ event, signals, network }: { event: Event; signals: Signal[]; network: Network }) {
  const nodes = nodeIndex(network)
  const evidence = signals.filter(signal => event.signals.includes(signal.signal_id))
  return <article data-enter className={css.eventCard}>
    <div className={css.eventTop}><span className={event.status === 'published' ? css.published : css.pending}>{event.status === 'published' ? '● Published' : event.status.replaceAll('_', ' ')}</span><span>{Math.round(event.confidence * 100)}% confidence</span></div>
    <h3>{event.title}</h3><p>{event.summary}</p>
    <p className={css.segment}>{event.affected_segments.map(segment => `${nodes.get(segment.from_node)?.name_en ?? segment.from_node} → ${nodes.get(segment.to_node)?.name_en ?? segment.to_node}`).join(' · ')}</p>
    <div className={css.track}><span style={{ width: `${event.confidence * 100}%` }} /></div>
    <div className={css.eventMeta}><span>{event.signals.length} signals · Severity {event.severity}</span><span>{formatHkt(event.updated_at)}</span></div>
    <ProvenanceBadge value={event.provenance} />
    <details><summary>Evidence &amp; effect</summary><p>{event.status === 'published' ? 'This published state alone changes the map.' : 'Unreviewed; does not change the map or routing.'}</p><ul>{evidence.map(signal => <li key={signal.signal_id}>{signal.source_type}: {signal.source_name}</li>)}</ul>{evidence.length < event.signals.length && <p>Some referenced signals lack a separate record in this fixture.</p>}</details>
  </article>
}

export function App() {
  const [bundle, setBundle] = useState<Bundle | null>(null)
  const [loadError, setLoadError] = useState('')
  const [screen, setScreen] = useState<Screen>('journey')
  const [origin, setOrigin] = useState('TAW')
  const [destination, setDestination] = useState('')
  const [activeField, setActiveField] = useState<Field | null>(null)
  const [picking, setPicking] = useState<Field | null>(null)
  const [picked, setPicked] = useState('')
  const [error, setError] = useState('')
  const [preset, setPreset] = useState<Preset>('fastest')
  const [departure, setDeparture] = useState('08:20')
  const [departureDate, setDepartureDate] = useState('2026-09-22')
  const [searching, setSearching] = useState(false)
  const [queriedAt, setQueriedAt] = useState('')
  const [logs, setLogs] = useState<ReviewLog[]>([])
  const [success, setSuccess] = useState({ text: '', revision: 0 })
  const root = useRef<HTMLDivElement>(null)
  const toast = useRef<HTMLDivElement>(null)
  const originalEvents = useRef<Event[]>([])
  const searchingRef = useRef(false)
  const [routes, setRoutes] = useState<RouteCandidate[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected = useMemo(() => routes.find(route => route.route_id === selectedId), [routes, selectedId])
  usePageMotion(root, screen, Boolean(bundle))
  useSuccessMotion(toast, success.revision)
  useEffect(() => {
    if (!success.text) return
    const timer = setTimeout(() => setSuccess(value => ({ ...value, text: '' })), 4200)
    return () => clearTimeout(timer)
  }, [success.revision, success.text])

  useEffect(() => {
    let alive = true
    Promise.all([seedDataSource.getNetwork(), seedDataSource.getEvents(), seedDataSource.getMeta()])
      .then(async ([network, { events, signals }, meta]) => {
        const published = await seedDataSource.getPublishedEvents(meta.snapshotAt)
        if (alive) {
          originalEvents.current = structuredClone(events)
          setDepartureDate(meta.snapshotAt.slice(0, 10)); setDeparture(meta.snapshotAt.slice(11, 16))
          setBundle({ network, events, signals, published, meta })
        }
      }).catch(cause => { if (alive) setLoadError(String(cause)) })
    return () => { alive = false }
  }, [])

  if (loadError) return <div className={css.state}>Could not load seed data. {loadError}</div>
  if (!bundle) return <div className={css.state}>Loading the demo snapshot…</div>
  const { network, events, signals, published, meta } = bundle
  const nodes = nodeIndex(network)
  const celebrate = (text: string) => setSuccess(previous => ({ text, revision: previous.revision + 1 }))
  const review = (event: Event, action: 'edit' | 'publish' | 'reject', reason = '') => {
    const record = { ...event, updated_at: meta.snapshotAt, status: action === 'publish' ? 'published' as const : action === 'reject' ? 'rejected' as const : 'pending_review' as const, ...(action === 'publish' ? { published_at: meta.snapshotAt } : {}) }
    setBundle(previous => {
      if (!previous) return previous
      const next = previous.events.map(item => item.event_id === record.event_id ? record : action === 'publish' && item.status === 'published' ? { ...item, status: 'updated' as const } : item)
      return { ...previous, events: next, published: activePublishedEvents(next, previous.meta.snapshotAt) }
    })
    setLogs(previous => [...previous, { id: event.event_id, action, detail: `${new Date().toLocaleTimeString('en-HK', { timeZone: 'Asia/Hong_Kong' })} HKT local action. ${reason || (action === 'publish' ? 'Explicitly confirmed; evaluated at seed snapshot.' : 'Saved local structured fields.')}` }])
    celebrate(action === 'publish' ? 'Event published · demo map updated' : action === 'reject' ? 'Event rejected · reason recorded' : 'Draft saved')
  }
  const replay = () => {
    const next = structuredClone(originalEvents.current).map(event => ({ ...event, status: 'pending_review' as const, published_at: null }))
    setBundle(previous => previous ? { ...previous, events: next, published: [] } : previous)
    setLogs([{ id: 'scenario', action: 'replay', detail: 'Restored seed fields and confidence values; all stages now await review. Fixed route candidates are unchanged.' }])
    celebrate('Review replay ready · no published disruption')
  }
  const setField = (field: Field, value: string) => {
    if (field === 'origin') setOrigin(value)
    else setDestination(value)
    setActiveField(null); setPicking(null); setError(''); setPicked('')
  }
  const showRoutes = async (from = origin, to = destination, preference = preset) => {
    if (searchingRef.current) return
    setActiveField(null)
    if (!to || !from) { setError('Choose a destination and starting point before continuing.'); return }
    if (from === to) { setError('Choose two different stations.'); return }
    const departAt = hktDeparture(departureDate, departure)
    if (!Number.isFinite(Date.parse(departAt))) { setError('Choose a valid Hong Kong departure date and time.'); return }
    searchingRef.current = true; setSearching(true)
    try {
      const next = await seedDataSource.getRoutes({ origin: from, destination: to, departAt, preset: preference })
      setRoutes(next.slice(0, 3)); setOrigin(from); setDestination(to); setPreset(preference); setQueriedAt(departAt)
      setSelectedId(next[0]?.route_id ?? null)
      setScreen('results'); setError(''); setPicking(null)
      if (next.length) celebrate(`${Math.min(next.length, 3)} seed alternatives ready`)
    } catch { setError('Route data could not be loaded. Please try again.') }
    finally { setSearching(false); searchingRef.current = false }
  }
  const mapPick = (point: { lat: number; lng: number }) => {
    if (!picking) return
    const nearest = nearestAccessPoint(network, point)
    if (!nearest) { setError(`No modelled access point within ${network.meta.catchment_m} m. Search by station instead.`); return }
    setField(picking, nearest.node.id)
    setPicked(`Closest accessible seed point: ${nearest.node.name_en} · about ${Math.round(nearest.metres)} m straight-line. Confirm access on site.`)
  }
  const activeRoutes = screen === 'results' || screen === 'detail' ? routes : []
  return <div ref={root} className={css.shell}>
    <header className={css.header}>
      <button type="button" className={css.brand} onClick={() => setScreen('journey')} aria-label="ResilientRoute home">rr<span>.</span></button>
      <nav aria-label="Main navigation">
        <button type="button" aria-current={screen === 'journey' || screen === 'results' || screen === 'detail' ? 'page' : undefined} onClick={() => { setScreen('journey'); setPicking(null) }}>Plan journey</button>
        <button type="button" aria-current={screen === 'updates' ? 'page' : undefined} onClick={() => setScreen('updates')}>Updates</button>
        <button type="button" aria-current={screen === 'review' ? 'page' : undefined} onClick={() => { setScreen('review'); setPicking(null) }}>Review</button>
        <button type="button" aria-current={screen === 'agent' ? 'page' : undefined} onClick={() => { setScreen('agent'); setPicking(null) }}>Agent</button>
        <button type="button" aria-current={screen === 'sources' ? 'page' : undefined} onClick={() => setScreen('sources')}>How it works</button>
      </nav>
      <span className={css.demo}>ACADEMIC DEMO</span>
    </header>
    <main className={css.stage}>
      <MapView network={network} published={published} routes={activeRoutes} selectedRouteId={selectedId} picking={Boolean(picking) && screen === 'journey'} onMapPick={point => { if (screen === 'journey') mapPick(point) }} />
      {screen === 'agent' && <AgentPanel published={published} departAt={hktDeparture(departureDate, departure)} onRoutes={preference => void showRoutes('TAW', 'ADM', preference)} onBack={() => setScreen('journey')} />}
      {screen === 'review' && <ReviewConsole events={events} signals={signals} network={network} logs={logs} onSave={review} onReplay={replay} />}
      {screen === 'journey' && <div data-panel className={css.panel}>
          <h1>Where are you<br />heading?</h1>
          <p className={css.subhead}>Search a modelled station or select it on the map.</p>
          <button type="button" className={css.agentEntry} onClick={() => { setScreen('agent'); setActiveField(null); setPicking(null); setError('') }}><AgentAvatar issue={published.length > 0} small /><span><strong>Meet your route companion</strong><small>Ask the Agent · explore this scenario</small></span><b>↗</b></button>
          <form onSubmit={event => { event.preventDefault(); void showRoutes() }}>
            <StationField id="origin" label="FROM" value={origin} network={network} active={activeField === 'origin'} onFocus={() => { setActiveField('origin'); setPicking(null) }} onSelect={value => setField('origin', value)} onPickMap={() => { setActiveField(null); setPicking('origin') }} />
            <button className={css.swap} type="button" onClick={() => { setOrigin(destination); setDestination(origin); setActiveField(null) }} aria-label="Swap stations">⇅</button>
            <StationField id="destination" label="TO" value={destination} network={network} active={activeField === 'destination'} invalid={Boolean(error && !destination)} onFocus={() => { setActiveField('destination'); setPicking(null) }} onSelect={value => setField('destination', value)} onPickMap={() => { setActiveField(null); setPicking('destination') }} />
            <div className={css.fieldAssist}><button type="button" onClick={() => { setActiveField(null); setPicking('destination') }}>◎ Tap the map</button><span>Within {network.meta.catchment_m} m of a station</span></div>
            {picked && <p className={css.confirm}>{picked}</p>}
            {error && <p role="alert" className={css.error}>{error}</p>}
            <DeparturePicker date={departureDate} time={departure} onDate={setDepartureDate} onTime={setDeparture} />
            <fieldset className={css.presets}><legend>WHAT MATTERS MOST?</legend>{PRESETS.map(option => <button key={option.id} type="button" aria-pressed={preset === option.id} className={preset === option.id ? css.activePreset : ''} onClick={() => setPreset(option.id)}>{option.label}</button>)}</fieldset>
            <button type="submit" disabled={searching} className={css.primary}>{searching ? 'Finding seed routes…' : 'Find resilient routes'} <span>↗</span></button>
          </form>

          <p className={css.tiny}>Only Tai Wai → Admiralty has route candidates in this fixture.</p>
      </div>}
      {screen === 'results' && <>
        {published[0] && <div className={css.alert}><span>!</span><strong>{published[0].title}</strong><span className={css.alertDetail}>Published simulated scenario · {formatHkt(published[0].updated_at)}</span><button type="button" onClick={() => setScreen('updates')}>View update →</button></div>}
        <section data-panel className={`${css.panel} ${css.results}`} aria-labelledby="routes-heading">
          <button type="button" className={css.back} onClick={() => setScreen('journey')}>← Edit journey</button>
          <span className={css.kicker}>ROUTES FOR YOUR JOURNEY</span>
          <h1 id="routes-heading">{nodes.get(origin)?.name_en ?? origin} <span>→</span><br />{nodes.get(destination)?.name_en ?? destination}</h1>
          <p className={css.subhead}>{routes.length} alternatives · {PRESETS.find(option => option.id === preset)?.label} · fixed seed snapshot</p>
          <p className={css.queryStamp}>Requested departure: {formatHkt(queriedAt)}<br /><small>Query value: {queriedAt} · seed estimates are not recalculated.</small></p>
          {routes.length ? <div className={css.routeList}>{routes.map((route, index) => <RouteCard key={route.route_id} route={route} letter={'ABC'[index]} network={network} selected={route.route_id === selectedId} onSelect={() => setSelectedId(route.route_id)} onDetail={() => { setSelectedId(route.route_id); setScreen('detail') }} />)}</div> : <div className={css.empty}><strong>No seed route for this pair.</strong><p>Only Tai Wai → Admiralty is modelled. Edit the journey to inspect the demonstration.</p></div>}
          <p className={css.tiny}>Illustrative, not a live journey query. Published events alone affect the network overlay. Times, fares and scores are derived estimates.</p>
        </section>
      </>}
      {screen === 'updates' && <section data-panel className={`${css.panel} ${css.widePanel}`}>
        <button type="button" className={css.back} onClick={() => setScreen('journey')}>← Back to journey</button>
        <span className={css.kicker}>SCENARIO SNAPSHOT · {formatHkt(meta.snapshotAt)}</span><h1>What we know.</h1>
        <p className={css.subhead}>Three stages of one simulated incident. Pending reports do not change routes or the map.</p>
        <ol className={css.timeline} aria-label="Seed confidence timeline">{events.map((event, index) => <li data-enter key={event.event_id}><span>0{index + 1} · {formatHkt(event.updated_at)}</span><strong>{Math.round(event.confidence * 100)}<small>%</small></strong><p>{index === 0 ? 'First report' : index === 1 ? 'Corroborating signals' : 'Official demo evidence'} · {event.status.replaceAll('_', ' ')}</p><div><i data-confidence style={{ width: `${event.confidence * 100}%` }} /></div></li>)}</ol>
        <button type="button" className={css.reviewLink} onClick={() => setScreen('review')}>Open the review desk →</button>
        <div className={css.eventGrid}>{events.map(event => <EventCard key={event.event_id} event={event} signals={signals} network={network} />)}</div>
      </section>}
      {screen === 'detail' && selected && <section data-panel className={`${css.panel} ${css.detailPanel}`}>
        <button type="button" className={css.back} onClick={() => setScreen('results')}>← All routes</button><span className={css.kicker}>ROUTE DETAILS · DERIVED ESTIMATE</span>
        <h1>{nodes.get(origin)?.name_en} <span>→</span><br />{nodes.get(destination)?.name_en}</h1>
        <div className={css.detailStats}><strong>{formatRange(selected.total.time_range_s)}</strong><span>{selected.total.transfers} transfer{selected.total.transfers === 1 ? '' : 's'}</span><span>{selected.total.walk_m} m walk</span><span>HK${selected.total.fare_hkd.toFixed(2)}</span></div>
        <h2>Step by step</h2><ol className={css.steps}>{selected.legs.map((leg, i) => <li data-enter key={i}><strong><i className={css.lineDot} style={{ background: leg.mode === 'WALK' ? '#6d7e70' : lineGradient(lineStyle(resolveLine(network, leg.line), leg.line).colors) }} />{leg.mode === 'WALK' ? 'Walk' : resolveLine(network, leg.line)?.name_en ?? leg.line ?? leg.mode}</strong><span>{nodes.get(leg.from)?.name_en ?? leg.from} → {nodes.get(leg.to)?.name_en ?? leg.to}</span><small>About {Math.round(leg.travel_s / 60)} min{leg.walk_m ? ` · ${leg.walk_m} m walking` : ''}</small></li>)}</ol>
        <h2>Why this route?</h2><p>{selected.explain}</p>
        {selected.warnings.length > 0 && <div className={css.warning}><strong>Check before travel</strong>{selected.warnings.map(warning => <p key={warning}>{warning}</p>)}</div>}
        {selected.score_breakdown && <div className={css.breakdown}><h2>Seed score factors</h2>{selected.score_breakdown.map(factor => <div key={factor.criterion}><span>{factor.criterion}</span><span>weight {Math.round(factor.weight * 100)}% · contribution {factor.contribution.toFixed(3)}</span></div>)}</div>}
        <ProvenanceBadge value={selected.provenance} /><p className={css.tiny}>Source: routes.seed.json · {formatHkt(meta.snapshotAt)} · {meta.disclaimer}</p>
      </section>}
      {screen === 'sources' && <section data-panel className={`${css.panel} ${css.sourcesPanel}`}>
        <button type="button" className={css.back} onClick={() => setScreen('journey')}>← Back to journey</button><span className={css.kicker}>HOW THIS DEMO WORKS</span><h1>Clarity before certainty.</h1>
        <p>Network, event, route and simulation seeds load through a shared data-source boundary. The map displays modelled nodes, schematic links, and only effective published events. Unreviewed reports remain visible on the Updates screen but do not modify routing.</p>
        <p>Route choices are fixed Tai Wai → Admiralty seed candidates. Station-search, map selection and departure input are interface demonstrations, not live timetable, geocoding or accessibility verification.</p>
        <p><strong>Snapshot:</strong> {formatHkt(meta.snapshotAt)} · <strong>Network:</strong> {network.meta.version} · <strong>Access radius:</strong> {network.meta.catchment_m} m straight-line.</p>
        <p>{meta.disclaimer}</p>
        <h2>What changes in this demo?</h2><p>Review decisions live only in this browser session. Publishing replaces the previous incident stage and updates the map overlay and Agent alert. Routes remain fixed seed estimates. The selected departure is sent as an HKT query value; there is no timetable recalculation or live Agent API.</p>
        <h2>Colour & motion credits</h2><p>Lines follow <a href="https://www.mtr.com.hk/ch/customer/services/system_map.html" target="_blank" rel="noreferrer">MTR colours</a> and local operator branding. Joint bus services show both colours; unknown services receive a stable assigned colour. Geometry remains schematic.</p><p>Our route companion is an adaptation of <a href="https://github.com/jeremy-prt/bloub" target="_blank" rel="noreferrer">Bloub</a>'s clock-free bot engine (MIT): resting ball, sphere-projected eyes, deterministic blink calendar, and the measured triangle silhouette, coloured with its own palette. <a href="https://github.com/Jakubantalik/Libraries.dev/tree/main/packages/border-beam" target="_blank" rel="noreferrer">BorderBeam</a> handles the focused composer. Reduced-motion preferences are respected.</p>
      </section>}
    </main>
    <div ref={toast} role="status" aria-live="polite" className={success.text ? css.successToast : css.hiddenToast}>{success.text && <><span>✓</span><strong>{success.text}</strong></>}</div>
  </div>
}
