import { requestJson } from './liveTransitApi'

export interface BusPoint { lat: number; lng: number; name?: string }
export interface BusStop extends BusPoint { td_stop_id: string; sequence: number; name: string; corridor_distances: Record<string, number> }
export interface BusService { id: string; route: string; operators: string[]; name: string; direction_label: string; stops: BusStop[] }
export interface BusArrival { at: string; minutes: number; remark: string }
export interface BusOperatorEta { operator: string; status: 'live' | 'stale' | 'no_arrivals' | 'unavailable'; arrivals: BusArrival[]; observed_at: string | null; stop_name?: string; source_url?: string }
export interface BusEta { checked_at?: string; operators: BusOperatorEta[]; status: string; browser_request?: { service: { route: string; operators: string[]; stops: BusPoint[] }; stop: BusStop } }
type Row = Record<string, string | number | null>
const KMB = 'https://data.etabus.gov.hk/v1/transport/kmb'
const CTB = 'https://rt.data.gov.hk/v2/transport/citybus'
const cache = new Map<string, { at: number; promise: Promise<{ data: Row | Row[]; generated_timestamp?: string }> }>()

async function official(url: string, ttl = 60_000) {
  const saved = cache.get(url)
  if (saved && Date.now() - saved.at < ttl) return saved.promise
  const promise = fetch(url, { headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(ttl > 60_000 ? 20_000 : 8000) }).then(async response => {
    if (!response.ok) throw new Error('Official bus API unavailable')
    const value = await response.json()
    if (!value || typeof value !== 'object' || !('data' in value)) throw new Error('Malformed official bus response')
    return value as { data: Row | Row[]; generated_timestamp?: string }
  })
  cache.set(url, { at: Date.now(), promise })
  try { return await promise } catch (error) { cache.delete(url); throw error }
}
function list(data: Row | Row[]) { if (!Array.isArray(data)) throw new Error('Official list unavailable'); return data }
function point(row: Row): BusPoint { return { lat: Number(row.lat), lng: Number(row.long ?? row.lng) } }
function metres(a: BusPoint, b: BusPoint) {
  if (![a.lat, a.lng, b.lat, b.lng].every(Number.isFinite)) return Infinity
  const rad = Math.PI / 180, h = Math.sin((b.lat - a.lat) * rad / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin((b.lng - a.lng) * rad / 2) ** 2
  return 6371000 * 2 * Math.asin(Math.min(1, Math.sqrt(h)))
}
interface Mapping { operator: string; route: string; bound: string; service_type: string; stop_id: string; sequence: number; stop_name: string }
async function kmbMapping(service: NonNullable<BusEta['browser_request']>['service'], target: BusStop): Promise<Mapping> {
  const [stopReply, routeReply] = await Promise.all([official(`${KMB}/stop`, 86_400_000), official(`${KMB}/route`, 86_400_000)])
  const stops = new Map(list(stopReply.data).map(row => [String(row.stop), row]))
  const variants = list(routeReply.data).filter(row => row.route === service.route)
  const candidates: { score: number; mapping: Mapping }[] = []
  // Requests are serial per operator; shared promises deduplicate metadata
  // between cards, services and refreshes without polling the entire network.
  for (const variant of variants) {
    const direction = variant.bound === 'O' ? 'outbound' : 'inbound'
    const rows = list((await official(`${KMB}/route-stop/${encodeURIComponent(service.route)}/${direction}/${variant.service_type}`, 86_400_000)).data)
    const known = rows.filter(row => stops.has(String(row.stop)))
    if (!known.length) continue
    const first = Math.min(...known.slice(0, 3).map(row => metres(service.stops[0], point(stops.get(String(row.stop))!))))
    const last = Math.min(...known.slice(-3).map(row => metres(service.stops.at(-1)!, point(stops.get(String(row.stop))!))))
    const sorted = known.map(row => ({ row, stop: stops.get(String(row.stop))!, distance: metres(target, point(stops.get(String(row.stop))!)) })).sort((a, b) => a.distance - b.distance)
    const hit = sorted[0]
    if (hit.distance > 40 || first + last > 300) continue
    candidates.push({ score: first + last + hit.distance, mapping: { operator: 'KMB', route: service.route, bound: String(variant.bound), service_type: String(variant.service_type), stop_id: String(hit.row.stop), sequence: Number(hit.row.seq), stop_name: String(hit.stop.name_en) } })
  }
  candidates.sort((a, b) => a.score - b.score)
  if (!candidates.length) throw new Error('Official stop not verified')
  return candidates[0].mapping
}
async function citybusMapping(service: NonNullable<BusEta['browser_request']>['service'], target: BusStop): Promise<Mapping> {
  const candidates: { score: number; mapping: Mapping }[] = []
  for (const [direction, bound] of [['outbound', 'O'], ['inbound', 'I']]) {
    const rows = list((await official(`${CTB}/route-stop/CTB/${encodeURIComponent(service.route)}/${direction}`, 86_400_000)).data)
    if (!rows.length) continue
    const position = Math.max(0, Math.min(rows.length - 1, target.sequence - 1))
    const indices = [...new Set([0, rows.length - 1, ...Array.from({ length: 5 }, (_, i) => position + i - 2).filter(i => i >= 0 && i < rows.length)])].sort((a, b) => a - b)
    const points = [] as { row: Row; stop: Row }[]
    for (let start = 0; start < indices.length; start += 4) {
      points.push(...await Promise.all(indices.slice(start, start + 4).map(async i => {
        const data = (await official(`${CTB}/stop/${rows[i].stop}`, 86_400_000)).data
        if (Array.isArray(data)) throw new Error('Malformed stop')
        return { row: rows[i], stop: data }
      })))
    }
    const hit = points.map(p => ({ ...p, distance: metres(target, point(p.stop)) })).sort((a, b) => a.distance - b.distance)[0]
    const endpoints = metres(service.stops[0], point(points[0].stop)) + metres(service.stops.at(-1)!, point(points.at(-1)!.stop))
    if (hit.distance > 40 || endpoints > 300) continue
    candidates.push({ score: endpoints + hit.distance, mapping: { operator: 'CTB', route: service.route, bound, service_type: '1', stop_id: String(hit.row.stop), sequence: Number(hit.row.seq), stop_name: String(hit.stop.name_en) } })
  }
  candidates.sort((a, b) => a.score - b.score)
  if (!candidates.length) throw new Error('Official stop not verified')
  return candidates[0].mapping
}
export function parseBusEta(payload: { data: Row | Row[]; generated_timestamp?: string }, mapping: Mapping, now = Date.now()): BusOperatorEta {
  const rows = list(payload.data).filter(row => row.route === mapping.route && row.dir === mapping.bound && Number(row.seq) === mapping.sequence && (mapping.operator === 'CTB' || String(row.service_type) === mapping.service_type))
  const recent = (value: unknown) => {
    if (typeof value !== 'string' || !/(?:Z|[+-]\d\d:\d\d)$/.test(value)) return false
    const age = now - Date.parse(value)
    return Number.isFinite(age) && age <= 180_000 && age >= -60_000
  }
  const fresh = rows.filter(row => recent(row.data_timestamp ?? payload.generated_timestamp))
  const observed = String(fresh.at(-1)?.data_timestamp ?? rows.at(-1)?.data_timestamp ?? payload.generated_timestamp ?? '')
  if (!fresh.length && !(list(payload.data).length === 0 && recent(observed))) return { operator: mapping.operator, status: 'stale', arrivals: [], observed_at: observed || null, stop_name: mapping.stop_name }
  const arrivals = fresh.filter(row => typeof row.eta === 'string' && /(?:Z|[+-]\d\d:\d\d)$/.test(row.eta) && Date.parse(row.eta) >= now).map(row => ({ at: String(row.eta), minutes: Math.ceil((Date.parse(String(row.eta)) - now) / 60_000), remark: String(row.rmk_en ?? row.remark_en ?? '') }))
  const unique = [...new Map(arrivals.map(a => [a.at, a])).values()].sort((a, b) => Date.parse(a.at) - Date.parse(b.at)).slice(0, 3)
  return { operator: mapping.operator, status: unique.length ? 'live' : 'no_arrivals', arrivals: unique, observed_at: observed, stop_name: mapping.stop_name }
}
async function browserEta(request: NonNullable<BusEta['browser_request']>): Promise<BusEta> {
  const operators = [...(request.service.operators.some(o => ['KMB', 'LWB'].includes(o)) ? ['KMB'] : []), ...(request.service.operators.includes('CTB') ? ['CTB'] : [])]
  const outcomes = await Promise.all(operators.map(async operator => {
    try {
      const mapping = operator === 'KMB' ? await kmbMapping(request.service, request.stop) : await citybusMapping(request.service, request.stop)
      const url = operator === 'KMB' ? `${KMB}/eta/${mapping.stop_id}/${encodeURIComponent(mapping.route)}/${mapping.service_type}` : `${CTB}/eta/CTB/${mapping.stop_id}/${encodeURIComponent(mapping.route)}`
      return { ...parseBusEta(await official(url), mapping), source_url: url }
    } catch (error) {
      if (import.meta.env.DEV) console.warn('Official bus arrivals unavailable', operator, error)
      return { operator, status: 'unavailable' as const, arrivals: [], observed_at: null }
    }
  }))
  return { status: 'checked_in_browser', checked_at: new Date().toISOString(), operators: outcomes }
}
export async function getBusEta(serviceId: string, stopId: string, signal?: AbortSignal): Promise<BusEta> {
  const response = await requestJson('GET', `/api/buses/eta?service_id=${encodeURIComponent(serviceId)}&td_stop_id=${encodeURIComponent(stopId)}`, undefined, { signal, timeoutMs: 30_000 }) as BusEta
  if (response.status === 'server_offline' && response.browser_request) return browserEta(response.browser_request)
  return response
}
export async function getCorridorBusServices(station: string, query: string, offset = 0, signal?: AbortSignal): Promise<{ total: number; services: BusService[] }> {
  return requestJson('GET', `/api/buses/services?station=${encodeURIComponent(station)}&q=${encodeURIComponent(query)}&offset=${offset}`, undefined, { signal }) as Promise<{ total: number; services: BusService[] }>
}
