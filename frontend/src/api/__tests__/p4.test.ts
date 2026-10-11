import { afterEach, describe, expect, it, vi } from 'vitest'
import baseline from '../../../../data/sim/m2_six_station_directed_od_am_peak_p3_shared_segments.json'
import stress from '../../../../data/sim/m2_six_station_directed_od_am_peak_p3_shared_segments_residual_10pct.json'
import legacy from '../../../../data/sim/scn_huh_exc_closed_am_peak.json'
import routes from '../../../../contracts/seed/routes.seed.json'
import { allocationRows, chatPayload, compare, delayOutcome, parseChat, parseSimulation } from '../p3Api'
import { applyPreference, parsePreference, preference } from '../preferences'
import { contextKey, profileFor, resolveProfile } from '../p3Context'
import { lastSuccessfulCollection, parseReplanningStatus, parseSourcesStatus } from '../runtimeStatus'
import { queryRoutesWithMetadata } from '../liveTransitApi'
import type { JourneyContext } from '../types'

const context: JourneyContext = { origin: 'TAW', destination: 'ADM', departAt: '2026-10-07T08:20:00+08:00', preset: 'fastest', persona: 'commuter', eventIds: [], eventRevisions: '' }
const weights = { time: .25, transfers: .1, walk: .1, price: .35, comfort: .05, reliability: .1, carbon: .025, freshness: .025 }
const json = (body: unknown, snapshot?: string) => new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json', ...(snapshot ? { 'X-Route-Snapshot': snapshot } : {}) } })
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('explicit preference application', () => {
  it('tightens reduced mobility and never loosens existing wheelchair restrictions', () => {
    const standard = applyPreference(profileFor('commuter', 'fastest'), { mobility: 'reduced', max_walk_m: 500, hard_flags: [] })
    expect(standard).toMatchObject({ mobility: 'reduced', max_walk_m: 400, hard_flags: ['no_stairs'] })
    const wheelchair = applyPreference({ ...profileFor('wheelchair', 'most_stable'), max_walk_m: 200 }, { mobility: 'standard', max_walk_m: 800, hard_flags: [], weights })
    expect(wheelchair).toMatchObject({ mobility: 'wheelchair', max_walk_m: 200, max_transfers: 2, weights })
    expect(wheelchair.hard_flags).toEqual(['no_minibus', 'no_non_lowfloor_bus', 'no_stairs'])
  })
  it('sends confirmed weights and hard limits identically to routing and chat', async () => {
    const profile = applyPreference(profileFor('wheelchair', 'fastest'), { max_walk_m: 200, hard_flags: [], weights })
    const selected = { ...context, profile, persona: 'wheelchair' as const }
    const fetch = vi.fn().mockResolvedValue(json([], 'calculation-12'))
    vi.stubGlobal('fetch', fetch)
    const result = await queryRoutesWithMetadata(selected)
    const routeBody = JSON.parse(fetch.mock.calls[0][1].body)
    expect(chatPayload(selected, 'Explain').profile).toEqual(routeBody.profile)
    expect(routeBody.profile).toMatchObject({ mobility: 'wheelchair', max_walk_m: 200, weights })
    expect(result.snapshotId).toBe('calculation-12')
    expect(contextKey(selected)).not.toBe(contextKey(context))
    expect(resolveProfile({ ...selected, preset: 'fewest_transfers' }).preset).toBe('fewest_transfers')
  })
  it('rejects unsafe or malformed patches without silently accepting arbitrary keys', () => {
    const valid = { patch: { mobility: null, max_walk_m: null, hard_flags: [], weights }, method: 'rule_fallback', explanation: 'Prefer lower fares.' }
    expect(parsePreference(valid).patch.weights).toEqual(weights)
    for (const patch of [
      { ...valid.patch, max_walk_m: -1 }, { ...valid.patch, max_walk_m: 900 },
      { ...valid.patch, hard_flags: ['ignore_accessibility'] }, { ...valid.patch, origin: 'ADM' },
      { ...valid.patch, weights: { ...weights, price: .9 } }, { ...valid.patch, price_sensitive: Infinity },
    ]) expect(() => parsePreference({ ...valid, patch })).toThrow('Invalid preference patch')
  })
  it('uses the actual persona endpoint and exposes its fallback method', async () => {
    const result = { patch: { hard_flags: [], max_walk_m: 200 }, explanation: 'Walking limit extracted.', method: 'rule_fallback' }
    const fetch = vi.fn().mockResolvedValue(json(result)); vi.stubGlobal('fetch', fetch)
    expect(await preference('  少走路  ', profileFor('commuter', 'fastest'), new AbortController().signal)).toEqual(result)
    expect(fetch.mock.calls[0][0]).toContain('/api/persona/parse')
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({ free_text: '少走路', current_profile: { mobility: 'standard' } })
  })
  it('accepts legacy chat replies and validates supplied calculation metadata', () => {
    const reply = { message: 'Actual reply', fallback: true, tool_calls: [], routes: [] }
    expect(parseChat(reply).graph_snapshot).toBeUndefined()
    const profile = profileFor('wheelchair', 'most_stable')
    expect(parseChat({ ...reply, graph_snapshot: 'graph-17', effective_profile: profile })).toMatchObject({ graph_snapshot: 'graph-17', effective_profile: profile })
    expect(() => parseChat({ ...reply, graph_snapshot: '' })).toThrow('snapshot metadata')
    expect(() => parseChat({ ...reply, effective_profile: { ...profile, weights: { time: 1 } } })).toThrow('profile weights')
  })
})

