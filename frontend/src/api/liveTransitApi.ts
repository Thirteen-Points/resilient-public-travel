// Live HTTP client for the ResilientRoute backend (graph, route query, meta).
//
// Contract with callers (main-agent data-source wiring):
// - Every call hits the real API and either returns the parsed response body
//   or throws LiveApiError carrying the HTTP status plus the backend's
//   error.message. Nothing here falls back to seed data, and no field is
//   synthesised client-side: timestamps, provenance and source freshness are
//   reported exactly as the backend sent them, or left absent.
// - Success bodies are trusted to be supersets of the shared Network /
//   RouteCandidate shapes (the engine emits extra fields such as co2_g and
//   per-leg depart/arrive). Only gross top-level structure is checked, so a
//   broken backend fails loudly instead of handing back mistyped data.

import type { Network, RouteCandidate, RouteQuery } from './types'
import { resolveProfile } from './p3Context'

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000'

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL
export const API_BASE_URL: string =
  typeof configuredBaseUrl === 'string' && configuredBaseUrl.trim() !== ''
    ? configuredBaseUrl.trim().replace(/\/+$/, '')
    : DEFAULT_BASE_URL

/**
 * Thrown for every non-2xx response and for transport or parse failures.
 * `status` is the HTTP status of the offending response: 200 means the body of
 * a successful response was malformed, 0 means no HTTP response arrived
 * (offline, DNS, refused connection). `code` / `fallback` mirror the backend
 * error envelope and are null when the backend did not send them.
 */
export class LiveApiError extends Error {
  readonly status: number
  readonly code: string | null
  readonly method: string
  readonly path: string
  readonly fallback: string | null

  constructor(
    method: string, path: string, status: number,
    code: string | null, detail: string, fallback: string | null = null,
  ) {
    super(`${method} ${path} failed (HTTP ${status}${code ? ` ${code}` : ''}): ${detail}`)
    this.name = 'LiveApiError'
    this.status = status
    this.code = code
    this.method = method
    this.path = path
    this.fallback = fallback
  }
}

/** GET /api/graph/snapshot — engine's Snapshot.describe(). */
export interface SnapshotAffectedEdge {
  from_node: string
  to_node: string
  line: string
  capacity_factor: number
  event_ids: string[]
}

export interface GraphSnapshot {
  snapshot_id: string
  affected_edges: SnapshotAffectedEdge[]
}

/**
 * GET /api/meta — defined here, not in ./types, because only the live
 * backend serves it. `sources` is currently a plain string array; a backend
 * that upgrades it to objects exposes `name` and an optional `last_ok`, and
 * only a `last_ok` actually present in the response ever reaches callers —
 * this module never invents a source freshness timestamp.
 */
export interface LiveMetaSourceStatus {
  name: string
  last_ok?: string
}

export interface LiveMeta {
  generated_at: string
  graph_snapshot: string | null
  sources: Array<string | LiveMetaSourceStatus>
  disclaimer: string
}

export function sourceLastOk(source: string | LiveMetaSourceStatus): string | undefined {
  return typeof source === 'object' && typeof source.last_ok === 'string' ? source.last_ok : undefined
}

function errorFields(body: unknown): { code: string | null; message: string | null; fallback: string | null } {
  const error = typeof body === 'object' && body !== null ? (body as { error?: unknown }).error : null
  if (typeof error !== 'object' || error === null) return { code: null, message: null, fallback: null }
  const { code, message, fallback } = error as Record<string, unknown>
  return {
    code: typeof code === 'string' ? code : null,
    message: typeof message === 'string' ? message : null,
    fallback: typeof fallback === 'string' ? fallback : null,
  }
}

interface RequestOptions { signal?: AbortSignal; timeoutMs?: number }

export async function requestJson<T>(method: string, path: string, body?: unknown, options: RequestOptions = {}): Promise<T> {
  return (await requestJsonWithMetadata<T>(method, path, body, options)).body
}

export async function requestJsonWithMetadata<T>(method: string, path: string, body?: unknown, options: RequestOptions = {}): Promise<{ body: T; headers: Headers }> {
  const deadline = AbortSignal.timeout(options.timeoutMs ?? 10000)
  const signal = options.signal ? AbortSignal.any([options.signal, deadline]) : deadline
  let response: Response
  let text: string
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: body === undefined
        ? { Accept: 'application/json' }
        : { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
    text = await response.text()
  } catch (cause) {
    const reason = cause instanceof Error ? cause.message : String(cause)
    const code = deadline.aborted ? 'TIMEOUT' : options.signal?.aborted ? 'CANCELLED' : 'NETWORK_ERROR'
    throw new LiveApiError(method, path, 0, code, code === 'TIMEOUT' ? 'Request timed out. Retry when the service is available.' : `no complete HTTP response (${reason})`)
  }

  let parsed: unknown = null
  let parseFailed = false
  if (text !== '') {
    try {
      parsed = JSON.parse(text)
    } catch {
      parseFailed = true
    }
  }

  if (!response.ok) {
    const fields = errorFields(parsed)
    const detail = fields.message ?? (typeof parsed === 'object' && parsed !== null && typeof (parsed as { detail?: unknown }).detail === 'string' ? (parsed as { detail: string }).detail : null)
      ?? (parseFailed ? `non-JSON error body: ${text.slice(0, 200)}` : 'error body carried no error.message')
    throw new LiveApiError(method, path, response.status, fields.code, detail, fields.fallback)
  }
  if (parseFailed) {
    throw new LiveApiError(method, path, response.status, null, `response body is not JSON: ${text.slice(0, 200)}`)
  }
  if (parsed === null) {
    throw new LiveApiError(method, path, response.status, null, 'response body is empty')
  }
  return { body: parsed as T, headers: response.headers }
}

