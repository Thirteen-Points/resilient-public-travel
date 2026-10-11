import type { AffectedSegment, Network, NetworkLine, RouteLeg } from '../api/types'
import capture from './geometry.snapshot.json'

/** Rendering data only. The backend's graph, costs and accessibility are unchanged. */
export type GeometryPoint = [lat: number, lng: number]
export type GeometryPartQuality = 'official' | 'osm' | 'schematic'
export type GeometryQuality = GeometryPartQuality | 'mixed' | 'missing'

export interface GeometrySource {
  id: string
  label: string
  url: string
  capturedAt: string
  sha256: string
  captures?: Array<{ url: string; capturedAt: string; sha256: string }>
  featureIds: Array<string | number>
  licenseUrl: string
  attribution: string
}

export interface GeometryResolution {
  /** Separate paths must be drawn separately; a gap is never an implied connection. */
  parts: GeometryPoint[][]
  partQualities: GeometryPartQuality[]
  quality: GeometryQuality
  sources: GeometrySource[]
  note?: string
}

interface CapturedSegment {
  mode: string
  lineId: string | null
  from: string
  to: string
  geometry: { type: string; coordinates: number[][][] }
  quality: GeometryPartQuality
  sourceIds: string[]
  endpointOffsetM: number[]
  variant?: string
  note?: string
}

interface GeometrySnapshot {
  version: number
  coordinateOrder: string
  sources: GeometrySource[]
  segments: CapturedSegment[]
  missing: Array<{ mode: string; lineId: string | null; from: string; to: string; reason: string }>
}

const snapshot = capture as unknown as GeometrySnapshot
const key = (mode: string, lineId: string | null, from: string, to: string) => JSON.stringify([mode, lineId, from, to])
const segments = new Map(snapshot.segments.map(segment => [key(segment.mode, segment.lineId, segment.from, segment.to), segment]))
const missingReasons = new Map(snapshot.missing.map(segment => [key(segment.mode, segment.lineId, segment.from, segment.to), segment.reason]))
const sourceIndex = new Map(snapshot.sources.map(source => [source.id, source]))

export const geometrySources: readonly GeometrySource[] = snapshot.sources

function lineFor(network: Network, reference?: string, mode?: string): NetworkLine | undefined {
  if (!reference) return undefined
  const raw = reference === 'EAL' ? 'ERL' : reference
  const identities = new Set([raw, `BUS_${raw}`, `GMB_${raw}`, `FERRY_${raw}`])
  return network.lines.find(line => (!mode || line.mode === mode) && (identities.has(line.id) || line.name_en === raw))
}

function endpoint(network: Network, id: string): GeometryPoint | null {
  const node = network.nodes.find(item => item.id === id)
  return node && Number.isFinite(node.lat) && Number.isFinite(node.lng) ? [node.lat, node.lng] : null
}

function fallback(network: Network, mode: string, lineId: string | null, from: string, to: string): GeometryResolution {
  const a = endpoint(network, from), b = endpoint(network, to)
  if (!a || !b) return { parts: [], partQualities: [], quality: 'missing', sources: [], note: 'A modeled endpoint has no usable coordinates.' }
  return {
    parts: from === to ? [] : [[a, b]],
    partQualities: from === to ? [] : ['schematic'],
    quality: 'schematic', sources: [],
    note: missingReasons.get(key(mode, lineId, from, to)) ?? 'Schematic connection; verified path geometry is unavailable.',
  }
}

function captured(segment: CapturedSegment): GeometryResolution {
  // The source follows GeoJSON [longitude, latitude]; Leaflet requires [lat, lng].
  const parts = segment.geometry.coordinates.map(part => part.map(point => [point[1], point[0]] as GeometryPoint))
  return {
    parts, partQualities: parts.map(() => segment.quality), quality: segment.quality,
    sources: segment.sourceIds.map(id => sourceIndex.get(id)).filter((value): value is GeometrySource => Boolean(value)),
    note: segment.note,
  }
}

