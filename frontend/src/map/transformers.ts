// Pure transformers from the shared api types into the map data model.
// No DOM, no Leaflet, no colours. Geometry is only ever read from seed
// coordinates — never invented, interpolated beyond known stops, or
// back-filled with plausible values.

import type { Event, Network, NetworkNode, RouteCandidate, RouteLeg } from '../api/types'
import type {
  ImpactModel, ImpactPassability, ImpactSegmentView, MapLatLng, MapLineSegment, MapLineLayer,
  MapModel, MapRouteLayer, MapRouteLeg, MapStation,
} from './model'

/** Convention fallback when the network seed carries no catchment radius. */
export const DEFAULT_CATCHMENT_M = 800

/** Fully accessible heavy-rail stations are the demo's access points. */
const ACCESS_POINT_KIND = 'mtr_station'

/**
 * Impact severity for merging events that hit the same segment. Higher wins;
 * keywords outside the list score 0 and leave passability undecided (null).
 */
const IMPACT_SEVERITY: Record<string, number> = {
  closed: 4,
  reduced_capacity: 3,
  slow: 2,
  degraded: 2,
  crowded: 1,
}

/**
 * Route legs reference bare service codes (`182`, `481B`) while network line
 * ids carry a mode prefix (`BUS_182`, `GMB_481B`). Exact matches win.
 */
const LINE_ID_PREFIXES = ['', 'BUS_', 'GMB_', 'FERRY_']

function toPosition(node: NetworkNode): MapLatLng | null {
  if (typeof node.lat !== 'number' || !Number.isFinite(node.lat)) return null
  if (typeof node.lng !== 'number' || !Number.isFinite(node.lng)) return null
  return { lat: node.lat, lng: node.lng }
}

function toPoints(position: MapLatLng): [number, number] {
  return [position.lat, position.lng]
}

function severityOf(impact: string): number {
  return IMPACT_SEVERITY[impact] ?? 0
}

function passabilityFromImpact(impact: string): ImpactPassability {
  if (impact === 'closed') return false
  if (impact in IMPACT_SEVERITY) return true
  return null
}

/** Stable layer identity for the A/B/C route layers (colours live in the token layer). */
export function routeLayerId(index: number): string {
  return index < 3 ? `route-${'ABC'[index]}` : `route-${index + 1}`
}

export function effectiveCatchmentM(station: MapStation, model: Pick<MapModel, 'defaultCatchmentM'>): number {
  return station.catchmentM ?? model.defaultCatchmentM
}

export function buildMapModel(network: Network): MapModel {
  const stations: MapStation[] = []
  const stationsWithoutPosition: string[] = []
  const stationById = new Map<string, MapStation>()
  for (const node of network.nodes) {
    const position = toPosition(node)
    const station: MapStation = {
      id: node.id,
      name_en: node.name_en,
      name_zh: node.name_zh,
      kind: node.kind,
      position,
      accessible: node.accessible,
      lines: [...node.lines],
      provenance: node.provenance,
      catchmentM: typeof node.catchment_m === 'number' && Number.isFinite(node.catchment_m) && node.catchment_m > 0
        ? node.catchment_m
        : null,
      isAccessPoint: node.kind === ACCESS_POINT_KIND && node.accessible === true,
    }
    stations.push(station)
    stationById.set(node.id, station)
    if (!position) stationsWithoutPosition.push(node.id)
  }

  const stopIdsWithoutStation: string[] = []
  const noteMissingStop = (id: string) => {
    if (!stationById.has(id) && !stopIdsWithoutStation.includes(id)) stopIdsWithoutStation.push(id)
  }

  const lines: MapLineLayer[] = network.lines.map(line => {
    const stopIds = [...line.stops]
    const segments: MapLineSegment[] = []
    for (let i = 0; i < line.stops.length - 1; i++) {
      const fromId = line.stops[i]
      const toId = line.stops[i + 1]
      noteMissingStop(fromId)
      noteMissingStop(toId)
      const from = stationById.get(fromId)?.position ?? null
      const to = stationById.get(toId)?.position ?? null
      segments.push({
        fromId,
        toId,
        points: from && to ? [toPoints(from), toPoints(to)] : null,
      })
    }
    return { id: line.id, name_en: line.name_en, mode: line.mode, provenance: line.provenance, stopIds, segments }
  })

  const catchmentCircles = stations
    .filter(station => station.catchmentM !== null && station.position !== null)
    .map(station => ({ stationId: station.id, center: station.position as MapLatLng, radiusM: station.catchmentM as number }))

  const labels = stations
    .filter(station => station.position !== null)
    .map(station => ({ stationId: station.id, text: `${station.name_en} · ${station.name_zh}`, position: station.position as MapLatLng }))

  const metaCatchment = network.meta.catchment_m
  const defaultCatchmentM = typeof metaCatchment === 'number' && Number.isFinite(metaCatchment) && metaCatchment > 0
    ? metaCatchment
    : DEFAULT_CATCHMENT_M

  return {
    defaultCatchmentM,
    stations,
    lines,
    catchmentCircles,
    accessPoints: stations.filter(station => station.isAccessPoint),
    labels,
    stationsWithoutPosition,
    stopIdsWithoutStation,
  }
}

