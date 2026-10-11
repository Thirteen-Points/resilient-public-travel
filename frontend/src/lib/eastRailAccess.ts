import type { Network, NetworkNode } from '../api/types'
import { CORRIDOR_IDS, distanceMetres } from '../data'

export type Point = { lat: number; lng: number }
export type StraightLineAccess = { station: NetworkNode; metres: number; point: Point }

export function eastRailStations(network: Network): NetworkNode[] {
  return network.nodes.filter(node => CORRIDOR_IDS.some(id => id === node.id) &&
    node.kind === 'mtr_station' && node.lines.includes('ERL') &&
    Number.isFinite(node.lat) && Number.isFinite(node.lng))
}

export function findEastRailAccess(network: Network, point: Point): StraightLineAccess | null {
  if (!Number.isFinite(point.lat) || !Number.isFinite(point.lng)) return null
  return eastRailStations(network)
    .map(station => ({ station, metres: distanceMetres(point, station), point }))
    .filter(access => access.metres <= 800)
    .sort((a, b) => a.metres - b.metres)[0] ?? null
}
