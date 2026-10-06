import { useEffect, useMemo, useRef, useState } from 'react'
import { MapView } from './MapView'
import { activePublishedEvents, seedDataSource } from './api/seedDataSource'
import { useLiveSession } from './api/useLiveSession'
import { SignalReportForm } from './components/SignalReportForm'
import { DeparturePicker, hktDeparture } from './components/DeparturePicker'
import { AgentAvatar } from './components/AgentAvatar'
import { AgentPanel } from './components/AgentPanel'
import { ComparePage } from './components/ComparePage'
import { SimulationPage } from './components/SimulationPage'
import { PreferenceEditor } from './components/PreferenceEditor'
import { LatestRequest, resolveProfile, profileLabel } from './api/p3Context'
import { ReviewConsole, type ReviewLog } from './components/ReviewConsole'
import { ReviewAccess } from './components/ReviewAccess'
import { SignalInbox } from './components/SignalInbox'
import { HowItWorksPage } from './components/HowItWorksPage'
import { UpdatesPage } from './components/UpdatesPage'
import { ProvenanceBadge } from './components/ProvenanceBadge'
import { gsap, useGSAP, usePageMotion, useSuccessMotion } from './lib/motion'
import { lineGradient, lineStyle, resolveLine } from './lib/lineColors'
import type { DemoMeta, Event, JourneyContext, Network, Persona, Preset, RouteCandidate, Signal, TravelProfile } from './api/types'
import { CORRIDOR_IDS, formatHkt, formatRange, legDuration, modeSummary, nearestAccessPoint, nodeIndex } from './data'
import css from './App.module.css'

type Screen = 'journey' | 'results' | 'updates' | 'detail' | 'sources' | 'agent' | 'review' | 'report' | 'compare' | 'simulation'
const SEED_MODE = new URLSearchParams(window.location.search).get('data') === 'seed'
function switchDataMode() {
  const url = new URL(window.location.href)
  if (SEED_MODE) url.searchParams.delete('data')
  else url.searchParams.set('data', 'seed')
  window.location.assign(url)
}
type Field = 'origin' | 'destination'
type Bundle = { network: Network; events: Event[]; signals: Signal[]; published: Event[]; meta: DemoMeta }
const PRESETS: { id: Preset; label: string }[] = [
  { id: 'fastest', label: 'Fastest' },
  { id: 'most_stable', label: 'Most stable' },
  { id: 'fewest_transfers', label: 'Fewer transfers' },
  { id: 'least_walking', label: 'Less walking' },
]

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
  return <article ref={card} data-enter data-route-id={route.route_id} className={`${css.routeCard} ${selected ? css.selectedRoute : ''}`}>
    <button type="button" className={css.routeSelect} onClick={onSelect} aria-pressed={selected}>
      <span className={css.routeTop}><span className={css.routeLetter}>{letter}</span><span className={css.routeName}>Option {letter}<small>{modeSummary(route, network)}</small></span><strong>{formatRange(route.total.time_range_s)}</strong></span>
      <span className={css.routeMetrics}><span>{route.total.transfers} transfer{route.total.transfers === 1 ? '' : 's'}</span><span>{route.total.walk_m} m walk</span><span>HK${route.total.fare_hkd.toFixed(2)}</span></span>
    </button>
    <div className={css.routeFooter}><span>Score {Math.round(route.score * 100)}/100 · Estimated</span><button type="button" onClick={onDetail}>View steps →</button></div>
    <div className={css.scoreTrack} aria-label={`Route score ${Math.round(route.score * 100)} out of 100`}><span style={{ width: `${route.score * 100}%` }} /></div>
    <div className={css.routeCaveat}><ProvenanceBadge value={route.provenance} compact /><span>{route.warnings[0] ?? 'No specific warning in fixture; verify service.'}</span></div>
    <p className={css.routeFreshness}>{route.notes[0] ?? 'Illustrative candidate'} · {SEED_MODE ? 'Seed age at snapshot' : 'Source age at query'} {route.total.freshness_s}s</p>
    <div className={css.lineChips}>{Array.from(new Set(route.legs.filter(leg => leg.line).map(leg => leg.line!))).map(id => {
      const style = lineStyle(resolveLine(network, id), id)
      return <span key={id} title={style.label}><i style={{ background: lineGradient(style.colors) }} />{id.replace('BUS_', '')}{style.colors.length > 1 ? ' · joint' : ''}</span>
    })}</div>
    <details className={css.routeEvidence}><summary>Score, preferences & sources</summary>
      {route.score_breakdown?.length ? route.score_breakdown.map(factor => <div className={css.factor} key={factor.criterion}><span>{factor.criterion}</span><span>{Math.round(factor.weight * 100)}% weight · {factor.contribution.toFixed(3)}</span></div>) : <p>No factor breakdown supplied in this seed.</p>}
      <p>{route.explain}</p><strong>Risks</strong>{route.warnings.length ? route.warnings.map(note => <p key={note}>{note}</p>) : <p>No specific seed warning; verify current service.</p>}<strong>Preference notes</strong>{route.notes.map(note => <p key={note}>{note}</p>)}<p>Source: {SEED_MODE ? 'routes.seed.json' : 'route engine API'} · {route.provenance}. Freshness is measured at query time.</p>
    </details>
    <p className={css.routeDisclaimer}>Academic estimate · not official travel advice.</p>
  </article>
}

