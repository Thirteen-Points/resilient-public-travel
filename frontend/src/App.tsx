import { useEffect, useMemo, useRef, useState } from 'react'
import { MapView } from './MapView'
import { seedDataSource } from './api/seedDataSource'
import { useLiveSession } from './api/useLiveSession'
import { SignalReportForm } from './components/SignalReportForm'
import { DeparturePicker, hktDeparture } from './components/DeparturePicker'
import { AgentAvatar } from './components/AgentAvatar'
import { AgentPanel } from './components/AgentPanel'
import { PreferenceEditor } from './components/PreferenceEditor'
import { LatestRequest, resolveProfile, profileLabel } from './api/p3Context'
import { HowItWorksPage } from './components/HowItWorksPage'
import { UpdatesPage } from './components/UpdatesPage'
import { ProvenanceBadge } from './components/ProvenanceBadge'
import { gsap, useGSAP, usePageMotion, useSuccessMotion } from './lib/motion'
import { lineGradient, lineStyle, resolveLine } from './lib/lineColors'
import { TRANSPORT_OPTIONS, transportLabel } from './lib/transport'
import { eastRailStations, findEastRailWalkingAccess, type WalkingAccess } from './lib/eastRailAccess'
import type { DemoMeta, Event, JourneyContext, Network, Persona, Preset, RouteCandidate, Signal, TravelProfile, TransitMode } from './api/types'
import { formatHkt, formatRange, legDuration, modeSummary, nodeIndex } from './data'
import css from './App.module.css'

