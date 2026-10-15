import { Suspense, lazy, useEffect } from 'react'
import { Onboarding } from './Onboarding'
import { readState } from './model'
import css from './Onboarding.module.css'

// Keep the questionnaire independent from the planner's network requests and map bundle.
const Planner = lazy(() => import('../App').then(module => ({ default: module.App })))
export function EntryApp() {
  const view = new URLSearchParams(window.location.search).get('view')
  const preferences = view === 'preferences' || (view !== 'planner' && readState().phase !== 'complete')
  useEffect(() => {
    document.documentElement.lang = preferences ? 'zh-CN' : 'en'
    document.title = preferences ? '认识你的旅程 · ResilientRoute' : 'ResilientRoute'
  }, [preferences])
  return preferences ? <Onboarding /> : <Suspense fallback={<div className={css.plannerLoading}>正在连接你的旅程…</div>}><Planner /><a className={css.plannerPreferences} href="?view=preferences">我的出行偏好 ↗</a></Suspense>
}
