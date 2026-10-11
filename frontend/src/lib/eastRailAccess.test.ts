import { describe, expect, it } from 'vitest'
import type { Network, NetworkNode } from '../api/types'
import { CORRIDOR_IDS } from '../data'
import { eastRailStations, findEastRailAccess } from './eastRailAccess'

const station = (id: string, lat: number, lines = ['ERL']): NetworkNode => ({
  id, name_en: id, name_zh: id, kind: 'mtr_station', lat, lng: 114.1,
  lines, accessible: true, provenance: 'real',
})
const network: Network = {
  meta: { version: 'test', built_at: '2026-09-22', catchment_m: 800, note: '' },
  nodes: [
    ...CORRIDOR_IDS.map((id, index) => station(id, 22.3 + index * 0.03)),
    station('EXTRA_ERL', 22.301), station('OTHER_LINE', 22.302, ['KTL']),
  ],
  lines: [],
}
const northOfTaiWai = (metres: number) => ({ lat: 22.3 + metres / 6371000 * 180 / Math.PI, lng: 114.1 })

describe('six East Rail station access circles', () => {
  it('uses only the six corridor East Rail stations', () => {
    expect(eastRailStations(network).map(node => node.id)).toEqual([...CORRIDOR_IDS])
    expect(findEastRailAccess(network, { lat: 22.301, lng: 114.1 })?.station.id).toBe('TAW')
  })

  it('accepts points 799 m away and rejects points 801 m away by straight-line distance', () => {
    const inside = findEastRailAccess(network, northOfTaiWai(799))
    expect(inside?.station.id).toBe('TAW')
    expect(inside?.metres).toBeCloseTo(799, 4)
    expect(findEastRailAccess(network, northOfTaiWai(801))).toBeNull()
  })

  it('rejects invalid map coordinates', () => {
    expect(findEastRailAccess(network, { lat: Number.NaN, lng: 114.1 })).toBeNull()
  })
})
