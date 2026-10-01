import { describe, expect, it } from 'vitest'
import networkFixture from '../fixtures/network.fixture.json'
import eventFixture from '../fixtures/event.fixture.json'
import routesFixture from '../fixtures/routes.fixture.json'
import { SeedStructureError, normalizeEventFeed, normalizeNetwork, normalizeRoutes } from '../normalizers'
import { activePublishedEvents, seedDataSource, seedIssues, snapshotAt } from '../seedDataSource'

const issueTexts = (issues: { path: string; message: string }[]) => issues.map(issue => `${issue.path}: ${issue.message}`)

describe('shipped seeds through the normalizers', () => {
  it('reads all four seed files with zero field-level conflicts against the shared types', () => {
    // network + event feed + routes normalize at import time (they would throw otherwise);
    // the sim seed is proven readable through getMeta below.
    expect(seedIssues).toEqual([])
  })

  it('reports the sim seed as available and pins the demo snapshot', async () => {
    const meta = await seedDataSource.getMeta()
    expect(meta.simulationSeedAvailable).toBe(true)
    expect(meta.snapshotAt).toBe('2026-09-22T08:20:00+08:00')
    expect(snapshotAt).toBe('2026-09-22T08:20:00+08:00')
  })

  it('keeps the six corridor stations with the catchment radius taken from the data', async () => {
    const network = await seedDataSource.getNetwork()
    const corridor = ['TAW', 'KOT', 'MKK', 'HUH', 'EXC', 'ADM']
      .map(id => network.nodes.find(node => node.id === id))
    expect(corridor).toHaveLength(6)
    expect(corridor.every(node => node?.catchment_m === 800)).toBe(true)
    expect(network.meta.catchment_m).toBe(800)
  })

  it('preserves provenance on every node, line, event and route candidate', async () => {
    const [network, { events }, routes] = await Promise.all([
      seedDataSource.getNetwork(),
      seedDataSource.getEvents(),
      seedDataSource.getRoutes({ origin: 'TAW', destination: 'ADM', departAt: snapshotAt, preset: 'fastest' }),
    ])
    expect(network.nodes.every(node => typeof node.provenance === 'string')).toBe(true)
    expect(network.lines.every(line => typeof line.provenance === 'string')).toBe(true)
    expect(events.every(event => typeof event.provenance === 'string')).toBe(true)
    expect(routes.every(route => typeof route.provenance === 'string')).toBe(true)
    // Engine estimates use simulated fare/capacity policies and remain labelled.
    expect(events.find(event => event.event_id === 'evt_seed_003')?.provenance).toBe('simulated')
    expect(routes.every(route => route.provenance === 'simulated')).toBe(true)
  })

  it('returns stable route results for identical queries', async () => {
    const query = { origin: 'TAW', destination: 'ADM', departAt: snapshotAt, preset: 'most_stable' } as const
    const first = await seedDataSource.getRoutes(query)
    const second = await seedDataSource.getRoutes(query)
    expect(second).toEqual(first)
    expect(first.length).toBeGreaterThan(3)
  })

  it('treats only published, in-window events as active impact events', async () => {
    const { events } = await seedDataSource.getEvents()
    const active = await seedDataSource.getPublishedEvents(snapshotAt)
    expect(active.map(event => event.event_id)).toEqual(['evt_seed_003'])
    const activeIds = new Set(active.map(event => event.event_id))
    expect(events.filter(event => event.status !== 'published').every(event => !activeIds.has(event.event_id))).toBe(true)
    // Later within the published window it is still the only active event.
    expect(activePublishedEvents(events, '2026-09-22T09:30:00+08:00').map(event => event.event_id)).toEqual(['evt_seed_003'])
  })
})

describe('normalizers against imperfect fixtures', () => {
  it('flags invalid network fields without rewriting or fabricating values', () => {
    const { value, issues } = normalizeNetwork(networkFixture)
    const texts = issueTexts(issues)
    expect(texts.some(text => text.startsWith('nodes[1].lat:'))).toBe(true)
    expect(texts.some(text => text.startsWith('nodes[1].provenance:'))).toBe(true)
    expect(texts.some(text => text.startsWith('nodes[2].name_zh:'))).toBe(true)
    expect(texts.some(text => text.startsWith('lines[1].mode:'))).toBe(true)
    // Values are kept exactly as shipped, so nothing silently becomes "valid".
    expect(value.nodes[1].lat).toBe('22.3')
    expect(value.nodes[1].provenance).toBe('maybe')
    // An absent optional catchment_m stays absent and is not an issue.
    expect('catchment_m' in value.nodes[1]).toBe(false)
    expect(texts.some(text => text.includes('nodes[1].catchment_m'))).toBe(false)
  })

  it('flags off-enum status and out-of-range numbers, but not absent optional published_at', () => {
    const { value, issues } = normalizeEventFeed(eventFixture)
    const texts = issueTexts(issues)
    expect(texts.some(text => text.startsWith('events[1].status:'))).toBe(true)
    expect(texts.some(text => text.startsWith('events[1].severity:'))).toBe(true)
    expect(texts.some(text => text.startsWith('events[1].confidence:'))).toBe(true)
    expect(texts.some(text => text.startsWith('events[1].affected_segments[0].capacity_factor:'))).toBe(true)
    expect(texts.some(text => text.startsWith('events[2].expires_at:'))).toBe(true)
    expect(texts.some(text => text.startsWith('events[2].published_at'))).toBe(false)
    expect(value.events[1].status).toBe('rumour')
  })

  it('accepts missing optional fields (score_breakdown) and flags inverted ranges and wrong shapes', () => {
    const { value, issues } = normalizeRoutes(routesFixture)
    const texts = issueTexts(issues)
    expect(texts.filter(text => text.startsWith('routes[0]'))).toEqual([])
    expect(texts.some(text => text.startsWith('routes[1].total.time_range_s:'))).toBe(true)
    expect(texts.some(text => text.startsWith('routes[1].score:'))).toBe(true)
    expect(texts.some(text => text.startsWith('routes[1].warnings:'))).toBe(true)
    // The inverted range is reported, not silently swapped.
    expect(value.routes[1].total.time_range_s[0]).toBe(340)
    expect(value.routes[0].score_breakdown).toBeUndefined()
  })

  it('throws SeedStructureError only for unusable overall structures', () => {
    expect(() => normalizeNetwork(null)).toThrow(SeedStructureError)
    expect(() => normalizeNetwork({ meta: { catchment_m: 800 }, nodes: [], lines: [] })).toThrow(SeedStructureError)
    expect(() => normalizeNetwork({ meta: { catchment_m: '800' }, nodes: [{}], lines: [{}] })).toThrow(SeedStructureError)
    expect(() => normalizeEventFeed({ events: [], signals: [] })).toThrow(SeedStructureError)
    expect(() => normalizeEventFeed({ events: [{}], signals: 'none' })).toThrow(SeedStructureError)
    expect(() => normalizeRoutes({ routes: [] })).toThrow(SeedStructureError)
  })
})
