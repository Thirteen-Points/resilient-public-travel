import type { Network, NetworkNode } from '../api/types'
import { distanceMetres } from '../data'

export type Point = { lat: number; lng: number }
export type WalkingAccess = { station: NetworkNode; metres: number; point: Point }

const ROUTE_URL = 'https://valhalla1.openstreetmap.de/route'

export function eastRailStations(network: Network): NetworkNode[] {
  return network.nodes.filter(node => node.kind === 'mtr_station' && node.lines.includes('ERL') &&
    Number.isFinite(node.lat) && Number.isFinite(node.lng))
}

async function walkingMetres(from: Point, to: Point, signal: AbortSignal): Promise<number> {
  const response = await fetch(ROUTE_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Client-Id': 'resilient-public-travel.pages.dev' },
    body: JSON.stringify({ locations: [{ lat: from.lat, lon: from.lng }, { lat: to.lat, lon: to.lng }], costing: 'pedestrian', units: 'kilometers' }),
    signal,
  })
  if (!response.ok) throw new Error(`Walking route HTTP ${response.status}`)
  const result: unknown = await response.json()
  const km = (result as { trip?: { summary?: { length?: unknown } } })?.trip?.summary?.length
  if (typeof km !== 'number' || !Number.isFinite(km) || km < 0) throw new Error('Walking route has no valid distance')
  return km * 1000
}

/** Returns null only when the pedestrian routes were checked and none meets the limit. */
export async function findEastRailWalkingAccess(network: Network, point: Point, signal?: AbortSignal): Promise<WalkingAccess | null> {
  const limit = Math.min(network.meta.catchment_m, 800)
  const candidates = eastRailStations(network).filter(station => distanceMetres(point, station) <= limit)
  if (!candidates.length) return null // Walking distance cannot be shorter than straight-line distance.
  const timeout = AbortSignal.timeout(10000)
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout
  const results = await Promise.allSettled(candidates.map(async station => ({
    station, metres: await walkingMetres(point, station, combined), point,
  })))
  if (signal?.aborted) throw new DOMException('Walking check cancelled', 'AbortError')
  const measured = results.filter((item): item is PromiseFulfilledResult<WalkingAccess> => item.status === 'fulfilled')
    .map(item => item.value)
  if (!measured.length) throw new Error('Walking-route service is unavailable. Choose an East Rail station by name or try again.')
  const within = measured.filter(item => item.metres <= limit).sort((a, b) => a.metres - b.metres)[0]
  if (within) return within
  if (results.some(item => item.status === 'rejected')) throw new Error('Some walking routes could not be checked. Try again or choose an East Rail station by name.')
  return null
}
