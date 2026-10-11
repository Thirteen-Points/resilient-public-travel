import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Network } from '../api/types'
import { eastRailStations, findEastRailWalkingAccess } from './eastRailAccess'

const network: Network = {
  meta: { version: 'test', built_at: '2026-09-22', catchment_m: 800, note: '' },
  nodes: [
    { id: 'ERL', name_en: 'East Rail', name_zh: '東鐵', kind: 'mtr_station', lat: 22.3, lng: 114.1, lines: ['ERL'], accessible: true, provenance: 'real' },
    { id: 'OTHER', name_en: 'Other', name_zh: '其他', kind: 'mtr_station', lat: 22.3, lng: 114.1001, lines: ['KTL'], accessible: true, provenance: 'real' },
  ],
  lines: [],
}

afterEach(() => vi.unstubAllGlobals())

describe('East Rail walking access', () => {
  it('only considers East Rail stations and checks routed walking distance', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ trip: { summary: { length: 0.799 } } }) })
    vi.stubGlobal('fetch', fetcher)
    const result = await findEastRailWalkingAccess(network, { lat: 22.3, lng: 114.1002 })
    expect(eastRailStations(network).map(station => station.id)).toEqual(['ERL'])
    expect(result?.station.id).toBe('ERL')
    expect(result?.metres).toBe(799)
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(JSON.parse(fetcher.mock.calls[0][1].body).costing).toBe('pedestrian')
  })

  it('rejects a point whose walking route exceeds 800 m despite being close on the map', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ trip: { summary: { length: 0.801 } } }) }))
    expect(await findEastRailWalkingAccess(network, { lat: 22.3, lng: 114.1002 })).toBeNull()
  })

  it('does not accept a map point when walking distance could not be verified', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    await expect(findEastRailWalkingAccess(network, { lat: 22.3, lng: 114.1002 })).rejects.toThrow('unavailable')
  })
})
