import type { Event, Network, Signal } from '../api/types'
import { formatHkt, nodeIndex } from '../data'
import { ProvenanceBadge } from './ProvenanceBadge'
import { CardDisclosure, EventSources } from './Disclosures'
import css from '../App.module.css'

/**
 * Standalone Updates page (left pane; the map docks as a card on the right).
 * Plain migration of the former in-map updates panel.
 */
export interface UpdatesPageProps {
  events: Event[]
  signals: Signal[]
  network: Network
  seedMode: boolean
  snapshotAt: string
  onOpenReview: () => void
  onBack: () => void
}

function EventCard({ event, signals, network, seedMode }: { event: Event; signals: Signal[]; network: Network; seedMode: boolean }) {
  const nodes = nodeIndex(network)
  const evidence = signals.filter(signal => event.signals.includes(signal.signal_id))
  return <article data-enter className={css.eventCard}>
    <div className={css.eventTop}><span className={event.status === 'published' ? css.published : css.pending}>{event.status === 'published' ? '● Published' : event.status.replaceAll('_', ' ')}</span><span>{Math.round(event.confidence * 100)}% confidence</span></div>
    <h3>{event.title}</h3><p>{event.summary}</p>
    <p className={css.segment}>{event.affected_segments.map(segment => `${nodes.get(segment.from_node)?.name_en ?? segment.from_node} → ${nodes.get(segment.to_node)?.name_en ?? segment.to_node}`).join(' · ')}</p>
    <div className={css.track}><span style={{ width: `${event.confidence * 100}%` }} /></div>
    <div className={css.eventMeta}><span>{event.signals.length} signals · Severity {event.severity}</span><span>{formatHkt(event.updated_at)}</span></div>
    <ProvenanceBadge value={event.provenance} />
    <EventSources event={event} signals={signals} />
    <p>Confidence is this system's evidence score, not a probability or official confirmation.</p>
    {event.audit_log?.length ? <details><summary>Confidence history</summary><ol>{event.audit_log.map((entry, index) => <li key={index}>{formatHkt(entry.at)} · {entry.action} · {entry.actor}{entry.confidence_after !== undefined ? ` · ${Math.round(entry.confidence_after * 100)}%` : ''}</li>)}</ol></details> : null}
    {event.confidence_factors?.length ? <details><summary>Confidence factors</summary>{event.confidence_factors.map(factor => <p key={factor.factor}>{factor.factor}: {Math.round(factor.score * 100)}% · weight {Math.round(factor.weight * 100)}% · {factor.note}</p>)}</details> : null}
    <details><summary>Evidence &amp; effect</summary><p>{event.status === 'published' ? 'This published state alone changes the map.' : 'Unreviewed; does not change the map or routing.'}</p><ul>{evidence.map(signal => <li key={signal.signal_id}>{signal.source_type}: {signal.source_name}</li>)}</ul>{evidence.length < event.signals.length && <p>Some referenced signals lack a separate record in this fixture.</p>}</details>
    <CardDisclosure seedMode={seedMode} />
  </article>
}

export function UpdatesPage({ events, signals, network, seedMode, snapshotAt, onOpenReview, onBack }: UpdatesPageProps) {
  return <section data-panel className={`${css.panel} ${css.widePanel} ${css.pagePanel}`}>
    <button type="button" className={css.back} onClick={onBack}>← Back to journey</button>
    <span className={css.kicker}>{seedMode ? 'SCENARIO SNAPSHOT' : 'API GENERATED AT'} · {formatHkt(snapshotAt)}</span><h1>What we know.</h1>
    <p className={css.subhead}>{seedMode ? 'Three stages of one simulated incident.' : 'Events and confidence supplied by the API.'} Pending reports do not change routes or the map.</p>
    <ol className={css.timeline} aria-label="Confidence timeline">{events.map((event, index) => <li data-enter key={event.event_id}><span>{String(index + 1).padStart(2, '0')} · {formatHkt(event.updated_at)}</span><strong>{Math.round(event.confidence * 100)}<small>%</small></strong><p>{seedMode ? (index === 0 ? 'First report' : index === 1 ? 'Corroborating signals' : 'Official demo evidence') : event.title}<span className={css.timelineStatus} data-status={event.status}>{event.status.replaceAll('_', ' ')}</span></p><div><i data-confidence style={{ width: `${event.confidence * 100}%` }} /></div></li>)}</ol>
    <button type="button" className={css.reviewLink} onClick={onOpenReview}>Open the review desk →</button>
    <div className={css.eventGrid}>{events.map(event => <EventCard key={event.event_id} event={event} signals={signals} network={network} seedMode={seedMode} />)}</div>
  </section>
}
