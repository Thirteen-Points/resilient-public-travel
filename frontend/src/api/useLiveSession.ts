import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import * as transit from './liveTransitApi'
import * as eventApi from './eventApi'
import { getReviewToken, reviewerRevision, subscribeReviewer } from './reviewerSession'
import type { Event, Network, RouteCandidate, RouteQuery, Signal } from './types'

export interface LiveBundle {
  network: Network; events: Event[]; published: Event[]; signals: Signal[]; meta: transit.LiveMeta
}
const message = (cause: unknown) => cause instanceof Error ? cause.message : String(cause)
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

export function useLiveSession(enabled: boolean) {
  const authRevision = useSyncExternalStore(subscribeReviewer, reviewerRevision)
  const [bundle, setBundle] = useState<LiveBundle | null>(null)
  const [error, setError] = useState(''), [warning, setWarning] = useState('')
  const [reviewWarning, setReviewWarning] = useState(''), [routeWarning, setRouteWarning] = useState('')
  const [connected, setConnected] = useState(false), [routes, setRoutes] = useState<RouteCandidate[]>([])
  const [revision, setRevision] = useState(0)
  const lastQuery = useRef<RouteQuery | null>(null), queryVersion = useRef(0), active = useRef(false)
  const refreshRef = useRef<() => Promise<void>>(async () => {})

  const query = useCallback(async (value: RouteQuery) => {
    lastQuery.current = value
    const version = ++queryVersion.current
    try {
      const result = await transit.queryRoutes(value)
      if (active.current && version === queryVersion.current) { setRoutes(result.slice(0, 3)); setRouteWarning('') }
      return result
    } catch (cause) {
      if (active.current && version === queryVersion.current) setRouteWarning(`Routes may be stale: ${message(cause)}`)
      throw cause
    }
  }, [])

  useEffect(() => {
    if (!enabled) return
    let disposed = false, busy = false, queued = false, privateBusy = false
    let signature = '', evidenceSignature = '', routeDirty = Boolean(lastQuery.current)
    active.current = true
    setBundle(previous => previous ? { ...previous, events: previous.published, signals: [] } : previous)
    setReviewWarning('')
    async function refreshReviewer() {
      if (!getReviewToken() || disposed || privateBusy) return
      privateBusy = true
      try {
        const events = await eventApi.getEvents()
        if (disposed) return
        setBundle(previous => previous ? { ...previous, events: same(previous.events, events) ? previous.events : events } : previous)
        const next = JSON.stringify(events.map(event => [event.event_id, event.version, event.signals]))
        if (next !== evidenceSignature) {
          const evidence = await Promise.allSettled(events.filter(event => event.signals.length).map(event => eventApi.getEventSignals(event.event_id)))
          if (disposed) return
          const signals = [...new Map(evidence.flatMap(result => result.status === 'fulfilled' ? result.value : []).map(signal => [signal.signal_id, signal])).values()]
          const failed = evidence.some(result => result.status === 'rejected')
          if (!failed) evidenceSignature = next
          setBundle(previous => previous ? { ...previous, signals } : previous)
          setReviewWarning(failed ? 'Some original evidence is unavailable. Missing text has not been inferred.' : '')
        } else setReviewWarning('')
      } catch (cause) { if (!disposed) setReviewWarning(`Reviewer data unavailable: ${message(cause)}`) }
      finally { privateBusy = false }
    }
    async function refresh() {
      if (disposed) return
      if (busy) { queued = true; return }
      busy = true
      try {
        const at = lastQuery.current?.departAt
        const [network, meta, snapshot, published] = await Promise.all([
          transit.getNetwork(), transit.getMeta(), transit.getSnapshot(at), eventApi.getPublishedEvents(at),
        ])
        if (disposed) return
        if (at !== lastQuery.current?.departAt) { queued = true; return }
        const nextSignature = JSON.stringify([snapshot, published, at])
        if (signature && nextSignature !== signature) routeDirty = true
        signature = nextSignature
        setBundle(previous => ({
          network: previous && same(previous.network, network) ? previous.network : network,
          meta,
          published: previous && same(previous.published, published) ? previous.published : published,
          events: getReviewToken() ? previous?.events ?? published : published,
          signals: previous?.signals ?? [],
        }))
        setError(''); setWarning('')
        // Protected reads never hold up public map updates or route queries.
        void refreshReviewer()
        if (routeDirty && lastQuery.current) {
          try { await query(lastQuery.current); routeDirty = false; if (!disposed) setRevision(value => value + 1) }
          catch { /* Keep old cards visibly stale; next poll retries. */ }
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
  }, [enabled, query, authRevision])

  const review = async (event: Event, action: 'edit' | 'publish' | 'reject' | 'expire', _reason: string) => {
    const saved = await eventApi.reviewEvent(event, action)
    setBundle(previous => previous ? { ...previous, events: previous.events.map(item => item.event_id === saved.event_id ? saved : item) } : previous)
    // A committed write stays successful even if following reads fail.
    await refreshRef.current()
  }
  return { bundle, error, warning, reviewWarning, routeWarning, connected, routes, revision, query, review, refresh: () => refreshRef.current() }
}
