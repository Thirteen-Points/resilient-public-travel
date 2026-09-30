import { API_BASE_URL } from './liveTransitApi'
import type { Event, Signal } from './types'

// Demo credential only; the server remains the authority for review access.
const REVIEW_TOKEN = import.meta.env.VITE_REVIEW_TOKEN as string | undefined

async function request(path: string, body?: unknown): Promise<unknown> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {
      Accept: 'application/json',
      ...(REVIEW_TOKEN ? { 'x-review-token': REVIEW_TOKEN } : {}),
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(10000),
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
export const getPublishedEvents = async () => events(await request('/api/events/published'))
export async function getEventSignals(id: string): Promise<Signal[]> {
  const data = await request(`/api/events/${encodeURIComponent(id)}/signals`)
  if (!Array.isArray(data) || data.some(item => typeof item?.signal_id !== 'string')) throw new Error('Invalid evidence response')
  return data as Signal[]
}

// Backend review contract: {action: approve|edit|reject, actor, edits?}. The
// server owns status, confidence and audit history; no reason field exists.
export async function reviewEvent(event: Event, action: 'edit' | 'publish' | 'reject'): Promise<Event> {
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
  // EventSource cannot send headers, so the review token rides as a query param.
  const url = new URL(`${API_BASE_URL}/api/stream/events`)
  if (REVIEW_TOKEN) url.searchParams.set('token', REVIEW_TOKEN)
  const stream = new EventSource(url.toString())
  stream.onopen = () => onStatus(true)
  stream.onerror = () => onStatus(false)
  stream.onmessage = onChange
  stream.addEventListener('event', onChange)
  stream.addEventListener('event_updated', onChange)
  return () => stream.close()
}