describe('same-calculation comparison', () => {
  it('verifies matching response headers even if surrounding graph reads differ', async () => {
    let reads = 0
    const fetch = vi.fn((url: string) => Promise.resolve(url.includes('/snapshot') ? json({ snapshot_id: `observed-${++reads}`, affected_edges: [] }) : json([], 'calculated-42')))
    vi.stubGlobal('fetch', fetch)
    const result = await compare({ ...context, profile: { ...profileFor('commuter', 'fastest'), weights, max_walk_m: 100 } }, new AbortController().signal)
    expect(result).toMatchObject({ verified: true, snapshotId: 'calculated-42', observedSnapshot: 'observed-2' })
    const bodies = fetch.mock.calls.filter(call => call[0].includes('/routes/query')).map(call => JSON.parse((call as unknown as [string, RequestInit])[1].body as string))
    expect(bodies[0].profile.weights).toBeUndefined()
    expect(bodies[0].profile.max_walk_m).toBeUndefined()
    expect(bodies[1].profile).toMatchObject({ mobility: 'wheelchair', max_walk_m: 400, max_transfers: 2 })
  })
  it('retries the entire pair once on mismatched headers, never commits half a pair', async () => {
    let queries = 0
    vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(url.includes('/snapshot') ? json({ snapshot_id: 'observed', affected_edges: [] }) : json([], ++queries <= 2 ? `old-${queries}` : 'matched'))))
    expect(await compare(context, new AbortController().signal)).toMatchObject({ verified: true, snapshotId: 'matched' })
    expect(queries).toBe(4)
    queries = 0
    vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(url.includes('/snapshot') ? json({ snapshot_id: 'observed', affected_edges: [] }) : json([], `never-matched-${++queries}`))))
    await expect(compare(context, new AbortController().signal)).rejects.toThrow('Both profiles were retried')
    expect(queries).toBe(4)
  })
  it('withholds routes that violate wheelchair accessibility instead of showing misleading alternatives', async () => {
    const inaccessible = structuredClone(routes.routes[0]); inaccessible.legs[0].accessible = false
    vi.stubGlobal('fetch', vi.fn((url: string, options?: RequestInit) => Promise.resolve(url.includes('/snapshot') ? json({ snapshot_id: 'observed', affected_edges: [] }) : json(JSON.parse(String(options?.body)).profile.mobility === 'wheelchair' ? [inaccessible] : [], 'same'))))
    await expect(compare(context, new AbortController().signal)).rejects.toThrow('wheelchair constraints')
  })
})

