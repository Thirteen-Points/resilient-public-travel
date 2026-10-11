import { afterEach, describe, expect, it, vi } from 'vitest'
import m0 from '../../../../data/sim/scn_huh_exc_closed_am_peak.json'
import m2 from '../../../../data/sim/m2-simulation-result.json'
import { chat, chatPayload, compare, delayOutcome, parseChat, parseSimulation, simulation, sourceView } from '../p3Api'
import { contextKey, LatestRequest, profileFor } from '../p3Context'
import { getMeta, queryRoutes, requestJson } from '../liveTransitApi'
import type { JourneyContext } from '../types'

const context: JourneyContext = { origin: 'KOT', destination: 'ADM', departAt: '2026-10-07T08:20:00+08:00', preset: 'fastest', persona: 'commuter', eventIds: ['e-approved'], eventRevisions: 'e-approved@3' }
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('current confirmed chat contract', () => {
  it('sends the selected OD and timezone-aware time, never the hardcoded seed OD', async () => {
    const fetch = vi.fn().mockResolvedValue(json({ message: 'Actual backend reply', tool_calls: [], routes: [], fallback: true }))
    vi.stubGlobal('fetch', fetch)
    const reply = await chat(context, 'Please explain', new AbortController().signal)
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ message: 'Please explain', origin: 'KOT', destination: 'ADM', depart_at: context.departAt, profile: profileFor('commuter', 'fastest') })
    expect(reply).toMatchObject({ message: 'Actual backend reply', fallback: true, routes: [] })
    expect(fetch.mock.calls[0][0]).toContain('/api/ai/chat')
  })
  it('sends supported accessibility profiles and blocks the unsupported preset', () => {
    expect(chatPayload({ ...context, persona: 'wheelchair' }, 'route').profile).toEqual(profileFor('wheelchair', 'fastest'))
    expect(chatPayload({ ...context, preset: 'most_stable' }, 'route').profile.preset).toBe('most_stable')
    expect(() => chatPayload({ ...context, preset: 'least_walking' }, 'route')).toThrow('CONTRACT_PENDING')
    expect(() => chatPayload({ ...context, destination: '' }, 'route')).toThrow('different stations')
    expect(() => chatPayload({ ...context, departAt: '2026-10-07T08:20' }, 'route')).toThrow('timezone')
  })
  it('preserves backend fallback and tool failures, rejects malformed data', () => {
    expect(parseChat({ message: 'Tool unavailable', fallback: true, tool_calls: [{ ok: false, error: 'tool_timeout' }] }).tool_calls[0].error).toBe('tool_timeout')
    expect(parseChat({ message: 'Normal backend answer', fallback: false, tool_calls: [] }).fallback).toBe(false)
    expect(() => parseChat({ message: 'bad', tool_calls: [] })).toThrow('Malformed')
    expect(() => parseChat({ message: 'bad', fallback: false, tool_calls: [{ ok: false, error: {} }] })).toThrow('Malformed')
    expect(() => parseChat({ message: 'bad', fallback: true, tool_calls: [], routes: [{}] })).toThrow('Malformed')
  })
})

describe('transport failures and obsolete requests', () => {
  it('surfaces the real HTTP error instead of seed data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ detail: 'Backend unavailable' }, 503)))
    await expect(requestJson('GET', '/api/meta')).rejects.toMatchObject({ status: 503, message: expect.stringContaining('Backend unavailable') })
  })
  it('enforces a deadline even while reading a response body', async () => {
    vi.stubGlobal('fetch', vi.fn((_url, options) => Promise.resolve({ ok: true, status: 200, text: () => new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true })) })))
    await expect(requestJson('POST', '/api/ai/chat', {}, { timeoutMs: 10 })).rejects.toMatchObject({ code: 'TIMEOUT' })
  })
  it('distinguishes user cancellation from timeout', async () => {
    vi.stubGlobal('fetch', vi.fn((_url, options) => new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true }))))
    const controller = new AbortController(), pending = requestJson('GET', '/api/sim/result', undefined, { signal: controller.signal })
    controller.abort()
    await expect(pending).rejects.toMatchObject({ code: 'CANCELLED' })
  })
  it('rejects old completions even if their transport ignored abort', () => {
    const latest = new LatestRequest(), a = latest.begin(), b = latest.begin()
    expect(a.current()).toBe(false); expect(a.signal.aborted).toBe(true); expect(b.current()).toBe(true)
    latest.cancel(); expect(b.current()).toBe(false)
    expect(contextKey(context)).not.toEqual(contextKey({ ...context, eventRevisions: 'e-approved@4' }))
  })
})

