import { describe, expect, it } from 'vitest'
import { BotEngine, mixHex } from '../engine'
import { liveliness } from '../face'

const R = 36

// closedPath emits Catmull-Rom cubics: each `C` segment ends on a contour
// point, so pulling the third coordinate pair recovers the outline.
function outline(d: string) {
  return [...d.matchAll(/C([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)/g)].map(
    m => ({ x: Number(m[5]), y: Number(m[6]) })
  )
}

describe('BotEngine silhouettes', () => {
  it('renders the resting ball as a circle of radius scale', () => {
    const engine = new BotEngine(R)
    const points = outline(engine.sample(10).bodyPath)
    expect(points).toHaveLength(64)
    for (const p of points) {
      const r = Math.hypot(p.x, p.y)
      expect(r).toBeGreaterThan(R - 0.5)
      expect(r).toBeLessThan(R + 0.5)
    }
  })

  it('settles on the measured three-corner triangle after the morph', () => {
    const engine = new BotEngine(R)
    engine.setState('triangle', 0)
    const points = outline(engine.sample(10).bodyPath)
    const radii = points.map(p => Math.hypot(p.x, p.y - 0.213 * R))
    const peaks = radii.filter((v, i) => v > radii[(i + 1) % 64]! && v >= radii[(i + 63) % 64]!)
    expect(peaks).toHaveLength(3)
    expect(Math.max(...radii)).toBeGreaterThan(1.1 * R)
    expect(Math.min(...radii)).toBeLessThan(0.72 * R)
  })

  it('morphs continuously between states', () => {
    const engine = new BotEngine(R)
    engine.setState('triangle', 100)
    const a = outline(engine.sample(100.05).bodyPath)
    const b = outline(engine.sample(100.066).bodyPath)
    for (let i = 0; i < 64; i++) {
      // easeOutQuint is fastest at morph entry: one 60 fps step may carry a
      // few percent of the ball diameter, which still reads as motion.
      expect(Math.hypot(a[i]!.x - b[i]!.x, a[i]!.y - b[i]!.y)).toBeLessThan(2)
    }
  })

  it('keeps a fade-in-flight continuous when the state changes again mid-morph', () => {
    const engine = new BotEngine(R)
    engine.setState('triangle', 100)
    engine.setState('thinking', 100.1)
    const a = outline(engine.sample(100.12).bodyPath)
    const b = outline(engine.sample(100.14).bodyPath)
    let worst = 0
    for (let i = 0; i < 64; i++) {
      worst = Math.max(worst, Math.hypot(a[i]!.x - b[i]!.x, a[i]!.y - b[i]!.y))
    }
    expect(worst).toBeLessThan(8)
  })
})

describe('BotEngine face and thinking', () => {
  it('renders two eyes at rest and none while thinking', () => {
    const engine = new BotEngine(R)
    expect(engine.sample(5).eyes).toHaveLength(2)
    engine.setState('thinking', 10)
    const frame = engine.sample(11)
    expect(frame.eyes).toHaveLength(0)
    expect(frame.dots).toHaveLength(2)
  })

  it('pulses the thinking dots in a travelling wave', () => {
    const engine = new BotEngine(R)
    engine.setState('thinking', 0)
    const left = engine.sample(2).dots[0]!
    const right = engine.sample(2).dots[1]!
    // dot i peaks when p = (t - 0.5i)/1.5 mod 1 sits on the 0.25-0.5 plateau:
    // dot 0 at t = 2, dot 2 at t = 2.9.
    expect(left.r / right.r).toBeGreaterThan(1.05)
    const later = engine.sample(2.9).dots
    expect(later[1]!.r / later[0]!.r).toBeGreaterThan(1.05)
  })

  it('blinks from the calendar and rests open most of the time', () => {
    let closed = 0
    let open = 0
    for (let t = 0; t < 30; t += 1 / 60) {
      const lid = liveliness(t).lid
      if (lid < 0.5) closed++
      if (lid === 1) open++
    }
    expect(closed).toBeGreaterThan(0)
    expect(open).toBeGreaterThan(closed * 10)
  })
})

describe('BotEngine determinism', () => {
  it('is a pure function of time and its time-stamped setters', () => {
    const run = () => {
      const engine = new BotEngine(R, { state: 'triangle', body: '#e8483f' })
      engine.setState('idle', 3)
      engine.setState('thinking', 4.2)
      return engine.sample(4.5).bodyPath
    }
    expect(run()).toBe(run())
  })

  it('renders a frozen still frame independent of the clock', () => {
    const engine = new BotEngine(R)
    engine.setState('triangle', 1)
    engine.setColor('#e8483f', '#fcece7', 1)
    expect(engine.sample(2, true)).toEqual(engine.sample(99, true))
  })
})

describe('colour morph', () => {
  it('mixes hex colours and reaches its endpoints', () => {
    expect(mixHex('#3ecf8e', '#3ecf8e', 0.5)).toBe('#3ecf8e')
    expect(mixHex('#3ecf8e', '#e8483f', 0)).toBe('#3ecf8e')
    expect(mixHex('#3ecf8e', '#e8483f', 1)).toBe('#e8483f')
    const engine = new BotEngine(R)
    engine.setColor('#e8483f', '#fcece7', 5)
    expect(engine.sample(6).bodyColor).toBe('#e8483f')
  })
})
