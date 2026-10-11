import type { RouteCandidate } from '../api/types'
import { formatRange } from '../data'
import { ProvenanceBadge } from './ProvenanceBadge'
import css from './P3.module.css'

export function BackendRoute({ route }: { route: RouteCandidate }) {
  return <section className={css.summary} data-backend-route={route.route_id}>
    <strong>{route.label}</strong>
    <p className={css.routeTime}>{formatRange(route.total.time_range_s)}</p>
    <dl className={css.metrics}><div><dt>Walking</dt><dd>{route.total.walk_m} <small>m</small></dd></div><div><dt>Transfers</dt><dd>{route.total.transfers}</dd></div><div><dt>Fare estimate</dt><dd>HK${route.total.fare_hkd.toFixed(2)}</dd></div><div><dt>Engine score</dt><dd>{Math.round(route.score * 100)}<small> /100</small></dd></div></dl>
    <ProvenanceBadge value={route.provenance} />
    <details open><summary>What shapes this recommendation</summary><div className={css.factors}>{route.score_breakdown?.length ? route.score_breakdown.map(row => <div className={css.factor} key={row.criterion}><span>{row.criterion}</span><span>{(row.weight * 100).toFixed(0)}% weight · {row.contribution.toFixed(3)} contribution</span><div><i style={{ width: `${Math.max(0, Math.min(100, row.weight * 100))}%` }} /></div></div>) : <p>Score factors not supplied.</p>}</div></details>
    <p>{route.explain}</p>
    {route.notes.map((text, index) => <p key={`n${index}`}>{text}</p>)}
    {route.warnings.length > 0 && <div className={css.notice}><strong>Check before travelling</strong><p>{route.warnings[0]}</p>{route.warnings.length > 1 && <details><summary>More backend warnings ({route.warnings.length - 1})</summary>{route.warnings.slice(1).map((text, index) => <p key={index}>{text}</p>)}</details>}</div>}
    <details><summary>Inspect backend route steps</summary><ol>{route.legs.map((leg, index) => <li key={index}>{leg.mode} {leg.line ?? ''}: {leg.from} → {leg.to} · {leg.walk_m} m walking · accessibility: {String(leg.accessible)}</li>)}</ol></details>
    <p>Source: deterministic route engine · source age at query {route.total.freshness_s}s. Modelled accessibility; verify current lift and service conditions.</p>
  </section>
}
