// Validation boundary between raw seed JSON and the shared types in ./types.
// Contract: validate, never mutate. Missing optional fields stay missing,
// invalid values are kept as-is and reported as issues so a human can see the
// conflict, and only an unusable overall structure throws — the app fails
// loudly instead of silently rendering fabricated data.

import type { Event, Network, RouteCandidate, Signal } from './types'

export interface NormalizationIssue {
  path: string
  message: string
}

export interface NormalizationResult<T> {
  value: T
  issues: NormalizationIssue[]
}

export class SeedStructureError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SeedStructureError'
  }
}

const PROVENANCE_VALUES: readonly unknown[] = ['real', 'real-derived', 'simulated']
const STATUS_VALUES: readonly unknown[] = ['draft', 'pending_review', 'published', 'updated', 'expired', 'rejected']
const MODE_VALUES: readonly unknown[] = ['MTR', 'BUS', 'MINIBUS', 'WALK', 'FERRY']
const ACCESSIBLE_VALUES: readonly unknown[] = [true, false, 'partial', null]

type Issues = NormalizationIssue[]

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value)

function describe(value: unknown): string {
  if (value === null) return 'null'
  if (Array.isArray(value)) return 'an array'
  return `a ${typeof value}`
}

function expectString(target: Record<string, unknown>, key: string, path: string, issues: Issues): void {
  const value = target[key]
  if (typeof value !== 'string' || value === '') {
    issues.push({ path: `${path}.${key}`, message: `should be a non-empty string but is ${describe(value)}; kept as-is, not fabricated` })
  }
}

function expectFiniteNumber(
  target: Record<string, unknown>, key: string, path: string, issues: Issues,
  predicate?: (value: number) => boolean, expectation?: string,
): void {
  const value = target[key]
  if (!isFiniteNumber(value) || (predicate !== undefined && !predicate(value))) {
    issues.push({ path: `${path}.${key}`, message: `should be ${expectation ?? 'a finite number'} but is ${describe(value)}; kept as-is, not fabricated` })
  }
}

function expectStringArray(target: Record<string, unknown>, key: string, path: string, issues: Issues): void {
  const value = target[key]
  if (!Array.isArray(value) || !value.every(item => typeof item === 'string')) {
    issues.push({ path: `${path}.${key}`, message: `should be an array of strings but is ${describe(value)}` })
  }
}

function expectEnum(target: Record<string, unknown>, key: string, path: string, issues: Issues, allowed: readonly unknown[]): void {
  const value = target[key]
  if (!allowed.includes(value)) {
    const shown = value === undefined ? 'missing' : JSON.stringify(value)
    issues.push({ path: `${path}.${key}`, message: `should be one of [${allowed.join(', ')}] but is ${shown}; kept as-is, not rewritten` })
  }
}

function validateNode(raw: unknown, path: string, issues: Issues): void {
  if (!isRecord(raw)) {
    issues.push({ path, message: `node should be an object but is ${describe(raw)}` })
    return
  }
  expectString(raw, 'id', path, issues)
  expectString(raw, 'name_en', path, issues)
  expectString(raw, 'name_zh', path, issues)
  expectString(raw, 'kind', path, issues)
  expectFiniteNumber(raw, 'lat', path, issues, value => Math.abs(value) <= 90, 'a finite latitude')
  expectFiniteNumber(raw, 'lng', path, issues, value => Math.abs(value) <= 180, 'a finite longitude')
  expectStringArray(raw, 'lines', path, issues)
  expectEnum(raw, 'accessible', path, issues, ACCESSIBLE_VALUES)
  expectEnum(raw, 'provenance', path, issues, PROVENANCE_VALUES)
  if (raw.catchment_m !== undefined) {
    expectFiniteNumber(raw, 'catchment_m', path, issues, value => value > 0, 'a positive catchment radius in metres')
  }
}

function validateLine(raw: unknown, path: string, issues: Issues): void {
  if (!isRecord(raw)) {
    issues.push({ path, message: `line should be an object but is ${describe(raw)}` })
    return
  }
  expectString(raw, 'id', path, issues)
  expectString(raw, 'name_en', path, issues)
  expectEnum(raw, 'mode', path, issues, MODE_VALUES)
  expectStringArray(raw, 'stops', path, issues)
  expectEnum(raw, 'provenance', path, issues, PROVENANCE_VALUES)
}

function validateSegment(raw: unknown, path: string, issues: Issues): void {
  if (!isRecord(raw)) {
    issues.push({ path, message: `affected segment should be an object but is ${describe(raw)}` })
    return
  }
  expectString(raw, 'from_node', path, issues)
  expectString(raw, 'to_node', path, issues)
  expectString(raw, 'impact', path, issues)
  expectFiniteNumber(raw, 'capacity_factor', path, issues, value => value >= 0 && value <= 1, 'a capacity factor between 0 and 1')
}

