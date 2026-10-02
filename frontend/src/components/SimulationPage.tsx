import { useCallback, useEffect, useRef, useState } from 'react'
import { delayOutcome, simulation, type Simulation } from '../api/p3Api'
import { LatestRequest } from '../api/p3Context'
import { formatHktTime } from '../lib/formatters'
import { ProvenanceBadge } from './ProvenanceBadge'
import css from './P3.module.css'

export function SimulationPage({ active, seedMode, onBack }: { active: boolean; seedMode: boolean; onBack: () => void }) {
  const [scenario, setScenario] = useState('scn_huh_exc_closed_am_peak'), [value, setValue] = useState<Simulation | null>(null)
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const latest = useRef(new LatestRequest())
  const needsRefresh = useRef(false)
  const run = useCallback(async () => {
    if (seedMode) return
    const request = latest.current.begin(); setBusy(true); setError('')
    try { const next = await simulation(scenario, request.signal); if (request.current()) { setValue(next); needsRefresh.current = false } }
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
  return <section className={css.page} data-panel aria-labelledby="simulation-heading">
    <button type="button" onClick={onBack}>← Station planner</button><h1 id="simulation-heading">Where the capacity ends.</h1>
    <p>Baseline and guided results, exactly as calculated by the backend. No live passenger measurement is implied.</p>
    <p className={css.notice}>The default is the repository's older M0 demonstration. A P3 scenario and allocation definitions await C confirmation. The M2 scenario currently has an API filename mismatch; it is never substituted silently.</p>
    {seedMode ? <p>Simulation API is unavailable in fixed seed mode. Switch to API mode; no placeholder numbers are shown here.</p> : <div className={css.actions}>
      <label>Scenario id supplied by C<input aria-label="Simulation scenario id" value={scenario} maxLength={128} onChange={event => { latest.current.cancel(); setBusy(false); setScenario(event.target.value) }} /></label>
      <button type="button" disabled={busy} onClick={() => void run()}>{busy ? 'Loading result…' : 'Load precomputed result'}</button>
      {busy && <button type="button" onClick={() => { latest.current.cancel(); setBusy(false); setError('Cancelled. Previous result retained.') }}>Cancel</button>}
    </div>}
    {error && <p className={css.error} role="alert">{error}</p>}
    {value && <div data-simulation-id={value.scenario_id}>
      {(error || scenario !== value.scenario_id) && <p className={css.notice}>Previous result retained — data may be stale. Displayed scenario: {value.scenario_id}; requested scenario: {scenario}.</p>}
      <p className={css.context}>PRECOMPUTED · <ProvenanceBadge value={value.provenance} /> · {value.scenario_id}<br />Population: {value.population.toLocaleString('en-HK')} simulated people · scenario window {value.time_range.join('–')}{value.window_min !== undefined ? ` (${value.window_min} min)` : ''}<br />Generated: {value.generated_at ? formatHktTime(value.generated_at) : 'not supplied — age unknown'} · route query time: {value.query_time ? formatHktTime(value.query_time) : 'not supplied'}</p>
      <p className={css.notice}>{delayOutcome(value)}{value.delta?.delay_reduction_pct !== undefined && ` Backend delay reduction: ${value.delta.delay_reduction_pct}%.`}</p>
      <div className={css.columns}>{(['baseline', 'guided'] as const).map(strategy => <article key={strategy} className={css.card}>
        <h2>{strategy === 'baseline' ? 'Baseline · no guidance' : 'Guided · capacity allocation'}</h2><p>Backend policy: {value[strategy].policy}</p>
        <dl className={css.metrics}><div><dt>Total delay · person-minutes</dt><dd>{value[strategy].total_delay_person_min.toLocaleString('en-HK')}</dd></div><div><dt>Average delay · min</dt><dd>{value[strategy].avg_delay_min}</dd></div><div><dt>P95 waiting · min</dt><dd>{value[strategy].p95_wait_min}</dd></div><div><dt>Overloaded routes</dt><dd>{value[strategy].overloaded_routes}</dd></div></dl>
        <div className={css.bar} aria-label={`${strategy} total delay ${value[strategy].total_delay_person_min} person-minutes`}><span>Total delay</span><div className={css.barTrack}><i style={{ width: `${Math.max(value.baseline.total_delay_person_min, value.guided.total_delay_person_min) ? value[strategy].total_delay_person_min / Math.max(value.baseline.total_delay_person_min, value.guided.total_delay_person_min) * 100 : 0}%` }} /></div></div>
        {value[strategy].route_load && <details><summary>Backend route loads</summary><div className={css.tableWrap}><table><thead><tr><th>Route</th><th>Users</th><th>Capacity/hour</th><th>Load factor</th><th>Overload</th></tr></thead><tbody>{value[strategy].route_load!.map(row => <tr key={row.route_id}><td>{row.route_id}</td><td>{row.users}</td><td>{row.capacity_per_hour}</td><td>{row.load_factor}</td><td>{row.overloaded ? 'Yes' : 'No'}</td></tr>)}</tbody></table></div></details>}
      </article>)}</div>
      <article className={css.card}><h2>Capacity gap & allocation</h2><p><strong>{value.guided.unstoppable_demand === undefined ? 'Capacity gap not supplied' : `Capacity gap (backend output): ${value.guided.unstoppable_demand.toLocaleString('en-HK')}`}</strong></p><p>Gap unit and accounting await C confirmation for P3. This precomputed output is not observed passenger flow or a live operational forecast.</p>
        {value.guided.shares ? value.guided.shares.map(row => <div key={row.route_id} className={css.bar}><span><b>{row.route_id}</b><span>{(row.share * 100).toFixed(2)}% · {row.users} people</span></span><div className={css.barTrack}><i style={{ width: `${row.share * 100}%` }} /></div></div>) : <p>Allocation proportions not supplied. No percentages have been calculated from another field.</p>}
        <p>Allocation denominator and capacity-gap unit require C confirmation; shares are displayed verbatim and are not renormalized to conceal unassigned demand.</p>
      </article>
      <h2>Assumptions</h2><ul>{value.assumptions.map((text, index) => <li key={index}>{text}</li>)}</ul>
      <p className={css.footer}>Source: /api/sim/result · generation and scenario times above. Precomputed simulation; not official travel advice. All demand and operational assumptions must be checked before real-world use.</p>
    </div>}
  </section>
}
