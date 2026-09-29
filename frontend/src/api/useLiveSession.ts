import { useCallback, useEffect, useRef, useState } from 'react'
import * as transit from './liveTransitApi'
import * as eventApi from './eventApi'
import type { Event, Network, RouteCandidate, RouteQuery, Signal } from './types'

export interface LiveBundle {
  network: Network
  events: Event[]
  published: Event[]
  signals: Signal[]
  meta: transit.LiveMeta
}

const message = (cause: unknown) => cause instanceof Error ? cause.message : String(cause)

export function useLiveSession(enabled: boolean) {
  const [bundle, setBundle] = useState<LiveBundle | null>(null)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [routeWarning, setRouteWarning] = useState('')
  const [connected, setConnected] = useState(false)
  const [routes, setRoutes] = useState<RouteCandidate[]>([])
  const [revision, setRevision] = useState(0)
  const lastQuery = useRef<RouteQuery | null>(null)
  const queryVersion = useRef(0)
  const active = useRef(false)
  const refreshRef = useRef<() => Promise<void>>(async () => {})

  const query = useCallback(async (value: RouteQuery) => {
    lastQuery.current = value
    const version = ++queryVersion.current
    try {
      const result = await transit.queryRoutes(value)
      if (active.current && version === queryVersion.current) {
        setRoutes(result.slice(0, 3)); setRouteWarning('')
      }
      return result
    } catch (cause) {
      if (active.current && version === queryVersion.current) setRouteWarning(`Routes may be stale: ${message(cause)}`)
      throw cause
    }
  }, [])

  useEffect(() => {
    if (!enabled) return
    let disposed = false
    let busy = false
    let queued = false
    let signature = ''
    let evidenceVersion = 0
    let evidenceSignature = ''
    let evidenceBusy = false
    let evidenceNotice = ''
    let routeDirty = false
    active.current = true
    async function refresh() {
      if (disposed) return
      if (busy) { queued = true; return }
      busy = true
      try {
        const [network, meta, snapshot, eventResult] = await Promise.all([
          transit.getNetwork(), transit.getMeta(), transit.getSnapshot(),
          Promise.all([eventApi.getEvents(), eventApi.getPublishedEvents()]).then(value => ({ value, error: '' }), cause => ({ value: null, error: message(cause) })),
        ])
        if (disposed) return
        const notices: string[] = [evidenceNotice].filter(Boolean)
        if (eventResult.value) {
          const nextEvidenceSignature = JSON.stringify(eventResult.value[0].map(event => [event.event_id, event.version, event.updated_at, event.signals]))
          if (!evidenceBusy && nextEvidenceSignature !== evidenceSignature) {
          evidenceBusy = true
          const version = ++evidenceVersion
          // Evidence loading must not delay map updates or route recalculation.
          void Promise.allSettled(eventResult.value[0].filter(event => event.signals.length).map(event => eventApi.getEventSignals(event.event_id))).then(evidence => {
            if (disposed || version !== evidenceVersion) return
            evidenceBusy = false
            const signals = [...new Map(evidence.flatMap(result => result.status === 'fulfilled' ? result.value : []).map(signal => [signal.signal_id, signal])).values()]
            setBundle(previous => previous ? { ...previous, signals } : previous)
            evidenceNotice = evidence.some(result => result.status === 'rejected') ? 'Some event evidence is unavailable; no missing evidence has been inferred.' : ''
            if (!evidenceNotice) evidenceSignature = nextEvidenceSignature
            else setWarning(evidenceNotice)
          })
          }
        } else notices.push(`Event status unavailable; retained overlays may be stale. ${eventResult.error}`)
        // Reference stability: the map rebuilds its layers whenever network or
        // published change identity, so identical data must keep old references
        // and polling alone must not re-render anything.
        const nextSignature = JSON.stringify([
          snapshot,
          network.meta.version,
          eventResult.value?.[0]?.map(event => [event.event_id, event.version, event.status, event.updated_at]),
          eventResult.value?.[1],
        ])
        const changed = nextSignature !== signature
        if (changed) { signature = nextSignature; routeDirty = true }
        if (changed) {
          setBundle(previous => ({
            network,
            meta,
            events: eventResult.value?.[0] ?? previous?.events ?? [],
            published: eventResult.value?.[1] ?? previous?.published ?? [],
            signals: previous?.signals ?? [],
          }))
          setRevision(value => value + 1)
        }
        setError(''); setWarning(notices.join(' '))
        if (routeDirty && lastQuery.current) {
          try { await query(lastQuery.current); routeDirty = false } catch { /* query retains old cards with a stale notice; next poll retries */ }
        }
      } catch (cause) {
        if (!disposed) { setError(message(cause)); setWarning(`Refresh failed; displayed data may be stale. ${message(cause)}`) }
      } finally {
        busy = false
        if (queued && !disposed) { queued = false; void refresh() }
      }
    }
    refreshRef.current = refresh
    void refresh()
    const timer = window.setInterval(() => void refresh(), 3000)
    const close = eventApi.subscribeEvents(() => void refresh(), value => { if (!disposed) setConnected(value) })
    return () => { disposed = true; active.current = false; ++queryVersion.current; clearInterval(timer); close() }
  }, [enabled, query])

  const review = async (event: Event, action: 'edit' | 'publish' | 'reject', _reason: string) => {
    // The API contract has no reason field; the caller's note stays in local logs.
    const saved = await eventApi.reviewEvent(event, action)
    setBundle(previous => previous ? { ...previous, events: previous.events.map(item => item.event_id === saved.event_id ? saved : item) } : previous)
    // A successful write stays successful even if subsequent reads fail.
    // Refresh errors are shown separately and never invite a duplicate publication.
    await refreshRef.current()
  }
  return { bundle, error, warning, routeWarning, connected, routes, revision, query, review, refresh: () => refreshRef.current() }
}
