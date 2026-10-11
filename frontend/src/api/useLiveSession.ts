import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import * as transit from './liveTransitApi'
import * as eventApi from './eventApi'
import { getReviewToken, reviewerRevision, subscribeReviewer } from './reviewerSession'
import { getSourcesStatus, getReplanningStatus, type SourcesStatus, type ReplanningStatus } from './runtimeStatus'
import type { Event, Network, RouteCandidate, RouteQuery, Signal } from './types'

export interface LiveBundle {
  network: Network; events: Event[]; published: Event[]; signals: Signal[]; meta: transit.LiveMeta | null
}
const message = (cause: unknown) => cause instanceof Error ? cause.message : String(cause)
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

export function useLiveSession(enabled: boolean) {
  const authRevision = useSyncExternalStore(subscribeReviewer, reviewerRevision)
  const [bundle, setBundle] = useState<LiveBundle | null>(null)
  const [error, setError] = useState(''), [warning, setWarning] = useState('')
  const [sourceWarning, setSourceWarning] = useState('')
  const [sources, setSources] = useState<SourcesStatus | null>(null), [sourcesWarning, setSourcesWarning] = useState('')
  const [replanning, setReplanning] = useState<ReplanningStatus | null>(null), [replanningWarning, setReplanningWarning] = useState('')
  const [sourcesReadAt, setSourcesReadAt] = useState('')
  const [reviewWarning, setReviewWarning] = useState(''), [routeWarning, setRouteWarning] = useState('')
  const [connected, setConnected] = useState(false), [routes, setRoutes] = useState<RouteCandidate[]>([])
  const [revision, setRevision] = useState(0)
  const lastQuery = useRef<RouteQuery | null>(null), committedQuery = useRef<RouteQuery | null>(null), queryVersion = useRef(0), active = useRef(false)
  const manualQuery = useRef<number | null>(null)
  const refreshRef = useRef<() => Promise<void>>(async () => {})

  const query = useCallback(async (value: RouteQuery, signal?: AbortSignal) => {
    lastQuery.current = value
    const version = ++queryVersion.current
    if (signal) manualQuery.current = version
    try {
      const result = await transit.queryRoutes(value, undefined, signal)
      if (signal?.aborted || version !== queryVersion.current) throw new Error('Route request superseded; current results retained.')
      if (active.current && version === queryVersion.current) { committedQuery.current = value; setRoutes(result); setRouteWarning('') }
      return result
    } catch (cause) {
      if (signal?.aborted && version === queryVersion.current) lastQuery.current = committedQuery.current
      if (active.current && version === queryVersion.current) setRouteWarning(`Routes may be stale: ${message(cause)}`)
      throw cause
    } finally { if (manualQuery.current === version) manualQuery.current = null }
  }, [])

  useEffect(() => {
    if (!enabled) return
    let disposed = false, busy = false, queued = false, privateBusy = false, metaBusy = false, sourcesBusy = false, replanBusy = false
    let currentMeta: transit.LiveMeta | null = null
    let signature = '', evidenceSignature = '', routeDirty = Boolean(lastQuery.current)
    active.current = true
    setBundle(previous => previous ? { ...previous, events: previous.published, signals: [] } : previous)
    setReviewWarning('')
    async function refreshSources() {
      if (disposed || sourcesBusy) return
      sourcesBusy = true
      try { const next = await getSourcesStatus(); if (!disposed) { setSources(next); setSourcesWarning(''); setSourcesReadAt(new Date().toISOString()) } }
      catch (cause) { if (!disposed) setSourcesWarning(message(cause)) }
      finally { sourcesBusy = false }
    }
    async function refreshReplanning() {
      if (disposed || replanBusy) return
      replanBusy = true
      try { const next = await getReplanningStatus(); if (!disposed) { setReplanning(next); setReplanningWarning('') } }
      catch (cause) { if (!disposed) setReplanningWarning(message(cause)) }
      finally { replanBusy = false }
    }
    async function refreshMeta() {
      if (disposed || metaBusy) return
      metaBusy = true
      try {
        const next = await transit.getMeta()
        if (disposed) return
        currentMeta = next
        setBundle(previous => previous ? { ...previous, meta: next } : previous)
        setSourceWarning('')
      } catch (cause) { if (!disposed) setSourceWarning(message(cause)) }
      finally { metaBusy = false }
    }
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
      // Optional source metadata must never delay graph/route publication.
      void refreshMeta()
      void refreshReplanning()
      if (busy) { queued = true; return }
      busy = true
      try {
        const at = lastQuery.current?.departAt
        const [network, snapshot, published] = await Promise.all([
          transit.getNetwork(), transit.getSnapshot(at), eventApi.getPublishedEvents(at),
        ])
        if (disposed) return
        if (at !== lastQuery.current?.departAt) { queued = true; return }
        const nextSignature = JSON.stringify([snapshot, published, at])
        if (signature && nextSignature !== signature) routeDirty = true
        signature = nextSignature
        setBundle(previous => ({
          network: previous && same(previous.network, network) ? previous.network : network,
          meta: currentMeta ?? previous?.meta ?? null,
          published: previous && same(previous.published, published) ? previous.published : published,
          events: getReviewToken() ? previous?.events ?? published : published,
          signals: previous?.signals ?? [],
        }))
        setError(''); setWarning('')
        // Protected reads never hold up public map updates or route queries.
        void refreshReviewer()
        if (routeDirty && lastQuery.current && manualQuery.current === null) {
          const requested = lastQuery.current
          try {
            await query(requested)
            if (lastQuery.current === requested) { routeDirty = false; if (!disposed) setRevision(value => value + 1) }
            else queued = true
          }
          catch { /* Keep old cards visibly stale; next poll retries. */ }
        }
      } catch (cause) {
        routeDirty = Boolean(lastQuery.current)
        if (!disposed) { setError(message(cause)); setWarning(`Refresh failed; displayed data may be stale. ${message(cause)}`) }
      } finally {
        busy = false
        if (queued && !disposed) { queued = false; void refresh() }
      }
    }
    refreshRef.current = async () => { void refreshSources(); await refresh() }
    void refresh()
    void refreshSources()
    const timer = window.setInterval(() => void refresh(), 3000)
    const sourcesTimer = window.setInterval(() => void refreshSources(), 15000)
    const offline = () => {
      routeDirty = Boolean(lastQuery.current)
      setWarning('Offline; displayed map and routes may be stale. Previous results retained.')
    }
    window.addEventListener('offline', offline)
    const online = () => { void refreshSources(); void refresh() }
    window.addEventListener('online', online)
    const close = eventApi.subscribeEvents(() => void refresh(), value => { if (!disposed) setConnected(value) })
    return () => { disposed = true; active.current = false; ++queryVersion.current; clearInterval(timer); clearInterval(sourcesTimer); window.removeEventListener('offline', offline); window.removeEventListener('online', online); close() }
  }, [enabled, query, authRevision])

  const review = async (event: Event, action: 'edit' | 'publish' | 'reject' | 'expire', _reason: string) => {
    const saved = await eventApi.reviewEvent(event, action)
    setBundle(previous => previous ? { ...previous, events: previous.events.map(item => item.event_id === saved.event_id ? saved : item) } : previous)
    // A committed write stays successful even if following reads fail.
    await refreshRef.current()
  }
  return { bundle, error, warning, sourceWarning, sources, sourcesWarning, sourcesReadAt, replanning, replanningWarning, reviewWarning, routeWarning, connected, routes, revision, query, review, refresh: () => refreshRef.current() }
}
