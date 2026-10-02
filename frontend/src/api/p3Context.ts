import type { JourneyContext, Persona, Preset, TravelProfile } from './types'

// Existing UserProfile contract + C-Route normalize_profile/allows_edge.
export function profileFor(persona: Persona, preset: Preset): TravelProfile {
  return persona === 'wheelchair'
    ? { mobility: 'wheelchair', preset, max_walk_m: 400, max_transfers: 2, hard_flags: ['no_stairs', 'no_minibus', 'no_non_lowfloor_bus'] }
    : { mobility: 'standard', preset, hard_flags: [] }
}

export function contextKey(context: JourneyContext): string {
  return JSON.stringify([context.origin, context.destination, context.departAt, context.persona, context.preset, [...context.eventIds].sort(), context.eventRevisions])
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
