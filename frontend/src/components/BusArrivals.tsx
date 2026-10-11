import { useEffect, useState } from 'react'
import { getBusEta, type BusEta } from '../api/busApi'
import { formatHkt } from '../data'
import css from './BusArrivals.module.css'

export function BusArrivals({ serviceId, stopId, routeNumber }: { serviceId: string; stopId: string; routeNumber: string }) {
  const [result, setResult] = useState<BusEta | null>(null)
  const [busy, setBusy] = useState(true)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let active = true
    let fetching = false
    const controller = new AbortController()
    setResult(null); setBusy(true); setFailed(false)
    const refresh = async () => {
      if (fetching || !active) return
      fetching = true
      try {
        const next = await getBusEta(serviceId, stopId, controller.signal)
        if (active) { setResult(next); setFailed(false) }
      } catch { if (active) setFailed(true) }
      finally { fetching = false; if (active) setBusy(false) }
    }
    void refresh()
    const timer = window.setInterval(() => { if (!document.hidden) void refresh() }, 60_000)
    return () => { active = false; controller.abort(); window.clearInterval(timer) }
  }, [serviceId, stopId])
  return <section className={css.box} aria-label={`Official arrivals for bus ${routeNumber}`} aria-live="polite">
    <strong>Bus {routeNumber} · official arrivals now</strong>
    {busy && <p>Checking operator arrivals…</p>}
    {failed && <p>Arrival refresh failed. Previous observations are stale; use the timetable estimate.</p>}
    {result?.operators.map(operator => <div key={operator.operator} className={css.operator}>
      <span>{operator.operator}{operator.stop_name ? ` · ${operator.stop_name}` : ''}</span>
      {operator.status === 'live' && !failed ? <p>{operator.arrivals.map(arrival => `${arrival.minutes} min${arrival.remark ? ` (${arrival.remark})` : ''}`).join(' · ')}</p>
        : <p>{operator.status === 'no_arrivals' ? 'No upcoming arrival supplied. This does not confirm a suspension.' : operator.status === 'stale' ? 'Operator observation is stale.' : 'Live arrivals unavailable; timetable estimates remain available.'}</p>}
      {operator.observed_at && <small>Operator updated {formatHkt(operator.observed_at)}</small>}
    </div>)}
    <small>Current arrivals refresh every minute. Journey times use the selected-date timetable and estimated intermediate travel times.</small>
  </section>
}
