// Clock-free bot engine, adapted from jeremy-prt/bloub (MIT, Copyright (c)
// 2026 Jérémy Perret), src/bot/{engine,states,decor}.ts. See
// frontend/THIRD_PARTY_NOTICES.md.
//
// `sample(t)` is a pure function of time: state changes enter through
// time-stamped setters, never by reading a clock inside the sampler, so
// pause, resume and seek always render the same picture, and the render is
// testable without a DOM.
//
// The full bloub catalogue has 14 states; this adaptation keeps the three
// this app needs, with their measured constants unchanged:
//   idle     — the resting ball and face (bloub `idle`)
//   thinking — the three-dot pulse (bloub `thinking`)
//   triangle — the measured disruption silhouette (bloub `play`'s still
//              triangle, gaze and eyes, without its celebratory swoosh)

import { blinkScale, eyePoses, liveliness, EYE_H, EYE_SPLIT, EYE_W, REST_GAZE, type HeadGaze } from './face'
import { clamp, easings, lerp, r2, TAU } from './math'
import { blend, capsulePath, circle, closedPath, radiusAtAngle, silhouette, toPoints, type Silhouette } from './shape'

export type AvatarStateId = 'idle' | 'thinking' | 'triangle'

export interface EyeCfg {
  /** local width (capsule short axis), in ball-radius units */
  w: number
  /** local height (long axis) */
  h: number
  /** 1 = open, 0 = closed */
  open: number
}

interface Dot {
  x: number
  y: number
  r: number
  opacity: number
}

export interface Pose {
  sil: Silhouette
  offX: number
  offY: number
  gaze: HeadGaze
  split: number
  eyes: [EyeCfg, EyeCfg]
  /** eyes opacity: serves states without a face */
  eyeAlpha: number
  bodyAlpha: number
  dots: Dot[]
}

const pair = (w: number, h: number): [EyeCfg, EyeCfg] => [
  { w, h, open: 1 },
  { w, h, open: 1 }
]

function base(over: Partial<Pose> = {}): Pose {
  return {
    sil: circle(1),
    offX: 0,
    offY: 0,
    gaze: { ...REST_GAZE },
    split: EYE_SPLIT,
    eyes: pair(EYE_W, EYE_H),
    eyeAlpha: 1,
    bodyAlpha: 1,
    dots: [],
    ...over
  }
}

/* ------------------------------------------------------------------ states */

/** Pulse wave travelling across the three dots, left to right. (bloub states.ts) */
function dotPulse(t: number, index: number): number {
  const p = ((((t - index * 0.5) / 1.5) % 1) + 1) % 1
  const k = p < 0.5 ? 0.5 - 0.5 * Math.cos(p * TAU) : 0
  return clamp(k * 2)
}

// Measured x positions of the three dots: -0.557 / -0.013 / +0.532, y = 0.
// Radius 0.165, pulse peak +25 %. (bloub decor.ts)
const DOT_X = [-0.557, -0.013, 0.532] as const
const DOT_R = 0.165
const DOT_PEAK = 1.25

// The triangle does not spin in place: its centre rides a circle of radius
// 0.213 around the origin (measured). At rest (rot 0) that leaves cy = 0.213,
// which is what makes it read as tipped rather than centred.
// (bloub states.ts, TRI_ORBIT)
const TRI_CY = 0.213

function thinkingPose(t: number): Pose {
  const mid = dotPulse(t, 1)
  // The side dots emerge from the flanks of the ball: in the video they stay
  // merged with it for 1-2 frames before detaching.
  const emerge = 0.3 + 0.7 * easings.easeOutCubic(clamp(t / 0.3))
  return base({
    // the ball BECOMES the middle dot: the morph stays continuous
    sil: circle(DOT_R * (1 + (DOT_PEAK - 1) * mid), { cx: DOT_X[1]! }),
    eyeAlpha: 0,
    dots: [0, 2].map((i) => {
      const k = dotPulse(t, i)
      return {
        x: DOT_X[i]! * emerge,
        y: 0,
        r: DOT_R * (1 + (DOT_PEAK - 1) * k),
        opacity: 0.55 + 0.45 * k
      }
    })
  })
}

// bloub `play`: still measured triangle + its gaze and eyes. The swoosh
// bouquet that sweeps over it in the original is celebratory and is not
// carried over to the disruption reading.
const trianglePose = (): Pose =>
  base({
    sil: silhouette('triangle', { cy: TRI_CY }),
    gaze: { yaw: 12, pitch: -8, roll: -6 },
    split: 15,
    eyes: pair(0.18, 0.34)
  })

