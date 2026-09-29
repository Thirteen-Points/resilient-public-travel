import { useEffect, useId, useRef } from 'react'
import { BotEngine, COLORS, type BotFrame } from '../lib/bloub/engine'
import { useReducedMotion } from '../lib/motion'
import css from './Experience.module.css'

// Bloub-style bot avatar (jeremy-prt/bloub, MIT — see THIRD_PARTY_NOTICES.md
// and lib/bloub/). The engine samples a pure-time frame; React mounts one
// static SVG picture and every tick is applied straight to the DOM. The eyes
// are holes cut in the body through an SVG mask, revealing the halo "paper"
// behind, exactly as in the original.
const R = 36

const nowSec = () => performance.now() / 1000

export function AgentAvatar({ issue, loading = false, small = false }: { issue: boolean; loading?: boolean; small?: boolean }) {
  const reduced = useReducedMotion()
  const root = useRef<SVGSVGElement>(null)
  const engine = useRef<BotEngine | null>(null)
  const initial = useRef<BotFrame | null>(null)
  const maskId = useId()
  const target = loading ? 'thinking' : issue ? 'triangle' : 'idle'
  if (!engine.current) {
    engine.current = new BotEngine(R, {
      state: target,
      body: issue ? COLORS.body.issue : COLORS.body.calm,
      halo: issue ? COLORS.halo.issue : COLORS.halo.calm
    })
    initial.current = engine.current.sample(0, true)
  }
  const first = initial.current!

  useEffect(() => {
    const svg = root.current
    if (!svg) return
    const pick = <T extends Element>(selector: string) => svg.querySelector<T>(selector)!
    const els = {
      halo: pick('[data-halo]'), body: pick('[data-body]'), maskBody: pick('[data-mask-body]'),
      eyes: [pick('[data-mask-eye-0]'), pick('[data-mask-eye-1]')],
      dots: [pick('[data-dot-0]'), pick('[data-dot-1]')]
    }
    const apply = (frame: BotFrame) => {
      els.halo.setAttribute('fill', frame.haloColor)
      els.body.setAttribute('d', frame.bodyPath)
      els.body.setAttribute('fill', frame.bodyColor)
      els.maskBody.setAttribute('d', frame.bodyPath)
      els.eyes.forEach((el, i) => {
        const eye = frame.eyes[i]
        el.setAttribute('d', eye?.d ?? '')
        el.setAttribute('transform', eye?.matrix ?? '')
        el.setAttribute('opacity', (eye?.alpha ?? 0).toFixed(3))
      })
      els.dots.forEach((el, i) => {
        const dot = frame.dots[i]
        el.setAttribute('cx', (dot?.x ?? 0).toFixed(2))
        el.setAttribute('cy', (dot?.y ?? 0).toFixed(2))
        el.setAttribute('r', (dot?.r ?? 0).toFixed(2))
        el.setAttribute('fill', frame.bodyColor)
        el.setAttribute('opacity', (dot?.opacity ?? 0).toFixed(3))
      })
    }
    const bot = engine.current!
    bot.setState(target, nowSec())
    bot.setColor(issue ? COLORS.body.issue : COLORS.body.calm, issue ? COLORS.halo.issue : COLORS.halo.calm, nowSec())
    if (reduced) {
      apply(bot.sample(nowSec(), true))
      return
    }
    let raf = requestAnimationFrame(function loop() {
      apply(bot.sample(nowSec()))
      raf = requestAnimationFrame(loop)
    })
    return () => cancelAnimationFrame(raf)
  }, [reduced, issue, loading, target])

  const label = `${issue ? 'Published transport disruption' : 'No active published disruption'}${loading ? ' · preparing reply' : ''}`
  const eye = (i: number) => first.eyes[i]
  const dot = (i: number) => first.dots[i]
  return <svg ref={root} viewBox="-50 -50 100 100" role="img" aria-label={label} className={`${css.avatar} ${small ? css.avatarSmall : ''}`}>
    <defs>
      <mask id={maskId} maskUnits="userSpaceOnUse" x="-50" y="-50" width="100" height="100">
        <path data-mask-body fill="#fff" d={first.bodyPath} />
        <path data-mask-eye-0 fill="#000" d={eye(0)?.d ?? ''} transform={eye(0)?.matrix ?? ''} opacity={eye(0)?.alpha ?? 0} />
        <path data-mask-eye-1 fill="#000" d={eye(1)?.d ?? ''} transform={eye(1)?.matrix ?? ''} opacity={eye(1)?.alpha ?? 0} />
      </mask>
    </defs>
    <circle data-halo cx="0" cy="0" r="47" fill={first.haloColor} />
    <path data-body fill={first.bodyColor} mask={`url(#${maskId})`} d={first.bodyPath} />
    <circle data-dot-0 r={dot(0)?.r ?? 0} cx={dot(0)?.x ?? 0} cy={dot(0)?.y ?? 0} fill={first.bodyColor} opacity={dot(0)?.opacity ?? 0} />
    <circle data-dot-1 r={dot(1)?.r ?? 0} cx={dot(1)?.x ?? 0} cy={dot(1)?.y ?? 0} fill={first.bodyColor} opacity={dot(1)?.opacity ?? 0} />
  </svg>
}
