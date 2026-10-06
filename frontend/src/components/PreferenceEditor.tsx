import { useEffect, useRef, useState } from 'react'
import { applyPreference, preference, type PreferenceResult } from '../api/preferences'
import { LatestRequest, profileLabel } from '../api/p3Context'
import type { TravelProfile } from '../api/types'
import css from './P3.module.css'

export function PreferenceEditor({ profile, active, onApply }: { profile: TravelProfile; active: boolean; onApply: (profile: TravelProfile) => void }) {
  const [text, setText] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState(''), [applied, setApplied] = useState(false)
  const [preview, setPreview] = useState<{ result: PreferenceResult; profile: TravelProfile; baseKey: string } | null>(null)
  const latest = useRef(new LatestRequest())
  const key = JSON.stringify(profile)
  useEffect(() => { latest.current.cancel(); setBusy(false); return () => latest.current.cancel() }, [key, active])
  const parse = async () => {
    const request = latest.current.begin(), frozen = structuredClone(profile), baseKey = key
    setBusy(true); setError(''); setApplied(false); setPreview(null)
    try {
      const result = await preference(text, frozen, request.signal)
      if (request.current()) setPreview({ result, profile: applyPreference(frozen, result.patch), baseKey })
    } catch (cause) { if (request.current()) setError(cause instanceof Error ? cause.message : String(cause)) }
    finally { if (request.current()) setBusy(false) }
  }
  return <section className={`${css.page} ${css.preference}`} aria-labelledby="preference-heading">
    <span className={css.kicker}>YOUR NEEDS, IN YOUR WORDS</span><h2 id="preference-heading">Tell us what matters.</h2>
    <p className={css.micro}>Describe a walking or price preference. Review it before applying; existing accessibility restrictions stay in place.</p>
    <form onSubmit={event => { event.preventDefault(); void parse() }}>
      <label htmlFor="preference-text">Travel preferences</label>
      <textarea id="preference-text" rows={2} maxLength={500} value={text} placeholder="例如：我坐轮椅，别让我走太多路 · e.g. wheelchair, please keep costs low" onChange={event => { latest.current.cancel(); setBusy(false); setText(event.target.value); setPreview(null); setApplied(false); setError('') }} />
      <div className={css.actions}><button type="submit" disabled={busy || !text.trim()}>{busy ? 'Reading preferences…' : 'Preview preferences'}</button>{busy && <button type="button" onClick={() => { latest.current.cancel(); setBusy(false); setError('Preference request cancelled. Current settings retained.') }}>Cancel preferences</button>}</div>
    </form>
    {error && <p role="alert" className={css.error}>{error}</p>}
    {preview && !applied && <div className={css.context} data-preference-preview>
      <span className={css.badge}>{preview.result.method === 'rule_fallback' ? 'Rule fallback' : preview.result.method === 'llm' ? 'Model-assisted extraction' : preview.result.method}</span>
      <p><strong>{profileLabel(preview.profile)}</strong></p>
      <p>{preview.result.explanation}</p>
      <p className={css.micro}>Hard restrictions: {preview.profile.hard_flags.length ? preview.profile.hard_flags.map(flag => flag.replaceAll('_', ' ')).join(' · ') : 'none added'}{preview.profile.max_transfers !== undefined ? ` · at most ${preview.profile.max_transfers} transfers` : ''}</p>
      {preview.profile.weights && <details><summary>Proposed scoring weights</summary><ul>{Object.entries(preview.profile.weights).map(([criterion, weight]) => <li key={criterion}>{criterion}: {(weight * 100).toFixed(1)}%</li>)}</ul></details>}
      {preview.baseKey !== key && <p className={css.notice}>Current settings changed. Preview the text again before applying.</p>}
      <button type="button" disabled={preview.baseKey !== key || busy} onClick={() => { onApply(preview.profile); setApplied(true) }}>Apply preferences</button>
    </div>}
    {applied && <p role="status" className={css.success}>Preferences applied to the planner and journey companion. Route estimates still come from the engine.</p>}
    <p className={css.micro}>Active: {profileLabel(profile)}. Source: /api/persona/parse; extraction is a preference suggestion, not travel advice.</p>
  </section>
}
