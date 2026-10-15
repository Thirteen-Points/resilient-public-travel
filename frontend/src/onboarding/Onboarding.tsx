import { useEffect, useReducer, useRef, useState, type KeyboardEvent } from 'react'
import { gsap, useGSAP, useReducedMotion } from '../lib/motion'
import { Icon } from './Icon'
import { PreferenceMap } from './PreferenceMap'
import { CORE, DIMENSIONS, QUESTIONS, calculateProfile, percentages, persistState, readState, reducer, track, type Action, type PreferenceEvent, type State } from './model'
import css from './Onboarding.module.css'

function Profile({ state }: { state: State }) {
  const profile = calculateProfile(state)
  const rounded = percentages(profile.weights)
  const maximum = Math.max(...Object.values(profile.weights))
  return <div className={css.profile} aria-label="Recommendation weight profile">
    {DIMENSIONS.map(dimension => <div className={css.weightRow} key={dimension.id} data-weight-dimension={dimension.id}>
      <Icon name={dimension.id} size={16} /><span>{dimension.short}</span>
      <div className={css.weightTrack}><i data-weight style={{ transform: `scaleX(${profile.weights[dimension.id] / maximum})`, backgroundColor: dimension.color }} /></div>
      <strong data-weight-percent={rounded[dimension.id]}>{rounded[dimension.id]}<span>%</span></strong>
      <span className={css.evidence} aria-label={`${dimension.label} source`}>{profile.evidence[dimension.id].status === 'collected' ? profile.evidence[dimension.id].option : profile.evidence[dimension.id].status === 'skipped' ? 'Skipped · Neutral' : 'Not answered · Neutral'}</span>
    </div>)}
  </div>
}