function validateEvent(raw: unknown, path: string, issues: Issues): void {
  if (!isRecord(raw)) {
    issues.push({ path, message: `event should be an object but is ${describe(raw)}` })
    return
  }
  expectString(raw, 'event_id', path, issues)
  expectFiniteNumber(raw, 'version', path, issues, Number.isInteger, 'an integer version')
  expectEnum(raw, 'status', path, issues, STATUS_VALUES)
  expectString(raw, 'title', path, issues)
  expectString(raw, 'summary', path, issues)
  expectString(raw, 'line', path, issues)
  expectFiniteNumber(raw, 'severity', path, issues)
  expectFiniteNumber(raw, 'confidence', path, issues, value => value >= 0 && value <= 1, 'a confidence between 0 and 1')
  if (isRecord(raw.window)) {
    expectString(raw.window, 'start', `${path}.window`, issues)
    if (typeof raw.window.end !== 'string' && raw.window.end !== null) {
      issues.push({ path: `${path}.window.end`, message: `should be an ISO string or null but is ${describe(raw.window.end)}` })
    }
  } else {
    issues.push({ path: `${path}.window`, message: `should be an object but is ${describe(raw.window)}` })
  }
  if (Array.isArray(raw.affected_segments)) {
    raw.affected_segments.forEach((segment, index) => validateSegment(segment, `${path}.affected_segments[${index}]`, issues))
  } else {
    issues.push({ path: `${path}.affected_segments`, message: `should be an array but is ${describe(raw.affected_segments)}` })
  }
  expectString(raw, 'updated_at', path, issues)
  if (raw.published_at !== undefined && typeof raw.published_at !== 'string' && raw.published_at !== null) {
    issues.push({ path: `${path}.published_at`, message: `should be an ISO string or null but is ${describe(raw.published_at)}` })
  }
  if (typeof raw.expires_at !== 'string' && raw.expires_at !== null) {
    issues.push({ path: `${path}.expires_at`, message: `required by the shared type as an ISO string or null but is ${describe(raw.expires_at)}` })
  }
  expectStringArray(raw, 'signals', path, issues)
  expectEnum(raw, 'provenance', path, issues, PROVENANCE_VALUES)
}

function validateSignal(raw: unknown, path: string, issues: Issues): void {
  if (!isRecord(raw)) {
    issues.push({ path, message: `signal should be an object but is ${describe(raw)}` })
    return
  }
  expectString(raw, 'signal_id', path, issues)
  expectString(raw, 'source_type', path, issues)
  expectString(raw, 'source_name', path, issues)
  expectString(raw, 'received_at', path, issues)
  expectString(raw, 'raw_text', path, issues)
  expectEnum(raw, 'provenance', path, issues, PROVENANCE_VALUES)
}

function validateLeg(raw: unknown, path: string, issues: Issues): void {
  if (!isRecord(raw)) {
    issues.push({ path, message: `leg should be an object but is ${describe(raw)}` })
    return
  }
  expectEnum(raw, 'mode', path, issues, MODE_VALUES)
  if (raw.line !== undefined) expectString(raw, 'line', path, issues)
  expectString(raw, 'from', path, issues)
  expectString(raw, 'to', path, issues)
  // Older fixtures use travel_s; engine output uses in_vehicle_s. Keep the
  // supplied field and its meaning rather than inventing a missing duration.
  const durationKey = raw.travel_s !== undefined ? 'travel_s' : 'in_vehicle_s'
  expectFiniteNumber(raw, durationKey, path, issues, value => value >= 0, 'a non-negative travel time in seconds')
  expectFiniteNumber(raw, 'walk_m', path, issues, value => value >= 0, 'a non-negative walking distance in metres')
  expectEnum(raw, 'accessible', path, issues, ACCESSIBLE_VALUES)
  expectEnum(raw, 'provenance', path, issues, PROVENANCE_VALUES)
}

