import { API_BASE_URL } from './liveTransitApi'
import type { Event, Signal } from './types'

async function request(path: string, body?: unknown): Promise<unknown> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
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

// Proposed B handoff payload; see M1-INTEGRATION.md. The server owns status and audit history.
export async function reviewEvent(event: Event, action: 'edit' | 'publish' | 'reject', reason: string): Promise<Event> {
  const { title, summary, line, severity, window, affected_segments } = event
  const result = await request(`/api/events/${encodeURIComponent(event.event_id)}/review`, {
    action: action === 'publish' ? 'approve' : action,
    actor: 'admin_demo',
    ...(action === 'edit' ? { changes: { title, summary, line, severity, window, affected_segments } } : {}),
    ...(reason ? { reason } : {}),
  })
  return events([result])[0]
}

export function subscribeEvents(onChange: () => void, onStatus: (connected: boolean) => void): () => void {
  const stream = new EventSource(`${API_BASE_URL}/api/stream/events`)
  stream.onopen = () => onStatus(true)
  stream.onerror = () => onStatus(false)
  stream.onmessage = onChange
  stream.addEventListener('event', onChange)
  stream.addEventListener('event_updated', onChange)
  return () => stream.close()
}