export function Onboarding({ onClose }: { onClose: () => void }) {
  const [state, dispatch] = useReducer(reducer, undefined, readState)
  const [storageAvailable, setStorageAvailable] = useState(true)
  const dialog = useRef<HTMLDialogElement>(null)
  const content = useRef<HTMLDivElement>(null)
  const title = useRef<HTMLHeadingElement>(null)
  const changing = useRef(false)
  const reduced = useReducedMotion()
  const transition = useRef<gsap.core.Timeline | null>(null)
  const profile = calculateProfile(state)
  const question = QUESTIONS[state.queue[state.cursor]]
  const answer = state.answers[question.id]
  const selectedIndex = question.options.findIndex(option => option.id === answer)
  const progress = state.phase === 'welcome' ? 0 : state.phase === 'question' ? state.cursor : state.queue.length
  const steps = state.queue.length

  useEffect(() => {
    const element = dialog.current
    if (!element) return
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    if (!element.open) element.showModal()
    title.current?.focus({ preventScroll: true })
    return () => {
      element.close()
      document.body.style.overflow = overflow
      previous?.focus({ preventScroll: true })
      transition.current?.kill()
    }
  }, [])

  useEffect(() => { setStorageAvailable(persistState(state)) }, [state])
  useEffect(() => {
    if (state.pending) return
    title.current?.focus({ preventScroll: true })
  }, [state.phase, state.cursor, state.pending])

  function send(action: Action) {
    if (changing.current) return
    const events: Partial<Record<Action['type'], PreferenceEvent>> = { START: 'start', SELECT: 'answer', SKIP: 'skip', BACK: 'back', CONTINUE: 'continue', FINISH: 'complete', NEXT: 'next' }
    if (events[action.type]) track(events[action.type]!, { dimension: question.id, ...(action.type === 'SELECT' ? { option: action.option } : {}), ...(action.type === 'FINISH' ? { weights: profile.weights, collected: profile.collected } : {}) })
    if (action.type === 'SELECT') { dispatch(action); return }
    move(action)
  }
  function move(action: Action) {
    if (changing.current) return
    transition.current?.kill()
    if (reduced || !content.current) { dispatch(action); return }
    changing.current = true
    transition.current = gsap.timeline({ onComplete: () => { changing.current = false; dispatch(action) } })
      .to(content.current, { opacity: 0, y: action.type === 'BACK' ? 8 : -8, duration: .16, ease: 'power1.in' })
  }

  useEffect(() => {
    if (!state.pending || state.phase !== 'question') return
    const delay = gsap.delayedCall(reduced ? .25 : .72, () => move({ type: 'ADVANCE', revision: state.revision }))
    return () => { delay.kill() }
    // The revision prevents an older answer's transition from advancing a new question.
  }, [state.pending, state.revision, state.phase, reduced])

  useGSAP(() => {
    if (reduced) { gsap.set(dialog.current, { opacity: 1, scale: 1 }); return }
    gsap.fromTo(dialog.current, { opacity: 0, scale: .96, y: 18 }, { opacity: 1, scale: 1, y: 0, duration: .65, ease: 'power3.out' })
  }, { dependencies: [reduced], revertOnUpdate: true })

  useGSAP(() => {
    if (!content.current) return
    gsap.set(content.current, { opacity: 1, y: 0 })
    if (reduced) return
    const timeline = gsap.timeline()
    timeline.fromTo(content.current, { opacity: 0, y: state.direction * 12 }, { opacity: 1, y: 0, duration: .4, ease: 'power3.out' })
    const options = content.current.querySelectorAll('[data-option]')
    if (options.length) timeline.fromTo(options, { opacity: 0, y: 10 }, { opacity: 1, y: 0, stagger: .045, duration: .32, ease: 'power2.out' }, .04)
    const weights = content.current.querySelectorAll('[data-weight]')
    if (weights.length) timeline.from(weights, { scaleX: 0, duration: .55, stagger: .025, ease: 'power2.out' }, .08)
  }, { scope: content, dependencies: [state.phase, state.cursor, reduced], revertOnUpdate: true })

  function close() {
    if (changing.current) return
    track('dismiss', { phase: state.phase })
    if (reduced || !dialog.current) { onClose(); return }
    changing.current = true
    transition.current = gsap.timeline({ onComplete: onClose }).to(dialog.current, { opacity: 0, scale: .98, y: 8, duration: .2, ease: 'power2.in' })
  }
  function optionKeys(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (!['ArrowDown', 'ArrowUp', 'ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? question.options.length - 1 : (index + (event.key === 'ArrowUp' || event.key === 'ArrowLeft' ? -1 : 1) + question.options.length) % question.options.length
    content.current?.querySelector<HTMLButtonElement>(`[data-option="${next}"]`)?.focus()
  }
  function keepFocus(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== 'Tab') return
    const controls = Array.from(dialog.current?.querySelectorAll<HTMLElement>('button, a[href], [tabindex]') ?? [])
      .filter(element => element.tabIndex >= 0 && !element.hasAttribute('disabled') && element.getClientRects().length > 0)
    const index = controls.indexOf(document.activeElement as HTMLElement)
    if (index === -1 || event.shiftKey && index === 0 || !event.shiftKey && index === controls.length - 1) {
      event.preventDefault()
      controls[event.shiftKey ? controls.length - 1 : 0]?.focus({ preventScroll: true })
    }
  }
  function download() {
    const blob = new Blob([JSON.stringify({ ...profile, completed: state.phase === 'complete', normalization: { formula: 'weight = raw / sum(all nine raw scores)', optionScores: [.95, .5, .15], neutralScore: .5 }, exportedAt: new Date().toISOString() }, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = 'resilientroute-preferences.json'; anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    track('export')
  }
  const liveText = state.phase === 'question'
    ? `Question ${state.cursor + 1} of ${steps}. ${question.title} ${state.pending ? `Selected: ${question.options[selectedIndex]?.label}. Moving to the next question. ` : ''}${profile.collected} dimensions collected. ${DIMENSIONS.find(d => d.id === question.id)?.label} weight: ${percentages(profile.weights)[question.id]} percent.`
    : state.phase === 'summary' ? `Your travel preferences are ready. ${profile.collected} dimensions collected. All weights total 100 percent.`
    : state.phase === 'complete' ? `Your preferences are ready. ${storageAvailable ? 'Saved in this browser.' : 'Browser storage is unavailable. You can export your profile.'}` : 'Welcome. Your journey. Your way.'

  return <dialog ref={dialog} className={css.dialog} aria-modal="true" aria-labelledby="onboarding-title" lang="en" onKeyDown={keepFocus} onCancel={event => { event.preventDefault(); if (state.phase === 'question') send({ type: 'BACK' }); else close() }}>
    <div className={css.dialogGrid}>
      <section className={css.left}>
        <header className={`${css.topbar} flex items-center justify-between`}>
          <span className={css.mark} data-brand="rr." aria-label="ResilientRoute">rr<span>.</span></span>
          <div className="flex items-center gap-3" aria-label={`Questionnaire progress: ${progress} of ${steps}`}>
            <div className={css.progressDots} aria-hidden="true">{Array.from({ length: steps }).map((_, index) => <i key={index} className={index < progress ? css.dotComplete : index === progress ? css.dotCurrent : ''} />)}</div>
            <span className={css.counter}>{String(progress).padStart(2, '0')}<i>/</i>{String(steps).padStart(2, '0')}</span>
          </div>
        </header>
        <div ref={content} className={css.content}>
          {state.phase === 'welcome' && <div className={css.welcome}>
            <div className={css.welcomeSymbol} aria-hidden="true"><span /><span /><i /><i /></div>
            <h1 ref={title} tabIndex={-1} id="onboarding-title">Your journey.<br /><em>Your way.</em></h1>
            <div className={css.dimensionIcons} aria-hidden="true">{DIMENSIONS.slice(0,6).map(dimension => <span key={dimension.id}><Icon name={dimension.id} size={19} /></span>)}</div>
            <button type="button" className={css.primary} onClick={() => send({ type: 'START' })}>Let's begin<Icon name="arrow" /></button>
            <button type="button" className={css.welcomeLater} onClick={close}>Maybe later</button>
          </div>}
          {state.phase === 'question' && <div className={css.question}>
            <span className={css.questionIcon} aria-hidden="true"><Icon name={question.id} size={27} /></span>
            <h1 ref={title} tabIndex={-1} id="onboarding-title">{question.title}</h1>
            <div className={css.options} role="radiogroup" aria-labelledby="onboarding-title">
              {question.options.map((option, index) => <button type="button" data-option={index} key={option.id} role="radio" aria-checked={answer === option.id} tabIndex={selectedIndex === -1 ? index === 0 ? 0 : -1 : index === selectedIndex ? 0 : -1} className={`${css.option} ${answer === option.id ? css.selected : ''}`} onKeyDown={event => optionKeys(event, index)} onClick={() => send({ type: 'SELECT', option: option.id })}>
                <span className={css.optionIndex} aria-hidden="true">0{index + 1}</span><span>{option.label}</span><i className={css.radio}>{answer === option.id && <Icon name="check" size={13} />}</i>
              </button>)}
            </div>
            <div className={`${css.questionActions} flex items-center justify-between`}>
              <button type="button" onClick={() => send({ type: 'BACK' })}><Icon name="back" size={16} />Back</button>
              {answer !== undefined && !state.pending && <button type="button" onClick={() => send({ type: 'NEXT' })}>Keep &amp; continue<Icon name="arrow" size={16} /></button>}
              <button type="button" onClick={() => send({ type: 'SKIP' })}>Skip<Icon name="arrow" size={16} /></button>
            </div>
          </div>}
          {(state.phase === 'summary' || state.phase === 'complete') && <div className={css.summary}>
            <h1 ref={title} tabIndex={-1} id="onboarding-title">{state.phase === 'complete' ? <>Your preferences, <em>ready.</em></> : <>Your travel <span>preferences</span></>}</h1>
            <Profile state={state} />
            <div className={css.summaryActions}>
              {state.phase === 'summary' ? <>
                <button type="button" className={css.primary} onClick={() => send({ type: 'FINISH' })}>Finish<Icon name="check" size={19} /></button>
                {state.queue.length === CORE.length && <button type="button" className={css.secondary} onClick={() => send({ type: 'CONTINUE' })}>Explore more<Icon name="arrow" size={18} /></button>}
              </> : <button type="button" className={css.primary} onClick={close}>Plan my journey<Icon name="arrow" size={19} /></button>}
            </div>
            <div className={`${css.summaryLinks} flex items-center justify-between`}>
              <button type="button" onClick={() => send({ type: 'BACK' })}><Icon name="back" size={15} />Review answers</button>
              <button type="button" onClick={download}><Icon name="download" size={15} />Export profile</button>
            </div>
            {!storageAvailable && <button type="button" className={css.storageRetry} onClick={() => setStorageAvailable(persistState(state))}>Couldn't save. Try again</button>}
          </div>}
        </div>
        <div className={css.bottomTrack} role="progressbar" aria-label="Preference collection progress" aria-valuemin={0} aria-valuemax={steps} aria-valuenow={progress}><span style={{ transform: `scaleX(${progress / steps})` }} /></div>
      </section>
      <div className={css.mapPanel}><PreferenceMap dimension={question.id} strength={selectedIndex === -1 ? .5 : [1,.5,.16][selectedIndex]} revision={state.revision} direction={state.direction} stage={state.phase} /></div>
    </div>
    <button type="button" className={css.close} aria-label="Close onboarding" onClick={close}><Icon name="close" size={19} /></button>
    <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">{liveText}</div>
  </dialog>
}
