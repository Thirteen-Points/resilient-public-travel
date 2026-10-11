import { getSnapshot, LiveApiError, queryRoutesWithMetadata, requestJson, type LiveMetaSourceStatus } from './liveTransitApi'
import { profileFor, resolveProfile, validateContext } from './p3Context'
import { parseEffectiveProfile } from './preferences'
import type { JourneyContext, RouteCandidate, TravelProfile } from './types'

const object = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === 'object' && !Array.isArray(value)
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(item => typeof item === 'string')

export function checkedRoutes(value: unknown): RouteCandidate[] {
  if (!Array.isArray(value)) throw new Error('Backend routes must be an array.')
  for (const route of value) {
    if (!object(route) || typeof route.route_id !== 'string' || typeof route.label !== 'string' || typeof route.explain !== 'string' || !['real', 'real-derived', 'simulated'].includes(String(route.provenance)) || !finite(route.score) || !strings(route.warnings) || !strings(route.notes) || !object(route.total)) throw new Error('Malformed backend route; no estimate was substituted.')
    const t = route.total
    if (!['time_s', 'transfers', 'walk_m', 'fare_hkd', 'reliability', 'freshness_s'].every(key => finite(t[key]) && (t[key] as number) >= 0) || !Array.isArray(t.time_range_s) || t.time_range_s.length !== 2 || !t.time_range_s.every(finite)) throw new Error('Malformed backend route totals.')
    if (!Array.isArray(route.legs) || !route.legs.every(leg => object(leg) && typeof leg.mode === 'string' && typeof leg.from === 'string' && typeof leg.to === 'string' && finite(leg.walk_m) && [true, false, 'partial', null].includes(leg.accessible as boolean | string | null))) throw new Error('Malformed backend route legs.')
    if (route.score_breakdown !== undefined && (!Array.isArray(route.score_breakdown) || !route.score_breakdown.every(row => object(row) && typeof row.criterion === 'string' && ['normalized', 'weight', 'contribution'].every(key => finite(row[key]))))) throw new Error('Malformed backend score breakdown.')
  }
  return value as RouteCandidate[]
}

export interface ChatReply {
  message: string
  fallback: boolean
  routes: RouteCandidate[]
  graph_snapshot?: string | null
  effective_profile?: TravelProfile | null
  tool_calls: Array<{ ok: boolean; error?: string; detail?: string; trace?: { tool?: string; provenance?: string; freshness_s?: number } }>
}

export function parseChat(value: unknown): ChatReply {
  if (!object(value) || typeof value.message !== 'string' || typeof value.fallback !== 'boolean' || !Array.isArray(value.tool_calls) || !value.tool_calls.every(call => object(call) && typeof call.ok === 'boolean' && ['error', 'detail'].every(key => call[key] === undefined || typeof call[key] === 'string') && (call.trace === undefined || object(call.trace) && ['tool', 'provenance'].every(key => call.trace && (call.trace as Record<string, unknown>)[key] === undefined || typeof (call.trace as Record<string, unknown>)[key] === 'string') && (call.trace.freshness_s === undefined || finite(call.trace.freshness_s))))) throw new Error('Malformed chat response. No seed answer was substituted.')
  const routes = value.routes === undefined ? [] : checkedRoutes(value.routes)
  if (value.graph_snapshot != null && (typeof value.graph_snapshot !== 'string' || !value.graph_snapshot.trim())) throw new Error('Malformed chat snapshot metadata.')
  const profile = value.effective_profile == null ? value.effective_profile as null | undefined : parseEffectiveProfile(value.effective_profile)
  return { message: value.message, fallback: value.fallback, routes, tool_calls: value.tool_calls as ChatReply['tool_calls'], graph_snapshot: value.graph_snapshot as string | null | undefined, effective_profile: profile }
}

export function chatPayload(context: JourneyContext, message: string) {
  validateContext(context)
  if (context.modes?.length || context.requiredModes?.length) throw new LiveApiError('POST', '/api/ai/chat', 0, 'CONTRACT_PENDING', 'The chat contract does not accept transport filters. Use the planner for the selected transport mode.')
  if (context.preset === 'least_walking') throw new LiveApiError('POST', '/api/ai/chat', 0, 'CONTRACT_PENDING', 'Less walking preset is unavailable. Apply a walking limit in the planner instead.')
  return { message, origin: context.origin, destination: context.destination, depart_at: context.departAt, profile: resolveProfile(context) }
}

export async function chat(context: JourneyContext, message: string, signal: AbortSignal): Promise<ChatReply> {
  return parseChat(await requestJson('POST', '/api/ai/chat', chatPayload(context, message), { signal, timeoutMs: 30000 }))
}

export interface Comparison {
  context: JourneyContext
  commuter: RouteCandidate[]
  wheelchair: RouteCandidate[]
  observedSnapshot: string
  snapshotId: string | null
  verified: boolean
}

