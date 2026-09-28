import { useEffect, useMemo, useState } from 'react'
import { MapView } from './MapView'
import { seedDataSource } from './api/seedDataSource'
import type { DemoMeta, Event, Network, Preset, RouteCandidate, Signal } from './api/types'
import { CORRIDOR_IDS, formatHkt, formatRange, modeSummary, nearestAccessPoint, nodeIndex } from './data'
import css from './App.module.css'

type Screen = 'journey' | 'results' | 'updates' | 'detail' | 'sources'
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
  return <article className={`${css.routeCard} ${selected ? css.selectedRoute : ''}`}>
    <button type="button" className={css.routeSelect} onClick={onSelect} aria-pressed={selected}>
      <span className={css.routeTop}><span className={css.routeLetter}>{letter}</span><span className={css.routeName}>Option {letter}<small>{modeSummary(route, network)}</small></span><strong>{formatRange(route.total.time_range_s)}</strong></span>
      <span className={css.routeMetrics}><span>{route.total.transfers} transfer{route.total.transfers === 1 ? '' : 's'}</span><span>{route.total.walk_m} m walk</span><span>HK${route.total.fare_hkd.toFixed(2)}</span></span>
    </button>
    <div className={css.routeFooter}><span>Score {Math.round(route.score * 100)}/100 · Estimated</span><button type="button" onClick={onDetail}>View steps →</button></div>
    <div className={css.scoreTrack} aria-label={`Route score ${Math.round(route.score * 100)} out of 100`}><span style={{ width: `${route.score * 100}%` }} /></div>
    <div className={css.routeCaveat}><ProvenanceBadge value={route.provenance} /><span>{route.warnings[0] ?? 'No specific warning in fixture; verify service.'}</span></div>
    <p className={css.routeFreshness}>{route.notes[0] ?? 'Illustrative candidate'} · Seed age at snapshot {route.total.freshness_s}s</p>
  </article>
}

