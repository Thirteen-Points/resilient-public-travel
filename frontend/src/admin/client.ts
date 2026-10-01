import type { Event, Signal, Network } from '../api/types'
import type { EventDraft, IngestResult } from '../api/eventApi'
export type ProviderName = 'deepseek' | 'qwen' | 'glm'
export interface Provider { model: string; base_url: string; key_configured: boolean; api_key?: string; clear_key?: boolean }
export interface SourceConfig { enabled: boolean; timeout_s: number; poll_interval_seconds: number; lang?: 'tc' | 'sc' | 'en'; ttnt_threshold_minutes?: number; min_adjacent_stations?: number; min_consecutive_polls?: number; min_usable_stations?: number }
export interface Settings { revision: number; ai: { enabled: boolean; provider: ProviderName; timeout_s: number; providers: Record<ProviderName, Provider> }; sources: { mtr: SourceConfig; hko: SourceConfig } }
export interface SourceResult { status: string; at: string; added: number; duplicate: number; failures: number; details: Record<string, unknown> }
export interface Overview { health: { ok: boolean; mode: string }; reports: number; unlinked_reports: number; pending_review: number; published: number; ai: Settings['ai']; sources: Record<'mtr' | 'hko', SourceResult | null> }
export interface Activity { id: number; at: string; actor: string; action: string; target: string; result: string; detail: string }
export interface Session { username: string; csrf_token: string }
let csrf = ''
export function setSession(value: Session | null) { csrf = value?.csrf_token ?? '' }
export async function call<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/admin${path}`, { method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin',
    headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }) },
    body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(120_000) })
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    if (response.status === 401 && path !== '/login' && path !== '/session') window.dispatchEvent(new window.Event('admin-session-expired'))
    const message = typeof data?.detail === 'string' ? data.detail : Array.isArray(data?.detail) ? data.detail.map((e: {loc: string[]; msg: string}) => `${e.loc.slice(1).join('.')}: ${e.msg}`).join('; ') : 'Request failed'
    throw new Error(`${message} (HTTP ${response.status})`)
  }
  return data as T
}
export const reviewApi = {
  getInbox: () => call<Signal[]>('/signals?unlinked_only=true'),
  ingestSignal: (id: string) => call<IngestResult>('/events/ingest', { signal_id: id }),
  createEvent: (body: unknown) => call<Event>('/events', body),
}
export async function network(): Promise<Network> {
  const response = await fetch('/api/graph/network')
  if (!response.ok) throw new Error('Network is unavailable')
  return response.json()
}
export async function saveReview(event: Event, action: 'edit' | 'publish' | 'reject' | 'expire', reason = '') {
  return call<Event>(`/events/${encodeURIComponent(event.event_id)}/review`, {
    action: action === 'publish' ? 'approve' : action, expected_version: event.version, reason,
    ...(action === 'edit' ? { edits: { event_type: event.event_type, title: event.title, summary: event.summary, mode: event.mode,
      line: event.line, direction: event.direction, affected_segments: event.affected_segments, window: event.window, severity: event.severity } } : {}),
  })
}
export type { EventDraft }