export async function compare(context: JourneyContext, signal: AbortSignal): Promise<Comparison> {
  validateContext(context)
  for (let attempt = 0; attempt < 2; attempt++) {
    const before = await getSnapshot(context.departAt, signal)
    const responses = await Promise.all([
      queryRoutesWithMetadata({ ...context, profile: comparisonProfiles.commuter, persona: 'commuter', preset: 'fastest' }, context.eventIds, signal),
      queryRoutesWithMetadata({ ...context, profile: comparisonProfiles.wheelchair, persona: 'wheelchair', preset: 'most_stable' }, context.eventIds, signal),
    ])
    const after = await getSnapshot(context.departAt, signal)
    if (signal.aborted) throw new Error('Comparison cancelled.')
    const [a, b] = responses.map(response => response.snapshotId)
    const verified = Boolean(a && b && a === b)
    if (a && b ? a !== b : JSON.stringify(before) !== JSON.stringify(after)) {
      if (attempt === 0) continue
      throw new Error('The approved network changed during comparison. Both profiles were retried; previous results retained.')
    }
    const [commuter, wheelchair] = responses.map(response => checkedRoutes(response.routes))
    const bad = wheelchair.some(route => route.total.walk_m > 400 || route.total.transfers > 2 || route.legs.some(leg => leg.mode === 'MINIBUS' || leg.accessible !== true))
    if (bad) throw new Error('The backend returned a route violating the wheelchair constraints. Results withheld; report this to the maintainer.')
    return { context: structuredClone(context), commuter, wheelchair, observedSnapshot: after.snapshot_id, snapshotId: verified ? a : null, verified }
  }
  throw new Error('Comparison unavailable.')
}

export const comparisonProfiles = { commuter: profileFor('commuter', 'fastest'), wheelchair: profileFor('wheelchair', 'most_stable') }

export interface Strategy {
  policy: string
  total_delay_person_min: number
  avg_delay_min: number
  p95_wait_min: number
  overloaded_routes: number
  route_load?: Array<{ route_id: string; users: number; capacity_per_hour: number; load_factor: number; overloaded: boolean; assigned_users?: number }>
  served_demand?: number
  assigned_demand?: number
  unmet_demand?: number
  unassigned_demand?: number
  overloaded_shared_resources?: number
  resource_load?: Array<{ resource_id: string; assigned_users: number; physical_capacity: number; target_capacity: number; physical_capacity_excess: number; target_capacity_excess: number }>
  unstoppable_demand?: number
  shares?: Array<{ route_id: string; share: number; users: number }>
}
export interface Simulation {
  scenario_id: string
  population: number
  baseline: Strategy
  guided: Strategy
  time_range: [string, string]
  assumptions: string[]
  provenance: 'real' | 'real-derived' | 'simulated'
  generated_at?: string
  query_time?: string
  window_min?: number
  seed?: number
  od_count?: number
  capacity_model?: { shared_resource_count?: number; note?: string; capacity_unit?: string }
  fairness?: { max_extra_delay_min?: number; guided_accessibility_violations?: number; guided_fairness_violations?: number }
  delta?: { delay_reduction_pct?: number }
}

