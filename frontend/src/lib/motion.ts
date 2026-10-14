import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'
import { flushSync } from 'react-dom'
import gsap from 'gsap'
import { useGSAP } from '@gsap/react'

gsap.registerPlugin(useGSAP)
export { gsap, useGSAP }

type PageTransition = {
  finished: Promise<void>
  ready: Promise<void>
  skipTransition: () => void
}
type TransitionSurface = HTMLElement & {
  startViewTransition?: (update: () => void) => PageTransition
}
type ActivePageTransition = {
  transition: PageTransition
  scope: HTMLDivElement
  commit: () => void
}

// Keep transition state outside the DOM so no temporary styles or attributes can
// survive an interrupted navigation or affect an unrelated component update.
const transitioningScopes = new WeakSet<HTMLDivElement>()

export function usePageTransition(scope: RefObject<HTMLDivElement | null>) {
  const active = useRef<ActivePageTransition | null>(null)
  const generation = useRef(0)
  const mounted = useRef(true)

  const stopTransition = useCallback(() => {
    const current = active.current
    if (!current) return
    active.current = null
    transitioningScopes.delete(current.scope)
    current.transition.skipTransition()
  }, [])

  useEffect(() => {
    mounted.current = true
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => {
      if (!media.matches) return
      const current = active.current
      stopTransition()
      // A preference change may happen before the native snapshot callback.
      // Commit the latest navigation immediately, once, with motion disabled.
      current?.commit()
    }
    media.addEventListener('change', update)
    return () => {
      mounted.current = false
      generation.current += 1
      media.removeEventListener('change', update)
      stopTransition()
    }
  }, [stopTransition])

  return useCallback((update: () => void, animate = true) => {
    const revision = ++generation.current
    stopTransition()
    const element = scope.current
    const surface = element?.querySelector<HTMLElement>('main') as TransitionSurface | null
    // Document snapshots suppress hit testing even on the uncaptured header.
    // Scope snapshots to the workspace; older browsers keep live panel motion.
    if (!animate || !element || !surface?.startViewTransition || document.hidden || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      flushSync(update)
      return
    }

    let committed = false
    const commit = () => {
      if (committed || !mounted.current || generation.current !== revision) return
      committed = true
      // Capture the new page only after React has committed its complete layout.
      // No exit-animation timer delays request cancellation or page state.
      flushSync(update)
    }
    transitioningScopes.add(element)
    try {
      const transition = surface.startViewTransition(commit)
      const current = { transition, scope: element, commit }
      active.current = current
      // Skipping a superseded transition rejects ready; it is an expected visual
      // cancellation, while the latest DOM update still completes normally.
      void transition.ready.catch(commit)
      const finish = () => {
        if (active.current !== current) return
        active.current = null
        transitioningScopes.delete(element)
      }
      void transition.finished.then(finish, finish)
    } catch {
      transitioningScopes.delete(element)
      commit()
    }
  }, [scope, stopTransition])
}

export function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReduced(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return reduced
}

export function usePageMotion(scope: RefObject<HTMLDivElement | null>, screen: string, ready: boolean) {
  useGSAP(() => {
    const element = scope.current
    if (!ready || !element || transitioningScopes.has(element)) return
    const media = gsap.matchMedia()
    media.add('(prefers-reduced-motion: no-preference)', () => {
      const visible = (selector: string) => Array.from(element.querySelectorAll<HTMLElement>(selector))
        .filter(target => !target.closest('[hidden]') && target.getClientRects().length > 0)
      const panels = visible('[data-panel]')
      const cards = visible('[data-enter]')
      const confidence = visible('[data-confidence]')
      if (panels.length) gsap.from(panels, { opacity: 0, y: 6, duration: .26, ease: 'power2.out', clearProps: 'opacity,transform' })
      if (cards.length) gsap.from(cards, { opacity: 0, y: 4, stagger: .02, duration: .24, clearProps: 'opacity,transform' })
      if (confidence.length) gsap.from(confidence, { scaleX: 0, transformOrigin: 'left center', duration: .24, ease: 'power2.out', clearProps: 'transform,transformOrigin' })
    })
    return () => media.revert()
  }, { scope, dependencies: [screen, ready], revertOnUpdate: true })
}

export function useSuccessMotion(scope: RefObject<HTMLElement | null>, revision: number) {
  useGSAP(() => {
    if (!revision || !scope.current) return
    const media = gsap.matchMedia()
    media.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.fromTo(scope.current, { y: 8, opacity: 0 }, { y: 0, opacity: 1, duration: .18, ease: 'power2.out', clearProps: 'all' })
    })
    return () => media.revert()
  }, { dependencies: [revision], revertOnUpdate: true })
}
