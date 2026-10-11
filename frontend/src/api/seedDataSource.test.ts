import { describe, expect, it } from 'vitest'
import { activePublishedEvents, seedDataSource, snapshotAt, verifiedWheelchairSeedRoute } from './seedDataSource'
import { profileFor } from './p3Context'
import { CORRIDOR_IDS, distanceMetres, legCoordinates, legDuration, nearestAccessPoint } from '../data'

describe('M0 seed boundary', () => {
  it('keeps bus and ferry filters meaningful in the fixed demo', async () => {
    const query = { origin: 'TAW', destination: 'ADM', departAt: snapshotAt, preset: 'fastest' } as const
    for (const mode of ['BUS', 'FERRY'] as const) {
      const routes = await seedDataSource.getRoutes({ ...query, requiredModes: [mode] })
      expect(routes.length).toBeGreaterThan(0)
      expect(routes.every(route => route.legs.some(leg => leg.mode === mode))).toBe(true)
    }
    expect(await seedDataSource.getRoutes({ ...query, requiredModes: ['MINIBUS'] })).toEqual([])
  })

  it('supports bus stops and ferry piers as map access points', async () => {
    const network = await seedDataSource.getNetwork()
    for (const id of ['BS_TAW', 'PIER_TST', 'PIER_CEN']) {
      const node = network.nodes.find(item => item.id === id)!
      expect(nearestAccessPoint(network, node)?.node.id).toBe(id)
    }
  })

  it('loads all four versioned seeds through the adapter and reports a fixed snapshot', async () => {
    const [network, { events, signals }, meta] = await Promise.all([
      seedDataSource.getNetwork(), seedDataSource.getEvents(), seedDataSource.getMeta(),
    ])
    expect(network.nodes.length).toBeGreaterThanOrEqual(6)
    expect(network.lines.length).toBeGreaterThan(1)
    expect(events).toHaveLength(3)
    expect(signals.length).toBeGreaterThan(0)
    expect(meta.simulationSeedAvailable).toBe(true)
    expect(meta.snapshotAt).toBe(snapshotAt)
    expect(CORRIDOR_IDS.every(id => network.nodes.some(node => node.id === id))).toBe(true)
  })

  it('keeps unreviewed and expired reports off the map', async () => {
    const { events } = await seedDataSource.getEvents()
    const active = await seedDataSource.getPublishedEvents(snapshotAt)
    expect(active.map(event => event.event_id)).toEqual(['evt_seed_003'])
    expect(activePublishedEvents(events, '2026-09-22T15:00:00+08:00')).toEqual([])
    expect(activePublishedEvents(events, '2026-09-22T08:04:00+08:00')).toEqual([])
  })

  it('does not fabricate other OD routes; presets reorder only modelled candidates', async () => {
    const base = { origin: 'TAW', destination: 'ADM', departAt: snapshotAt } as const
    const fastest = await seedDataSource.getRoutes({ ...base, preset: 'fastest' })
    const stable = await seedDataSource.getRoutes({ ...base, preset: 'most_stable' })
    const lessWalking = await seedDataSource.getRoutes({ ...base, preset: 'least_walking' })
    expect(fastest[0].total.time_s).toBe(Math.min(...fastest.map(route => route.total.time_s)))
    expect(stable[0].total.reliability).toBeGreaterThanOrEqual(stable[1].total.reliability)
    expect(lessWalking[0].total.walk_m).toBeLessThanOrEqual(lessWalking[1].total.walk_m)
    expect(lessWalking[0].total.reliability).toBeGreaterThanOrEqual(0.7)
    expect(fastest.some(route => route.route_id === 'r_seed_008')).toBe(false)
    expect(fastest.every(route => route.legs.every(leg =>
      !(leg.line === 'ERL' && (leg.from === 'HUH' && leg.to === 'EXC' || leg.from === 'EXC' && leg.to === 'ADM')),
    ))).toBe(true)
    expect(await seedDataSource.getRoutes({ ...base, destination: 'HUH', preset: 'fastest' })).toEqual([])
  })

  it('filters fixed seed cards by the selected Hong Kong boarding time', async () => {
    const query = { origin: 'TAW', destination: 'ADM', preset: 'fastest' } as const
    const night = await seedDataSource.getRoutes({ ...query, departAt: '2026-10-11T03:00:00+08:00' })
    const day = await seedDataSource.getRoutes({ ...query, departAt: '2026-10-11T12:00:00+08:00' })
    expect(night).toEqual([])
    expect(day.length).toBeGreaterThan(0)
  })

  it('keeps commuter cards while withholding wheelchair cards without affirmative access evidence', async () => {
    const base = { origin: 'TAW', destination: 'ADM', departAt: snapshotAt, preset: 'fastest' } as const
    const commuter = await seedDataSource.getRoutes({ ...base, persona: 'commuter', profile: profileFor('commuter', 'fastest') })
    const wheelchair = await seedDataSource.getRoutes({ ...base, persona: 'wheelchair', profile: profileFor('wheelchair', 'fastest') })
    expect(commuter.length).toBeGreaterThan(0)
    expect(wheelchair).toEqual([])
    expect(await seedDataSource.getRoutes({ ...base, persona: 'commuter', profile: profileFor('wheelchair', 'fastest') })).toEqual([])
    expect(commuter.every(route => !verifiedWheelchairSeedRoute(route))).toBe(true)
  })

  it('requires confirmed step-free nodes and legs, no bus, and both wheelchair limits', async () => {
    const network = structuredClone(await seedDataSource.getNetwork())
    const route = structuredClone((await seedDataSource.getRoutes({ origin: 'TAW', destination: 'ADM', departAt: snapshotAt, preset: 'fastest' }))[0])
    for (const node of network.nodes) { node.accessible = true; node.stairs = false }
    for (const leg of route.legs) { leg.accessible = true; leg.stairs = false }
    expect(verifiedWheelchairSeedRoute(route, network)).toBe(true)
    route.total.walk_m = 401; expect(verifiedWheelchairSeedRoute(route, network)).toBe(false)
    route.total.walk_m = 0; route.total.transfers = 3; expect(verifiedWheelchairSeedRoute(route, network)).toBe(false)
    route.total.transfers = 2; route.legs[0].mode = 'BUS'; expect(verifiedWheelchairSeedRoute(route, network)).toBe(false)
    route.legs[0].mode = 'MTR'; route.legs[0].stairs = undefined; expect(verifiedWheelchairSeedRoute(route, network)).toBe(false)
    route.legs[0].stairs = false; network.nodes.find(node => node.id === route.legs[0].from)!.accessible = null
    expect(verifiedWheelchairSeedRoute(route, network)).toBe(false)
  })

  it('uses seed catchment radius and does not invent geometry for missing stops', async () => {
    const network = await seedDataSource.getNetwork()
    const taiWai = network.nodes.find(node => node.id === 'TAW')!
    expect(nearestAccessPoint(network, taiWai)?.node.id).toBe('TAW')
    expect(taiWai.accessible).toBeNull()
    const accessible = nearestAccessPoint(network, taiWai, true)
    expect(accessible?.node.id).toBe('BS_TAW')
    expect(accessible?.node.accessible).toBe(true)
    expect(nearestAccessPoint(network, { lat: 0, lng: 0 })).toBeNull()
    expect(distanceMetres(taiWai, taiWai)).toBe(0)
    expect(network.meta.catchment_m).toBe(800)
    expect(legCoordinates({ mode: 'MINIBUS', from: 'BS_TAW', to: 'BS_TW', travel_s: 600, walk_m: 0, accessible: false, provenance: 'real-derived' }, network)).toEqual([])
  })

  it('reads engine durations without fabricating missing values', () => {
    const leg = { mode: 'MTR', from: 'TAW', to: 'KOT', walk_m: 0, accessible: true, provenance: 'simulated' } as const
    expect(legDuration({ ...leg, in_vehicle_s: 270 })).toBe('About 5 min')
    expect(legDuration(leg)).toBe('Travel time unavailable')
  })
  it('ships official adult fares for rail and mixed-mode tickets', async () => {
    const routes = await seedDataSource.getRoutes({ origin: 'TAW', destination: 'ADM', departAt: snapshotAt, preset: 'fastest' })
    expect(routes.filter(route => route.legs.every(leg => leg.mode === 'MTR' || leg.mode === 'WALK'))
      .every(route => route.total.fare_hkd === 17.1)).toBe(true)
    expect(routes.find(route => route.route_id === 'r_a3bb2d93a795746f')?.total.fare_hkd).toBe(18.9)
    expect(routes.find(route => route.route_id === 'r_007c4e09879d19cc')?.total.fare_hkd).toBe(20)
    for (const route of routes) {
      expect(route.legs.reduce((sum, leg) => sum + (leg.fare_hkd ?? 0), 0)).toBeCloseTo(route.total.fare_hkd)
    }
  })
})
