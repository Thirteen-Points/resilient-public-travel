import { requestJson } from './liveTransitApi'
import { resolveProfile } from './p3Context'
import type { TravelProfile } from './types'

export const WEIGHT_CRITERIA = ['time', 'transfers', 'walk', 'price', 'comfort', 'reliability', 'carbon', 'freshness'] as const
const FLAGS = ['no_stairs', 'no_minibus', 'no_non_lowfloor_bus']
const object = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === 'object' && !Array.isArray(value)
const nonnegative = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value >= 0

export interface PreferencePatch {
  mobility?: TravelProfile['mobility'] | null
  max_walk_m?: number | null
  hard_flags: string[]
  price_sensitive?: number | null
  weights?: Record<string, number> | null
}
export interface PreferenceResult { patch: PreferencePatch; explanation: string; method: string }

export function validWeights(value: unknown): value is Record<string, number> {
  return object(value) && Object.keys(value).length === WEIGHT_CRITERIA.length && WEIGHT_CRITERIA.every(key => nonnegative(value[key]) && value[key] <= 1) && Math.abs(Object.values(value).reduce<number>((sum, n) => sum + Number(n), 0) - 1) < 1e-6
}

export function parsePreference(value: unknown): PreferenceResult {
  if (!object(value) || !object(value.patch) || typeof value.explanation !== 'string' || !value.explanation.trim() || typeof value.method !== 'string' || !value.method.trim()) throw new Error('Malformed preference response; current settings retained.')
  const p = value.patch
  if (Object.keys(p).some(key => !['mobility', 'max_walk_m', 'hard_flags', 'price_sensitive', 'weights'].includes(key)) ||
      p.mobility != null && !['standard', 'reduced', 'wheelchair'].includes(String(p.mobility)) ||
      p.max_walk_m != null && (!nonnegative(p.max_walk_m) || !Number.isInteger(p.max_walk_m) || p.max_walk_m > 800) ||
      !Array.isArray(p.hard_flags) || !p.hard_flags.every(flag => typeof flag === 'string' && FLAGS.includes(flag)) ||
      p.price_sensitive != null && (!nonnegative(p.price_sensitive) || p.price_sensitive > 1) ||
      p.weights != null && !validWeights(p.weights)) throw new Error('Invalid preference patch; current settings retained.')
  return value as unknown as PreferenceResult
}

export async function preference(text: string, profile: TravelProfile, signal: AbortSignal): Promise<PreferenceResult> {
  if (!text.trim() || text.length > 500) throw new Error('Describe your preferences in 1–500 characters.')
  return parsePreference(await requestJson('POST', '/api/persona/parse', { free_text: text.trim(), current_profile: profile }, { signal, timeoutMs: 15000 }))
}

export function applyPreference(profile: TravelProfile, patch: PreferencePatch): TravelProfile {
  const rank = { standard: 0, reduced: 1, wheelchair: 2 }
  const mobility = patch.mobility && rank[patch.mobility] > rank[profile.mobility] ? patch.mobility : profile.mobility
  const limits = [profile.max_walk_m, patch.max_walk_m].filter((n): n is number => n != null)
  return resolveProfile({ preset: profile.preset, profile: { ...profile, mobility,
    hard_flags: [...new Set([...profile.hard_flags, ...patch.hard_flags])],
    ...(limits.length ? { max_walk_m: Math.min(...limits) } : {}),
    ...(patch.weights ? { weights: { ...patch.weights } } : {}) } })
}

/** Response metadata is optional on older servers; never manufacture it. */
export function parseEffectiveProfile(value: unknown): TravelProfile {
  if (!object(value) || !['standard', 'reduced', 'wheelchair'].includes(String(value.mobility)) || !['fastest', 'most_stable', 'fewest_transfers'].includes(String(value.preset)) || !Array.isArray(value.hard_flags) || !value.hard_flags.every(flag => typeof flag === 'string' && FLAGS.includes(flag))) throw new Error('Malformed effective profile metadata.')
  for (const key of ['max_walk_m', 'max_transfers', 'walking_speed_mps']) if (value[key] !== undefined && !nonnegative(value[key])) throw new Error('Malformed effective profile limits.')
  if (value.max_transfers !== undefined && !Number.isInteger(value.max_transfers)) throw new Error('Malformed effective profile transfer limit.')
  if (value.weights !== undefined && !validWeights(value.weights)) throw new Error('Malformed effective profile weights.')
  return value as unknown as TravelProfile
}
