import type { JourneyContext, Persona, Preset, TravelProfile } from './types'

// Existing UserProfile contract + C-Route normalize_profile/allows_edge.
export function profileFor(persona: Persona, preset: Preset): TravelProfile {
  return persona === 'wheelchair'
    ? { mobility: 'wheelchair', preset, max_walk_m: 400, max_transfers: 2, hard_flags: ['no_minibus', 'no_non_lowfloor_bus', 'no_stairs'] }
    : { mobility: 'standard', preset, hard_flags: [] }
}

export function contextKey(context: JourneyContext): string {
  return JSON.stringify([context.origin, context.destination, context.departAt, context.persona, context.preset, resolveProfile(context), [...context.eventIds].sort(), context.eventRevisions])
}

/** Explicit preferences can tighten a selected accessibility preset, never loosen it. */
export function resolveProfile(query: { persona?: Persona; preset: Preset; profile?: TravelProfile }): TravelProfile {
  const base = profileFor(query.persona ?? 'commuter', query.preset)
  if (!query.profile) return base
  const explicit = query.profile
  const rank = { standard: 0, reduced: 1, wheelchair: 2 }
  const mobility = rank[base.mobility] > rank[explicit.mobility] ? base.mobility : explicit.mobility
  const flags = new Set([...base.hard_flags, ...explicit.hard_flags])
  if (mobility !== 'standard') flags.add('no_stairs')
  if (mobility === 'wheelchair') ['no_minibus', 'no_non_lowfloor_bus'].forEach(flag => flags.add(flag))
  const limits = [base.max_walk_m, explicit.max_walk_m, mobility !== 'standard' ? 400 : undefined].filter((n): n is number => n !== undefined)
  const transfers = [base.max_transfers, explicit.max_transfers, mobility === 'wheelchair' ? 2 : undefined].filter((n): n is number => n !== undefined)
  return { ...explicit, mobility, preset: query.preset, hard_flags: [...flags].sort(),
    ...(limits.length ? { max_walk_m: Math.min(...limits) } : {}),
    ...(transfers.length ? { max_transfers: Math.min(...transfers) } : {}) }
}

export function profileLabel(profile: TravelProfile): string {
  const mobility = { standard: 'Standard mobility', reduced: 'Reduced mobility', wheelchair: 'Wheelchair' }[profile.mobility]
  return `${mobility} · ${profile.preset.replaceAll('_', ' ')}${profile.max_walk_m !== undefined ? ` · walking ≤${profile.max_walk_m} m` : ''}${profile.weights ? ' · custom weights' : ''}`
}

export function validateContext(context: JourneyContext): void {
  if (!context.origin || !context.destination || context.origin === context.destination) throw new Error('Choose two different stations in the station planner first.')
  if (!/(Z|[+-]\d\d:\d\d)$/.test(context.departAt) || !Number.isFinite(Date.parse(context.departAt))) throw new Error('Choose a valid departure date and time with a timezone.')
}

/** Abort plus generation guard: even a transport ignoring abort cannot win. */
export class LatestRequest {
  private revision = 0
  private controller?: AbortController
  begin() {
    this.cancel()
    const revision = this.revision
    this.controller = new AbortController()
    return { signal: this.controller.signal, current: () => revision === this.revision }
  }
  cancel() { ++this.revision; this.controller?.abort() }
}
