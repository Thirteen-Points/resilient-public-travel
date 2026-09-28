import type { Network, RouteCandidate, RouteLeg } from './api/types'

export const CORRIDOR_IDS = ['TAW', 'KOT', 'MKK', 'HUH', 'EXC', 'ADM'] as const

export const nodeIndex = (network: Network) => new Map(network.nodes.map(node => [node.id, node]))

export function formatHkt(value: string) {
  return new Intl.DateTimeFormat('en-HK', {
    timeZone: 'Asia/Hong_Kong', day: 'numeric', month: 'short',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).format(new Date(value)) + ' HKT'
}

export function formatRange(range: [number, number]) {
  return `${Math.round(range[0] / 60)}–${Math.round(range[1] / 60)} min`
}

export function modeSummary(route: RouteCandidate, network: Network) {
  const lines = new Map(network.lines.map(line => [line.id, line]))
  return route.legs.map(leg => leg.mode === 'WALK' ? 'Walk' : (lines.get(leg.line ?? '')?.name_en ?? leg.line ?? leg.mode)).join(' → ')
}

export function legCoordinates(leg: RouteLeg, network: Network): [number, number][] {
  const nodes = nodeIndex(network)
  const from = nodes.get(leg.from)
  const to = nodes.get(leg.to)
  if (!from || !to) return []
  const line = network.lines.find(item => item.id === leg.line || item.id === `BUS_${leg.line}`)
  if (line) {
    const a = line.stops.indexOf(leg.from), b = line.stops.indexOf(leg.to)
    if (a >= 0 && b >= 0) {
      const ids = a <= b ? line.stops.slice(a, b + 1) : line.stops.slice(b, a + 1).reverse()
      const points = ids.map(id => nodes.get(id))
      if (points.every(Boolean)) return points.map(node => [node!.lat, node!.lng])
    }
  }
  return [[from.lat, from.lng], [to.lat, to.lng]] // Seed geometry is schematic.
}

export function distanceMetres(a: { lat: number; lng: number }, b: { lat: number; lng: number }) {
  const rad = (degree: number) => degree * Math.PI / 180
  const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2
  return 6371000 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h))
}

export function nearestAccessPoint(network: Network, point: { lat: number; lng: number }) {
  const ordered = network.nodes.filter(node => node.kind === 'mtr_station' && node.accessible === true)
    .map(node => ({ node, metres: distanceMetres(node, point) }))
    .sort((a, b) => a.metres - b.metres)
  return ordered[0]?.metres <= network.meta.catchment_m ? ordered[0] : null
}