type Screen = 'journey' | 'results' | 'updates' | 'detail' | 'sources' | 'agent' | 'report'
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
  const choices = eastRailStations(network).filter(node =>
    node.name_en.toLowerCase().includes(query.toLowerCase()) || node.name_zh.includes(query) || node.id.toLowerCase().includes(query.toLowerCase()),
  )
  return <div className={css.fieldWrap}>
    <label htmlFor={id} className={css.fieldLabel}>{label}</label>
    <input id={id} className={`${css.input} ${invalid ? css.invalid : ''}`} role="combobox"
      aria-expanded={active} aria-controls={`${id}-options`} aria-autocomplete="list" aria-invalid={Boolean(invalid)}
      aria-activedescendant={active && choices[index] ? `${id}-option-${choices[index].id}` : undefined}
      placeholder={label === 'TO' ? 'Choose an East Rail destination' : 'Search an East Rail station'}
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
      <span className={css.suggestionLabel}>EAST RAIL STATIONS</span>
      {choices.map((node, i) => <button key={node.id} id={`${id}-option-${node.id}`} type="button" role="option" aria-selected={index === i}
        className={`${css.suggestion} ${index === i ? css.highlighted : ''}`} onMouseDown={event => event.preventDefault()}
        onClick={() => { onSelect(node.id); setQuery('') }}>{node.name_en}<small>East Rail · {node.name_zh}</small></button>)}
      {!choices.length && <p className={css.small}>No matching East Rail station. Map selection is available.</p>}
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
      if (selected) gsap.fromTo(card.current, { y: 4 }, { y: 0, duration: .18, ease: 'power2.out', clearProps: 'transform' })
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
      const line = resolveLine(network, id)
      const style = lineStyle(line, id)
      return <span key={id} title={style.label}><i style={{ background: lineGradient(style.colors) }} />{line?.name_en ?? id}{style.colors.length > 1 ? ' · joint' : ''}</span>
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
  const [menuOpen, setMenuOpen] = useState(false)
  const [compactViewport, setCompactViewport] = useState(() => window.matchMedia('(max-width: 1023px)').matches)
  const [mobileView, setMobileView] = useState<'content' | 'map'>('content')
  const [refreshing, setRefreshing] = useState(false)
  const [origin, setOrigin] = useState('TAW')
  const [destination, setDestination] = useState('')
  const [activeField, setActiveField] = useState<Field | null>(null)
  const [picking, setPicking] = useState<Field | null>(null)
  const [picked, setPicked] = useState('')
  const [access, setAccess] = useState<{ origin: WalkingAccess | null; destination: WalkingAccess | null }>({ origin: null, destination: null })
  const [checkingWalk, setCheckingWalk] = useState(false)
  const walkCheck = useRef<AbortController | null>(null)
  const [error, setError] = useState('')
  const [preset, setPreset] = useState<Preset>('fastest')
  const [persona, setPersona] = useState<Persona>('commuter')
  const [transport, setTransport] = useState<'all' | TransitMode>('all')
  const [customProfile, setCustomProfile] = useState<TravelProfile | undefined>()
  const effectiveProfile = useMemo(() => resolveProfile({ persona, preset, profile: customProfile }), [persona, preset, customProfile])
  const [largeText, setLargeText] = useState(false), [highContrast, setHighContrast] = useState(false)
  const [departure, setDeparture] = useState('08:20')
  const [departureDate, setDepartureDate] = useState('2026-09-22')
  const [searching, setSearching] = useState(false)
  const [queriedAt, setQueriedAt] = useState('')
  const [success, setSuccess] = useState({ text: '', revision: 0 })
  const root = useRef<HTMLDivElement>(null)
  const toast = useRef<HTMLDivElement>(null)
  const searchingRef = useRef(false)
  const routeRequests = useRef(new LatestRequest()), requestedJourney = useRef('')
  const requestedScreen = useRef<Screen>('journey')
  const [seedRoutes, setRoutes] = useState<RouteCandidate[]>([])
  const routes = SEED_MODE ? seedRoutes : live.routes
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected = useMemo(() => routes.find(route => route.route_id === selectedId), [routes, selectedId])
  const eventRevisions = (SEED_MODE ? seedBundle?.published : live.bundle?.published)?.map(event => `${event.event_id}@${event.version}`).sort().join(',') ?? ''
  const context = useMemo<JourneyContext>(() => ({ origin, destination, departAt: hktDeparture(departureDate, departure), preset, persona, profile: effectiveProfile, requiredModes: transport === 'all' ? undefined : [transport], eventRevisions, eventIds: eventRevisions ? eventRevisions.split(',').map(value => value.slice(0, value.lastIndexOf('@'))) : [] }), [origin, destination, departureDate, departure, preset, persona, effectiveProfile, transport, eventRevisions])
  const plannerKey = JSON.stringify([origin, destination, context.departAt, effectiveProfile, transport])
  useEffect(() => {
    if (searchingRef.current && (requestedJourney.current !== plannerKey || requestedScreen.current !== screen)) { routeRequests.current.cancel(); searchingRef.current = false; setSearching(false) }
  }, [plannerKey, screen])
  useEffect(() => () => routeRequests.current.cancel(), [])
  useEffect(() => {
    if (compactViewport) window.scrollTo({ top: 0, behavior: 'instant' })
  }, [screen, mobileView, compactViewport])
  useEffect(() => {
    const media = window.matchMedia('(max-width: 1023px)')
    const update = () => { setCompactViewport(media.matches); setMenuOpen(false) }
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  useEffect(() => {
    if (!menuOpen) return
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setMenuOpen(false); document.getElementById('navigation-toggle')?.focus() }
    }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [menuOpen])
  usePageMotion(root, screen, Boolean(bundle))
  useSuccessMotion(toast, success.revision)
  useEffect(() => {
    if (!success.text) return
    const timer = setTimeout(() => setSuccess(value => ({ ...value, text: '' })), 4200)
    return () => clearTimeout(timer)
  }, [success.revision, success.text])
  useEffect(() => {
    if (!SEED_MODE && live.revision > 0) setSuccess(previous => ({ text: 'Routes updated for the latest network.', revision: previous.revision + 1 }))
  }, [live.revision])

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
  const navigate = (next: Screen) => {
    walkCheck.current?.abort(); setCheckingWalk(false)
    if (next === 'journey') window.scrollTo({ top: 0, behavior: 'instant' })
    setScreen(next); setMenuOpen(false); setMobileView('content'); setActiveField(null); setPicking(null)
  }
  const pickOnMap = (field: Field) => {
    walkCheck.current?.abort(); setCheckingWalk(false)
    setActiveField(null); setPicking(field); setError(''); setMobileView('map')
  }
  const setField = (field: Field, value: string) => {
    walkCheck.current?.abort(); setCheckingWalk(false)
    if (field === 'origin') setOrigin(value)
    else setDestination(value)
    setAccess(previous => ({ ...previous, [field]: null }))
    setActiveField(null); setPicking(null); setError(''); setPicked(''); setMobileView('content')
  }
  const showRoutes = async (from = origin, to = destination, preference = preset, profile = effectiveProfile) => {
    if (checkingWalk) return
    setActiveField(null)
    if (!to || !from) { setError('Choose a destination and starting point before continuing.'); return }
    const allowed = new Set(eastRailStations(network).map(station => station.id))
    if (!allowed.has(from) || !allowed.has(to)) { setError('Choose East Rail stations for both ends.'); return }
    if (from === to) { setError('Choose two different East Rail stations.'); return }
    const departAt = hktDeparture(departureDate, departure)
    if (!Number.isFinite(Date.parse(departAt))) { setError('Choose a valid Hong Kong departure date and time.'); return }
    searchingRef.current = true; setSearching(true)
    const request = routeRequests.current.begin()
    const requestedProfile = resolveProfile({ persona, preset: preference, profile })
    requestedJourney.current = JSON.stringify([from, to, departAt, requestedProfile, transport])
    requestedScreen.current = screen
    try {
      const value = { origin: from, destination: to, departAt, preset: preference, persona, requiredModes: context.requiredModes, ...(!SEED_MODE ? { profile: requestedProfile } : {}) }
      const next = SEED_MODE ? await seedDataSource.getRoutes(value) : await live.query(value, request.signal)
      if (!request.current()) return
      setRoutes(next); setOrigin(from); setDestination(to); setPreset(preference); setQueriedAt(departAt)
      setSelectedId(next[0]?.route_id ?? null)
      setScreen('results'); setMobileView('content'); setError(''); setPicking(null)
      if (next.length) celebrate(`${next.length} ${SEED_MODE ? 'seed' : 'API'} alternatives ready`)
    } catch (cause) { if (request.current()) setError(`Route data could not be loaded. ${cause instanceof Error ? cause.message : String(cause)}`) }
    finally { if (request.current()) { setSearching(false); searchingRef.current = false } }
  }
  const mapPick = async (point: { lat: number; lng: number }) => {
    if (!picking) return
    walkCheck.current?.abort()
    const controller = new AbortController()
    walkCheck.current = controller
    const field = picking
    setCheckingWalk(true); setError(''); setPicked('')
    try {
      const match = await findEastRailWalkingAccess(network, point, controller.signal)
      if (controller.signal.aborted) return
      if (!match) { setError('No East Rail station is within 800 m by a modelled walking route. Choose a closer point.'); return }
      if (field === 'origin') setOrigin(match.station.id)
      else setDestination(match.station.id)
      setAccess(previous => ({ ...previous, [field]: match }))
      setActiveField(null); setPicking(null); setMobileView('content')
      setPicked(`${field === 'origin' ? 'Start' : 'End'} point: ${Math.round(match.metres)} m walking to ${match.station.name_en} (OpenStreetMap pedestrian route). Verify the station entrance and path on site.`)
      if (compactViewport) requestAnimationFrame(() => {
        document.getElementById(field)?.scrollIntoView({ block: 'center' })
        document.getElementById('content-view-tab')?.focus({ preventScroll: true })
      })
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Walking route could not be checked.')
    } finally {
      if (walkCheck.current === controller) { walkCheck.current = null; setCheckingWalk(false) }
    }
  }
  const activeRoutes = screen === 'results' || screen === 'detail' ? routes : []
  const journeyScreen = screen === 'journey' || screen === 'results' || screen === 'detail'
  const showViewTabs = compactViewport && journeyScreen
  const mapVisible = screen !== 'sources' && (!compactViewport || (journeyScreen && mobileView === 'map'))
  const contentVisible = !showViewTabs || mobileView === 'content'
  const chooseView = (view: 'content' | 'map') => {
    if (view === 'content') { walkCheck.current?.abort(); setCheckingWalk(false) }
    setMobileView(view); setActiveField(null)
    if (screen === 'journey' && view === 'map') { setPicking(previous => previous ?? 'destination'); setError('') }
    else setPicking(null)
  }
  const mapMode: 'full' | 'docked' | 'hidden' =
    screen === 'updates' ? 'docked' : mapVisible ? 'full' : 'hidden'
  return <div ref={root} className={`${css.shell} ${largeText ? css.largeText : ''} ${highContrast ? css.highContrast : ''}`}>
    <header className={css.header}>
      <button type="button" className={css.brand} onClick={() => navigate('journey')} aria-label="ResilientRoute home">rr<span>.</span></button>
      <button id="navigation-toggle" type="button" className={css.menuToggle} aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen} aria-controls="main-navigation" onClick={() => setMenuOpen(value => !value)}>{menuOpen ? 'Close' : 'Menu'} <span aria-hidden="true">{menuOpen ? '×' : '☰'}</span></button>
      <nav id="main-navigation" aria-label="Main navigation" hidden={compactViewport && !menuOpen} className={menuOpen ? css.navOpen : undefined}>
        <button type="button" aria-current={screen === 'report' ? 'page' : undefined} onClick={() => navigate('report')}>Report</button>
        <button type="button" aria-current={screen === 'agent' ? 'page' : undefined} onClick={() => navigate('agent')}>Agent</button>
        <button type="button" aria-current={journeyScreen ? 'page' : undefined} onClick={() => navigate('journey')}>Plan journey</button>
        <button type="button" aria-current={screen === 'updates' ? 'page' : undefined} onClick={() => navigate('updates')}>Updates</button>
        <button type="button" aria-current={screen === 'sources' ? 'page' : undefined} onClick={() => navigate('sources')}>How it works</button>
      </nav>
      <button type="button" className={css.demo} onClick={switchDataMode}>{SEED_MODE ? 'FIXED SEED · USE API' : 'API MODE · USE SEED'}</button>
    </header>
    <main className={`${css.stage} ${journeyScreen ? css.journeyLayout : ''} ${screen === 'detail' ? css.detailLayout : ''} ${showViewTabs ? mobileView === 'map' ? css.mapOnly : css.contentOnly : ''}`}>
      <div className={css.accessControls} aria-label="Display accessibility"><button type="button" aria-pressed={largeText} onClick={() => setLargeText(value => !value)}>Large text</button><button type="button" aria-pressed={highContrast} onClick={() => setHighContrast(value => !value)}>High contrast</button></div>
      {!SEED_MODE && (live.warning || live.routeWarning) && <div className={css.refreshNotice} role="alert"><p>{live.warning} {live.routeWarning}</p><button type="button" disabled={refreshing} aria-busy={refreshing} onClick={async () => { setRefreshing(true); try { await live.refresh() } finally { setRefreshing(false) } }}>{refreshing ? 'Refreshing…' : 'Refresh'}</button></div>}
      {showViewTabs && <div className={css.viewTabs} role="tablist" aria-label="Journey view" onKeyDown={event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
        event.preventDefault()
        const view = event.key === 'Home' ? 'content' : event.key === 'End' ? 'map' : mobileView === 'content' ? 'map' : 'content'
        chooseView(view); document.getElementById(`${view}-view-tab`)?.focus()
      }}>
        <button id="content-view-tab" type="button" role="tab" aria-selected={mobileView === 'content'} aria-controls="journey-content" tabIndex={mobileView === 'content' ? 0 : -1} onClick={() => chooseView('content')}>{screen === 'journey' ? 'Journey' : screen === 'detail' ? 'Steps' : 'Routes'}</button>
        <button id="map-view-tab" type="button" role="tab" aria-selected={mobileView === 'map'} aria-controls="journey-map" tabIndex={mobileView === 'map' ? 0 : -1} onClick={() => chooseView('map')}>Map</button>
      </div>}
      <div id="journey-map" className={css.mapFrame} hidden={!mapVisible} role={showViewTabs ? 'tabpanel' : undefined} aria-labelledby={showViewTabs ? 'map-view-tab' : undefined}>
        <MapView network={network} published={published} routes={activeRoutes} selectedRouteId={selectedId} picking={Boolean(picking) && screen === 'journey'} onMapPick={point => { if (screen === 'journey') void mapPick(point) }} mode={mapMode} />
        {showViewTabs && mobileView === 'map' && error && <p className={css.mapPickNotice} role="alert">{error}</p>}
        {showViewTabs && mobileView === 'map' && checkingWalk && <p className={css.mapPickNotice} role="status">Checking pedestrian routes…</p>}
      </div>
      {(mapMode === 'docked' || screen === 'sources') && <div className={`${css.pagePane} ${screen === 'sources' ? css.full : ''}`}>
        {screen === 'sources' && <HowItWorksPage seedMode={SEED_MODE} snapshotAt={meta.snapshotAt} networkVersion={network.meta.version} catchmentM={network.meta.catchment_m} disclaimer={meta.disclaimer} apiSources={live.bundle?.meta?.sources} sourceWarning={live.sourceWarning} collectorStatus={live.sources} replanningStatus={live.replanning} collectorWarning={live.sourcesWarning || live.warning} replanningWarning={live.replanningWarning} sourcesReadAt={live.sourcesReadAt} onRefresh={live.refresh} onClose={() => navigate('journey')} />}
        {screen === 'updates' && <UpdatesPage events={events} signals={signals} network={network} seedMode={SEED_MODE} snapshotAt={meta.snapshotAt} onBack={() => navigate('journey')} />}
      </div>}
      <div hidden={screen !== 'agent'}><AgentPanel active={screen === 'agent'} seedMode={SEED_MODE} published={published} context={context} onRoutes={preference => void showRoutes(SEED_MODE ? meta.od.origin : origin, SEED_MODE ? meta.od.destination : destination, preference)} onBack={() => navigate('journey')} /></div>
      {screen === 'report' && (SEED_MODE ? <section className={css.panel}><h1>Reports use the API.</h1><p>Switch to API mode to submit an unverified report.</p><button type="button" onClick={switchDataMode}>Use API mode</button></section> : <SignalReportForm onAccepted={() => void live.refresh()} />)}
      {screen === 'journey' && <div id="journey-content" data-panel hidden={!contentVisible} role={showViewTabs ? 'tabpanel' : undefined} aria-labelledby={showViewTabs ? 'content-view-tab' : undefined} className={`${css.panel} ${css.mobilePanel}`}>
          <h1>Where are you<br />heading?</h1>
          <p className={css.subhead}>Choose transport, then select East Rail stations or map points within 800 m walking distance of them.</p>
          <fieldset className={`${css.presets} ${css.transportChoices}`}><legend>TRANSPORT · 交通方式</legend>{TRANSPORT_OPTIONS.map(option => <button key={option.id} type="button" aria-pressed={transport === option.id} disabled={searching} className={transport === option.id ? css.activePreset : ''} onClick={() => { setTransport(option.id); setActiveField(null); setPicking(null); setError('') }}>{option.label}</button>)}</fieldset>
          <p className={css.tiny}>{transport === 'MINIBUS' && !network.lines.some(line => line.mode === 'MINIBUS') ? 'Minibus · 小巴: routes are not available in this modelled network yet. Choose another mode for available routes.' : transport === 'all' ? 'Compare all available modes, including bus and ferry connections.' : `Routes include ${transportLabel([transport])}; other modes and walking may provide connections.`}</p>
          <button type="button" className={css.agentEntry} onClick={() => { navigate('agent'); setError('') }}><AgentAvatar issue={published.length > 0} small /><span><strong>Meet your route companion</strong><small>Ask the Agent · explore this scenario</small></span><b>↗</b></button>
          <form onSubmit={event => { event.preventDefault(); void showRoutes() }}>
            <StationField id="origin" label="FROM" value={origin} network={network} active={activeField === 'origin'} onFocus={() => { setActiveField('origin'); setPicking(null) }} onSelect={value => setField('origin', value)} onPickMap={() => pickOnMap('origin')} />
            <button className={css.swap} type="button" onClick={() => { walkCheck.current?.abort(); setCheckingWalk(false); setOrigin(destination); setDestination(origin); setAccess(previous => ({ origin: previous.destination, destination: previous.origin })); setActiveField(null); setPicking(null); setPicked('') }} aria-label="Swap stations">⇅</button>
            <StationField id="destination" label="TO" value={destination} network={network} active={activeField === 'destination'} invalid={Boolean(error && !destination)} onFocus={() => { setActiveField('destination'); setPicking(null) }} onSelect={value => setField('destination', value)} onPickMap={() => pickOnMap('destination')} />
            <div className={css.fieldAssist}><button type="button" onClick={() => pickOnMap('destination')}>◎ Tap the map</button><span>Up to 800 m walking to East Rail</span></div>
            {checkingWalk && <p role="status" className={css.confirm}>Checking pedestrian routes…</p>}
            {access.origin && <p className={css.confirm}>Start point → {nodes.get(origin)?.name_en}: {Math.round(access.origin.metres)} m walking</p>}
            {access.destination && <p className={css.confirm}>End point → {nodes.get(destination)?.name_en}: {Math.round(access.destination.metres)} m walking</p>}
            {picked && <p className={css.confirm}>{picked}</p>}
            {error && <p role="alert" className={css.error}>{error}</p>}
            <DeparturePicker date={departureDate} time={departure} onDate={setDepartureDate} onTime={setDeparture} />
            <fieldset className={css.presets}><legend>TRAVELLER PROFILE</legend><button type="button" aria-pressed={persona === 'commuter'} onClick={() => { setPersona('commuter'); setCustomProfile(undefined) }}>Commuter</button><button type="button" aria-pressed={persona === 'wheelchair'} disabled={SEED_MODE} onClick={() => { setPersona('wheelchair'); setCustomProfile(undefined) }}>Wheelchair</button></fieldset>
            <fieldset className={css.presets}><legend>WHAT MATTERS MOST?</legend>{PRESETS.map(option => <button key={option.id} type="button" aria-pressed={preset === option.id} disabled={!SEED_MODE && option.id === 'least_walking'} title={!SEED_MODE && option.id === 'least_walking' ? 'Use a walking limit in your travel preferences' : undefined} className={preset === option.id ? css.activePreset : ''} onClick={() => { setPreset(option.id); setCustomProfile(previous => previous ? { ...previous, weights: undefined } : undefined) }}>{option.label}</button>)}</fieldset>
            {!SEED_MODE && <p className={css.tiny}>Less walking preset awaits backend support. Wheelchair hard walking and accessibility constraints still apply.</p>}
            <button type="submit" disabled={searching || checkingWalk} className={css.primary}>{searching ? 'Finding routes…' : 'Find resilient routes'} <span>↗</span></button>
          </form>
          {!SEED_MODE && <PreferenceEditor active={screen === 'journey'} profile={effectiveProfile} onApply={next => { setCustomProfile(next); setPersona(next.mobility === 'wheelchair' ? 'wheelchair' : 'commuter'); if (origin && destination) void showRoutes(origin, destination, preset, next) }} />}
          <p className={css.tiny}>{SEED_MODE ? 'Only Tai Wai → Admiralty has route candidates in this fixture.' : 'Routes use the modelled network and published events; estimates are not a live timetable.'}</p>
      </div>}
      {screen === 'results' && <>
        <section id="journey-content" data-panel hidden={!contentVisible} role={showViewTabs ? 'tabpanel' : undefined} data-route-refresh-revision={live.revision} data-route-ids={routes.map(route => route.route_id).join(',')} className={`${css.panel} ${css.results} ${css.mobilePanel}`} aria-labelledby={showViewTabs ? 'content-view-tab' : 'routes-heading'}>
          <button type="button" className={css.back} onClick={() => navigate('journey')}>← Edit journey</button>
          {published[0] && <div className={css.alert}><span aria-hidden="true">!</span><strong>{published[0].title}</strong><span className={css.alertDetail}>Published event · {formatHkt(published[0].updated_at)}</span><button type="button" onClick={() => navigate('updates')}>View update →</button></div>}
          <span className={css.kicker}>ROUTES FOR YOUR JOURNEY</span>
          <h1 id="routes-heading">{nodes.get(origin)?.name_en ?? origin} <span>→</span><br />{nodes.get(destination)?.name_en ?? destination}</h1>
          <p className={css.subhead}>{routes.length} alternatives · {transportLabel(context.requiredModes)} · {PRESETS.find(option => option.id === preset)?.label} · {SEED_MODE ? 'fixed seed snapshot' : 'API estimates'}</p>
          {(access.origin || access.destination) && <p className={css.confirm}>Access walks: {access.origin ? `start point → ${nodes.get(origin)?.name_en} ${Math.round(access.origin.metres)} m` : 'start at station'} · {access.destination ? `${nodes.get(destination)?.name_en} → end point ${Math.round(access.destination.metres)} m` : 'end at station'}. These walks are separate from the route times and walking totals below.</p>}
          {!SEED_MODE && <p className={css.queryStamp}>Requested profile: {profileLabel(effectiveProfile)}</p>}
          <p className={css.queryStamp}>Requested departure: {formatHkt(queriedAt)}<br /><small>Query value: {queriedAt} · {SEED_MODE ? 'fixed seed estimates filtered by modelled service hours; journey times are not recalculated.' : 'recomputed when the graph or published events change.'}</small></p>
          {routes.length ? <div className={css.routeList}>{routes.map((route, index) => <RouteCard key={route.route_id} route={route} letter={String.fromCharCode(65 + index)} network={network} selected={route.route_id === selectedId} onSelect={() => setSelectedId(route.route_id)} onDetail={() => { setSelectedId(route.route_id); navigate('detail') }} />)}</div> : <div className={css.empty} role="status"><strong>No {transport === 'all' ? '' : `${transportLabel([transport])} `}route returned for this pair.</strong><p>{transport === 'MINIBUS' && !network.lines.some(line => line.mode === 'MINIBUS') ? 'Minibus routes are not available in the current modelled network yet. Choose another transport mode.' : SEED_MODE ? 'The fixed fixture only covers Tai Wai → Admiralty. Switch to API mode to query other stations, stops and piers.' : 'Try All modes, another departure, or another station, bus stop or ferry pier.'}</p><button type="button" className={css.back} onClick={() => navigate('journey')}>Edit transport and journey →</button></div>}
          <p className={css.tiny}>{SEED_MODE ? 'Fixed illustrative candidates.' : 'API candidates on the modelled network.'} Fares use adult Octopus ordinary class, bus section fares and ferry upper deck prices; personal concessions are excluded. Published events affect the network overlay. Times and scores are derived estimates.</p>
        </section>
      </>}
      {screen === 'detail' && selected && <section id="journey-content" data-panel hidden={!contentVisible} role={showViewTabs ? 'tabpanel' : undefined} aria-labelledby={showViewTabs ? 'content-view-tab' : undefined} className={`${css.panel} ${css.detailPanel} ${css.mobilePanel}`}>
        <button type="button" className={css.back} onClick={() => navigate('results')}>← All routes</button><span className={css.kicker}>ROUTE DETAILS · DERIVED ESTIMATE</span>
        <h1>{nodes.get(origin)?.name_en} <span>→</span><br />{nodes.get(destination)?.name_en}</h1>
        {(access.origin || access.destination) && <p className={css.confirm}>Map-point access walks: {access.origin ? `${Math.round(access.origin.metres)} m at start` : 'start at station'} · {access.destination ? `${Math.round(access.destination.metres)} m at end` : 'end at station'}. Add these to the route walking total; time estimates below exclude them.</p>}
        <div className={css.detailStats}><strong>{formatRange(selected.total.time_range_s)}</strong><span>{selected.total.transfers} transfer{selected.total.transfers === 1 ? '' : 's'}</span><span>{selected.total.walk_m} m walk</span><span>HK${selected.total.fare_hkd.toFixed(2)}</span></div>
        <p className={css.tiny}>Adult fares · Octopus ordinary class · ferry upper deck (lower deck for wheelchair routes). Each ticket is shown on its first step; connecting MTR lines share the same ticket.</p>
        <h2>Step by step</h2><ol className={css.steps}>{selected.legs.map((leg, i) => <li data-enter key={i}><strong><i className={css.lineDot} style={{ background: leg.mode === 'WALK' ? '#6d7e70' : lineGradient(lineStyle(resolveLine(network, leg.line), leg.line).colors) }} />{leg.mode === 'WALK' ? 'Walk' : resolveLine(network, leg.line)?.name_en ?? leg.line ?? leg.mode}</strong><span>{nodes.get(leg.from)?.name_en ?? leg.from} → {nodes.get(leg.to)?.name_en ?? leg.to}</span><small>{legDuration(leg)}{leg.walk_m ? ` · ${leg.walk_m} m walking` : ''}{leg.mode !== 'WALK' && leg.fare_hkd !== undefined ? ` · ${leg.fare_hkd > 0 ? `HK$${leg.fare_hkd.toFixed(2)}` : 'Included in ticket'}` : ''}</small></li>)}</ol>
        <h2>Why this route?</h2><p>{selected.explain}</p>
        {selected.warnings.length > 0 && <div className={css.warning}><strong>Check before travel</strong>{selected.warnings.map(warning => <p key={warning}>{warning}</p>)}</div>}
        {selected.score_breakdown && <div className={css.breakdown}><h2>Score factors</h2>{selected.score_breakdown.map(factor => <div key={factor.criterion}><span>{factor.criterion}</span><span>weight {Math.round(factor.weight * 100)}% · contribution {factor.contribution.toFixed(3)}</span></div>)}</div>}
        <ProvenanceBadge value={selected.provenance} /><p className={css.tiny}>Source: {SEED_MODE ? 'routes.seed.json' : 'route engine API'} · {formatHkt(meta.snapshotAt)} · {meta.disclaimer}</p>
      </section>}
    </main>
    <div ref={toast} role="status" aria-live="polite" className={success.text ? css.successToast : css.hiddenToast}>{success.text && <><span>✓</span><strong>{success.text}</strong></>}</div>
  </div>
}
