import { getSnapshot, LiveApiError, queryRoutes, requestJson, type LiveMetaSourceStatus } from './liveTransitApi'
import { profileFor, validateContext } from './p3Context'
import type { JourneyContext, RouteCandidate } from './types'

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
  tool_calls: Array<{ ok: boolean; error?: string; detail?: string; trace?: { tool?: string; provenance?: string; freshness_s?: number } }>
}

export function parseChat(value: unknown): ChatReply {
  if (!object(value) || typeof value.message !== 'string' || typeof value.fallback !== 'boolean' || !Array.isArray(value.tool_calls) || !value.tool_calls.every(call => object(call) && typeof call.ok === 'boolean' && ['error', 'detail'].every(key => call[key] === undefined || typeof call[key] === 'string') && (call.trace === undefined || object(call.trace) && ['tool', 'provenance'].every(key => call.trace && (call.trace as Record<string, unknown>)[key] === undefined || typeof (call.trace as Record<string, unknown>)[key] === 'string') && (call.trace.freshness_s === undefined || finite(call.trace.freshness_s))))) throw new Error('Malformed chat response. No seed answer was substituted.')
  const routes = value.routes === undefined ? [] : checkedRoutes(value.routes)
  return { message: value.message, fallback: value.fallback, routes, tool_calls: value.tool_calls as ChatReply['tool_calls'] }
}

export function chatPayload(context: JourneyContext, message: string) {
  validateContext(context)
  if (context.persona !== 'commuter' || context.preset !== 'fastest') throw new LiveApiError('POST', '/api/ai/chat', 0, 'CONTRACT_PENDING', 'Personalized chat is blocked: B/C must confirm profile and preference fields. The current endpoint uses standard mobility / fastest defaults. Use the station planner for your selected profile.')
  // Do not send a made-up profile id or silently ignored profile/preset fields.
  return { message, origin: context.origin, destination: context.destination, depart_at: context.departAt }
}

export async function chat(context: JourneyContext, message: string, signal: AbortSignal): Promise<ChatReply> {
  return parseChat(await requestJson('POST', '/api/ai/chat', chatPayload(context, message), { signal, timeoutMs: 30000 }))
}

export interface Comparison {
  context: JourneyContext
  commuter: RouteCandidate[]
  wheelchair: RouteCandidate[]
  observedSnapshot: string
  verified: false
}

export async function compare(context: JourneyContext, signal: AbortSignal): Promise<Comparison> {
  validateContext(context)
  const before = await getSnapshot(context.departAt)
  const responses = await Promise.all([
    queryRoutes({ ...context, persona: 'commuter', preset: 'fastest' }, context.eventIds, signal),
    queryRoutes({ ...context, persona: 'wheelchair', preset: 'most_stable' }, context.eventIds, signal),
  ])
  const after = await getSnapshot(context.departAt)
  if (signal.aborted) throw new Error('Comparison cancelled.')
  if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('The approved network changed during comparison. Retry both profiles together.')
  const [commuter, wheelchair] = responses.map(checkedRoutes)
  const bad = wheelchair.some(route => route.total.walk_m > 400 || route.total.transfers > 2 || route.legs.some(leg => leg.mode === 'MINIBUS' || leg.accessible !== true))
  if (bad) throw new Error('The backend returned a route violating the wheelchair constraints. Results withheld; report this to C.')
  // Matching surrounding reads is not proof that both route queries pinned
  // the same snapshot. Current public route responses contain no such token.
  return { context: structuredClone(context), commuter, wheelchair, observedSnapshot: before.snapshot_id, verified: false }
}

export const comparisonProfiles = { commuter: profileFor('commuter', 'fastest'), wheelchair: profileFor('wheelchair', 'most_stable') }

export interface Strategy {
  policy: string
  total_delay_person_min: number
  avg_delay_min: number
  p95_wait_min: number
  overloaded_routes: number
  route_load?: Array<{ route_id: string; users: number; capacity_per_hour: number; load_factor: number; overloaded: boolean }>
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
  delta?: { delay_reduction_pct?: number }
}

export function parseSimulation(value: unknown): Simulation {
  if (!object(value) || typeof value.scenario_id !== 'string' || !finite(value.population) || value.population <= 0 || !strings(value.assumptions) || !value.assumptions.length || !strings(value.time_range) || value.time_range.length !== 2 || !['real', 'real-derived', 'simulated'].includes(String(value.provenance))) throw new Error('Malformed simulation metadata; no fixture was substituted.')
  for (const key of ['baseline', 'guided']) {
    const result = value[key]
    if (!object(result) || typeof result.policy !== 'string' || !['total_delay_person_min', 'avg_delay_min', 'p95_wait_min', 'overloaded_routes'].every(field => finite(result[field]) && (result[field] as number) >= 0)) throw new Error('Malformed simulation metrics.')
    if (result.unstoppable_demand !== undefined && (!finite(result.unstoppable_demand) || result.unstoppable_demand < 0)) throw new Error('Invalid capacity gap.')
    if (result.shares !== undefined && (!Array.isArray(result.shares) || !result.shares.every(row => object(row) && typeof row.route_id === 'string' && finite(row.share) && row.share >= 0 && row.share <= 1 && finite(row.users) && row.users >= 0))) throw new Error('Invalid allocation shares.')
    if (result.route_load !== undefined && (!Array.isArray(result.route_load) || !result.route_load.every(row => object(row) && typeof row.route_id === 'string' && ['users', 'capacity_per_hour', 'load_factor'].every(field => finite(row[field]) && (row[field] as number) >= 0) && typeof row.overloaded === 'boolean'))) throw new Error('Invalid route load.')
  }
  if (value.delta !== undefined && (!object(value.delta) || value.delta.delay_reduction_pct !== undefined && !finite(value.delta.delay_reduction_pct))) throw new Error('Invalid simulation delta.')
  for (const key of ['generated_at', 'query_time']) if (value[key] !== undefined && (typeof value[key] !== 'string' || !Number.isFinite(Date.parse(value[key] as string)))) throw new Error('Invalid simulation timestamp.')
  if (value.window_min !== undefined && (!finite(value.window_min) || value.window_min <= 0)) throw new Error('Invalid simulation window.')
  return value as unknown as Simulation
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
  return { name: typeof source === 'string' ? source : source.name, lastOk: typeof source === 'string' ? undefined : source.last_ok, status: 'Collection status unavailable — public contract pending B.', classification: 'Classification unavailable from this endpoint.' }
}
