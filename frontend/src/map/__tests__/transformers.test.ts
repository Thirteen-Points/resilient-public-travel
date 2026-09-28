import { describe, expect, it } from 'vitest'
import networkSeed from '../../../../contracts/seed/network.seed.json'
import eventSeed from '../../../../contracts/seed/event.seed.json'
import routeSeed from '../../../../contracts/seed/routes.seed.json'
import type { Event, Network, RouteCandidate } from '../../api/types'
import { seedDataSource, snapshotAt } from '../../api/seedDataSource'
import {
  DEFAULT_CATCHMENT_M, buildImpactModel, buildMapModel, buildRouteLayers, effectiveCatchmentM, routeLayerId,
} from '../transformers'

// The api boundary tests cover normalization; here the raw seeds stand in
// directly so the transformers can be exercised on all seed rows unfiltered.
const network = networkSeed as unknown as Network
const events = eventSeed.events as unknown as Event[]
const routes = routeSeed.routes as unknown as RouteCandidate[]

describe('buildMapModel', () => {
  const model = buildMapModel(network)

  it('converts the six corridor stations with data-driven 800 m catchment circles', () => {
    const corridor = ['TAW', 'KOT', 'MKK', 'HUH', 'EXC', 'ADM'].map(id => model.stations.find(station => station.id === id))
    expect(corridor.every(Boolean)).toBe(true)
    expect(model.catchmentCircles).toHaveLength(6)
    for (const circle of model.catchmentCircles) expect(circle.radiusM).toBe(800)
    expect(model.defaultCatchmentM).toBe(800)
    expect(DEFAULT_CATCHMENT_M).toBe(800)
    expect(model.stations.find(station => station.id === 'TAW')?.position).toEqual({ lat: 22.3731, lng: 114.1789 })
  })

  it('falls back to the network default when a station has no explicit catchment', () => {
    const taiWai = model.stations.find(station => station.id === 'TAW')!
    const diamondHill = model.stations.find(station => station.id === 'DIH')!
    expect(taiWai.catchmentM).toBe(800)
    expect(effectiveCatchmentM(taiWai, model)).toBe(800)
    expect(diamondHill.catchmentM).toBeNull()
    expect(effectiveCatchmentM(diamondHill, model)).toBe(800)
    // No circle is fabricated for stations without an explicit radius.
    expect(model.catchmentCircles.some(circle => circle.stationId === 'DIH')).toBe(false)
  })

  it('marks only fully accessible MTR stations as access points', () => {
    expect(model.accessPoints.every(station => station.kind === 'mtr_station' && station.accessible === true)).toBe(true)
    expect(model.accessPoints).toHaveLength(16)
    expect(model.accessPoints.some(station => station.id === 'BS_TAW')).toBe(false)
    expect(model.accessPoints.some(station => station.id === 'PIER_TST')).toBe(false)
  })

  it('preserves line stop order and builds one segment per consecutive pair', () => {
    const erl = model.lines.find(line => line.id === 'ERL')!
    expect(erl.stopIds).toEqual(['TAW', 'KOT', 'MKK', 'HUH', 'EXC', 'ADM'])
    expect(erl.segments.map(segment => [segment.fromId, segment.toId]))
      .toEqual([['TAW', 'KOT'], ['KOT', 'MKK'], ['MKK', 'HUH'], ['HUH', 'EXC'], ['EXC', 'ADM']])
    expect(erl.segments.every(segment => segment.points !== null)).toBe(true)
  })

  it('reports unmodelled stops instead of inventing geometry', () => {
    expect(model.stopIdsWithoutStation).toEqual(['BS_TW'])
    const gmb = model.lines.find(line => line.id === 'GMB_481B')!
    expect(gmb.segments[0].points).toBeNull()
    expect(model.stationsWithoutPosition).toEqual([])
    expect(model.labels).toHaveLength(22)
    expect(model.labels[0].text).toBe('Tai Wai · 大圍')
  })

  it('keeps missing coordinates explicitly unknown end to end', () => {
    const broken = {
      meta: { version: 't', built_at: 't', catchment_m: 800, note: 'test' },
      nodes: [
        { id: 'A', name_en: 'A', name_zh: 'A', kind: 'mtr_station', lat: 22.3, lng: 114.1, lines: [], accessible: true, provenance: 'real' },
        { id: 'B', name_en: 'B', name_zh: 'B', kind: 'mtr_station', lng: 114.2, lines: [], accessible: true, provenance: 'real' },
      ],
      lines: [{ id: 'L', name_en: 'L', mode: 'MTR', stops: ['A', 'B'], provenance: 'real' }],
    } as unknown as Network
    const partial = buildMapModel(broken)
    expect(partial.stationsWithoutPosition).toEqual(['B'])
    expect(partial.lines[0].segments[0].points).toBeNull()
    expect(partial.labels.map(label => label.stationId)).toEqual(['A'])
    const event = { ...events[2], event_id: 'evt_test_ab', affected_segments: [{ from_node: 'A', to_node: 'B', impact: 'closed', capacity_factor: 0 }] }
    const impact = buildImpactModel([event], broken)
    expect(impact.segments[0].points).toBeNull()
    expect(impact.segmentsWithoutGeometry).toEqual(['A->B'])
  })
})