interface StateDef {
  /** entry morph duration */
  morph: number
  /** true = the entry is masked by a blink, as in the video */
  blinkIn: boolean
  pose(t: number): Pose
}

const STATES: Record<AvatarStateId, StateDef> = {
  idle: { morph: 0.45, blinkIn: false, pose: () => base() },
  thinking: { morph: 0.4, blinkIn: true, pose: thinkingPose },
  triangle: { morph: 0.5, blinkIn: true, pose: trianglePose }
}

/** Most readable instant of each state (bloub states.ts, POSES). Used for frozen frames. */
const FROZEN_AT: Record<AvatarStateId, number> = { idle: 1, thinking: 1.1, triangle: 0.9 }

/* ------------------------------------------------------------------ render */

export interface RenderedEye {
  d: string
  matrix: string
  alpha: number
}

export interface BotFrame {
  bodyPath: string
  bodyColor: string
  haloColor: string
  eyes: RenderedEye[]
  dots: Dot[]
}

const lerpEye = (a: EyeCfg, b: EyeCfg, t: number): EyeCfg => ({
  w: lerp(a.w, b.w, t),
  h: lerp(a.h, b.h, t),
  open: lerp(a.open, b.open, t)
})

/** Interpolates two poses. Dots cross-fade in opacity, not geometry. */
function blendPose(a: Pose, b: Pose, t: number): Pose {
  const out = 1 - t
  return {
    sil: blend(a.sil, b.sil, t),
    offX: lerp(a.offX, b.offX, t),
    offY: lerp(a.offY, b.offY, t),
    gaze: {
      yaw: lerp(a.gaze.yaw, b.gaze.yaw, t),
      pitch: lerp(a.gaze.pitch, b.gaze.pitch, t),
      roll: lerp(a.gaze.roll, b.gaze.roll, t)
    },
    split: lerp(a.split, b.split, t),
    eyes: [lerpEye(a.eyes[0]!, b.eyes[0]!, t), lerpEye(a.eyes[1]!, b.eyes[1]!, t)],
    eyeAlpha: lerp(a.eyeAlpha, b.eyeAlpha, t),
    bodyAlpha: lerp(a.bodyAlpha, b.bodyAlpha, t),
    dots: [
      ...a.dots.map((d) => ({ ...d, opacity: d.opacity * out })),
      ...b.dots.map((d) => ({ ...d, opacity: d.opacity * t }))
    ]
  }
}

/** Mixes two hex colours. (bloub skins.ts) */
export function mixHex(from: string, to: string, t: number): string {
  const parse = (h: string) => {
    const v = parseInt(h.slice(1), 16)
    return [(v >> 16) & 255, (v >> 8) & 255, v & 255]
  }
  const a = parse(from)
  const b = parse(to)
  const c = a.map((x, i) => Math.round(x + (b[i]! - x) * t))
  return `#${c.map((x) => x.toString(16).padStart(2, '0')).join('')}`
}

// bloub palette entries used by this project: 'vert' and 'rouge' unchanged.
export const COLORS = {
  body: { calm: '#3ecf8e', issue: '#e8483f' },
  halo: { calm: '#e8efde', issue: '#fcece7' }
} as const

const COLOR_MORPH = 0.45

export class BotEngine {
  /** radius of the resting ball, in viewBox units */
  readonly scale: number

  private cur: AvatarStateId
  private prev: AvatarStateId | null = null
  /**
   * Frozen departure pose, laid down only when a state change arrives while a
   * fade is already in flight. Cf. `setState` in the original engine.
   */
  private departFige: Pose | null = null
  private tCur = 0
  private tPrev = 0
  private blinkAt = -10
  private body: string
  private bodyPrev: string | null = null
  private halo: string
  private haloPrev: string | null = null
  private colorAt = -1e3

  constructor(scale: number, initial: { state?: AvatarStateId; body?: string; halo?: string } = {}) {
    this.scale = scale
    this.cur = initial.state ?? 'idle'
    this.body = initial.body ?? COLORS.body.calm
    this.halo = initial.halo ?? COLORS.halo.calm
  }

  get state(): AvatarStateId {
    return this.cur
  }

  /**
   * New state, time-stamped. A change arriving mid-fade freezes the current
   * composite pose and blends from it — continuous by construction, however
   * many changes are chained. And only then: freezing at every change would
   * stop the outgoing state's animation dead for the whole fade.
   */
  setState(id: AvatarStateId, now: number) {
    if (id === this.cur) return
    const morph = STATES[this.cur].morph
    const midFade = this.prev !== null && now - this.tCur < morph
    this.departFige = midFade ? this.poseComposee(now) : null
    this.prev = this.cur
    this.tPrev = this.tCur
    this.cur = id
    this.tCur = now
    // In the video, every shape change is masked by a blink.
    if (STATES[id].blinkIn) this.blinkAt = now
  }

