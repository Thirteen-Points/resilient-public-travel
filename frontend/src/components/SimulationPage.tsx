import { useCallback, useEffect, useRef, useState } from 'react'
import { allocationRows, delayOutcome, P3_SCENARIOS, simulation, type Simulation } from '../api/p3Api'
import { LatestRequest } from '../api/p3Context'
import { formatHktTime } from '../lib/formatters'
import { ProvenanceBadge } from './ProvenanceBadge'
import css from './P3.module.css'

const count = (value: number | undefined) => value === undefined ? 'Not supplied' : value.toLocaleString('en-HK')

export function SimulationPage({ active, seedMode, onBack }: { active: boolean; seedMode: boolean; onBack: () => void }) {
  const [scenario, setScenario] = useState<string>(P3_SCENARIOS[0].id), [value, setValue] = useState<Simulation | null>(null)
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [readAt, setReadAt] = useState('')
  const latest = useRef(new LatestRequest()), needsRefresh = useRef(false)
  const run = useCallback(async () => {
    if (seedMode) return
    const request = latest.current.begin(); setBusy(true); setError('')
    try { const next = await simulation(scenario, request.signal); if (request.current()) { setValue(next); setReadAt(new Date().toISOString()); needsRefresh.current = false } }
    catch (cause) { if (request.current()) setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { if (request.current()) setBusy(false) }
  }, [scenario, seedMode])
  useEffect(() => {
    if (seedMode) return
    const online = () => { if (active) void run() }
    const offline = () => { needsRefresh.current = true; latest.current.cancel(); setBusy(false); setError('Offline. Previous simulation retained; data may be stale.') }
    if (!navigator.onLine) offline()
    else if (active && needsRefresh.current) void run()
    window.addEventListener('online', online); window.addEventListener('offline', offline)
    return () => { latest.current.cancel(); setBusy(false); window.removeEventListener('online', online); window.removeEventListener('offline', offline) }
  }, [active, run, seedMode])
  const choose = (id: string) => { latest.current.cancel(); setBusy(false); setScenario(id); setError('') }
  const allocations = value ? allocationRows(value) : null
  const stress = value?.scenario_id === P3_SCENARIOS[1].id
  const maxDelay = value ? Math.max(value.baseline.total_delay_person_min, value.guided.total_delay_person_min) : 0
  return <section className={css.page} data-panel aria-labelledby="simulation-heading">
    <button type="button" className={css.back} onClick={onBack}>← Station planner</button>
    <span className={css.kicker}>CAPACITY & GROUP GUIDANCE</span><h1 id="simulation-heading">Where the capacity ends.</h1>
    <p className={css.lead}>The same population, two strategies. Explore what guidance changes and what it cannot solve.</p>
    {seedMode ? <p className={css.notice}>Simulation API is unavailable in fixed seed mode. Switch to API mode to read the precomputed results.</p> : <div className={css.scenarioControls}>
      <label>Scenario<select aria-label="Simulation scenario" value={P3_SCENARIOS.some(item => item.id === scenario) ? scenario : ''} onChange={event => { if (event.target.value) choose(event.target.value) }}><option value="" disabled>Custom scenario</option>{P3_SCENARIOS.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
      <button type="button" disabled={busy} onClick={() => void run()}>{busy ? 'Loading result…' : 'Load precomputed result'}</button>
      {busy && <button type="button" onClick={() => { latest.current.cancel(); setBusy(false); setError('Cancelled. Previous result retained.') }}>Cancel simulation</button>}
      <details className={css.customScenario}><summary>Use another scenario id</summary><label>Scenario id<input aria-label="Simulation scenario id" value={scenario} maxLength={128} onChange={event => choose(event.target.value)} /></label></details>
    </div>}
    {error && <p className={css.error} role="alert">{error}</p>}
    {value && <div data-simulation-id={value.scenario_id}>
      {(error || scenario !== value.scenario_id) && <p className={css.notice}>Previous result retained — data may be stale. Displayed scenario: {value.scenario_id}; requested scenario: {scenario}.</p>}
      <div className={css.context}><div className={css.cardHeading}><strong>{P3_SCENARIOS.find(item => item.id === value.scenario_id)?.label ?? 'Custom precomputed scenario'}</strong><ProvenanceBadge value={value.provenance} /></div>
        <p>{count(value.population)} simulated people · {value.od_count === undefined ? 'OD count not supplied' : `${value.od_count} directed OD pairs`} · {value.time_range.join('–')}{value.window_min !== undefined ? ` (${value.window_min} min)` : ''} · seed {value.seed ?? 'not supplied'}</p>
        <p className={css.micro}>Generated: {value.generated_at ? formatHktTime(value.generated_at) : 'Not supplied — age unknown'} · Browser read: {formatHktTime(readAt)}{value.query_time ? ` · Route query: ${formatHktTime(value.query_time)}` : ''}</p>
      </div>
      {stress && <p className={css.notice}><strong>Sensitivity experiment:</strong> only 10% of modelled segment capacity remains available. This factor is a testing assumption, not measured occupancy.</p>}
      <p className={css.outcome}>{delayOutcome(value)}{value.delta?.delay_reduction_pct !== undefined && <strong> Backend delay change: {value.delta.delay_reduction_pct}% reduction.</strong>}</p>
      <div className={css.columns}>{(['baseline', 'guided'] as const).map(strategy => <article key={strategy} className={css.card} data-strategy={strategy}>
        <span className={css.kicker}>{strategy === 'baseline' ? '01 · INDIVIDUAL CHOICE' : '02 · CAPACITY-AWARE CHOICE'}</span><h2>{strategy === 'baseline' ? 'Without guidance' : 'With guidance'}</h2>
        <p className={css.heroNumber}>{count(value[strategy].total_delay_person_min)}<span>person-minutes of delay</span></p>
        <div className={css.barTrack} role="img" aria-label={`${strategy} delay ${value[strategy].total_delay_person_min} person-minutes; same scale for both strategies`}><i style={{ width: `${maxDelay ? value[strategy].total_delay_person_min / maxDelay * 100 : 0}%` }} /></div>
        <dl className={css.metrics}><div><dt>Average delay</dt><dd>{value[strategy].avg_delay_min} <small>min</small></dd></div><div><dt>P95 waiting</dt><dd>{value[strategy].p95_wait_min} <small>min</small></dd></div><div><dt>Served in the window</dt><dd>{count(value[strategy].served_demand)}</dd></div><div><dt>Overloaded routes / segments</dt><dd>{value[strategy].overloaded_routes} / {count(value[strategy].overloaded_shared_resources)}</dd></div></dl>
        <p className={css.micro}>Backend policy: {value[strategy].policy}</p>
      </article>)}</div>
      <article className={`${css.card} ${css.gapCard}`}><span className={css.kicker}>UNMET DEMAND STAYS VISIBLE</span><h2>People the model cannot serve.</h2>
        <div className={css.columns}>{(['baseline', 'guided'] as const).map(strategy => <div key={strategy}><h3>{strategy === 'baseline' ? 'Without guidance' : 'With guidance'}</h3><dl className={css.metrics}><div><dt>Not served</dt><dd>{count(value[strategy].unmet_demand)}</dd></div><div><dt>Not assigned a route</dt><dd>{count(value[strategy].unassigned_demand)}</dd></div></dl></div>)}</div>
        <p className={css.micro}>Counts are people within the {value.window_min === undefined ? 'scenario' : `${value.window_min}-minute simulated`} window. Not served and not assigned measure different outcomes.</p>
        <details><summary>Legacy capacity-gap field</summary><p>Backend unstoppable_demand: {count(value.guided.unstoppable_demand)}. In the P3 multi-OD model this counts unassigned demand; it is not a substitute for all unmet demand. Historical scenarios retain their original model definitions.</p></details>
      </article>
      <article className={css.card}><div className={css.cardHeading}><h2>Where people are assigned.</h2><span className={css.badge}>Denominator: {count(value.population)}</span></div>
        <p className={css.micro}>Derived from assigned_users ÷ all simulated demand. The five largest assignments, other routes and unassigned demand retain the full denominator.</p>
        {allocations ? allocations.map(row => <div key={row.label} className={css.bar}><span><b>{row.label}</b><span>{(row.share * 100).toFixed(2)}% · {count(row.users)} people</span></span><div className={css.barTrack} role="img" aria-label={`${row.label}: ${row.users} of ${value.population} people`}><i style={{ width: `${row.share * 100}%` }} /></div></div>) : <p className={css.notice}>Comparable assignment counts are missing or do not reconcile with total demand. Allocation percentages are withheld.</p>}
      </article>
      <details className={css.card}><summary>Inspect route and shared-segment loads</summary>
        {(['baseline', 'guided'] as const).map(strategy => <div key={strategy}><h3>{strategy === 'baseline' ? 'Without guidance' : 'With guidance'}</h3>
          {value[strategy].route_load ? <div className={css.tableWrap} tabIndex={0} role="region" aria-label={`${strategy} route load table`}><table><thead><tr><th>Route</th><th>Assigned</th><th>Users</th><th>Capacity/hour</th><th>Load factor</th><th>Overloaded</th></tr></thead><tbody>{value[strategy].route_load!.map(row => <tr key={row.route_id}><td>{row.route_id}</td><td>{count(row.assigned_users)}</td><td>{count(row.users)}</td><td>{count(row.capacity_per_hour)}</td><td>{row.load_factor}</td><td>{row.overloaded ? 'Yes' : 'No'}</td></tr>)}</tbody></table></div> : <p>Route loads not supplied.</p>}
          {value[strategy].resource_load ? <div className={css.tableWrap} tabIndex={0} role="region" aria-label={`${strategy} shared segment table`}><table><thead><tr><th>Directed resource</th><th>Assigned</th><th>Physical capacity/window</th><th>Target capacity/window</th><th>Physical excess</th></tr></thead><tbody>{value[strategy].resource_load!.map(row => <tr key={row.resource_id}><td>{row.resource_id}</td><td>{row.assigned_users}</td><td>{row.physical_capacity}</td><td>{row.target_capacity}</td><td>{row.physical_capacity_excess}</td></tr>)}</tbody></table></div> : <p>Shared-segment loads not supplied.</p>}
        </div>)}
      </details>
      <h2>Model & fairness boundaries</h2><p>{value.capacity_model?.note ?? 'Detailed capacity model not supplied.'}</p>
      {value.fairness && <p className={css.context}>Guided accessibility violations: {count(value.fairness.guided_accessibility_violations)} · fairness violations: {count(value.fairness.guided_fairness_violations)}.<br />{value.fairness.max_extra_delay_min !== undefined && `The ${value.fairness.max_extra_delay_min}-minute limit covers extra route travel; queueing and unserved demand are not guaranteed within that limit.`}</p>}
      <h3>Assumptions</h3><ul>{value.assumptions.map((text, index) => <li key={index}>{text}</li>)}</ul>
      <p className={css.footer}>Source: /api/sim/result · precomputed simulated results. No live passenger measurement, operational forecast or accessibility guarantee is implied.</p>
    </div>}
  </section>
}