describe('comparison requests and constraints', () => {
  it('uses one shared OD/time/events but preserves unverified snapshot status', async () => {
    const fetch = vi.fn().mockImplementation((url: string) => Promise.resolve(json(url.includes('/snapshot') ? { snapshot_id: 'existing-snapshot', affected_edges: [] } : [])))
    vi.stubGlobal('fetch', fetch)
    const result = await compare(context, new AbortController().signal)
    const bodies = fetch.mock.calls.filter(call => String(call[0]).includes('/routes/query')).map(call => JSON.parse(call[1].body))
    expect(bodies).toHaveLength(2)
    for (const body of bodies) expect(body).toMatchObject({ origin: context.origin, destination: context.destination, depart_at: context.departAt, event_ids: context.eventIds })
    expect(bodies[1].profile).toEqual({ ...profileFor('wheelchair', 'most_stable'), hard_flags: [...profileFor('wheelchair', 'most_stable').hard_flags].sort() })
    expect(result.verified).toBe(false)
  })
  it('withholds both columns if the network changes during the queries', async () => {
    let reads = 0
    vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(json(url.includes('/snapshot') ? { snapshot_id: `snapshot-${++reads}`, affected_edges: [] } : []))))
    await expect(compare(context, new AbortController().signal)).rejects.toThrow('changed during comparison')
  })
  it('does not silently map less walking to a supported preset', async () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
    await expect(queryRoutes({ ...context, preset: 'least_walking' })).rejects.toMatchObject({ code: 'CONTRACT_PENDING' })
    expect(fetch).not.toHaveBeenCalled()
  })
})

describe('repository simulation results are displayed honestly', () => {
  it('keeps actual negative improvement in M0 and M2 samples', () => {
    for (const fixture of [m0, m2]) {
      const result = parseSimulation(fixture)
      expect(result.guided.total_delay_person_min).toBe(fixture.guided.total_delay_person_min)
      expect(result.delta?.delay_reduction_pct).toBeLessThan(0)
      expect(delayOutcome(result)).toContain('no delay improvement')
    }
  })
  it('does not invent timestamps, shares or capacity gaps missing in the M2 output', () => {
    const a = parseSimulation(m0), b = parseSimulation(m2)
    expect(a.generated_at).toBeUndefined()
    expect(b.guided.shares).toBeUndefined()
    expect(b.guided.unstoppable_demand).toBeUndefined()
  })
  it('reports unchanged delay without declaring success', () => {
    const fixture = structuredClone(m0)
    fixture.guided.total_delay_person_min = fixture.baseline.total_delay_person_min
    expect(delayOutcome(parseSimulation(fixture))).toContain('unchanged')
  })
  it('rejects malformed metrics and mismatched scenarios instead of switching fixtures', async () => {
    expect(() => parseSimulation({ ...m0, baseline: {} })).toThrow('Malformed')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(m0)))
    await expect(simulation('m2_six_station_directed_od_am_peak', new AbortController().signal)).rejects.toThrow('different scenario')
  })
})

describe('source freshness is never synthesized', () => {
  it('does not use meta generation time or source names as collection evidence', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ generated_at: context.departAt, graph_snapshot: 'existing', sources: ['contracts/seed/network.seed.json'], disclaimer: 'Existing disclaimer' })))
    const meta = await getMeta(), source = sourceView(meta.sources[0])
    expect(source.lastOk).toBeUndefined(); expect(source.status).toContain('unavailable'); expect(source.classification).toContain('unavailable')
  })
  it('preserves only an explicitly provided last_ok value', () => {
    expect(sourceView({ name: 'contract test source', last_ok: context.departAt }).lastOk).toBe(context.departAt)
  })
  it('rejects malformed source objects before rendering', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ generated_at: context.departAt, sources: [{}] })))
    await expect(getMeta()).rejects.toThrow('invalid source metadata')
  })
})