function requireObjectKeyArray(body: unknown, keys: string[]): Record<string, unknown> {
  if (typeof body !== 'object' || body === null || Array.isArray(body)) {
    throw new TypeError('response body is not a JSON object')
  }
  const record = body as Record<string, unknown>
  for (const key of keys) {
    if (!Array.isArray(record[key])) throw new TypeError(`response is missing array field "${key}"`)
  }
  return record
}

/** GET /api/graph/network — the frozen network source behind the current snapshot. */
export async function getNetwork(): Promise<Network> {
  const body = await requestJson<unknown>('GET', '/api/graph/network')
  try {
    return requireObjectKeyArray(body, ['nodes', 'lines']) as unknown as Network
  } catch (cause) {
    throw new LiveApiError('GET', '/api/graph/network', 200, null, `malformed network payload (${cause instanceof Error ? cause.message : String(cause)})`)
  }
}

/** GET /api/graph/snapshot — snapshot id plus currently affected edges. */
export async function getSnapshot(at?: string, signal?: AbortSignal): Promise<GraphSnapshot> {
  const body = await requestJson<unknown>('GET', `/api/graph/snapshot${at ? `?at=${encodeURIComponent(at)}` : ''}`, undefined, { signal })
  try {
    const record = requireObjectKeyArray(body, ['affected_edges'])
    if (typeof record.snapshot_id !== 'string') throw new TypeError('response is missing string field "snapshot_id"')
    return body as GraphSnapshot
  } catch (cause) {
    throw new LiveApiError('GET', '/api/graph/snapshot', 200, null, `malformed snapshot payload (${cause instanceof Error ? cause.message : String(cause)})`)
  }
}

/** GET /api/meta — service generation time and data sources, verbatim from the backend. */
export async function getMeta(): Promise<LiveMeta> {
  const body = await requestJson<unknown>('GET', '/api/meta')
  try {
    const record = requireObjectKeyArray(body, ['sources'])
    if (typeof record.generated_at !== 'string') throw new TypeError('response is missing string field "generated_at"')
    if (!Number.isFinite(Date.parse(record.generated_at))) throw new TypeError('invalid meta generation time')
    if (!record.sources || !(record.sources as unknown[]).every(source => typeof source === 'string' || typeof source === 'object' && source !== null && typeof (source as LiveMetaSourceStatus).name === 'string' && ((source as LiveMetaSourceStatus).last_ok === undefined || typeof (source as LiveMetaSourceStatus).last_ok === 'string' && Number.isFinite(Date.parse((source as LiveMetaSourceStatus).last_ok!))))) throw new TypeError('invalid source metadata')
    return body as LiveMeta
  } catch (cause) {
    throw new LiveApiError('GET', '/api/meta', 200, null, `malformed meta payload (${cause instanceof Error ? cause.message : String(cause)})`)
  }
}

/**
 * POST /api/routes/query — maps the frontend RouteQuery to the backend body
 * { origin, destination, depart_at, profile: { preset }, event_ids } and
 * returns the engine's RouteCandidate[] (already score-sorted; UI may take
 * [:3]). `eventIds` is sent only when the caller passes it, so the backend
 * distinguishes "no event filter" from an explicitly empty one.
 */
export async function queryRoutes(query: RouteQuery, eventIds?: string[], signal?: AbortSignal): Promise<RouteCandidate[]> {
  return (await queryRoutesWithMetadata(query, eventIds, signal)).routes
}

export async function queryRoutesWithMetadata(query: RouteQuery, eventIds?: string[], signal?: AbortSignal): Promise<{ routes: RouteCandidate[]; snapshotId: string | null }> {
  if (query.preset === 'least_walking') throw new LiveApiError('POST', '/api/routes/query', 0, 'CONTRACT_PENDING', 'Less walking is not supported by the current backend preset contract; no alternate preset was substituted.')
  const payload: Record<string, unknown> = {
    origin: query.origin,
    destination: query.destination,
    depart_at: query.departAt,
    profile: resolveProfile(query),
  }
  if (eventIds !== undefined) payload.event_ids = eventIds
  if (query.modes !== undefined) payload.modes = query.modes
  if (query.requiredModes !== undefined) payload.required_modes = query.requiredModes
  const { body, headers } = await requestJsonWithMetadata<unknown>('POST', '/api/routes/query', payload, { signal, timeoutMs: 30_000 })
  if (!Array.isArray(body)) {
    throw new LiveApiError('POST', '/api/routes/query', 200, null, 'malformed route payload: expected a RouteCandidate array')
  }
  return { routes: body as RouteCandidate[], snapshotId: headers?.get('X-Route-Snapshot')?.trim() || null }
}
