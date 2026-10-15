import { lazy, Suspense, useEffect, useState } from 'react'
import { Onboarding } from './Onboarding'
import { readState } from './model'
import { Icon } from './Icon'
import './tailwind.css'
import css from './Onboarding.module.css'

const Planner = lazy(() => import('../App').then(module => ({ default: module.App })))

// A network-independent preview keeps the first visit responsive even offline.
function PlannerPreview() {
  return <div className={css.preview} aria-hidden="true" inert>
    <header className={css.previewHeader}><b className={css.previewBrand}>rr<span>.</span></b><nav>Journey <span>Updates</span><span>How it works</span></nav><span className={css.previewAvatar}>F</span></header>
    <main className={css.previewMain}>
      <section className={css.previewPanel}><span className={css.previewKicker}>A BETTER WAY THROUGH THE CITY</span><h1>Your city.<br />Your way.</h1><div className={css.previewModes}><span>All modes</span><span>MTR</span><span>Bus</span><span>Ferry</span></div><label>FROM<div><i />Tai Wai</div></label><label>TO<div><i />Where are you headed?</div></label><div className={css.previewDeparture}>Today <span>Leave now ↗</span></div><div className={css.previewButton}>Find resilient routes <Icon name="arrow" /></div></section>
      <div className={css.previewMap}><svg viewBox="0 0 900 750" fill="none"><path d="M0 520C180 450 240 640 420 500S650 370 900 450V750H0Z" fill="#dbe7e2" /><g stroke="#d0d7ca" strokeWidth="26"><path d="M40 80 700 700M220 0 900 680M0 250 560 750M0 650 750 0M240 750 900 90" /></g><g stroke="#e8eddf" strokeWidth="21"><path d="M40 80 700 700M220 0 900 680M0 250 560 750M0 650 750 0M240 750 900 90" /></g><path d="M170 680V450q0-30 30-60l230-230q25-25 60-25h240" stroke="#5c8172" strokeWidth="7" /><path d="M100 280h200q40 0 70 30l210 210h200" stroke="#a3a47d" strokeWidth="6" />{[[170,580],[200,390],[320,270],[430,160],[550,135],[660,135],[230,280],[400,340],[530,470],[660,520]].map(([x,y]) => <circle key={`${x}-${y}`} cx={x} cy={y} r="10" fill="#fbfbf3" stroke="#5c8172" strokeWidth="3" />)}</svg></div>
    </main>
  </div>
}

export function EntryApp() {
  const [open, setOpen] = useState(() => {
    const view = new URLSearchParams(window.location.search).get('view')
    return view === 'preferences' || (view !== 'planner' && readState().phase !== 'complete')
  })
  const [plannerReady, setPlannerReady] = useState(!open)
  useEffect(() => {
    document.documentElement.lang = open ? 'zh-CN' : 'en'
    document.title = open ? '你的出行偏好 · ResilientRoute' : 'ResilientRoute'
  }, [open])
  function close() {
    if (readState().phase === 'complete') window.dispatchEvent(new Event('rr:preferences-applied'))
    setPlannerReady(true)
    setOpen(false)
    const url = new URL(window.location.href)
    if (url.searchParams.get('view') === 'preferences') { url.searchParams.delete('view'); window.history.replaceState(null, '', url) }
    window.requestAnimationFrame(() => document.getElementById('preferences-trigger')?.focus({ preventScroll: true }))
  }
  return <>
    <div inert={open} aria-hidden={open || undefined}>
      {plannerReady ? <Suspense fallback={<PlannerPreview />}><Planner /></Suspense> : <PlannerPreview />}
      <button type="button" id="preferences-trigger" lang="zh-CN" className={css.reopen} onClick={() => setOpen(true)}><Icon name="route" size={18} />我的出行偏好</button>
    </div>
    {open && <Onboarding onClose={close} />}
  </>
}
