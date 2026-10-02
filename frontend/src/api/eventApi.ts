import { API_BASE_URL } from './liveTransitApi'
import type { Event, Signal } from './types'
import { getReviewToken } from './reviewerSession'
import { createEventParser } from './eventStream'

async function request(path: string, body?: unknown, protectedRead = true): Promise<unknown> {
  const token = getReviewToken()
  if (protectedRead && !token) throw new Error('Connect a reviewer session to access the review queue.')
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {
      Accept: 'application/json',
      ...(protectedRead && token ? { 'x-review-token': token } : {}),
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(path === '/api/events/ingest' ? 70000 : 10000),
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status} — ${data?.error?.message ?? (typeof data?.detail === 'string' ? data.detail : 'Event service unavailable')}`)
  return data
}

function events(value: unknown): Event[] {
  if (!Array.isArray(value) || value.some(item => !item || typeof item.event_id !== 'string' || !Array.isArray(item.signals) || !Array.isArray(item.affected_segments))) {
    throw new Error('Invalid event response')
  }
  return value as Event[]
}

export const getEvents = async () => events(await request('/api/events'))
export const getPublishedEvents = async (at?: string) => events(await request(`/api/events/published${at ? `?at=${encodeURIComponent(at)}` : ''}`, undefined, false))
export async function getInbox(): Promise<Signal[]> {
  const data = await request('/api/signals?unlinked_only=true')
  if (!Array.isArray(data)) throw new Error('Invalid signal inbox response')
  return data as Signal[]
}
export interface EventDraft {
  event_type: string; title: string; summary: string; mode: string | null
  line: string | null; direction: string | null
  affected_segments: Array<{ from_node: string; to_node: string; impact: string }>
}
export interface IngestResult { signal_id: string; state: 'merged' | 'needs_review'; draft: EventDraft; event: Event | null; structure_method?: string; llm_used?: {name: string; model: string} | null; structure_errors?: string[] }
export const ingestSignal = async (id: string) => await request('/api/events/ingest', { signal_id: id }) as IngestResult
export const createEvent = async (body: unknown) => events([await request('/api/events', body)])[0]
export async function getEventSignals(id: string): Promise<Signal[]> {
  const data = await request(`/api/events/${encodeURIComponent(id)}/signals`)
  if (!Array.isArray(data) || data.some(item => typeof item?.signal_id !== 'string')) throw new Error('Invalid evidence response')
  return data as Signal[]
}

// Backend review contract: {action: approve|edit|reject, actor, edits?}. The
// server owns status, confidence and audit history; no reason field exists.
export async function reviewEvent(event: Event, action: 'edit' | 'publish' | 'reject' | 'expire'): Promise<Event> {
  const edits = action === 'edit'
    ? {
        event_type: event.event_type,
        title: event.title,
        summary: event.summary,
        mode: event.mode,
        line: event.line,
        direction: event.direction,
        affected_segments: event.affected_segments,
        window: { ...event.window, end_confidence: event.window.end_confidence || 'unknown' },
        severity: event.severity,
      }
    : undefined
  const result = await request(`/api/events/${encodeURIComponent(event.event_id)}/review`, {
    action: action === 'publish' ? 'approve' : action,
    actor: 'admin_demo',
    ...(edits ? { edits } : {}),
  })
  return events([result])[0]
}

export function subscribeEvents(onChange: () => void, onStatus: (connected: boolean) => void): () => void {
  const token = getReviewToken()
  onStatus(false)
  if (!token) return () => {}
  let stopped = false, cursor = '', retry: ReturnType<typeof setTimeout> | undefined
  let controller: AbortController | undefined
  async function connect() {
    controller = new AbortController()
    try {
      const response = await fetch(`${API_BASE_URL}/api/stream/events`, {
        headers: { Accept: 'text/event-stream', 'x-review-token': token, ...(cursor ? { 'Last-Event-ID': cursor } : {}) },
        signal: controller.signal,
      })
      if (!response.ok || !response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
        await response.body?.cancel()
        throw new Error('Event stream unavailable')
      }
      if (stopped) { await response.body.cancel(); return }
      onStatus(true)
      const reader = response.body.getReader(), decoder = new TextDecoder()
      const parse = createEventParser((id, data) => {
        if (stopped) return
        try { JSON.parse(data) } catch { return }
        if (id) cursor = id
        onChange()
      })
      try {
        while (!stopped) {
          const { done, value } = await reader.read()
          if (done) break
          parse(decoder.decode(value, { stream: true }))
        }
      } finally { reader.releaseLock() }
    } catch { /* Polling remains active while the stream reconnects. */ }
    if (!stopped) { onStatus(false); retry = setTimeout(() => void connect(), 3000) }
  }
  void connect()
  return () => { stopped = true; clearTimeout(retry); controller?.abort(); onStatus(false) }
}