function combine(resolutions: GeometryResolution[]): GeometryResolution {
  const parts: GeometryPoint[][] = [], partQualities: GeometryPartQuality[] = []
  const sources = new Map<string, GeometrySource>(), notes = new Set<string>()
  for (const resolution of resolutions) {
    resolution.sources.forEach(source => sources.set(source.id, source))
    if (resolution.note) notes.add(resolution.note)
    resolution.parts.forEach((part, index) => {
      if (part.length < 2) return
      const quality = resolution.partQualities[index]
      const previous = parts.at(-1)
      const a = previous?.at(-1), b = part[0]
      // Only identical actual endpoints may be merged. In particular, source
      // gaps and schematic/verified boundaries never receive invented joins.
      if (a && a[0] === b[0] && a[1] === b[1] && partQualities.at(-1) === quality) previous!.push(...part.slice(1))
      else { parts.push(part.map(point => [...point] as GeometryPoint)); partQualities.push(quality) }
    })
  }
  const qualities = new Set(partQualities)
  const hasMissing = resolutions.some(resolution => resolution.quality === 'missing')
  const quality: GeometryQuality = qualities.size > 1 || (hasMissing && parts.length > 0) ? 'mixed' : partQualities[0] ?? 'missing'
  return { parts, partQualities, quality, sources: [...sources.values()], note: [...notes].join(' ') || undefined }
}

export interface SegmentGeometryRequest {
  mode: string
  lineId?: string | null
  from: string
  to: string
}

/** Resolve exact captures, then known consecutive stop slices, then an honest fallback. */
export function resolveSegmentGeometry(network: Network, request: SegmentGeometryRequest): GeometryResolution {
  const { mode, from, to } = request
  if (!endpoint(network, from) || !endpoint(network, to)) return fallback(network, mode, request.lineId ?? null, from, to)
  const line = lineFor(network, request.lineId ?? undefined, mode)
  const lineId = mode === 'WALK' ? null : line?.id ?? request.lineId ?? null
  const direct = segments.get(key(mode, lineId, from, to))
  if (direct) return captured(direct)
  if (line) {
    const a = line.stops.indexOf(from), b = line.stops.indexOf(to)
    if (a >= 0 && b >= 0 && a !== b) {
      const ids = a < b ? line.stops.slice(a, b + 1) : line.stops.slice(b, a + 1).reverse()
      const slices = ids.slice(0, -1).map((start, index) => {
        const end = ids[index + 1]
        if (!endpoint(network, start) || !endpoint(network, end)) return { parts: [], partQualities: [], quality: 'missing', sources: [], note: 'An intermediate modeled stop has no usable coordinates.' } as GeometryResolution
        const segment = segments.get(key(mode, lineId, start, end))
        return segment ? captured(segment) : fallback(network, mode, lineId, start, end)
      })
      return combine(slices)
    }
  }
  return fallback(network, mode, lineId, from, to)
}

export function resolveRouteLegGeometry(leg: RouteLeg, network: Network): GeometryResolution {
  return resolveSegmentGeometry(network, { mode: leg.mode, lineId: leg.line, from: leg.from, to: leg.to })
}

export function resolveNetworkLineGeometry(line: NetworkLine, network: Network): Array<GeometryResolution & { from: string; to: string }> {
  return line.stops.slice(0, -1).map((from, index) => {
    const to = line.stops[index + 1]
    return { from, to, ...resolveSegmentGeometry(network, { mode: line.mode, lineId: line.id, from, to }) }
  })
}

/** The event's line identity prevents cross-service ambiguity at interchanges. */
export function resolveImpactGeometry(segment: AffectedSegment, eventLine: string, network: Network): GeometryResolution {
  const line = lineFor(network, eventLine)
  return resolveSegmentGeometry(network, {
    mode: line?.mode ?? 'UNKNOWN', lineId: line?.id ?? eventLine,
    from: segment.from_node, to: segment.to_node,
  })
}