export function App() {
  const [seedBundle, setBundle] = useState<Bundle | null>(null)
  const live = useLiveSession(!SEED_MODE)
  const bundle: Bundle | null = SEED_MODE ? seedBundle : live.bundle ? {
    ...live.bundle,
    meta: { snapshotAt: live.bundle.meta?.generated_at ?? '', od: { origin: '', destination: '' }, provenance: 'simulated', disclaimer: live.bundle.meta?.disclaimer ?? 'Modelled estimates; source metadata unavailable. Follow official travel advice.', simulationSeedAvailable: false },
  } : null
  const [loadError, setLoadError] = useState('')
  const [screen, setScreen] = useState<Screen>('journey')
  const [origin, setOrigin] = useState('TAW')
  const [destination, setDestination] = useState('')
  const [activeField, setActiveField] = useState<Field | null>(null)
  const [picking, setPicking] = useState<Field | null>(null)
  const [picked, setPicked] = useState('')
  const [error, setError] = useState('')
  const [preset, setPreset] = useState<Preset>('fastest')
  const [persona, setPersona] = useState<Persona>('commuter')
  const [customProfile, setCustomProfile] = useState<TravelProfile | undefined>()
  const effectiveProfile = useMemo(() => resolveProfile({ persona, preset, profile: customProfile }), [persona, preset, customProfile])
  const [largeText, setLargeText] = useState(false), [highContrast, setHighContrast] = useState(false)
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
  const routeRequests = useRef(new LatestRequest()), requestedJourney = useRef('')
  const requestedScreen = useRef<Screen>('journey')
  const [seedRoutes, setRoutes] = useState<RouteCandidate[]>([])
  const routes = SEED_MODE ? seedRoutes : live.routes
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected = useMemo(() => routes.find(route => route.route_id === selectedId), [routes, selectedId])
  const eventRevisions = (SEED_MODE ? seedBundle?.published : live.bundle?.published)?.map(event => `${event.event_id}@${event.version}`).sort().join(',') ?? ''
  const context = useMemo<JourneyContext>(() => ({ origin, destination, departAt: hktDeparture(departureDate, departure), preset, persona, profile: effectiveProfile, eventRevisions, eventIds: eventRevisions ? eventRevisions.split(',').map(value => value.slice(0, value.lastIndexOf('@'))) : [] }), [origin, destination, departureDate, departure, preset, persona, effectiveProfile, eventRevisions])
  const plannerKey = JSON.stringify([origin, destination, context.departAt, effectiveProfile])
  useEffect(() => {
    if (searchingRef.current && (requestedJourney.current !== plannerKey || requestedScreen.current !== screen)) { routeRequests.current.cancel(); searchingRef.current = false; setSearching(false) }
  }, [plannerKey, screen])
  useEffect(() => () => routeRequests.current.cancel(), [])
  usePageMotion(root, screen, Boolean(bundle))
  useSuccessMotion(toast, success.revision)
  useEffect(() => {
    if (!success.text) return
    const timer = setTimeout(() => setSuccess(value => ({ ...value, text: '' })), 4200)
    return () => clearTimeout(timer)
  }, [success.revision, success.text])

  useEffect(() => {
    if (!SEED_MODE) {
      const now = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date())
      setDepartureDate(now.slice(0, 10)); setDeparture(now.slice(11, 16))
      return
    }
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

  useEffect(() => {
    if (!SEED_MODE) setSelectedId(previous => routes.some(route => route.route_id === previous) ? previous : routes[0]?.route_id ?? null)
  }, [routes])

  if (loadError || (!bundle && live.error)) return <div className={css.state}><p role="alert">Could not load {SEED_MODE ? 'seed' : 'API'} data. {loadError || live.error}</p><button className={css.quietAction} onClick={() => void live.refresh()}>Retry API</button> <button className={css.quietAction} onClick={switchDataMode}>{SEED_MODE ? 'Use API' : 'Open fixed seed demo'}</button></div>
  if (!bundle) return <div className={css.state}>Loading {SEED_MODE ? 'the demo snapshot' : 'API data'}… <button className={css.quietAction} onClick={switchDataMode}>{SEED_MODE ? 'Use API' : 'Open fixed seed demo'}</button></div>
  const { network, events, signals, published, meta } = bundle
  const nodes = nodeIndex(network)
  const celebrate = (text: string) => setSuccess(previous => ({ text, revision: previous.revision + 1 }))
  const review = async (event: Event, action: 'edit' | 'publish' | 'reject' | 'expire', reason = '') => {
    if (!SEED_MODE) {
      await live.review(event, action, reason)
      setLogs(previous => [...previous, { id: event.event_id, action, detail: `API accepted the review. Server audit history is authoritative.${reason ? ' Session-only note: ' + reason : ''}` }])
      celebrate('Review saved by API · refreshing events and routes')
      return
    }
    const record = { ...event, updated_at: meta.snapshotAt, status: action === 'publish' ? 'published' as const : action === 'reject' ? 'rejected' as const : action === 'expire' ? 'expired' as const : 'pending_review' as const, ...(action === 'publish' ? { published_at: meta.snapshotAt } : {}) }
    setBundle(previous => {
      if (!previous) return previous
      const next = previous.events.map(item => item.event_id === record.event_id ? record : action === 'publish' && item.status === 'published' ? { ...item, status: 'updated' as const } : item)
      return { ...previous, events: next, published: activePublishedEvents(next, previous.meta.snapshotAt) }
    })
    setLogs(previous => [...previous, { id: event.event_id, action, detail: `${new Date().toLocaleTimeString('en-HK', { timeZone: 'Asia/Hong_Kong' })} HKT local action. ${reason || (action === 'publish' ? 'Explicitly confirmed; evaluated at seed snapshot.' : 'Saved local structured fields.')}` }])
    celebrate(action === 'publish' ? 'Event published · demo map updated' : action === 'reject' ? 'Event rejected · reason recorded' : 'Draft saved')
  }
  const replay = () => {
    if (!SEED_MODE) { void live.refresh(); return }
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
  const showRoutes = async (from = origin, to = destination, preference = preset, profile = effectiveProfile) => {
    setActiveField(null)
    if (!to || !from) { setError('Choose a destination and starting point before continuing.'); return }
    if (from === to) { setError('Choose two different stations.'); return }
    const departAt = hktDeparture(departureDate, departure)
    if (!Number.isFinite(Date.parse(departAt))) { setError('Choose a valid Hong Kong departure date and time.'); return }
    searchingRef.current = true; setSearching(true)
    const request = routeRequests.current.begin()
    const requestedProfile = resolveProfile({ persona, preset: preference, profile })
    requestedJourney.current = JSON.stringify([from, to, departAt, requestedProfile])
    requestedScreen.current = screen
    try {
      const value = { origin: from, destination: to, departAt, preset: preference, persona, ...(!SEED_MODE ? { profile: requestedProfile } : {}) }
      const next = SEED_MODE ? await seedDataSource.getRoutes(value) : await live.query(value, request.signal)
      if (!request.current()) return
      setRoutes(next.slice(0, 3)); setOrigin(from); setDestination(to); setPreset(preference); setQueriedAt(departAt)
      setSelectedId(next[0]?.route_id ?? null)
      setScreen('results'); setError(''); setPicking(null)
      if (next.length) celebrate(`${Math.min(next.length, 3)} ${SEED_MODE ? 'seed' : 'API'} alternatives ready`)
    } catch (cause) { if (request.current()) setError(`Route data could not be loaded. ${cause instanceof Error ? cause.message : String(cause)}`) }
    finally { if (request.current()) { setSearching(false); searchingRef.current = false } }
  }
  const mapPick = (point: { lat: number; lng: number }) => {
    if (!picking) return
    const nearest = nearestAccessPoint(network, point)
    if (!nearest) { setError(`No modelled access point within ${network.meta.catchment_m} m. Search by station instead.`); return }
    setField(picking, nearest.node.id)
    setPicked(`Closest modelled station: ${nearest.node.name_en} · about ${Math.round(nearest.metres)} m straight-line. ${nearest.node.accessible === true ? 'Accessibility uses modelled assumptions; verify on site.' : 'Accessibility is unknown or incomplete; verify on site.'}`)
  }
  const activeRoutes = screen === 'results' || screen === 'detail' ? routes : []
  // Map footprint: full behind the floating panels, a right-hand card beside
  // page content, faded out on the plain How-it-works page.
  const mapMode: 'full' | 'docked' | 'hidden' =
    screen === 'updates' || screen === 'review' ? 'docked' : ['sources', 'compare', 'simulation'].includes(screen) ? 'hidden' : 'full'
  return <div ref={root} className={`${css.shell} ${largeText ? css.largeText : ''} ${highContrast ? css.highContrast : ''}`}>
    <header className={css.header}>
      <button type="button" className={css.brand} onClick={() => setScreen('journey')} aria-label="ResilientRoute home">rr<span>.</span></button>
      <nav aria-label="Main navigation">
        <button type="button" aria-current={screen === 'report' ? 'page' : undefined} onClick={() => { setScreen('report'); setPicking(null) }}>Report</button>
        <button type="button" aria-current={screen === 'agent' ? 'page' : undefined} onClick={() => { setScreen('agent'); setPicking(null) }}>Agent</button>
        <button type="button" aria-current={screen === 'journey' || screen === 'results' || screen === 'detail' ? 'page' : undefined} onClick={() => { setScreen('journey'); setPicking(null) }}>Plan journey</button>
        <button type="button" aria-current={screen === 'updates' ? 'page' : undefined} onClick={() => setScreen('updates')}>Updates</button>
        <button type="button" aria-current={screen === 'compare' ? 'page' : undefined} onClick={() => { setScreen('compare'); setPicking(null) }}>Compare</button>
        <button type="button" aria-current={screen === 'simulation' ? 'page' : undefined} onClick={() => { setScreen('simulation'); setPicking(null) }}>Simulation</button>
        <button type="button" aria-current={screen === 'review' ? 'page' : undefined} onClick={() => { setScreen('review'); setPicking(null) }}>Review</button>
        <button type="button" aria-current={screen === 'sources' ? 'page' : undefined} onClick={() => setScreen('sources')}>How it works</button>
      </nav>
      <button type="button" className={css.demo} onClick={switchDataMode}>{SEED_MODE ? 'FIXED SEED · USE API' : 'API MODE · USE SEED'}</button>
    </header>
    <main className={css.stage}>
      <div className={css.accessControls} aria-label="Display accessibility"><button type="button" aria-pressed={largeText} onClick={() => setLargeText(value => !value)}>Large text</button><button type="button" aria-pressed={highContrast} onClick={() => setHighContrast(value => !value)}>High contrast</button></div>
      {!SEED_MODE && <div className={css.connectionStatus} role="status"><strong>{live.connected ? 'Live updates connected' : 'Checking public updates every 3s'}</strong>{live.revision > 0 && <p>Routes refreshed for the latest approved network state.</p>}{(live.warning || live.routeWarning) && <p>{live.warning} {live.routeWarning}</p>}<button type="button" onClick={() => void live.refresh()}>Refresh</button></div>}
      <MapView network={network} published={published} routes={activeRoutes} selectedRouteId={selectedId} picking={Boolean(picking) && screen === 'journey'} onMapPick={point => { if (screen === 'journey') mapPick(point) }} mode={mapMode} />
      {(mapMode === 'docked' || screen === 'sources') && <div className={`${css.pagePane} ${screen === 'sources' ? css.full : ''}`}>
        {screen === 'sources' && <HowItWorksPage seedMode={SEED_MODE} snapshotAt={meta.snapshotAt} networkVersion={network.meta.version} catchmentM={network.meta.catchment_m} disclaimer={meta.disclaimer} apiSources={live.bundle?.meta?.sources} sourceWarning={live.sourceWarning} collectorStatus={live.sources} replanningStatus={live.replanning} collectorWarning={live.sourcesWarning || live.warning} replanningWarning={live.replanningWarning} sourcesReadAt={live.sourcesReadAt} onClose={() => setScreen('journey')} />}
        {screen === 'updates' && <UpdatesPage events={events} signals={signals} network={network} seedMode={SEED_MODE} snapshotAt={meta.snapshotAt} onOpenReview={() => setScreen('review')} onBack={() => setScreen('journey')} />}
        {screen === 'review' && (SEED_MODE ? <ReviewConsole events={events} signals={signals} network={network} logs={logs} onSave={review} onReplay={replay} /> : <ReviewAccess><SignalInbox network={network} onChanged={live.refresh} />{live.reviewWarning && <p role="alert">{live.reviewWarning}</p>}<ReviewConsole events={events} signals={signals} network={network} logs={logs} onSave={review} onReplay={replay} live /></ReviewAccess>)}
      </div>}
      <div hidden={screen !== 'agent'}><AgentPanel active={screen === 'agent'} seedMode={SEED_MODE} published={published} context={context} onRoutes={preference => void showRoutes(SEED_MODE ? meta.od.origin : origin, SEED_MODE ? meta.od.destination : destination, preference)} onBack={() => setScreen('journey')} /></div>
      <div hidden={screen !== 'compare' && screen !== 'simulation'} className={`${css.pagePane} ${css.full}`}>
        <div hidden={screen !== 'compare'}><ComparePage active={screen === 'compare'} seedMode={SEED_MODE} context={context} warning={live.warning} onBack={() => setScreen('journey')} /></div>
        <div hidden={screen !== 'simulation'}><SimulationPage active={screen === 'simulation'} seedMode={SEED_MODE} onBack={() => setScreen('journey')} /></div>
      </div>
      {screen === 'report' && (SEED_MODE ? <section className={css.panel}><h1>Reports use the API.</h1><p>Switch to API mode to submit an unverified report.</p><button type="button" onClick={switchDataMode}>Use API mode</button></section> : <SignalReportForm onAccepted={() => void live.refresh()} />)}
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
            <fieldset className={css.presets}><legend>TRAVELLER PROFILE</legend><button type="button" aria-pressed={persona === 'commuter'} onClick={() => { setPersona('commuter'); setCustomProfile(undefined) }}>Commuter</button><button type="button" aria-pressed={persona === 'wheelchair'} disabled={SEED_MODE} onClick={() => { setPersona('wheelchair'); setCustomProfile(undefined) }}>Wheelchair</button></fieldset>
            <fieldset className={css.presets}><legend>WHAT MATTERS MOST?</legend>{PRESETS.map(option => <button key={option.id} type="button" aria-pressed={preset === option.id} disabled={!SEED_MODE && option.id === 'least_walking'} title={!SEED_MODE && option.id === 'least_walking' ? 'Use a walking limit in your travel preferences' : undefined} className={preset === option.id ? css.activePreset : ''} onClick={() => { setPreset(option.id); setCustomProfile(previous => previous ? { ...previous, weights: undefined } : undefined) }}>{option.label}</button>)}</fieldset>
            {!SEED_MODE && <p className={css.tiny}>Less walking preset awaits backend support. Wheelchair hard walking and accessibility constraints still apply.</p>}
            <button type="submit" disabled={searching} className={css.primary}>{searching ? 'Finding routes…' : 'Find resilient routes'} <span>↗</span></button>
          </form>
          {!SEED_MODE && <PreferenceEditor active={screen === 'journey'} profile={effectiveProfile} onApply={next => { setCustomProfile(next); setPersona(next.mobility === 'wheelchair' ? 'wheelchair' : 'commuter'); if (origin && destination) void showRoutes(origin, destination, preset, next) }} />}
          <p className={css.tiny}>{SEED_MODE ? 'Only Tai Wai → Admiralty has route candidates in this fixture.' : 'Routes use the modelled network and published events; estimates are not a live timetable.'}</p>
      </div>}
      {screen === 'results' && <>
        {published[0] && <div className={css.alert}><span>!</span><strong>{published[0].title}</strong><span className={css.alertDetail}>Published event · {formatHkt(published[0].updated_at)}</span><button type="button" onClick={() => setScreen('updates')}>View update →</button></div>}
        <section data-panel data-route-refresh-revision={live.revision} data-route-ids={routes.map(route => route.route_id).join(',')} className={`${css.panel} ${css.results}`} aria-labelledby="routes-heading">
          <button type="button" className={css.back} onClick={() => setScreen('journey')}>← Edit journey</button>
          <span className={css.kicker}>ROUTES FOR YOUR JOURNEY</span>
          <h1 id="routes-heading">{nodes.get(origin)?.name_en ?? origin} <span>→</span><br />{nodes.get(destination)?.name_en ?? destination}</h1>
          <p className={css.subhead}>{routes.length} alternatives · {PRESETS.find(option => option.id === preset)?.label} · {SEED_MODE ? 'fixed seed snapshot' : 'API estimates'}</p>
          {!SEED_MODE && <p className={css.queryStamp}>Requested profile: {profileLabel(effectiveProfile)}</p>}
          <p className={css.queryStamp}>Requested departure: {formatHkt(queriedAt)}<br /><small>Query value: {queriedAt} · {SEED_MODE ? 'seed estimates are not recalculated.' : 'recomputed when the graph or published events change.'}</small></p>
          {routes.length ? <div className={css.routeList}>{routes.map((route, index) => <RouteCard key={route.route_id} route={route} letter={'ABC'[index]} network={network} selected={route.route_id === selectedId} onSelect={() => setSelectedId(route.route_id)} onDetail={() => { setSelectedId(route.route_id); setScreen('detail') }} />)}</div> : <div className={css.empty}><strong>No route returned for this pair.</strong><p>Try another departure or station pair. No feasible alternative has been supplied.</p></div>}
          <p className={css.tiny}>{SEED_MODE ? 'Fixed illustrative candidates.' : 'API candidates on the modelled network.'} Published events affect the network overlay. Times, fares and scores are derived estimates.</p>
        </section>
      </>}
      {screen === 'detail' && selected && <section data-panel className={`${css.panel} ${css.detailPanel}`}>
        <button type="button" className={css.back} onClick={() => setScreen('results')}>← All routes</button><span className={css.kicker}>ROUTE DETAILS · DERIVED ESTIMATE</span>
        <h1>{nodes.get(origin)?.name_en} <span>→</span><br />{nodes.get(destination)?.name_en}</h1>
        <div className={css.detailStats}><strong>{formatRange(selected.total.time_range_s)}</strong><span>{selected.total.transfers} transfer{selected.total.transfers === 1 ? '' : 's'}</span><span>{selected.total.walk_m} m walk</span><span>HK${selected.total.fare_hkd.toFixed(2)}</span></div>
        <h2>Step by step</h2><ol className={css.steps}>{selected.legs.map((leg, i) => <li data-enter key={i}><strong><i className={css.lineDot} style={{ background: leg.mode === 'WALK' ? '#6d7e70' : lineGradient(lineStyle(resolveLine(network, leg.line), leg.line).colors) }} />{leg.mode === 'WALK' ? 'Walk' : resolveLine(network, leg.line)?.name_en ?? leg.line ?? leg.mode}</strong><span>{nodes.get(leg.from)?.name_en ?? leg.from} → {nodes.get(leg.to)?.name_en ?? leg.to}</span><small>{legDuration(leg)}{leg.walk_m ? ` · ${leg.walk_m} m walking` : ''}</small></li>)}</ol>
        <h2>Why this route?</h2><p>{selected.explain}</p>
        {selected.warnings.length > 0 && <div className={css.warning}><strong>Check before travel</strong>{selected.warnings.map(warning => <p key={warning}>{warning}</p>)}</div>}
        {selected.score_breakdown && <div className={css.breakdown}><h2>Score factors</h2>{selected.score_breakdown.map(factor => <div key={factor.criterion}><span>{factor.criterion}</span><span>weight {Math.round(factor.weight * 100)}% · contribution {factor.contribution.toFixed(3)}</span></div>)}</div>}
        <ProvenanceBadge value={selected.provenance} /><p className={css.tiny}>Source: {SEED_MODE ? 'routes.seed.json' : 'route engine API'} · {formatHkt(meta.snapshotAt)} · {meta.disclaimer}</p>
      </section>}
    </main>
    <div ref={toast} role="status" aria-live="polite" className={success.text ? css.successToast : css.hiddenToast}>{success.text && <><span>✓</span><strong>{success.text}</strong></>}</div>
  </div>
}
