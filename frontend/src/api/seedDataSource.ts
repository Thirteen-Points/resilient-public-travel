import networkSeed from '../../../contracts/seed/network.seed.json'
import eventSeed from '../../../contracts/seed/event.seed.json'
import routeSeed from '../../../contracts/seed/routes.seed.json'
import simSeed from '../../../contracts/seed/sim.seed.json'
import { normalizeEventFeed, normalizeNetwork, normalizeRoutes, simSeedAvailable } from './normalizers'
import { resolveProfile } from './p3Context'
import type { DemoMeta, Event, Network, Preset, RouteCandidate, RouteQuery, TransitDataSource } from './types'

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

/** Seed accessibility is unknown at several stations. Only affirmative evidence can qualify a wheelchair demo card. */
export function verifiedWheelchairSeedRoute(route: RouteCandidate, sourceNetwork: Network = network): boolean {
  if (route.total.walk_m > 400 || route.legs.reduce((sum, leg) => sum + leg.walk_m, 0) > 400 || route.total.transfers > 2 || !route.legs.length) return false
  const nodes = new Map(sourceNetwork.nodes.map(node => [node.id, node]))
  return route.legs.every(leg =>
    leg.accessible === true && leg.stairs === false &&
    // The seed has no affirmative low-floor evidence for bus legs.
    (leg.mode === 'MTR' || leg.mode === 'WALK') &&
    nodes.get(leg.from)?.accessible === true && nodes.get(leg.from)?.stairs === false &&
    nodes.get(leg.to)?.accessible === true && nodes.get(leg.to)?.stairs === false,
  )
}

const HKT_OFFSET_MS = 8 * 60 * 60 * 1000
const DAY_MS = 24 * 60 * 60 * 1000

function serviceSeconds(clock: string): number {
  const [hour, minute] = clock.split(':').map(Number)
  return (hour * 60 + minute) * 60
}

function withinServiceHours(at: number, hours: string, offsetSeconds: number): boolean {
  const [startText, endText] = hours.split('-')
  const start = serviceSeconds(startText) + offsetSeconds
  let end = serviceSeconds(endText) + offsetSeconds
  if (end < start) end += 24 * 60 * 60
  const local = at + HKT_OFFSET_MS
  const midnight = Math.floor(local / DAY_MS) * DAY_MS
  return [-DAY_MS, 0].some(day => midnight + day + start * 1000 <= local && local <= midnight + day + end * 1000)
}

function seedRouteBoardable(route: RouteCandidate, departAt: string): boolean {
  const queryTime = Date.parse(departAt)
  const snapshotTime = Date.parse(snapshotAt)
  if (!Number.isFinite(queryTime)) return false
  return route.legs.every(leg => {
    if (leg.mode === 'WALK') return true
    const line = network.lines.find(item => item.id === leg.line)
    if (!line?.service_hours) return true // An actual overnight service remains eligible.
    const fromIndex = line.stops.indexOf(leg.from)
    const toIndex = line.stops.indexOf(leg.to)
    if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex || !leg.depart) return false
    const reverse = toIndex < fromIndex
    const durations = line.seg_time_s ?? []
    const offset = reverse
      ? durations.slice(fromIndex).reduce((sum, seconds) => sum + seconds, 0)
      : durations.slice(0, fromIndex).reduce((sum, seconds) => sum + seconds, 0)
    const boardAt = queryTime + Date.parse(leg.depart) - snapshotTime
    const hours = reverse ? line.service_hours_reverse ?? line.service_hours : line.service_hours
    return Number.isFinite(boardAt) && withinServiceHours(boardAt, hours, offset)
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
    const profile = resolveProfile(query)
    // Seed travel times stay fixed; discard cards that would board a closed service.
    return rankSeedRoutes(routes, query.preset).filter(route =>
      seedRouteBoardable(route, query.departAt) &&
      (profile.mobility !== 'wheelchair' || verifiedWheelchairSeedRoute(route) &&
        route.total.walk_m <= (profile.max_walk_m ?? 400) &&
        route.total.transfers <= (profile.max_transfers ?? 2)),
    )
  },
  async getMeta() { return meta },
}