/**
 * Build the effective impact model. Time-window filtering belongs to the
 * DataSource (getPublishedEvents); this transformer enforces only the
 * published-status gate and never lets a non-published event colour a segment.
 */
export function buildImpactModel(events: Event[], network: Network): ImpactModel {
  const positions = new Map(network.nodes.map(node => [node.id, toPosition(node)]))
  const segmentMap = new Map<string, ImpactSegmentView>()
  const excludedEvents: ImpactModel['excludedEvents'] = []
  const segmentsWithoutGeometry: string[] = []

  for (const event of events) {
    if (event.status !== 'published') {
      excludedEvents.push({
        eventId: String(event.event_id),
        reason: `status is ${String(event.status)}, not published — not effective on the map`,
      })
      continue
    }
    for (const segment of event.affected_segments) {
      const key = `${segment.from_node}->${segment.to_node}`
      const from = positions.get(segment.from_node) ?? null
      const to = positions.get(segment.to_node) ?? null
      const points = from && to ? [toPoints(from), toPoints(to)] : null
      if (!points && !segmentsWithoutGeometry.includes(key)) segmentsWithoutGeometry.push(key)
      const passable = passabilityFromImpact(segment.impact)
      const capacityFactor = typeof segment.capacity_factor === 'number' && Number.isFinite(segment.capacity_factor)
        ? segment.capacity_factor
        : null
      const existing = segmentMap.get(key)
      if (!existing) {
        segmentMap.set(key, {
          key,
          eventIds: [event.event_id],
          fromNodeId: segment.from_node,
          toNodeId: segment.to_node,
          impact: segment.impact,
          capacityFactor,
          passable,
          published: true,
          points,
        })
        continue
      }
      // Same segment hit by several events: keep both event ids and the worst
      // impact — an earlier event is never silently overwritten.
      if (!existing.eventIds.includes(event.event_id)) existing.eventIds.push(event.event_id)
      if (severityOf(segment.impact) > severityOf(existing.impact)) {
        existing.impact = segment.impact
        existing.passable = passable
        existing.capacityFactor = capacityFactor ?? existing.capacityFactor
      }
    }
  }

  return { segments: [...segmentMap.values()], excludedEvents, segmentsWithoutGeometry }
}

function resolveLine(lineRef: string | undefined, network: Network) {
  if (!lineRef) return null
  for (const prefix of LINE_ID_PREFIXES) {
    const found = network.lines.find(line => line.id === `${prefix}${lineRef}`)
    if (found) return found
  }
  return null
}

function legGeometry(leg: RouteLeg, network: Network, positions: Map<string, MapLatLng | null>): Pick<MapRouteLeg, 'points' | 'lineId'> {
  const from = positions.get(leg.from) ?? null
  const to = positions.get(leg.to) ?? null
  const line = resolveLine(leg.line, network)
  if (!from || !to) return { points: null, lineId: line?.id ?? leg.line ?? null }
  if (line) {
    const a = line.stops.indexOf(leg.from)
    const b = line.stops.indexOf(leg.to)
    if (a >= 0 && b >= 0) {
      const ids = a <= b ? line.stops.slice(a, b + 1) : line.stops.slice(b, a + 1).reverse()
      const stopPositions = ids.map(id => positions.get(id))
      if (stopPositions.every(position => position !== null)) {
        return { points: stopPositions.map(position => toPoints(position as MapLatLng)), lineId: line.id }
      }
    }
  }
  // Seed geometry is schematic: fall back to the two known endpoints.
  return { points: [toPoints(from), toPoints(to)], lineId: line?.id ?? leg.line ?? null }
}

export function buildRouteLayers(routes: RouteCandidate[], network: Network): MapRouteLayer[] {
  const positions = new Map(network.nodes.map(node => [node.id, toPosition(node)]))
  return routes.map((route, index) => {
    const unmodelledStopIds: string[] = []
    const legs: MapRouteLeg[] = route.legs.map(leg => {
      for (const id of [leg.from, leg.to]) {
        if (!network.nodes.some(node => node.id === id) && !unmodelledStopIds.includes(id)) unmodelledStopIds.push(id)
      }
      return {
        mode: leg.mode,
        fromId: leg.from,
        toId: leg.to,
        ...legGeometry(leg, network, positions),
      }
    })
    return { layerId: routeLayerId(index), routeId: route.route_id, legs, unmodelledStopIds }
  })
}
