// Pure data model consumed by map rendering (Leaflet wiring stays with the
// main agent's components). Everything here is plain data with no DOM, map
// library, or styling dependency — colours belong to the token layer.

/** Geographic position. `null` means the seed has no coordinates for the entity; the missing state must be preserved, never filled with plausible values. */
export interface MapLatLng {
  lat: number
  lng: number
}

export interface MapStation {
  id: string
  name_en: string
  name_zh: string
  kind: string
  position: MapLatLng | null
  accessible: boolean | 'partial' | null
  lines: string[]
  provenance: string
  /** Explicit catchment radius in metres from the seed, or null when the station has none. */
  catchmentM: number | null
  /** Fully accessible MTR stations — the demo's entry points within the catchment radius. */
  isAccessPoint: boolean
}

/** A consecutive stop pair on a line. `points` is null when an endpoint has no coordinates. */
export interface MapLineSegment {
  fromId: string
  toId: string
  points: [number, number][] | null
}

export interface MapLineLayer {
  id: string
  name_en: string
  mode: string
  provenance: string
  /** Stop ids in seed order — never re-sorted or de-duplicated. */
  stopIds: string[]
  segments: MapLineSegment[]
}

/** Geographic catchment circle. `radiusM` is a ground distance in metres, not a pixel radius. */
export interface MapCatchmentCircle {
  stationId: string
  center: MapLatLng
  radiusM: number
}

export interface MapLabel {
  stationId: string
  text: string
  position: MapLatLng
}

export interface MapModel {
  /** Network-wide fallback radius (network.meta.catchment_m, or the 800 m convention when absent). */
  defaultCatchmentM: number
  stations: MapStation[]
  lines: MapLineLayer[]
  /** Only stations that carry an explicit catchment_m in the seed (the six corridor stations). */
  catchmentCircles: MapCatchmentCircle[]
  accessPoints: MapStation[]
  labels: MapLabel[]
  /** Stations whose seed record has no usable coordinates. */
  stationsWithoutPosition: string[]
  /** Stop ids referenced by lines but absent from the node list (e.g. BS_TW). */
  stopIdsWithoutStation: string[]
}

/** true = passable, false = blocked, null = impact keyword unknown, passability honestly undecided. */
export type ImpactPassability = boolean | null

export interface ImpactSegmentView {
  /** `${fromNodeId}->${toNodeId}` — stable identity of the affected pair. */
  key: string
  eventIds: string[]
  fromNodeId: string
  toNodeId: string
  /** Worst impact across merged events (severity order in transformers.ts). */
  impact: string
  capacityFactor: number | null
  passable: ImpactPassability
  published: true
  points: [number, number][] | null
}

export interface ImpactModel {
  segments: ImpactSegmentView[]
  /** Events kept out of the model, with a reason — never silently dropped. */
  excludedEvents: Array<{ eventId: string; reason: string }>
  /** Segment keys whose endpoints lack coordinates. */
  segmentsWithoutGeometry: string[]
}

export interface MapRouteLeg {
  mode: string
  /** Network line id the leg was resolved to (e.g. `BUS_182`), or the raw reference when unresolvable. */
  lineId: string | null
  fromId: string
  toId: string
  /** Interpolated along the line's stop order when resolvable; endpoint pair otherwise; null when an endpoint is unmodelled. */
  points: [number, number][] | null
}

export interface MapRouteLayer {
  /** Stable layer identity for route A/B/C — colour assignment stays with the token layer. */
  layerId: string
  routeId: string
  legs: MapRouteLeg[]
  /** Stop ids referenced by this route but missing from the network seed. */
  unmodelledStopIds: string[]
}