function validateRoute(raw: unknown, path: string, issues: Issues): void {
  if (!isRecord(raw)) {
    issues.push({ path, message: `route should be an object but is ${describe(raw)}` })
    return
  }
  expectString(raw, 'route_id', path, issues)
  expectString(raw, 'label', path, issues)
  if (Array.isArray(raw.legs)) {
    if (raw.legs.length === 0) issues.push({ path: `${path}.legs`, message: 'route has no legs' })
    raw.legs.forEach((leg, index) => validateLeg(leg, `${path}.legs[${index}]`, issues))
  } else {
    issues.push({ path: `${path}.legs`, message: `should be an array but is ${describe(raw.legs)}` })
  }
  if (isRecord(raw.total)) {
    expectFiniteNumber(raw.total, 'time_s', `${path}.total`, issues, value => value >= 0, 'a non-negative total time in seconds')
    const range = raw.total.time_range_s
    if (Array.isArray(range) && range.length === 2 && range.every(isFiniteNumber)) {
      if (range[0] > (range[1] as number)) {
        issues.push({ path: `${path}.total.time_range_s`, message: 'lower bound is above the upper bound; kept as-is, not swapped' })
      }
    } else {
      issues.push({ path: `${path}.total.time_range_s`, message: `should be a pair of numbers but is ${describe(range)}` })
    }
    expectFiniteNumber(raw.total, 'transfers', `${path}.total`, issues, value => value >= 0 && Number.isInteger(value), 'a non-negative integer transfer count')
    expectFiniteNumber(raw.total, 'walk_m', `${path}.total`, issues, value => value >= 0, 'a non-negative walking distance in metres')
    expectFiniteNumber(raw.total, 'fare_hkd', `${path}.total`, issues, value => value >= 0, 'a non-negative fare in HKD')
    expectFiniteNumber(raw.total, 'reliability', `${path}.total`, issues, value => value >= 0 && value <= 1, 'a reliability between 0 and 1')
    expectFiniteNumber(raw.total, 'freshness_s', `${path}.total`, issues)
  } else {
    issues.push({ path: `${path}.total`, message: `should be an object but is ${describe(raw.total)}` })
  }
  expectFiniteNumber(raw, 'score', path, issues, value => value >= 0 && value <= 1, 'a score between 0 and 1')
  expectStringArray(raw, 'warnings', path, issues)
  expectStringArray(raw, 'notes', path, issues)
  expectString(raw, 'explain', path, issues)
  if (raw.score_breakdown !== undefined) {
    if (Array.isArray(raw.score_breakdown)) {
      raw.score_breakdown.forEach((factor, index) => {
        const factorPath = `${path}.score_breakdown[${index}]`
        if (!isRecord(factor)) {
          issues.push({ path: factorPath, message: `score factor should be an object but is ${describe(factor)}` })
          return
        }
        expectString(factor, 'criterion', factorPath, issues)
        expectFiniteNumber(factor, 'normalized', factorPath, issues)
        expectFiniteNumber(factor, 'weight', factorPath, issues)
        expectFiniteNumber(factor, 'contribution', factorPath, issues)
      })
    } else {
      issues.push({ path: `${path}.score_breakdown`, message: `should be an array but is ${describe(raw.score_breakdown)}` })
    }
  }
  expectEnum(raw, 'provenance', path, issues, PROVENANCE_VALUES)
}

export function normalizeNetwork(raw: unknown): NormalizationResult<Network> {
  const issues: Issues = []
  if (!isRecord(raw)) throw new SeedStructureError('network seed must be a JSON object')
  if (!isRecord(raw.meta)) throw new SeedStructureError('network seed has no meta object')
  const catchment = raw.meta.catchment_m
  if (!isFiniteNumber(catchment) || catchment <= 0) {
    throw new SeedStructureError('network meta.catchment_m is missing or invalid — refusing to guess an access radius')
  }
  expectString(raw.meta, 'version', 'meta', issues)
  expectString(raw.meta, 'built_at', 'meta', issues)
  if (!Array.isArray(raw.nodes) || raw.nodes.length === 0) throw new SeedStructureError('network seed has no nodes')
  if (!Array.isArray(raw.lines) || raw.lines.length === 0) throw new SeedStructureError('network seed has no lines')
  raw.nodes.forEach((node, index) => validateNode(node, `nodes[${index}]`, issues))
  raw.lines.forEach((line, index) => validateLine(line, `lines[${index}]`, issues))
  return { value: raw as unknown as Network, issues }
}

export function normalizeEventFeed(raw: unknown): NormalizationResult<{ events: Event[]; signals: Signal[] }> {
  const issues: Issues = []
  if (!isRecord(raw)) throw new SeedStructureError('event seed must be a JSON object')
  if (!Array.isArray(raw.events) || raw.events.length === 0) throw new SeedStructureError('event seed has no events')
  if (!Array.isArray(raw.signals)) throw new SeedStructureError('event seed has no signals array')
  raw.events.forEach((event, index) => validateEvent(event, `events[${index}]`, issues))
  raw.signals.forEach((signal, index) => validateSignal(signal, `signals[${index}]`, issues))
  return { value: raw as unknown as { events: Event[]; signals: Signal[] }, issues }
}

export function normalizeRoutes(raw: unknown): NormalizationResult<{ routes: RouteCandidate[] }> {
  const issues: Issues = []
  if (!isRecord(raw)) throw new SeedStructureError('routes seed must be a JSON object')
  if (!Array.isArray(raw.routes) || raw.routes.length === 0) throw new SeedStructureError('routes seed has no routes')
  raw.routes.forEach((route, index) => validateRoute(route, `routes[${index}]`, issues))
  return { value: raw as unknown as { routes: RouteCandidate[] }, issues }
}

export function simSeedAvailable(raw: unknown): boolean {
  return isRecord(raw)
}
