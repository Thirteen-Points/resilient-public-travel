import { useEffect, useState } from 'react'
import * as eventApi from '../api/eventApi'
import type { Network, Signal } from '../api/types'
import { formatHkt, hktLocalInput } from '../data'
import { capacityFactorForImpact, segmentsWithCapacity, validatePendingCard } from './reviewForm'
import css from './Experience.module.css'

export function SignalInbox({ network, onChanged, api = eventApi, onDirty }: { network: Network; onChanged: () => Promise<void>; api?: Pick<typeof eventApi, "getInbox" | "ingestSignal" | "createEvent">; onDirty?: (dirty: boolean) => void }) {
  const [signals, setSignals] = useState<Signal[]>([]), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const [candidate, setCandidate] = useState<{ signal: Signal; draft: eventApi.EventDraft } | null>(null)
  const [severity, setSeverity] = useState(''), [factors, setFactors] = useState<string[]>([])
  const [start, setStart] = useState(''), [end, setEnd] = useState('')
  const [notice, setNotice] = useState('')
  const [query, setQuery] = useState('')
  useEffect(() => { onDirty?.(Boolean(candidate)); return () => onDirty?.(false) }, [candidate, onDirty])
  const refresh = async () => {
    try { setSignals(await api.getInbox()); setError('') }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  useEffect(() => { void refresh() }, [])
  const updateDraft = (patch: Partial<eventApi.EventDraft>) => setCandidate(previous => previous ? { ...previous, draft: { ...previous.draft, ...patch } } : previous)
  return <section className={css.reviewPanel} aria-labelledby="inbox-heading">
    <div className={css.sectionTitle}><h2 id="inbox-heading">Unlinked reports</h2><button type="button" className={css.secondary} disabled={busy} onClick={() => void refresh()}>Refresh reports</button></div>
    <p>Receipt is unverified. Extract a draft or merge evidence into an existing card; publication remains a separate review decision.</p>
    <label>Search reports<input value={query} placeholder="Search evidence or source" onChange={e => setQuery(e.target.value)} /></label>
    {signals.filter(signal => `${signal.raw_text} ${signal.source_name}`.toLowerCase().includes(query.toLowerCase())).map(signal => <article className={css.evidence} key={signal.signal_id}><strong>{signal.source_name}</strong><p>{signal.raw_text}</p><small>{formatHkt(signal.received_at)} · {signal.provenance} channel · unverified</small><button type="button" className={css.secondary} disabled={busy} onClick={async () => {
      setBusy(true); setError(''); setNotice('')
      try {
        const result = await api.ingestSignal(signal.signal_id)
        setNotice(result.structure_method === "llm" ? `LLM extracted draft: ${result.llm_used?.name || "model"} · ${result.llm_used?.model || ""}` : `Rule extraction used. ${result.structure_errors?.join(" ") || "AI is disabled or no usable key is configured."}`)
        if (result.state === 'merged') { setCandidate(null); setNotice(`Evidence merged using ${result.structure_method === 'llm' ? `LLM ${result.llm_used?.name || ''}` : 'rule fallback'}. The server recalculated confidence; review is still required.`); await refresh(); try { await onChanged() } catch { setNotice('Saved successfully. The queue could not refresh; refresh it manually.') } }
        else { setCandidate({ signal, draft: result.draft }); setSeverity(''); setFactors(result.draft.affected_segments.map(() => '')); setStart(hktLocalInput(signal.received_at)); setEnd('') }
      } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
      finally { setBusy(false) }
    }}>Extract / merge</button></article>)}
    {!signals.length && <p>No unlinked reports. New public reports appear after refreshing.</p>}
    {candidate && <form className={css.structured} noValidate onSubmit={async event => {
      event.preventDefault(); if (busy) return
      const draft = candidate.draft
      const validation = validatePendingCard(draft, severity, start, end, factors)
      if (validation) { setError(validation); return }
      setBusy(true); setError('')
      const now = new Date().toISOString()
      try {
        await api.createEvent({
          ...draft, event_id: `evt_${crypto.randomUUID()}`, version: 1, status: 'pending_review',
          created_at: now, updated_at: now, published_at: null, expires_at: null,
          window: { start: `${start}:00+08:00`, end: end ? `${end}:00+08:00` : null, end_confidence: 'reviewer_supplied' },
          severity: Number(severity), affected_segments: segmentsWithCapacity(draft, factors),
          confidence: 0, confidence_factors: [], signals: [candidate.signal.signal_id], reviewed_by: null, audit_log: [], provenance: candidate.signal.provenance,
        })
        setCandidate(null); setNotice('Pending card created. Add corroborating evidence and review before publication.')
        await refresh(); try { await onChanged() } catch { setNotice('Saved successfully. The queue could not refresh; refresh it manually.') }
      } catch (cause) { setError(`Creation could not be confirmed. Refresh the queue before retrying. ${cause instanceof Error ? cause.message : String(cause)}`) }
      finally { setBusy(false) }
    }}>
      <h3>Confirm extracted draft</h3><p>Severity is reviewer supplied. Only reduced capacity needs a confirmed factor; other impacts use fixed factors. Extraction does not verify this report.</p>
      <fieldset disabled={busy}>
        <label>Title<input required value={candidate.draft.title} onChange={event => updateDraft({ title: event.target.value })} /></label>
        <label>Summary<textarea required value={candidate.draft.summary} onChange={event => updateDraft({ summary: event.target.value })} /></label>
        <div className={css.fieldPair}><label>Mode<select required value={candidate.draft.mode ?? ''} onChange={event => updateDraft({ mode: event.target.value })}><option value="">Choose mode</option>{['MTR', 'BUS', 'MINIBUS', 'FERRY', 'WALK'].map(value => <option key={value}>{value}</option>)}</select></label><label>Line<select required value={candidate.draft.line ?? ''} onChange={event => updateDraft({ line: event.target.value })}><option value="">Choose line</option>{network.lines.map(line => <option key={line.id} value={line.id}>{line.name_en}</option>)}</select></label></div>
        <label>Direction<select required value={candidate.draft.direction ?? ''} onChange={event => updateDraft({ direction: event.target.value })}><option value="">Choose direction</option>{['both', 'southbound', 'northbound', 'unknown'].map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Severity (1–5)<input required type="number" min="1" max="5" value={severity} onChange={event => setSeverity(event.target.value)} /></label>
        <div className={css.fieldPair}><label>Start · HKT<input required type="datetime-local" value={start} onChange={event => setStart(event.target.value)} /></label><label>End · HKT<input type="datetime-local" min={start} value={end} onChange={event => setEnd(event.target.value)} /></label></div>
        {candidate.draft.affected_segments.map((segment, index) => <div key={index} className={css.segmentEdit}>
          <div className={css.fieldPair}>{(['from_node', 'to_node'] as const).map(key => <label key={key}>{key === 'from_node' ? 'From' : 'To'}<select required value={segment[key]} onChange={event => updateDraft({ affected_segments: candidate.draft.affected_segments.map((item, i) => i === index ? { ...item, [key]: event.target.value } : item) })}><option value="">Choose station</option>{network.nodes.map(node => <option key={node.id} value={node.id}>{node.name_en}</option>)}</select></label>)}</div>
          <div className={css.fieldPair}><label>Impact<select value={segment.impact} onChange={event => updateDraft({ affected_segments: candidate.draft.affected_segments.map((item, i) => i === index ? { ...item, impact: event.target.value } : item) })}>{['closed', 'reduced_capacity', 'slow', 'crowded'].map(value => <option key={value}>{value}</option>)}</select></label><label>{segment.impact === 'reduced_capacity' ? 'Confirmed capacity factor (0–1)' : 'Capacity factor (fixed)'}<input required={segment.impact === 'reduced_capacity'} disabled={segment.impact !== 'reduced_capacity'} type="number" min="0" max={segment.impact === 'closed' ? '0' : '1'} step="0.05" value={segment.impact === 'reduced_capacity' ? factors[index] ?? '' : capacityFactorForImpact(segment.impact) ?? ''} onChange={event => setFactors(previous => previous.map((value, i) => i === index ? event.target.value : value))} /></label></div>
        </div>)}
        <button type="button" className={css.secondary} onClick={() => { updateDraft({ affected_segments: [...candidate.draft.affected_segments, { from_node: '', to_node: '', impact: 'closed' }] }); setFactors(previous => [...previous, '']) }}>Add affected segment</button>
      </fieldset>
      <div className={css.actions}><button type="submit" className={css.primary} disabled={busy}>{busy ? 'Saving…' : 'Create pending card'}</button><button type="button" className={css.secondary} disabled={busy} onClick={() => setCandidate(null)}>Cancel draft</button></div>
    </form>}
    {notice && <p role="status">{notice}</p>}{error && <p role="alert" className={css.error}>{error}</p>}
  </section>
}
