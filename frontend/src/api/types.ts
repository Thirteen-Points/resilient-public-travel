export type Provenance = 'real' | 'real-derived' | 'simulated'
export type Preset = 'fastest' | 'most_stable' | 'fewest_transfers' | 'least_walking'

export interface NetworkNode {
  id: string
  name_en: string
  name_zh: string
  kind: string
  lat: number
  lng: number
  lines: string[]
  accessible: boolean | 'partial'
  provenance: Provenance
  catchment_m?: number
}

export interface NetworkLine {
  id: string
  name_en: string
  mode: string
  stops: string[]
  provenance: Provenance
}

export interface Network {
  meta: { version: string; built_at: string; catchment_m: number; note: string }
  nodes: NetworkNode[]
  lines: NetworkLine[]
  missing_nodes_note?: string
}

export interface AffectedSegment {
  from_node: string
  to_node: string
  impact: 'closed' | 'crowded' | 'degraded' | string
  capacity_factor: number
}

export interface Event {
  event_id: string
  version: number
  status: 'draft' | 'pending_review' | 'published' | 'updated' | 'expired' | 'rejected'
  title: string
  summary: string
  line: string
  severity: number
  confidence: number
  affected_segments: AffectedSegment[]
  window: { start: string; end: string | null }
  updated_at: string
  published_at?: string | null
  expires_at: string | null
  signals: string[]
  provenance: Provenance
}

export interface Signal {
  signal_id: string
  source_type: string
  source_name: string
  received_at: string
  raw_text: string
  provenance: Provenance
}

export interface RouteLeg {
  mode: string
  line?: string
  from: string
  to: string
  travel_s: number
  walk_m: number
  accessible: boolean | 'partial'
  provenance: Provenance
}

export interface RouteCandidate {
  route_id: string
  label: string
  legs: RouteLeg[]
  total: {
    time_s: number
    time_range_s: [number, number]
    transfers: number
    walk_m: number
    fare_hkd: number
    reliability: number
    freshness_s: number
  }
  score: number
  score_breakdown?: Array<{ criterion: string; normalized: number; weight: number; contribution: number }>
  warnings: string[]
  notes: string[]
  explain: string
  provenance: Provenance
}

export interface RouteQuery {
  origin: string
  destination: string
  departAt: string
  preset: Preset
}

export interface DemoMeta {
  snapshotAt: string
  od: { origin: string; destination: string }
  provenance: Provenance
  disclaimer: string
  simulationSeedAvailable: boolean
}

export interface TransitDataSource {
  getNetwork(): Promise<Network>
  getEvents(): Promise<{ events: Event[]; signals: Signal[] }>
  getPublishedEvents(at: string): Promise<Event[]>
  getRoutes(query: RouteQuery): Promise<RouteCandidate[]>
  getMeta(): Promise<DemoMeta>
}
