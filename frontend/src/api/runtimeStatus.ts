import { requestJson } from './liveTransitApi'

const object = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === 'object' && !Array.isArray(value)
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value >= 0
const timestamp = (value: unknown): value is string => typeof value === 'string' && /(Z|[+-]\d\d:\d\d)$/.test(value) && Number.isFinite(Date.parse(value))

export interface CollectorStatus {
  enabled: boolean; scheduled: boolean; collecting: boolean; status: string; stale: boolean
  interval_seconds?: number; last_attempt?: number; next_attempt?: number
  last_success_at?: string | null
  last_result?: { at?: string; status?: string; added?: number; duplicate?: number; failures?: number }
}
export interface SourcesStatus { offline: boolean; configured: boolean; publishes_events: boolean; sources: Record<string, CollectorStatus> }
export interface ReplanningStatus {
  graph_snapshot: string
  latest: { should_replan: boolean; recomputed: boolean; trigger: string; reason: string | null; occurred_at: string | null; elapsed_ms: number; within_five_second_budget: boolean } | null
  live_load_provider_installed: boolean
}

export function parseSourcesStatus(value: unknown): SourcesStatus {
  if (!object(value) || !object(value.sources) || !['offline', 'configured', 'publishes_events'].every(key => typeof value[key] === 'boolean')) throw new Error('Malformed source status.')
  for (const source of Object.values(value.sources)) {
    if (!object(source) || !['enabled', 'scheduled', 'collecting', 'stale'].every(key => typeof source[key] === 'boolean') || typeof source.status !== 'string') throw new Error('Malformed collector status.')
    for (const key of ['interval_seconds', 'last_attempt', 'next_attempt']) if (source[key] != null && !finite(source[key])) throw new Error('Malformed collector time.')
    if (source.last_success_at != null && !timestamp(source.last_success_at)) throw new Error('Malformed last-success time.')
    if (source.last_result != null) {
      if (!object(source.last_result) || source.last_result.at != null && !timestamp(source.last_result.at) || source.last_result.status != null && typeof source.last_result.status !== 'string') throw new Error('Malformed collection result.')
      for (const key of ['added', 'duplicate', 'failures']) if (source.last_result[key] != null && (!finite(source.last_result[key]) || !Number.isInteger(source.last_result[key]))) throw new Error('Malformed collection counts.')
    }
  }
  return value as unknown as SourcesStatus
}

export function parseReplanningStatus(value: unknown): ReplanningStatus {
  if (!object(value) || typeof value.graph_snapshot !== 'string' || typeof value.live_load_provider_installed !== 'boolean') throw new Error('Malformed replanning status.')
  if (value.latest !== null) {
    const latest = value.latest
    if (!object(latest) || !['should_replan', 'recomputed', 'within_five_second_budget'].every(key => typeof latest[key] === 'boolean') || typeof latest.trigger !== 'string' || latest.reason != null && typeof latest.reason !== 'string' || latest.occurred_at != null && !timestamp(latest.occurred_at) || !finite(latest.elapsed_ms)) throw new Error('Malformed replanning result.')
  }
  return value as unknown as ReplanningStatus
}

export async function getSourcesStatus(signal?: AbortSignal): Promise<SourcesStatus> {
  return parseSourcesStatus(await requestJson('GET', '/api/sources/status', undefined, { signal }))
}
export async function getReplanningStatus(signal?: AbortSignal): Promise<ReplanningStatus> {
  return parseReplanningStatus(await requestJson('GET', '/api/replanning/status', undefined, { signal }))
}

export function lastSuccessfulCollection(source: CollectorStatus): string | undefined {
  return source.last_success_at ?? (source.last_result?.status === 'success' ? source.last_result.at : undefined)
}