export function parseSimulation(value: unknown): Simulation {
  if (!object(value) || typeof value.scenario_id !== 'string' || !finite(value.population) || value.population <= 0 || !strings(value.assumptions) || !value.assumptions.length || !strings(value.time_range) || value.time_range.length !== 2 || !['real', 'real-derived', 'simulated'].includes(String(value.provenance))) throw new Error('Malformed simulation metadata; no fixture was substituted.')
  for (const key of ['baseline', 'guided']) {
    const result = value[key]
    if (!object(result) || typeof result.policy !== 'string' || !['total_delay_person_min', 'avg_delay_min', 'p95_wait_min', 'overloaded_routes'].every(field => finite(result[field]) && (result[field] as number) >= 0)) throw new Error('Malformed simulation metrics.')
    for (const field of ['unstoppable_demand', 'served_demand', 'assigned_demand', 'unmet_demand', 'unassigned_demand', 'overloaded_shared_resources']) if (result[field] !== undefined && (!finite(result[field]) || result[field] < 0 || !Number.isInteger(result[field]))) throw new Error('Invalid demand or capacity count.')
    if (result.shares !== undefined && (!Array.isArray(result.shares) || !result.shares.every(row => object(row) && typeof row.route_id === 'string' && finite(row.share) && row.share >= 0 && row.share <= 1 && finite(row.users) && row.users >= 0))) throw new Error('Invalid allocation shares.')
    if (result.route_load !== undefined && (!Array.isArray(result.route_load) || !result.route_load.every(row => object(row) && typeof row.route_id === 'string' && ['users', 'capacity_per_hour', 'load_factor'].every(field => finite(row[field]) && (row[field] as number) >= 0) && typeof row.overloaded === 'boolean' && (row.assigned_users === undefined || finite(row.assigned_users) && row.assigned_users >= 0 && Number.isInteger(row.assigned_users))))) throw new Error('Invalid route load.')
    if (result.resource_load !== undefined && (!Array.isArray(result.resource_load) || !result.resource_load.every(row => object(row) && typeof row.resource_id === 'string' && ['assigned_users', 'physical_capacity', 'target_capacity', 'physical_capacity_excess', 'target_capacity_excess'].every(field => finite(row[field]) && row[field] >= 0)))) throw new Error('Invalid shared-resource load.')
  }
  if (value.delta !== undefined && (!object(value.delta) || value.delta.delay_reduction_pct !== undefined && !finite(value.delta.delay_reduction_pct))) throw new Error('Invalid simulation delta.')
  for (const key of ['generated_at', 'query_time']) if (value[key] !== undefined && (typeof value[key] !== 'string' || !Number.isFinite(Date.parse(value[key] as string)))) throw new Error('Invalid simulation timestamp.')
  if (value.window_min !== undefined && (!finite(value.window_min) || value.window_min <= 0)) throw new Error('Invalid simulation window.')
  for (const key of ['seed', 'od_count']) if (value[key] !== undefined && (!finite(value[key]) || !Number.isInteger(value[key]) || value[key] < 0)) throw new Error('Invalid simulation inputs.')
  for (const key of ['capacity_model', 'fairness']) if (value[key] !== undefined && !object(value[key])) throw new Error('Invalid simulation model metadata.')
  if (object(value.capacity_model)) {
    if (value.capacity_model.shared_resource_count !== undefined && (!finite(value.capacity_model.shared_resource_count) || value.capacity_model.shared_resource_count < 0)) throw new Error('Invalid resource count.')
    for (const key of ['note', 'capacity_unit']) if (value.capacity_model[key] !== undefined && typeof value.capacity_model[key] !== 'string') throw new Error('Invalid capacity model description.')
  }
  if (object(value.fairness)) for (const key of ['max_extra_delay_min', 'guided_accessibility_violations', 'guided_fairness_violations']) if (value.fairness[key] !== undefined && (!finite(value.fairness[key]) || value.fairness[key] < 0)) throw new Error('Invalid fairness metadata.')
  return value as unknown as Simulation
}

export const P3_SCENARIOS = [
  { id: 'm2_six_station_directed_od_am_peak_p3_shared_segments', label: 'P3 · shared-segment baseline' },
  { id: 'm2_six_station_directed_od_am_peak_p3_shared_segments_residual_10pct', label: 'P3 · 10% residual-capacity stress test' },
  { id: 'm2_six_station_directed_od_am_peak', label: 'Historical M2 · route buckets' },
  { id: 'scn_huh_exc_closed_am_peak', label: 'Historical M0 · single scenario' },
] as const

/** Chart shares use explicit assignments / total population; never renormalize served demand. */
export function allocationRows(value: Simulation): Array<{ label: string; users: number; share: number }> | null {
  const loads = value.guided.route_load, unassigned = value.guided.unassigned_demand
  if (!loads || unassigned === undefined || loads.some(row => row.assigned_users === undefined)) return null
  const total = loads.reduce((sum, row) => sum + row.assigned_users!, 0)
  if (total + unassigned !== value.population || value.guided.assigned_demand !== undefined && total !== value.guided.assigned_demand) return null
  const sorted = [...loads].filter(row => row.assigned_users! > 0).sort((a, b) => b.assigned_users! - a.assigned_users! || a.route_id.localeCompare(b.route_id))
  const rows = sorted.slice(0, 5).map(row => ({ label: row.route_id, users: row.assigned_users!, share: row.assigned_users! / value.population }))
  if (sorted.length > 5) { const users = sorted.slice(5).reduce((sum, row) => sum + row.assigned_users!, 0); rows.push({ label: `Other routes (${sorted.length - 5})`, users, share: users / value.population }) }
  rows.push({ label: 'Unassigned', users: unassigned, share: unassigned / value.population })
  return rows
}

export async function simulation(scenario: string, signal: AbortSignal): Promise<Simulation> {
  if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(scenario)) throw new Error('Enter a valid scenario id supplied by C.')
  const result = parseSimulation(await requestJson('GET', `/api/sim/result?scenario_id=${encodeURIComponent(scenario)}`, undefined, { signal }))
  if (result.scenario_id !== scenario) throw new Error('API returned a different scenario; result withheld.')
  return result
}

export function delayOutcome(value: Simulation): string {
  if (value.guided.total_delay_person_min > value.baseline.total_delay_person_min) return 'Guided delay is higher. This scenario shows no delay improvement.'
  if (value.guided.total_delay_person_min === value.baseline.total_delay_person_min) return 'Delay is unchanged. This scenario shows no delay improvement.'
  return 'Guided delay is lower in this simulated scenario; remaining overload and capacity gaps are shown below.'
}

export function sourceView(source: string | LiveMetaSourceStatus) {
  return { name: typeof source === 'string' ? source : source.name, lastOk: typeof source === 'string' ? undefined : source.last_ok, status: 'Collection status unavailable from /api/meta.', classification: 'Classification unavailable from this endpoint.' }
}
