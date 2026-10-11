import { useCallback, useEffect, useRef, useState } from 'react'
import { compare, comparisonProfiles, type Comparison } from '../api/p3Api'
import { contextKey, LatestRequest } from '../api/p3Context'
import type { JourneyContext } from '../api/types'
import { formatHktTime } from '../lib/formatters'
import { BackendRoute } from './BackendRoute'
import css from './P3.module.css'

export function ComparePage({ active, seedMode, context, warning, onBack }: { active: boolean; seedMode: boolean; context: JourneyContext; warning: string; onBack: () => void }) {
  const [value, setValue] = useState<Comparison | null>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const latest = useRef(new LatestRequest())
  const key = contextKey(context)
  const run = useCallback(async () => {
    if (seedMode) return
    const request = latest.current.begin()
    setBusy(true); setError('')
    try {
      const next = await compare(context, request.signal)
      if (request.current()) setValue(next)
    } catch (cause) { if (request.current()) setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { if (request.current()) setBusy(false) }
  }, [context, seedMode])
  useEffect(() => { if (active && !seedMode) void run(); return () => latest.current.cancel() }, [active, key, run, seedMode])
  useEffect(() => {
    const online = () => { if (active) void run() }
    window.addEventListener('online', online)
    return () => window.removeEventListener('online', online)
  }, [active, run])
  const old = Boolean(value && (contextKey(value.context) !== key || error || warning))
  return <section className={css.page} data-panel aria-labelledby="compare-heading">
    <button type="button" onClick={onBack}>← Edit shared journey</button>
    <span className={css.kicker}>PROFILE COMPARISON</span>
    <h1 id="compare-heading">One journey. Two needs.</h1>
    <p>Commuter and wheelchair queries use the same requested stations, departure and event identifiers. The engine supplies every route and score.</p>
    <p className={css.context}>Requested: {context.origin} → {context.destination || 'choose a destination'} · {formatHktTime(context.departAt)} · approved revisions: {context.eventRevisions || 'none'}</p>
    <p className={css.micro}>These are fixed benchmark profiles; your free-text preferences remain in the planner and Agent.</p>
    {seedMode ? <p className={css.notice}>Fixed seed mode has no verified profile comparison. Switch to API mode to query the engine.</p> : <div className={css.actions}><button type="button" disabled={busy} onClick={() => void run()}>{busy ? 'Querying both profiles…' : 'Refresh both profiles'}</button>{busy && <button type="button" onClick={() => { latest.current.cancel(); setBusy(false); setError('Comparison cancelled; previous results retained.') }}>Cancel</button>}</div>}
    {error && <p role="alert" className={css.error}>{error}</p>}
    {old && <p className={css.notice}>Previous comparison retained — data may be stale. Displayed results use {value!.context.origin} → {value!.context.destination}, {formatHktTime(value!.context.departAt)} and revisions {value!.context.eventRevisions || 'none'}.</p>}
    {value && <>
      <p className={value.verified ? css.success : css.notice} role="status" data-comparison-verified={value.verified}>{value.verified ? `Same-condition comparison verified · calculation snapshot ${value.snapshotId}.` : 'Pair consistency: unverified. One or both responses omit the calculation snapshot; matching surrounding reads cannot prove identical conditions.'}</p>
      <details><summary>Calculation context</summary><p className={css.micro}>Surrounding graph read: {value.observedSnapshot}. Verified snapshot: {value.snapshotId ?? 'not supplied'}.</p></details>
      <div className={css.columns}>{(['commuter', 'wheelchair'] as const).map(persona => <article className={css.card} key={persona} data-profile={persona}>
        <span className={css.kicker}>{persona === 'commuter' ? '01 · TIME FIRST' : '02 · ACCESSIBILITY FIRST'}</span><h2>{persona === 'commuter' ? 'Time-focused commuter' : 'Wheelchair user'}</h2>
        <p>Preference: {comparisonProfiles[persona].preset.replaceAll('_', ' ')}</p>
        <p>Hard constraints: {persona === 'wheelchair' ? 'No stairs · no minibus · low-floor buses · walking ≤400 m · at most 2 transfers.' : 'Standard mobility; no additional accessibility restriction.'}</p>
        {value[persona][0] ? <BackendRoute route={value[persona][0]} /> : <p>No feasible route returned. No alternative has been added.</p>}
      </article>)}</div>
      <h2>Why the choices differ</h2>
      <p>{!value.commuter.length || !value.wheelchair.length ? 'One or both profiles have no feasible route. See the returned constraints and warnings.' : value.commuter[0].route_id === value.wheelchair[0].route_id ? 'The engine returned the same first choice for both profiles. No ranking was changed to manufacture a difference.' : `The engine returned different first choices. Its explanations and score contributions are shown in each column.${value.verified ? '' : ' Snapshot consistency is still unverified.'}`}</p>
    </>}
    <p className={css.footer}>Source: /api/routes/query · requested departure above; route source age appears per card. Academic estimates, not official travel or accessibility guarantees.</p>
  </section>
}
