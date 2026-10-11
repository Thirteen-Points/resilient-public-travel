import { useCallback, useEffect, useRef, useState } from 'react'
import * as transit from './liveTransitApi'
import * as eventApi from './eventApi'
import { getSourcesStatus, getReplanningStatus, type SourcesStatus, type ReplanningStatus } from './runtimeStatus'
import type { Event, Network, RouteCandidate, RouteQuery, Signal } from './types'

export interface LiveBundle {
  network: Network; events: Event[]; published: Event[]; signals: Signal[]; meta: transit.LiveMeta | null
}
const message = (cause: unknown) => cause instanceof Error ? cause.message : String(cause)
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

export function useLiveSession(enabled: boolean) {
  const [bundle, setBundle] = useState<LiveBundle | null>(null)
  const [error, setError] = useState(''), [warning, setWarning] = useState('')
  const [sourceWarning, setSourceWarning] = useState('')
  const [sources, setSources] = useState<SourcesStatus | null>(null), [sourcesWarning, setSourcesWarning] = useState('')
  const [replanning, setReplanning] = useState<ReplanningStatus | null>(null), [replanningWarning, setReplanningWarning] = useState('')
  const [sourcesReadAt, setSourcesReadAt] = useState('')
  const [routeWarning, setRouteWarning] = useState('')
  const [routes, setRoutes] = useState<RouteCandidate[]>([])
  const [revision, setRevision] = useState(0)
  const lastQuery = useRef<RouteQuery | null>(null), committedQuery = useRef<RouteQuery | null>(null), queryVersion = useRef(0), active = useRef(false)
  const manualQuery = useRef<number | null>(null)
  const retryRoutes = useRef(false)
  const refreshRef = useRef<() => Promise<void>>(async () => {})

  const query = useCallback(async (value: RouteQuery, signal?: AbortSignal) => {
    lastQuery.current = value
    const version = ++queryVersion.current
    if (signal) manualQuery.current = version
    try {
      const result = await transit.queryRoutes(value, undefined, signal)
      if (signal?.aborted || version !== queryVersion.current) throw new Error('Route request superseded; current results retained.')
      if (active.current && version === queryVersion.current) { committedQuery.current = value; retryRoutes.current = false; setRoutes(result); setRouteWarning('') }
      return result
    } catch (cause) {
      if (signal?.aborted && version === queryVersion.current) lastQuery.current = committedQuery.current
      if (active.current && version === queryVersion.current && !signal?.aborted) { retryRoutes.current = true; setRouteWarning(`Routes may be stale: ${message(cause)}`) }
      throw cause
    } finally { if (manualQuery.current === version) manualQuery.current = null }
  }, [])

  useEffect(() => {
    if (!enabled) return
    let disposed = false, busy = false, queued = false, metaBusy = false, sourcesBusy = false, replanBusy = false
    let currentMeta: transit.LiveMeta | null = null
    let signature = '', routeDirty = Boolean(lastQuery.current)
    active.current = true
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
          events: previous && same(previous.published, published) ? previous.published : published,
          signals: [],
        }))
        setError(''); setWarning('')
        if ((routeDirty || retryRoutes.current) && lastQuery.current && manualQuery.current === null) {
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
    return () => { disposed = true; active.current = false; ++queryVersion.current; clearInterval(timer); clearInterval(sourcesTimer); window.removeEventListener('offline', offline); window.removeEventListener('online', online) }
  }, [enabled, query])

  return { bundle, error, warning, sourceWarning, sources, sourcesWarning, sourcesReadAt, replanning, replanningWarning, routeWarning, routes, revision, query, refresh: () => refreshRef.current() }
}
