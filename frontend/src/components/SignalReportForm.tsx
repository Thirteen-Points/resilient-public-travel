import { useRef, useState } from 'react'
import { submitSignalReport, type SignalLang } from '../api/signalReportClient'
import css from './SignalReport.module.css'

const MAX_CHARACTERS = 2000
const MAX_SOURCE_HINT_CHARACTERS = 100
const LANGUAGES: { id: SignalLang; label: string }[] = [
  { id: 'zh-HK', label: '中文' },
  { id: 'en', label: 'English' },
]

type Failure = { message: string; detail?: string; retryable: boolean }

/** Standalone public signal-report form: POSTs unverified evidence to /api/signals. */
export function SignalReportForm({ onAccepted }: { onAccepted?: (signalId: string) => void } = {}) {
  const [text, setText] = useState('')
  const [sourceHint, setSourceHint] = useState('')
  const [lang, setLang] = useState<SignalLang>('zh-HK')
  const [sending, setSending] = useState(false)
  const [inputError, setInputError] = useState('')
  const [acceptedId, setAcceptedId] = useState('')
  const [failure, setFailure] = useState<Failure | null>(null)
  const sendingRef = useRef(false)
  const textarea = useRef<HTMLTextAreaElement>(null)

  const submit = async () => {
    if (sendingRef.current || acceptedId) return
    const value = text.trim()
    if (!value) { setInputError('Describe what you saw in at least a few words so reviewers can assess it.'); return }
    if (value.length > MAX_CHARACTERS) { setInputError(`Reports are limited to ${MAX_CHARACTERS} characters. Shorten the text (currently ${value.length}).`); return }
    setInputError(''); setFailure(null)
    sendingRef.current = true; setSending(true)
    const result = await submitSignalReport({ rawText: value, lang, authorHint: sourceHint })
    sendingRef.current = false; setSending(false)
    if (result.ok) { setAcceptedId(result.signalId); onAccepted?.(result.signalId); return }
    setFailure({ message: result.message, detail: result.detail, retryable: result.kind !== 'invalid' })
  }

  const reset = () => {
    setText(''); setSourceHint(''); setAcceptedId(''); setFailure(null); setInputError('')
    requestAnimationFrame(() => textarea.current?.focus())
  }

  const counterState = text.length >= MAX_CHARACTERS ? css.counterOver : text.length >= MAX_CHARACTERS - 100 ? css.counterNear : ''

  return <section className={css.reportPanel} data-panel aria-labelledby="signal-report-heading" aria-busy={sending}>
    <span className={css.eyebrow}>REPORT A DISRUPTION <span>UNVERIFIED INTAKE</span></span>
    <h1 id="signal-report-heading">Seen something?</h1>
    <p className={css.subhead}>Send a short field report for human review. No sign-in or personal details are required. Your original report is stored for review.</p>
    {acceptedId ? <div role="status" className={css.accepted}>
      <strong>Report received — not yet verified.</strong>
      <p>Reference <code>{acceptedId}</code>. A reviewer will assess it before anything changes. This does not confirm an incident, and routes and the map are unchanged.</p>
      <button type="button" className={css.secondary} onClick={reset}>Report something else ↺</button>
    </div> : <form noValidate onSubmit={event => { event.preventDefault(); void submit() }}>
      <div className={css.labelRow}>
        <label htmlFor="signal-report-text" className={css.fieldLabel}>What did you see?</label>
        <span className={`${css.counter} ${counterState}`}>{text.length} / {MAX_CHARACTERS}</span>
      </div>
      <textarea id="signal-report-text" ref={textarea} className={`${css.textarea} ${inputError ? css.invalid : ''}`}
        required minLength={1} maxLength={MAX_CHARACTERS} rows={5} disabled={sending} value={text}
        aria-invalid={Boolean(inputError)} aria-describedby="signal-report-hint signal-report-input-error"
        placeholder="e.g. Lift outage at Tai Wai station concourse, crowds building at Exit A…"
        onChange={event => { setText(event.target.value); if (inputError) setInputError('') }} />
      <p id="signal-report-hint" className={css.micro}>Line or station, direction, and what is happening. Facts you observed only — reports are logged as unverified signals.</p>
      {inputError && <p id="signal-report-input-error" role="alert" className={css.error}>{inputError}</p>}
      <label htmlFor="signal-source-hint" className={css.fieldLabel}>Source hint (optional)</label>
      <input id="signal-source-hint" className={css.sourceHint} type="text" maxLength={MAX_SOURCE_HINT_CHARACTERS}
        disabled={sending} value={sourceHint} aria-describedby="signal-source-hint-help"
        onChange={event => setSourceHint(event.target.value.slice(0, MAX_SOURCE_HINT_CHARACTERS))} />
      <p id="signal-source-hint-help" className={css.micro}>Helps reviewers tell independent reports apart; it does not verify your report. No personal details are required.</p>
      <fieldset className={css.language}>
        <legend>Report language</legend>
        <div className={css.languageOptions}>{LANGUAGES.map(option => <label key={option.id} className={css.languageOption}>
          <input type="radio" name="signal-report-lang" value={option.id} checked={lang === option.id} disabled={sending} onChange={() => setLang(option.id)} />
          {option.label}
        </label>)}</div>
      </fieldset>
      <div className={css.actions}>
        <button type="submit" className={css.primary} disabled={sending}>{sending ? 'Submitting report…' : 'Send unverified report'} <span>↗</span></button>
        {sending && <span className={css.sendingNote} role="status">Sending — please wait…</span>}
      </div>
      {failure && <div role="alert" className={failure.retryable ? css.retryable : css.error}>
        <strong>{failure.retryable ? 'Not sent yet — you can retry.' : 'Not accepted — please revise.'}</strong>
        <p>{failure.message}</p>
        {failure.detail && <small>Service note: {failure.detail}</small>}
      </div>}
    </form>}
    <p className={css.tiny}>Academic demo · reports feed the review queue; only published, reviewed events affect routing.</p>
  </section>
}