function EventCard({ event, signals, network }: { event: Event; signals: Signal[]; network: Network }) {
  const nodes = nodeIndex(network)
  const evidence = signals.filter(signal => event.signals.includes(signal.signal_id))
  return <article className={css.eventCard}>
    <div className={css.eventTop}><span className={event.status === 'published' ? css.published : css.pending}>{event.status === 'published' ? '● Published' : '○ Awaiting review'}</span><span>{Math.round(event.confidence * 100)}% confidence</span></div>
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
  const [routes, setRoutes] = useState<RouteCandidate[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [natural, setNatural] = useState(false)
  const [naturalText, setNaturalText] = useState('')
  const [naturalResult, setNaturalResult] = useState(false)
  const selected = useMemo(() => routes.find(route => route.route_id === selectedId), [routes, selectedId])

  useEffect(() => {
    let alive = true
    Promise.all([seedDataSource.getNetwork(), seedDataSource.getEvents(), seedDataSource.getMeta()])
      .then(async ([network, { events, signals }, meta]) => {
        const published = await seedDataSource.getPublishedEvents(meta.snapshotAt)
        if (alive) setBundle({ network, events, signals, published, meta })
      }).catch(cause => { if (alive) setLoadError(String(cause)) })
    return () => { alive = false }
  }, [])

  if (loadError) return <div className={css.state}>Could not load seed data. {loadError}</div>
  if (!bundle) return <div className={css.state}>Loading the demo snapshot…</div>
  const { network, events, signals, published, meta } = bundle
  const nodes = nodeIndex(network)
  const setField = (field: Field, value: string) => {
    if (field === 'origin') setOrigin(value)
    else setDestination(value)
    setActiveField(null); setPicking(null); setError(''); setPicked('')
  }
  const showRoutes = async (from = origin, to = destination, preference = preset) => {
    setActiveField(null)
    if (!to || !from) { setError('Choose a destination and starting point before continuing.'); return }
    if (from === to) { setError('Choose two different stations.'); return }
    const next = await seedDataSource.getRoutes({ origin: from, destination: to, departAt: meta.snapshotAt, preset: preference })
    setRoutes(next.slice(0, 3))
    setSelectedId(next[0]?.route_id ?? null)
    setScreen('results'); setNaturalResult(false); setError('')
  }
  const mapPick = (point: { lat: number; lng: number }) => {
    if (!picking) return
    const nearest = nearestAccessPoint(network, point)
    if (!nearest) { setError(`No modelled access point within ${network.meta.catchment_m} m. Search by station instead.`); return }
    setField(picking, nearest.node.id)
    setPicked(`Closest accessible seed point: ${nearest.node.name_en} · about ${Math.round(nearest.metres)} m straight-line. Confirm access on site.`)
  }
  const interpretNatural = async () => {
    const lowered = naturalText.toLowerCase()
    const from = lowered.includes('tai wai') || naturalText.includes('大圍') || naturalText.includes('大围') ? 'TAW' : ''
    const to = lowered.includes('admiralty') || naturalText.includes('金鐘') || naturalText.includes('金钟') ? 'ADM' : ''
    if (!from || !to) { setError('This M0 demo can only parse Tai Wai → Admiralty. Use the station form for other inputs.'); return }
    const time = naturalText.match(/\b([01]?\d|2[0-3]):[0-5]\d\b/)?.[0]
    if (time) setDeparture(time)
    const preference: Preset = /less walking|short walk|少走|步行少/i.test(naturalText) ? 'least_walking' : 'fastest'
    setOrigin(from); setDestination(to); setPreset(preference)
    const next = await seedDataSource.getRoutes({ origin: from, destination: to, departAt: meta.snapshotAt, preset: preference })
    setRoutes(next.slice(0, 3)); setSelectedId(next[0]?.route_id ?? null)
    setNaturalResult(true); setError('')
  }
  const activeRoutes = screen === 'results' || screen === 'detail' ? routes : []
  return <div className={css.shell}>
    <header className={css.header}>
      <button type="button" className={css.brand} onClick={() => setScreen('journey')} aria-label="ResilientRoute home">rr<span>.</span></button>
      <nav aria-label="Main navigation">
        <button type="button" aria-current={screen === 'journey' || screen === 'results' || screen === 'detail' ? 'page' : undefined} onClick={() => { setScreen('journey'); setNatural(false) }}>Plan journey</button>
        <button type="button" aria-current={screen === 'updates' ? 'page' : undefined} onClick={() => setScreen('updates')}>Updates</button>
        <button type="button" aria-current={screen === 'sources' ? 'page' : undefined} onClick={() => setScreen('sources')}>How it works</button>
      </nav>
      <span className={css.demo}>ACADEMIC DEMO</span>
    </header>
    <main className={css.stage}>
      <MapView network={network} published={published} routes={activeRoutes} selectedRouteId={selectedId} picking={Boolean(picking)} onMapPick={mapPick} />
      {screen === 'journey' && <div className={`${css.panel} ${natural ? css.naturalPanel : ''} ${naturalResult ? css.naturalResultPanel : ''}`}>
        {natural ? <>
          <h1>Where are you<br />heading?</h1>
          {naturalResult ? <>
            <div className={css.chatBubble}>{naturalText}</div>
            <div className={css.chatResponse}><strong>Here we go!</strong><p>Recognized: Tai Wai → Admiralty · {departure} HKT. Preference: {PRESETS.find(item => item.id === preset)?.label}. This is a deterministic seed interpretation, not live AI.</p></div>
            {routes[0] && <div className={css.chatRoute}><strong>{formatRange(routes[0].total.time_range_s)} · {routes[0].total.walk_m} m walk · HK${routes[0].total.fare_hkd.toFixed(2)}</strong><span>Seed estimate · {Math.round(routes[0].score * 100)}/100</span><ol>{routes[0].legs.map((leg, index) => <li key={index}>{leg.mode === 'WALK' ? 'Walk' : network.lines.find(line => line.id === leg.line)?.name_en ?? leg.line ?? leg.mode}: {nodes.get(leg.from)?.name_en ?? leg.from} → {nodes.get(leg.to)?.name_en ?? leg.to}</li>)}</ol></div>}
            <button type="button" className={css.primary} onClick={() => void showRoutes(origin, destination, preset)}>See seed routes →</button>
          </> : <>
            <p className={css.subhead}>Describe the trip in your own words.</p>
            <label htmlFor="natural" className={css.fieldLabel}>YOUR JOURNEY</label>
            <textarea id="natural" className={css.textarea} placeholder="From Tai Wai to Admiralty at 08:30, with less walking." value={naturalText} onChange={e => setNaturalText(e.target.value)} />
            <button type="button" className={css.primary} onClick={() => void interpretNatural()}>Interpret journey →</button>
            <p className={css.tiny}>Seed-only text recognition. Voice input and live AI are not connected.</p>
          </>}
          {error && <p role="alert" className={css.error}>{error}</p>}
          <button type="button" className={css.textButton} onClick={() => { setNatural(false); setNaturalResult(false); setError('') }}>← Use station form</button>
        </> : <>
          <h1>Where are you<br />heading?</h1>
          <p className={css.subhead}>Search a modelled station or select it on the map.</p>
          <form onSubmit={event => { event.preventDefault(); void showRoutes() }}>
            <StationField id="origin" label="FROM" value={origin} network={network} active={activeField === 'origin'} onFocus={() => { setActiveField('origin'); setPicking(null) }} onSelect={value => setField('origin', value)} onPickMap={() => { setActiveField(null); setPicking('origin') }} />
            <button className={css.swap} type="button" onClick={() => { setOrigin(destination); setDestination(origin); setActiveField(null) }} aria-label="Swap stations">⇅</button>
            <StationField id="destination" label="TO" value={destination} network={network} active={activeField === 'destination'} invalid={Boolean(error && !destination)} onFocus={() => { setActiveField('destination'); setPicking(null) }} onSelect={value => setField('destination', value)} onPickMap={() => { setActiveField(null); setPicking('destination') }} />
            <div className={css.fieldAssist}><button type="button" onClick={() => { setActiveField(null); setPicking('destination') }}>◎ Tap the map</button><span>Within {network.meta.catchment_m} m of a station</span></div>
            {picked && <p className={css.confirm}>{picked}</p>}
            {error && <p role="alert" className={css.error}>{error}</p>}
            <div className={css.timeRow}><label htmlFor="departure" className={css.fieldLabel}>LEAVE · HONG KONG TIME</label><span>22 SEP 2026 · SEED SNAPSHOT</span></div>
            <input id="departure" className={css.input} type="time" value={departure} onChange={e => setDeparture(e.target.value)} />
            <p className={css.tiny}>Departure is for input preview; seed estimates are fixed at {formatHkt(meta.snapshotAt)}.</p>
            <fieldset className={css.presets}><legend>WHAT MATTERS MOST?</legend>{PRESETS.map(option => <button key={option.id} type="button" aria-pressed={preset === option.id} className={preset === option.id ? css.activePreset : ''} onClick={() => setPreset(option.id)}>{option.label}</button>)}</fieldset>
            <button type="submit" className={css.primary}>Find resilient routes <span>↗</span></button>
          </form>
          <button type="button" className={css.textButton} onClick={() => { setNatural(true); setActiveField(null); setError('') }}>Describe in your own words →</button>
          <p className={css.tiny}>Only Tai Wai → Admiralty has route candidates in this M0 fixture.</p>
        </>}
      </div>}
      {screen === 'results' && <>
        {published[0] && <div className={css.alert}><span>!</span><strong>East Rail cross-harbour service affected</strong><span className={css.alertDetail}>Published simulated scenario · {formatHkt(published[0].updated_at)}</span><button type="button" onClick={() => setScreen('updates')}>View update →</button></div>}
        <section className={`${css.panel} ${css.results}`} aria-labelledby="routes-heading">
          <button type="button" className={css.back} onClick={() => setScreen('journey')}>← Edit journey</button>
          <span className={css.kicker}>ROUTES FOR YOUR JOURNEY</span>
          <h1 id="routes-heading">{nodes.get(origin)?.name_en ?? origin} <span>→</span><br />{nodes.get(destination)?.name_en ?? destination}</h1>
          <p className={css.subhead}>Three alternatives · {PRESETS.find(option => option.id === preset)?.label} · fixed seed snapshot</p>
          {routes.length ? <div className={css.routeList}>{routes.map((route, index) => <RouteCard key={route.route_id} route={route} letter={'ABC'[index]} network={network} selected={route.route_id === selectedId} onSelect={() => setSelectedId(route.route_id)} onDetail={() => { setSelectedId(route.route_id); setScreen('detail') }} />)}</div> : <div className={css.empty}><strong>No seed route for this pair.</strong><p>Only Tai Wai → Admiralty is modelled. Edit the journey to inspect the demonstration.</p></div>}
          <p className={css.tiny}>Illustrative, not a live journey query. Published events alone affect the network overlay. Times, fares and scores are derived estimates.</p>
        </section>
        <div className={css.mapLegend}>● Selected route &nbsp; ┄ Closed segment &nbsp; ○ {network.meta.catchment_m} m access</div>
      </>}
      {screen === 'updates' && <section className={`${css.panel} ${css.widePanel}`}>
        <button type="button" className={css.back} onClick={() => setScreen('journey')}>← Back to journey</button>
        <span className={css.kicker}>SCENARIO SNAPSHOT · {formatHkt(meta.snapshotAt)}</span><h1>What we know.</h1>
        <p className={css.subhead}>Three stages of one simulated incident. Pending reports do not change routes or the map.</p>
        <div className={css.eventGrid}>{events.map(event => <EventCard key={event.event_id} event={event} signals={signals} network={network} />)}</div>
      </section>}
      {screen === 'detail' && selected && <section className={`${css.panel} ${css.detailPanel}`}>
        <button type="button" className={css.back} onClick={() => setScreen('results')}>← All routes</button><span className={css.kicker}>ROUTE DETAILS · DERIVED ESTIMATE</span>
        <h1>{nodes.get(origin)?.name_en} <span>→</span><br />{nodes.get(destination)?.name_en}</h1>
        <div className={css.detailStats}><strong>{formatRange(selected.total.time_range_s)}</strong><span>{selected.total.transfers} transfer{selected.total.transfers === 1 ? '' : 's'}</span><span>{selected.total.walk_m} m walk</span><span>HK${selected.total.fare_hkd.toFixed(2)}</span></div>
        <h2>Step by step</h2><ol className={css.steps}>{selected.legs.map((leg, i) => <li key={i}><strong>{leg.mode === 'WALK' ? 'Walk' : network.lines.find(line => line.id === leg.line)?.name_en ?? leg.line ?? leg.mode}</strong><span>{nodes.get(leg.from)?.name_en ?? leg.from} → {nodes.get(leg.to)?.name_en ?? leg.to}</span><small>About {Math.round(leg.travel_s / 60)} min{leg.walk_m ? ` · ${leg.walk_m} m walking` : ''}</small></li>)}</ol>
        <h2>Why this route?</h2><p>{selected.explain}</p>
        {selected.warnings.length > 0 && <div className={css.warning}><strong>Check before travel</strong>{selected.warnings.map(warning => <p key={warning}>{warning}</p>)}</div>}
        {selected.score_breakdown && <div className={css.breakdown}><h2>Seed score factors</h2>{selected.score_breakdown.map(factor => <div key={factor.criterion}><span>{factor.criterion}</span><span>weight {Math.round(factor.weight * 100)}% · contribution {factor.contribution.toFixed(3)}</span></div>)}</div>}
        <ProvenanceBadge value={selected.provenance} /><p className={css.tiny}>Source: routes.seed.json · {formatHkt(meta.snapshotAt)} · {meta.disclaimer}</p>
      </section>}
      {screen === 'sources' && <section className={`${css.panel} ${css.sourcesPanel}`}>
        <button type="button" className={css.back} onClick={() => setScreen('journey')}>← Back to journey</button><span className={css.kicker}>HOW THIS DEMO WORKS</span><h1>Clarity before certainty.</h1>
        <p>Network, event, route and simulation seeds load through a shared data-source boundary. The map displays modelled nodes, schematic links, and only effective published events. Unreviewed reports remain visible on the Updates screen but do not modify routing.</p>
        <p>Route choices are fixed Tai Wai → Admiralty seed candidates. Station-search, map selection and departure input are interface demonstrations, not live timetable, geocoding or accessibility verification.</p>
        <p><strong>Snapshot:</strong> {formatHkt(meta.snapshotAt)} · <strong>Network:</strong> {network.meta.version} · <strong>Access radius:</strong> {network.meta.catchment_m} m straight-line.</p>
        <p>{meta.disclaimer}</p>
      </section>}
    </main>
  </div>
}
