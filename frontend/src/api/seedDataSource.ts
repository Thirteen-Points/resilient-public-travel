import networkSeed from '../../../contracts/seed/network.seed.json'
import eventSeed from '../../../contracts/seed/event.seed.json'
import routeSeed from '../../../contracts/seed/routes.seed.json'
import simSeed from '../../../contracts/seed/sim.seed.json'
import { normalizeEventFeed, normalizeNetwork, normalizeRoutes, simSeedAvailable } from './normalizers'
import type { DemoMeta, Event, Preset, RouteCandidate, RouteQuery, TransitDataSource } from './types'

const networkResult = normalizeNetwork(networkSeed)
const feedResult = normalizeEventFeed(eventSeed)
const routesResult = normalizeRoutes(routeSeed)
const network = networkResult.value
const events = feedResult.value.events
const signals = feedResult.value.signals
const routes = routesResult.value.routes

/** Field-level conflicts between contracts/seed/*.json and src/api/types.ts, as "path: message" strings. Empty means the shipped seeds are clean. */
export const seedIssues: string[] = [...networkResult.issues, ...feedResult.issues, ...routesResult.issues]
  .map(issue => `${issue.path}: ${issue.message}`)

export const snapshotAt = routeSeed.meta.od.depart_at
export const seedOd = routeSeed.meta.od
export const disclaimer = 'Academic demonstration, not official emergency guidance. Routes and loads are estimated or simulated. Follow official MTR and Transport Department announcements.'

export function activePublishedEvents(items: Event[], at: string): Event[] {
  const instant = Date.parse(at)
  return items.filter(item =>
    item.status === 'published' &&
    Date.parse(item.window.start) <= instant &&
    (!item.published_at || Date.parse(item.published_at) <= instant) &&
    (!item.window.end || Date.parse(item.window.end) > instant) &&
    (!item.expires_at || Date.parse(item.expires_at) > instant),
  )
}

export function rankSeedRoutes(items: RouteCandidate[], preset: Preset): RouteCandidate[] {
  const usable = items.filter(item =>
    item.legs.every(leg => [leg.from, leg.to].every(id => network.nodes.some(node => node.id === id))) &&
    (preset !== 'least_walking' || item.total.reliability >= 0.7), // Do not elevate unreliable crowded buses solely for 30 m less walking.
  )
  return [...usable].sort((a, b) => {
    if (preset === 'fewest_transfers') return a.total.transfers - b.total.transfers || a.total.time_s - b.total.time_s
    if (preset === 'most_stable') return b.total.reliability - a.total.reliability || a.total.time_s - b.total.time_s
    if (preset === 'least_walking') return a.total.walk_m - b.total.walk_m || b.total.reliability - a.total.reliability || a.total.time_s - b.total.time_s
    return a.total.time_s - b.total.time_s
  })
}

function validateSeed() {
  if (!network.meta.catchment_m || !network.nodes.length || !network.lines.length) throw new Error('Network seed is incomplete')
  if (!events.length || !routes.length || !snapshotAt) throw new Error('Event or route seed is incomplete')
}

validateSeed()

const meta: DemoMeta = {
  snapshotAt,
  od: { origin: seedOd.origin, destination: seedOd.destination },
  provenance: 'simulated',
  disclaimer,
  simulationSeedAvailable: simSeedAvailable(simSeed),
}

export const seedDataSource: TransitDataSource = {
  async getNetwork() { return network },
  async getEvents() { return { events, signals } },
  async getPublishedEvents(at) { return activePublishedEvents(events, at) },
  async getRoutes(query: RouteQuery) {
    if (query.origin !== seedOd.origin || query.destination !== seedOd.destination) return []
    // Fixed seed estimates: preset reorders candidates, time does not recalculate them.
    return rankSeedRoutes(routes, query.preset)
  },
  async getMeta() { return meta },
}