  /** Colour change, time-stamped, with the same curve as the shape morph. */
  setColor(body: string, halo: string, now: number) {
    if (body === this.body && halo === this.halo) return
    this.bodyPrev = this.body
    this.haloPrev = this.halo
    this.body = body
    this.halo = halo
    this.colorAt = now
  }

  /** Composite pose at `now`, including any in-flight fade. */
  private poseComposee(now: number): Pose {
    const def = STATES[this.cur]
    const pose = def.pose(Math.max(0, now - this.tCur))
    const since = now - this.tCur
    if (since >= def.morph) return pose
    const origine = this.departFige ?? (this.prev ? STATES[this.prev].pose(Math.max(0, now - this.tPrev)) : null)
    if (!origine) return pose
    return blendPose(origine, pose, easings.easeOutQuint(clamp(since / def.morph)))
  }

  /**
   * `frozen` renders a still picture: the state at its most readable instant
   * (POSES), morph complete, no drift, blink or breathing. Bloub exposes the
   * same idea as its `frozenAt` prop.
   */
  sample(now: number, frozen = false): BotFrame {
    const pose = frozen ? STATES[this.cur].pose(FROZEN_AT[this.cur]) : this.poseComposee(now)

    // --- life at rest ---
    const alive = pose.eyeAlpha > 0.01
    const life = frozen
      ? { dYaw: 0, dPitch: 0, dRoll: 0, lid: 1, driftX: 0, driftY: 0, breath: 1 }
      : liveliness(now, { wander: alive, blink: alive })

    const gaze = {
      yaw: pose.gaze.yaw + life.dYaw,
      pitch: pose.gaze.pitch + life.dPitch,
      // roll follows nothing: the head is tilted -13deg in the video, and
      // making it roll breaks that signature
      roll: pose.gaze.roll + life.dRoll
    }

    // blink forced by the state change, on top of the calendar
    const forced = clamp((now - this.blinkAt) / 0.2)
    const forcedLid = !frozen && forced < 1 ? Math.abs(forced * 2 - 1) : 1
    const lid = Math.min(life.lid, forcedLid)

    const offX = pose.offX + life.driftX
    const offY = pose.offY + life.driftY

    // --- body ---
    const sil: Silhouette = {
      ...pose.sil,
      cx: pose.sil.cx + offX,
      cy: pose.sil.cy + offY,
      sy: pose.sil.sy * life.breath
    }
    const bodyPath = closedPath(toPoints(sil, this.scale))

    // --- eyes ---
    // The eyes live on a sphere of radius 1; as soon as the silhouette is no
    // longer a circle, they are brought back in proportion to the real radius
    // in their direction, otherwise they overflow and the mask clips them.
    const bodyRadius = (x: number, y: number) =>
      radiusAtAngle(pose.sil.radii, Math.atan2(y, x) - pose.sil.rot)

    const eyes: RenderedEye[] = []
    if (pose.eyeAlpha > 0.01) {
      const poses = eyePoses(gaze, this.scale, pose.split)
      for (let i = 0; i < 2; i++) {
        const e = poses[i]!
        if (e.depth <= 0.02) continue
        const cfg = pose.eyes[i]!
        const fit = bodyRadius(e.x, e.y)
        // The blink applies AFTER all of this: it is a vertical squash in
        // screen frame, not along the capsule's axis.
        const k = blinkScale(Math.min(lid, cfg.open))
        eyes.push({
          d: capsulePath(cfg.w * this.scale, cfg.h * this.scale),
          matrix: `matrix(${r2(e.a)},${r2(e.b * k)},${r2(e.c)},${r2(e.d * k)},${r2(e.x * fit + offX * this.scale)},${r2(e.y * fit + offY * this.scale)})`,
          alpha: pose.eyeAlpha * clamp(e.depth / 0.12)
        })
      }
    }

    // --- colour ---
    const k = easings.easeOutQuint(clamp((now - this.colorAt) / COLOR_MORPH))
    const bodyColor = this.bodyPrev ? mixHex(this.bodyPrev, this.body, k) : this.body
    const haloColor = this.haloPrev ? mixHex(this.haloPrev, this.halo, k) : this.halo

    return {
      bodyPath,
      bodyColor,
      haloColor,
      eyes,
      dots: pose.dots
        .filter((p) => p.opacity > 0.01 && p.r > 0.0005)
        .map((p) => ({ ...p, x: (p.x + offX) * this.scale, y: (p.y + offY) * this.scale, r: p.r * this.scale }))
    }
  }
}
