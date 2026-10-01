import { useState, useSyncExternalStore } from 'react'
import { getReviewToken, reviewerRevision, setReviewToken, subscribeReviewer } from '../api/reviewerSession'
import { getEvents } from '../api/eventApi'
import css from './Experience.module.css'

export function ReviewAccess({ children }: { children: React.ReactNode }) {
  useSyncExternalStore(subscribeReviewer, reviewerRevision)
  const [input, setInput] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const [verified, setVerified] = useState(Boolean(getReviewToken()))
  return <>
    <section className={css.reviewPanel} aria-label="Reviewer access">
      <h2>Reviewer access</h2>
      <p>Use a temporary reviewer credential for this controlled demo. It stays in memory until disconnect or page reload.</p>
      {verified && getReviewToken() ? <button type="button" className={css.secondary} onClick={() => { setReviewToken(''); setVerified(false); setInput(''); setError('') }}>Disconnect reviewer</button> :
        <form className={css.structured} onSubmit={async event => {
          event.preventDefault(); if (busy) return
          setBusy(true); setError(''); setReviewToken(input)
          try { await getEvents(); setVerified(true); setInput('') }
          catch (cause) { setReviewToken(''); setError(cause instanceof Error ? cause.message : String(cause)) }
          finally { setBusy(false) }
        }}><label>Temporary credential<input type="password" required autoComplete="off" value={input} onChange={event => setInput(event.target.value)} /></label><button type="submit" disabled={busy} className={css.primary}>{busy ? 'Connecting…' : 'Connect reviewer'}</button></form>}
      {error && <p role="alert" className={css.error}>{error}</p>}
    </section>
    {verified && getReviewToken() && children}
  </>
}
