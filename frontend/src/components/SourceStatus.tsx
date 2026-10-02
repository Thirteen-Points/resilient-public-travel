import type { LiveMetaSourceStatus } from '../api/liveTransitApi'
import { sourceView } from '../api/p3Api'
import { formatHktTime } from '../lib/formatters'
import css from './P3.module.css'

export function SourceStatus({ sources, warning }: { sources?: Array<string | LiveMetaSourceStatus>; warning?: string }) {
  return <section aria-labelledby="source-status-heading"><h2 id="source-status-heading">Source freshness & collection</h2>
    {warning && <p role="alert" className={css.error}>Source metadata refresh failed. Previous metadata retained; data may be stale. {warning}</p>}
    <p>Last successful collection is distinct from API generation, event update and browser retrieval times.</p>
    <ul className={css.sourceList}>{(sources ?? []).map((source, index) => { const value = sourceView(source); return <li key={index}><strong>{value.name}</strong><p>Last successful update: {value.lastOk ? formatHktTime(value.lastOk) : 'not supplied'}</p><p>{value.status}</p><p>{value.classification}</p></li> })}</ul>
    {!sources?.length && <p>Public source metadata unavailable. Success is not inferred.</p>}
    <p className={css.notice}>B must publish sanitized source classification, last-success time and failed/partial/disabled states. Administrator-only collection records are not fetched from this public page.</p>
  </section>
}
