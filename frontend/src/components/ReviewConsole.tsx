import { useEffect, useRef, useState } from 'react'
import type { Event, Network, Signal } from '../api/types'
import { formatHkt } from '../data'
import css from './Experience.module.css'

export type ReviewLog = { id: string; action: string; detail: string }
type Props = { live?: boolean; events: Event[]; signals: Signal[]; network: Network; logs: ReviewLog[]; onSave: (event: Event, action: 'edit' | 'publish' | 'reject', reason?: string) => void | Promise<void>; onReplay: () => void }

export function ReviewConsole({ events, signals, network, logs, onSave, onReplay, live = false }: Props) {
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [id, setId] = useState(events.at(-1)?.event_id ?? '')
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<Event | null>(null)
  const [confirm, setConfirm] = useState<'publish' | 'reject' | 'discard' | null>(null)
  const [nextId, setNextId] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<'edit' | 'publish' | 'reject' | null>(null)
  const saving = useRef(false)
  const dialog = useRef<HTMLDialogElement>(null)
  const form = useRef<HTMLFormElement>(null)
  const queue = useRef<HTMLDivElement>(null)
  const current = events.find(event => event.event_id === id)
  const item = editing && draft ? draft : current
  const filtered = events.filter(event => (filter === 'all' || event.status === filter) && `${event.title} ${event.event_id}`.toLowerCase().includes(query.toLowerCase()))
  useEffect(() => {
    if (!confirm) return
    const previous = document.activeElement as HTMLElement | null
    dialog.current?.showModal()
    return () => { dialog.current?.close(); previous?.focus() }
  }, [confirm])
  useEffect(() => {
    if (!busy && !editing && !events.some(event => event.event_id === id)) setId(events.at(-1)?.event_id ?? '')
  }, [events, id, busy, editing])
  const choose = (value: string) => {
    if (busy || value === id) return
    if (editing) { setNextId(value); setConfirm('discard'); return }
    setId(value); setError(''); setReason('')
  }
  const update = (values: Partial<Event>) => setDraft(previous => previous ? { ...previous, ...values } : previous)
  const valid = () => {
    if (!item || !form.current?.reportValidity()) return false
    if (!item.title.trim() || !item.summary.trim()) { setError('Title and summary cannot be blank.'); return false }
    if (!item.affected_segments.length || item.affected_segments.some(segment => segment.from_node === segment.to_node)) { setError('Each affected segment needs two different modelled stops.'); return false }
    if (item.window.end && Date.parse(item.window.end) <= Date.parse(item.window.start)) { setError('The end of the event must be after its start.'); return false }
    setError(''); return true
  }
  const finish = async (action: 'edit' | 'publish' | 'reject') => {
    if (!item || saving.current) return
    if (action === 'reject' && !reason.trim()) return
    saving.current = true
    setBusy(action)
    setError('')
    try {
      await onSave(action === 'reject' ? current! : item, action, reason.trim())
      setEditing(false); setDraft(null); setConfirm(null); setReason('')
    } catch (cause) {
      setConfirm(null)
      setError(`The review could not be confirmed. Your edits and reason are kept. Refresh the event before retrying. ${cause instanceof Error ? cause.message : String(cause)}`)
    } finally {
      saving.current = false
      setBusy(null)
    }
  }
  const nodeName = (value: string) => network.nodes.find(node => node.id === value)?.name_en ?? value
  return <section className={css.reviewPanel} data-panel aria-labelledby="review-heading">
    <header className={css.reviewHeader}><div><span className={css.eyebrow}>HUMAN REVIEW · {live ? 'API' : 'LOCAL DEMO'}</span><h1 id="review-heading">A clearer signal.</h1><p>{live ? 'Server events and evidence. Published events affect the modelled network.' : 'One incident, three seed stages. Only the current published state changes the map.'}</p></div><button className={css.secondary} type="button" disabled={editing || busy !== null} onClick={() => { onReplay(); setFilter('all'); setQuery(''); setId(events.at(-1)?.event_id ?? ''); setReason('') }}>{live ? 'Refresh events ↻' : 'Replay review scenario ↺'}</button></header>
    <div className={css.reviewLayout}>
      <aside className={css.queue}><div className={css.queueTitle}><strong>Review queue</strong><span>{filtered.length.toString().padStart(2, '0')}</span></div><label className={css.srOnly} htmlFor="review-search">Search queue</label><input id="review-search" placeholder="Search title or ID" value={query} onChange={e => setQuery(e.target.value)} /><label className={css.srOnly} htmlFor="review-filter">Filter queue</label><select id="review-filter" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All stages</option><option value="pending_review">Awaiting review</option><option value="published">Published</option><option value="rejected">Rejected</option><option value="updated">Superseded</option></select>
        <div ref={queue} className={css.queueItems} onKeyDown={e => {
          if (busy || !['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key) || !filtered.length) return
          e.preventDefault()
          const buttons = Array.from(queue.current!.querySelectorAll<HTMLButtonElement>('button'))
          const index = buttons.indexOf(document.activeElement as HTMLButtonElement)
          const next = e.key === 'Home' ? 0 : e.key === 'End' ? buttons.length - 1 : Math.max(0, Math.min(buttons.length - 1, index + (e.key === 'ArrowDown' ? 1 : -1)))
          buttons[next]?.focus(); choose(filtered[next].event_id)
        }}>{filtered.map(event => <button data-enter key={event.event_id} type="button" aria-pressed={id === event.event_id} onClick={() => choose(event.event_id)}><span className={css.eyebrow}>STAGE {event.version} <b>{Math.round(event.confidence * 100)}%</b></span><strong>{event.title}</strong><span className={css.statusTag}>{event.status.replaceAll('_', ' ')}</span></button>)}</div>
        {!filtered.length && <p className={css.micro}>No matching records. Change the filter to see other stages.</p>}<p className={css.micro}>↑ / ↓ or Home / End to navigate the queue. Selection remains visible while filtering.</p>
      </aside>
      {item && <div className={css.reviewWork}>
        <div className={css.recordHeader}><span className={css.eyebrow}>{item.event_id} · STAGE {item.version} · {item.provenance}</span><span className={css.statusTag}>{item.status.replaceAll('_', ' ')}</span></div>
        <div className={css.evidenceColumns}>
          <section className={css.evidence}><h2>Original evidence <span>{item.signals.length}</span></h2>{item.signals.map(signalId => {
            const signal = signals.find(value => value.signal_id === signalId)
            return <article key={signalId}><span className={css.eyebrow}>{signal?.source_type ?? 'MISSING RECORD'} · {signalId}</span><h3>{signal?.source_name ?? 'Referenced evidence unavailable'}</h3><p lang="zh-Hant">{signal?.raw_text ?? 'This seed references a signal without supplying its original text. No text has been inferred.'}</p>{signal && <small>{formatHkt(signal.received_at)} · {signal.provenance}</small>}</article>
          })}</section>
          <form ref={form} className={css.structured} onSubmit={e => { e.preventDefault(); if (valid()) finish('edit') }}><div className={css.sectionTitle}><h2>Structured event</h2>{!editing && ['pending_review', 'draft'].includes(item.status) && <button type="button" className={css.textButton} onClick={() => { setDraft(structuredClone(item)); setEditing(true) }}>Edit fields ↗</button>}</div>
            <fieldset disabled={!editing || busy !== null}><label>Title<input required maxLength={240} value={item.title} onChange={e => update({ title: e.target.value })} /></label><label>Summary<textarea required rows={4} maxLength={1600} value={item.summary} onChange={e => update({ summary: e.target.value })} /></label><div className={css.fieldPair}><label>Line<select value={item.line} onChange={e => update({ line: e.target.value })}>{network.lines.map(line => <option key={line.id} value={line.id}>{line.name_en}</option>)}</select></label><label>Severity (1–5)<input type="number" min="1" max="5" required value={item.severity} onChange={e => update({ severity: Number(e.target.value) })} /></label></div></fieldset>
            <div className={css.confidence}><span>Confidence <strong>{Math.round(item.confidence * 100)}%</strong></span><meter min="0" max="1" value={item.confidence} /><small>Evidence score · publication requires ≥ 60%. Editing text does not increase confidence.</small></div>
            <fieldset disabled={!editing || busy !== null}><div className={css.fieldPair}><label>Start · HKT<input type="datetime-local" required value={item.window.start.slice(0, 16)} onChange={e => update({ window: { ...item.window, start: `${e.target.value}:00+08:00` } })} /></label><label>End · HKT<input type="datetime-local" value={item.window.end?.slice(0, 16) ?? ''} onChange={e => update({ window: { ...item.window, end: e.target.value ? `${e.target.value}:00+08:00` : null } })} /></label></div>
            <h3>Affected segments</h3>{item.affected_segments.map((segment, i) => <div key={i} className={css.segmentEdit}><div className={css.fieldPair}>{(['from_node', 'to_node'] as const).map(key => <label key={key}>{key === 'from_node' ? 'From' : 'To'}<select value={segment[key]} onChange={e => update({ affected_segments: item.affected_segments.map((value, j) => i === j ? { ...value, [key]: e.target.value } : value) })}>{network.nodes.map(node => <option key={node.id} value={node.id}>{node.name_en}</option>)}</select></label>)}</div><div className={css.fieldPair}><label>Impact<select value={segment.impact} onChange={e => update({ affected_segments: item.affected_segments.map((value, j) => i === j ? { ...value, impact: e.target.value, capacity_factor: e.target.value === 'closed' ? 0 : value.capacity_factor } : value) })}>{['closed', 'crowded', 'degraded', 'reduced_capacity', 'slow'].map(impact => <option key={impact}>{impact}</option>)}</select></label><label>Capacity factor<input type="number" required min="0" max="1" step="0.05" disabled={!editing || segment.impact === 'closed'} value={segment.capacity_factor} onChange={e => update({ affected_segments: item.affected_segments.map((value, j) => i === j ? { ...value, capacity_factor: Number(e.target.value) } : value) })} /></label></div></div>)}</fieldset>
            {editing && <div className={css.actions}><button type="submit" className={css.secondary} aria-busy={busy === 'edit'} disabled={busy !== null}>{busy === 'edit' ? 'Saving…' : 'Save draft'}</button><button type="button" className={css.textButton} disabled={busy !== null} onClick={() => { setEditing(false); setDraft(null); setError('') }}>Cancel edits</button></div>}
          </form>
        </div>
        {error && <p className={css.error} role="alert">{error}</p>}
        <footer className={css.reviewActions}><div><strong>{item.status === 'published' ? 'Published to this demo map' : 'Your decision is the final step.'}</strong><small>{live ? 'Saved by the event API · route refresh follows publication.' : 'Local session only · refresh restores the seed. Routes stay fixed.'}</small></div>{['pending_review', 'draft'].includes(item.status) && <div className={css.actions}><button type="button" className={css.secondary} aria-busy={busy === 'reject'} disabled={busy !== null} onClick={() => setConfirm('reject')}>{busy === 'reject' ? 'Rejecting…' : 'Reject'}</button><button type="button" className={css.primary} aria-busy={busy === 'publish'} disabled={busy !== null || (live && editing) || item.confidence < .6} title={item.confidence < .6 ? 'More evidence required: minimum confidence 60%' : undefined} onClick={() => { if (valid()) setConfirm('publish') }}>{busy === 'publish' ? 'Publishing…' : 'Publish →'}</button></div>}</footer>
        {item.confidence < .6 && <p className={css.micro}>This earlier stage is below the 60% publication threshold. Replay the scenario to review the latest 90% stage.</p>}
        <details className={css.audit}><summary>Local review history ({logs.length})</summary>{logs.length ? <ol>{logs.map((log, i) => <li key={i}><strong>{log.action} · {log.id}</strong><p>{log.detail}</p></li>)}</ol> : <p>No local actions yet.</p>}</details>
      </div>}
    </div>
    {confirm && <dialog ref={dialog} className={css.dialog} onCancel={event => { if (busy) event.preventDefault(); else setConfirm(null) }} aria-labelledby="review-dialog-title"><span className={css.eyebrow}>{live ? 'CONFIRM API REVIEW' : 'LOCAL DEMONSTRATION'}</span><h2 id="review-dialog-title">{confirm === 'publish' ? 'Publish this event?' : confirm === 'reject' ? 'Why reject this event?' : 'Discard unsaved edits?'}</h2>{confirm === 'publish' && item && <><p>{item.title}</p><ul>{item.affected_segments.map((segment, i) => <li key={i}>{nodeName(segment.from_node)} → {nodeName(segment.to_node)} · {segment.impact}</li>)}</ul><p>{formatHkt(item.window.start)} → {item.window.end ? formatHkt(item.window.end) : 'Open ended'}</p><p>{live ? 'Saves the review decision on the server. Published events and graph changes refresh the map and current route query.' : 'Confirms this scenario for the map at the seed snapshot. Any previous published stage is superseded. Fixed route estimates are unchanged.'}</p></>}{confirm === 'reject' && <label>Review reason<textarea autoFocus required maxLength={800} rows={4} value={reason} onChange={e => setReason(e.target.value)} placeholder="Explain the missing or conflicting evidence…" /></label>}{confirm === 'discard' && <p>Your unsaved field edits will be discarded when you select another record.</p>}<div className={css.actions}><button autoFocus={confirm !== 'reject'} type="button" className={css.secondary} disabled={busy !== null} onClick={() => setConfirm(null)}>Cancel</button><button type="button" className={css.primary} aria-busy={busy === confirm} disabled={busy !== null || (confirm === 'reject' && !reason.trim())} onClick={() => { if (confirm === 'discard') { setEditing(false); setDraft(null); setId(nextId); setReason(''); setConfirm(null) } else finish(confirm) }}>{busy ? 'Confirming…' : confirm === 'publish' ? 'Confirm publication' : confirm === 'reject' ? 'Confirm rejection' : 'Discard & continue'}</button></div></dialog>}
  </section>
}
