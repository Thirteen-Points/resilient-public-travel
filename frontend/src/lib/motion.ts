import { useEffect, useState, type RefObject } from 'react'
import gsap from 'gsap'
import { useGSAP } from '@gsap/react'

gsap.registerPlugin(useGSAP)
export { gsap, useGSAP }

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
    if (!ready) return
    const media = gsap.matchMedia()
    media.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.from('[data-panel]', { opacity: 0, y: 8, duration: .18, ease: 'power2.out', clearProps: 'all' })
      const cards = scope.current?.querySelectorAll('[data-enter]')
      const confidence = scope.current?.querySelectorAll('[data-confidence]')
      if (cards?.length) gsap.from(cards, { opacity: 0, y: 4, stagger: .02, duration: .18, clearProps: 'all' })
      if (confidence?.length) gsap.from(confidence, { scaleX: 0, transformOrigin: 'left center', duration: .18, ease: 'power2.out', clearProps: 'transform' })
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
