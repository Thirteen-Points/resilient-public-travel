import type { LiveMetaSourceStatus } from '../api/liveTransitApi'
import { lastSuccessfulCollection, type SourcesStatus, type ReplanningStatus } from '../api/runtimeStatus'
import { formatHktTime } from '../lib/formatters'
import css from './P3.module.css'

const labels: Record<string, string> = { success: 'Success', partial: 'Partial result', partial_failure: 'Partial result · failed checks', failed: 'Collection failed', failure: 'Collection failed', error: 'Collection failed', disabled: 'Disabled', offline: 'Offline', waiting: 'Waiting', unconfigured: 'Not configured' }
export function SourceStatus({ sources, status, replanning, warning, statusWarning, replanWarning, readAt }: {
  sources?: Array<string | LiveMetaSourceStatus>; status?: SourcesStatus | null; replanning?: ReplanningStatus | null
  warning?: string; statusWarning?: string; replanWarning?: string; readAt?: string
}) {
  return <section className={css.page} aria-labelledby="source-status-heading">
    <span className={css.kicker}>PUBLIC OPERATIONS STATUS</span><h2 id="source-status-heading">Source freshness & collection</h2>
    <p>Collectors create unverified reports. Human approval is required before an event can change routes.</p>
    {statusWarning && <p role="alert" className={css.error}>Collection status refresh failed. Previous status retained; it may be stale. {statusWarning}</p>}
    {status && <><p className={css.context}>{status.offline ? 'External collection is offline.' : status.configured ? 'Source settings configured.' : 'Source settings not configured.'} {readAt && `Browser read: ${formatHktTime(readAt)}.`}</p>
      <div className={css.columns}>{Object.entries(status.sources).map(([name, source]) => {
        const success = lastSuccessfulCollection(source)
        return <article key={name} className={css.card} data-source={name}>
          <div className={css.cardHeading}><h3>{name === 'mtr' ? 'MTR · East Rail' : name === 'hko' ? 'Hong Kong Observatory' : name}</h3><span className={css.badge}>{labels[source.status] ?? `Unknown status: ${source.status}`}</span></div>
          <p>{source.collecting ? 'Collection in progress' : source.scheduled ? 'Scheduled collection enabled' : 'No scheduled collection running'}</p>
          <dl className={css.metrics}><div><dt>Last successful collection</dt><dd className={css.timeValue}>{success ? formatHktTime(success) : 'Not supplied'}</dd></div><div><dt>Latest attempt</dt><dd className={css.timeValue}>{source.last_attempt != null ? formatHktTime(new Date(source.last_attempt * 1000).toISOString()) : 'Not supplied'}</dd></div></dl>
          {source.last_success_at == null && <p className={css.micro}>{success ? 'Latest result was successful; earlier success history is unavailable.' : 'No persistent last-success time supplied. Attempt time is not used as a substitute.'}</p>}
          <p className={source.stale || statusWarning ? css.notice : css.micro}>{source.stale || statusWarning ? 'Data may be stale; verify current official announcements.' : 'Collector reports its data as fresh. This does not verify every report.'}</p>
          {source.last_result && <p className={css.micro}>Latest result: {source.last_result.added ?? 'unknown'} new reports · {source.last_result.duplicate ?? 'unknown'} duplicates · {source.last_result.failures ?? 'unknown'} failed checks</p>}
        </article>
      })}</div></>}
    {!status && <p className={css.notice}>Collection status unavailable. Success is not inferred from API availability.</p>}
    <h3>Replanning</h3>
    {replanWarning && <p role="alert" className={css.error}>Replanning status unavailable or stale. {replanWarning}</p>}
    {replanning ? <><p>{replanning.live_load_provider_installed ? 'Backend reports an installed load provider; its source still needs verification.' : 'No live passenger-load provider is installed. Manual load exercises are simulated.'}</p>
      {replanning.latest ? <div className={css.context}><p>Backend trigger: {replanning.latest.reason ?? replanning.latest.trigger}</p><p>{replanning.latest.should_replan ? 'Replanning requested' : 'Replanning not requested'} · {replanning.latest.recomputed ? 'recalculation completed' : 'no completed recalculation reported'}.</p><p className={css.micro}>{replanning.latest.occurred_at ? formatHktTime(replanning.latest.occurred_at) : 'Time not supplied'} · {replanning.latest.elapsed_ms.toFixed(0)} ms · {replanning.latest.within_five_second_budget ? 'within backend budget' : 'backend budget exceeded'}</p><p className={css.micro}>This is global backend activity; it does not prove when this browser finished rendering a route.</p></div> : <p>No replanning activity recorded.</p>}</> : <p>Replanning status not supplied.</p>}
    <details><summary>Repository data references</summary>{warning && <p role="alert">Metadata refresh failed; previous references may be stale. {warning}</p>}{sources?.length ? <ul>{sources.map((source, i) => <li key={i}>{typeof source === 'string' ? source : source.name}</li>)}</ul> : <p>No data references supplied.</p>}</details>
    <p className={css.footer}>Source: /api/sources/status and /api/replanning/status. Collection time, attempt time and browser read time have different meanings. Academic prototype; follow official travel advice.</p>
  </section>
}