describe('multi-OD simulation accounting', () => {
  it('displays unchanged baseline and the actual modest stress-case improvement', () => {
    const normal = parseSimulation(baseline), congested = parseSimulation(stress)
    expect(normal).toMatchObject({ population: 10000, od_count: 30, seed: 20260922 })
    expect(delayOutcome(normal)).toContain('unchanged')
    expect(normal.delta?.delay_reduction_pct).toBe(0)
    expect(congested.delta?.delay_reduction_pct).toBe(1.6)
    expect(congested.guided.unmet_demand).toBe(199)
    expect(congested.guided.unassigned_demand).toBe(199)
    expect(normal.generated_at).toBe(baseline.generated_at)
    expect(congested.generated_at).toBe(stress.generated_at)
  })
  it('keeps every person in the chart denominator, including unassigned demand', () => {
    const value = parseSimulation(stress), rows = allocationRows(value)!
    expect(rows.reduce((sum, row) => sum + row.users, 0)).toBe(10000)
    expect(rows.reduce((sum, row) => sum + row.share, 0)).toBeCloseTo(1, 12)
    expect(rows.at(-1)).toEqual({ label: 'Unassigned', users: 199, share: .0199 })
    expect(rows.some(row => row.label.startsWith('Other routes'))).toBe(true)
    const distinct = structuredClone(value); distinct.guided.unmet_demand = 600
    expect(allocationRows(distinct)).toEqual(rows)
    expect(distinct.guided.unmet_demand).not.toBe(distinct.guided.unassigned_demand)
  })
  it('withholds shares when legacy counts are missing or accounting is inconsistent', () => {
    expect(allocationRows(parseSimulation(legacy))).toBeNull()
    const bad = parseSimulation(structuredClone(stress)); bad.guided.unassigned_demand!++
    expect(allocationRows(bad)).toBeNull()
    const incomplete = parseSimulation(structuredClone(stress)); delete incomplete.guided.route_load![0].assigned_users
    expect(allocationRows(incomplete)).toBeNull()
  })
})

describe('actual collector and replanning status contracts', () => {
  const last = '2026-10-06T08:00:00Z', attempt = Date.parse('2026-10-06T08:15:00Z') / 1000
  const collector = { enabled: true, scheduled: true, collecting: false, status: 'partial_failure', stale: true, last_attempt: attempt, last_result: { at: '2026-10-06T08:15:00Z', status: 'partial_failure', failures: 2, added: 1, duplicate: 0 } }
  const sources = { offline: false, configured: true, publishes_events: false, sources: { mtr: collector } }
  it('accepts the numeric failure count and never substitutes attempt time for success', () => {
    const parsed = parseSourcesStatus(sources)
    expect(parsed.sources.mtr.last_result?.failures).toBe(2)
    expect(lastSuccessfulCollection(parsed.sources.mtr)).toBeUndefined()
    expect(lastSuccessfulCollection({ ...collector, last_success_at: last })).toBe(last)
    expect(lastSuccessfulCollection({ ...collector, last_result: { at: last, status: 'success', failures: 0 } })).toBe(last)
  })
  it('rejects malformed counts and ambiguous collection timestamps', () => {
    expect(() => parseSourcesStatus({ ...sources, sources: { mtr: { ...collector, last_success_at: '2026-10-06T08:00' } } })).toThrow('last-success')
    expect(() => parseSourcesStatus({ ...sources, sources: { mtr: { ...collector, last_result: { ...collector.last_result, failures: [] } } } })).toThrow('counts')
  })
  it('preserves global trigger, outcome and budget status separately', () => {
    const status = { graph_snapshot: 'snapshot', live_load_provider_installed: false, latest: { should_replan: true, recomputed: false, trigger: 'approved_event', reason: null, occurred_at: last, elapsed_ms: 420, within_five_second_budget: true } }
    expect(parseReplanningStatus(status).latest).toMatchObject({ should_replan: true, recomputed: false, within_five_second_budget: true })
    expect(parseReplanningStatus({ ...status, latest: null }).latest).toBeNull()
  })
})
