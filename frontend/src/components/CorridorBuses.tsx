import { useEffect, useState } from 'react'
import { getCorridorBusServices, type BusService } from '../api/busApi'
import { BusArrivals } from './BusArrivals'
import css from './BusArrivals.module.css'

export function CorridorBuses({ station }: { station: string }) {
  const [query, setQuery] = useState(''), [services, setServices] = useState<BusService[]>([])
  const [total, setTotal] = useState(0), [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<BusService | null>(null), [error, setError] = useState(''), [loading, setLoading] = useState(true)
  useEffect(() => { setOffset(0); setSelected(null) }, [station, query])
  useEffect(() => {
    let active = true
    const controller = new AbortController()
    setLoading(true)
    const timer = window.setTimeout(() => {
      getCorridorBusServices(station, query, offset, controller.signal).then(result => {
        if (active) { setServices(result.services); setTotal(result.total); setError('') }
      }).catch(() => { if (active) setError('Could not load the official corridor bus catalogue.') }).finally(() => { if (active) setLoading(false) })
    }, 200)
    return () => { active = false; controller.abort(); window.clearTimeout(timer) }
  }, [station, query, offset])
  const stop = selected?.stops.slice().sort((a, b) => a.corridor_distances[station] - b.corridor_distances[station])[0]
  return <section className={css.box} aria-label="Official corridor bus services">
    <strong>Official buses near this corridor station</strong>
    <p>Direct services and feeders within 800 m of the station. Walking distances are straight-line estimates.</p>
    <label>Search bus number or destination<input className={css.search} value={query} onChange={event => setQuery(event.target.value)} placeholder="182, 982X, Central…" /></label>
    {loading ? <p>Loading services…</p> : <p>{total} direction and service-variant records at {station}</p>}
    {error && <p role="alert">{error}</p>}
    <div className={css.services}>{services.map(service => <button key={service.id} type="button" disabled={loading} onClick={() => setSelected(service)} aria-pressed={selected?.id === service.id}>
      <strong>{service.route} · {service.operators.join(' + ')}</strong><span>{service.direction_label}</span><small>{service.stops[0]?.name}</small>
    </button>)}</div>
    <div className={css.pagination}>
      <button type="button" disabled={offset === 0 || loading} onClick={() => setOffset(value => Math.max(0, value - 30))}>Previous services</button>
      <button type="button" disabled={offset + services.length >= total || loading} onClick={() => setOffset(value => value + 30)}>More services</button>
    </div>
    {selected && stop && <BusArrivals serviceId={selected.id} stopId={stop.td_stop_id} routeNumber={selected.route} />}
    <small>Source: Transport Department GTFS; current arrivals from KMB/LWB and Citybus. Service availability depends on the operator timetable.</small>
  </section>
}