describe('buildImpactModel', () => {
  it('lets only published events generate effective segments', () => {
    const impact = buildImpactModel(events, network)
    expect(impact.segments.map(segment => segment.key).sort()).toEqual(['EXC->ADM', 'HUH->EXC', 'TAW->KOT'])
    expect(impact.excludedEvents.map(entry => entry.eventId)).toEqual(['evt_seed_001', 'evt_seed_002'])
    expect(impact.excludedEvents.every(entry => entry.reason.includes('not published'))).toBe(true)
  })

  it('maps impact types to passability and real coordinates', () => {
    const impact = buildImpactModel(events, network)
    const huhExc = impact.segments.find(segment => segment.key === 'HUH->EXC')!
    expect(huhExc.impact).toBe('closed')
    expect(huhExc.passable).toBe(false)
    expect(huhExc.published).toBe(true)
    expect(huhExc.points).toEqual([[22.3034, 114.1817], [22.2816, 114.1754]])
    const tawKot = impact.segments.find(segment => segment.key === 'TAW->KOT')!
    expect(tawKot.impact).toBe('crowded')
    expect(tawKot.passable).toBe(true)
    expect(tawKot.capacityFactor).toBe(0.9)
  })

  it('keeps disjoint events off each other\'s segments', () => {
    const evA = { ...events[2], event_id: 'ev_a', affected_segments: [{ from_node: 'HUH', to_node: 'EXC', impact: 'closed', capacity_factor: 0 }] }
    const evB = { ...events[2], event_id: 'ev_b', affected_segments: [{ from_node: 'TAW', to_node: 'KOT', impact: 'crowded', capacity_factor: 0.9 }] }
    const impact = buildImpactModel([evA, evB], network)
    expect(impact.segments).toHaveLength(2)
    expect(impact.segments.find(segment => segment.key === 'HUH->EXC')?.eventIds).toEqual(['ev_a'])
    expect(impact.segments.find(segment => segment.key === 'TAW->KOT')?.eventIds).toEqual(['ev_b'])
  })

  it('keeps the worst impact when events overlap, regardless of arrival order', () => {
    const closed = { ...events[2], event_id: 'ev_closed', affected_segments: [{ from_node: 'TAW', to_node: 'KOT', impact: 'closed', capacity_factor: 0 }] }
    const crowded = { ...events[2], event_id: 'ev_crowded', affected_segments: [{ from_node: 'TAW', to_node: 'KOT', impact: 'crowded', capacity_factor: 0.9 }] }
    for (const ordered of [[crowded, closed], [closed, crowded]]) {
      const impact = buildImpactModel(ordered, network)
      expect(impact.segments).toHaveLength(1)
      expect(impact.segments[0].impact).toBe('closed')
      expect(impact.segments[0].passable).toBe(false)
      expect([...impact.segments[0].eventIds].sort()).toEqual(['ev_closed', 'ev_crowded'])
    }
  })

  it('reports unknown impact keywords as undecided instead of guessing', () => {
    const weird = { ...events[2], affected_segments: [{ from_node: 'TAW', to_node: 'KOT', impact: 'mysterious', capacity_factor: 0.5 }] }
    const impact = buildImpactModel([weird], network)
    expect(impact.segments[0].passable).toBeNull()
  })
})

describe('buildRouteLayers', () => {
  it('assigns stable A/B/C layer identities', () => {
    const layers = buildRouteLayers(routes.slice(0, 3), network)
    expect(layers.map(layer => layer.layerId)).toEqual(['route-A', 'route-B', 'route-C'])
    expect(routeLayerId(0)).toBe('route-A')
    expect(routeLayerId(2)).toBe('route-C')
  })

  it('interpolates along known line stops and resolves prefixed line ids', () => {
    const all = buildRouteLayers(routes, network)
    const bus = all.find(layer => layer.routeId === 'r_seed_005')!
    expect(bus.legs[0].lineId).toBe('BUS_182')
    expect(bus.legs[0].points).toHaveLength(3) // BS_TAW → BS_HUH_TUNNEL → BS_ADM_E
    const tml = all.find(layer => layer.routeId === 'r_seed_001')!
    expect(tml.legs[0].lineId).toBe('TML')
    expect(tml.legs[0].points).toHaveLength(5) // TAW → DIH → HOM → HUH → ETS
    expect(tml.legs[1].mode).toBe('WALK')
    expect(tml.legs[1].points).toHaveLength(2) // ETS → TST schematic walk
  })

  it('flags unmodelled route endpoints instead of drawing them', () => {
    const all = buildRouteLayers(routes, network)
    const gmb = all.find(layer => layer.routeId === 'r_seed_008')!
    expect(gmb.unmodelledStopIds).toEqual(['BS_TW'])
    expect(gmb.legs[0].points).toBeNull()
  })

  it('stays consistent with DataSource-ranked queries', async () => {
    const fastest = await seedDataSource.getRoutes({ origin: 'TAW', destination: 'ADM', departAt: snapshotAt, preset: 'fastest' })
    const layers = buildRouteLayers(fastest.slice(0, 3), network)
    expect(layers.map(layer => layer.routeId)).toEqual(['r_seed_001', 'r_seed_004', 'r_seed_002'])
    expect(layers.map(layer => layer.layerId)).toEqual(['route-A', 'route-B', 'route-C'])
  })
})
