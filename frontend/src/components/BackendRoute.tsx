import type { RouteCandidate } from '../api/types'
import { formatRange } from '../data'
import { ProvenanceBadge } from './ProvenanceBadge'
import css from './P3.module.css'

export function BackendRoute({ route }: { route: RouteCandidate }) {
  return <section className={css.summary} data-backend-route={route.route_id}>
    <strong>{route.label}</strong>
    <p>{formatRange(route.total.time_range_s)} · {route.total.walk_m} m walk · {route.total.transfers} transfers · HK${route.total.fare_hkd.toFixed(2)}</p>
    <ProvenanceBadge value={route.provenance} />
    <div className={css.factors}>{route.score_breakdown?.map(row => <div className={css.factor} key={row.criterion}>{row.criterion} · {(row.weight * 100).toFixed(0)}% weight · contribution {row.contribution.toFixed(3)}<div><i style={{ width: `${Math.max(0, Math.min(100, row.weight * 100))}%` }} /></div></div>)}</div>
    <p>{route.explain}</p>
    {route.notes.map((text, index) => <p key={`n${index}`}>{text}</p>)}
    {route.warnings.length > 0 && <details><summary>Backend warnings ({route.warnings.length})</summary>{route.warnings.map((text, index) => <p key={index}>{text}</p>)}</details>}
    <details><summary>Inspect backend route steps</summary><ol>{route.legs.map((leg, index) => <li key={index}>{leg.mode} {leg.line ?? ''}: {leg.from} → {leg.to} · {leg.walk_m} m walking · accessibility: {String(leg.accessible)}</li>)}</ol></details>
    <p>Source: deterministic route engine · source age at query {route.total.freshness_s}s. Modelled accessibility; verify current lift and service conditions.</p>
  </section>
}
