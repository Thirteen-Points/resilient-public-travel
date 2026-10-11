import { afterEach, describe, expect, it, vi } from 'vitest'
import seed from '../../../../contracts/seed/network.seed.json'
import type { Network, RouteLeg } from '../../api/types'
import snapshot from '../geometry.snapshot.json'
import {
  geometrySources, resolveImpactGeometry, resolveNetworkLineGeometry,
  resolveRouteLegGeometry, resolveSegmentGeometry,
} from '../geometry'

const network = seed as unknown as Network
const resolve = (lineId: string, from: string, to: string, mode = 'MTR') => resolveSegmentGeometry(network, { mode, lineId, from, to })

afterEach(() => vi.unstubAllGlobals())

describe('offline map alignment resolver', () => {
  it('uses a verified curved railway alignment instead of drawing between station centers', () => {
    const railway = resolve('ERL', 'TAW', 'KOT')
    expect(railway.quality).toBe('official')
    const points = railway.parts.flat()
    expect(points.length).toBeGreaterThan(20)
    // The Lion Rock railway tunnel bends west of both modeled endpoints.
    expect(Math.min(...points.map(point => point[1]))).toBeLessThan(114.173)
    expect(railway.sources[0].featureIds).toContain(649624)
  })

  it('preserves the real cross-harbour tunnel and keeps event/route/network geometry identical', () => {
    const direct = resolve('ERL', 'HUH', 'EXC')
    const impact = resolveImpactGeometry({ from_node: 'HUH', to_node: 'EXC', impact: 'closed', capacity_factor: 0 }, 'ERL', network)
    const leg = resolveRouteLegGeometry({ mode: 'MTR', line: 'EAL', from: 'HUH', to: 'EXC' } as RouteLeg, network)
    const line = resolveNetworkLineGeometry(network.lines.find(item => item.id === 'ERL')!, network)
    expect(impact.parts).toEqual(direct.parts)
    expect(leg.parts).toEqual(direct.parts)
    expect(line.find(item => item.from === 'HUH')?.parts).toEqual(direct.parts)
    expect(direct.sources[0].featureIds).toContain(649719)
    expect(direct.parts.flat().length).toBeGreaterThan(20)
  })

  it('retains omitted intermediate station alignments and source gaps as separate paths', () => {
    const geometry = resolve('TML', 'TAW', 'HOM')
    expect(geometry.quality).toBe('official')
    expect(geometry.parts.length).toBeGreaterThan(3)
    expect(geometry.parts.flat().some(([lat, lng]) => lat > 22.355 && lat < 22.365 && lng < 114.174)).toBe(true)
    expect(geometry.note).toContain('source gaps remain separate')
    for (let i = 1; i < geometry.parts.length; i++) {
      // Adjacent parts have a real source discontinuity, not a fabricated join.
      expect(geometry.parts[i - 1].at(-1)).not.toEqual(geometry.parts[i][0])
    }
  })

  it('reverses the railway alignment and multipart order without changing topology', () => {
    const forward = resolve('TML', 'DIH', 'HOM')
    const reverse = resolve('TML', 'HOM', 'DIH')
    expect(reverse.parts).toEqual([...forward.parts].reverse().map(part => [...part].reverse()))
    expect(reverse.sources).toEqual(forward.sources)
  })

  it('uses different official bus paths in each direction', () => {
    const outward = resolve('BUS_182', 'BS_TAW', 'BS_ADM_E', 'BUS')
    const inward = resolve('182', 'BS_ADM_E', 'BS_TAW', 'BUS')
    expect(outward.quality).toBe('official')
    expect(inward.quality).toBe('official')
    expect(outward.sources[0].id).toBe('td-bus-1051-1')
    expect(inward.sources[0].id).toBe('td-bus-1051-2')
    expect(inward.parts).not.toEqual([...outward.parts].reverse().map(part => [...part].reverse()))
    expect(outward.parts.flat().length).toBeGreaterThan(100)
  })

  it('selects the recorded 982X morning and evening variants', () => {
    const morning = resolve('BUS_982X', 'BS_TAW', 'BS_ADM_E', 'BUS')
    const evening = resolve('BUS_982X', 'BS_ADM_E', 'BS_TAW', 'BUS')
    expect(morning.sources[0].id).toBe('td-bus-8104-1')
    expect(evening.sources[0].id).toBe('td-bus-8644-1')
    // Both real variants use the Western Harbour Crossing.
    expect(Math.min(...morning.parts.flat().map(point => point[1]))).toBeLessThan(114.16)
    expect(Math.min(...evening.parts.flat().map(point => point[1]))).toBeLessThan(114.16)
  })

  it('does not present a reversed one-direction bus service as a verified return alignment', () => {
    expect(resolve('BUS_985B', 'BS_TIN_SUM', 'BS_ADM_E', 'BUS').quality).toBe('official')
    const reverse = resolve('BUS_985B', 'BS_ADM_E', 'BS_TIN_SUM', 'BUS')
    expect(reverse.quality).toBe('schematic')
    expect(reverse.sources).toEqual([])
    expect(reverse.note).toContain('No verified official return-direction geometry')
  })

  it('draws actual pedestrian geometry while retaining uncertainty about exits and accessibility', () => {
    const before = JSON.stringify(network)
    const walking = resolveSegmentGeometry(network, { mode: 'WALK', from: 'ETS', to: 'TST' })
    expect(walking.quality).toBe('official')
    expect(walking.parts.flat().length).toBeGreaterThan(10)
    expect(walking.note).toContain('step-free continuity remain unverified')
    expect(walking.sources[0].featureIds.length).toBeGreaterThan(0)
    expect(JSON.stringify(network)).toBe(before)
  })

  it('keeps short Tai Wai bus transfers on their actual source footway', () => {
    const walking = resolveSegmentGeometry(network, { mode: 'WALK', from: 'TAW', to: 'BS_TAW' })
    expect(walking.quality).toBe('official')
    expect(walking.parts.flat().length).toBeGreaterThanOrEqual(2)
    expect(walking.parts[0][0]).not.toEqual(walking.parts[0].at(-1))
  })

  it('does not substitute a nearby tiny edge for the Hung Hom transfer', () => {
    const walking = resolveSegmentGeometry(network, { mode: 'WALK', from: 'BS_HUH_TUNNEL', to: 'HUH' })
    expect(walking.quality).toBe('official')
    expect(walking.parts.flat().length).toBeGreaterThan(20)
    const recorded = snapshot.segments.find(segment => segment.mode === 'WALK' && segment.from === 'BS_HUH_TUNNEL' && segment.to === 'HUH')!
    expect(Math.max(...recorded.endpointOffsetM)).toBeLessThan(40)
  })

  it('labels the ferry honestly when official data only supplies pier points', () => {
    const ferry = resolve('FERRY_TST_CEN', 'PIER_TST', 'PIER_CEN', 'FERRY')
    expect(ferry.quality).toBe('schematic')
    expect(ferry.sources).toEqual([])
    expect(ferry.note).toContain('pier points only')
  })

  it('preserves missing endpoints rather than inventing coordinates', () => {
    expect(resolve('ERL', 'TAW', 'missing').parts).toEqual([])
    const broken: Network = { ...network, nodes: network.nodes.map(node => node.id === 'TAW' ? { ...node, lat: NaN } : node) }
    const geometry = resolveSegmentGeometry(broken, { mode: 'MTR', lineId: 'ERL', from: 'TAW', to: 'KOT' })
    expect(geometry.quality).toBe('missing')
    expect(geometry.parts).toEqual([])
  })

  it('keeps an unknown service schematic even when its stops overlap a known railway', () => {
    const unknown = resolve('unknown', 'TAW', 'KOT')
    expect(unknown.quality).toBe('schematic')
    expect(unknown.sources).toEqual([])
  })

  it('does not make network requests and returns fresh coordinate arrays', () => {
    const fetch = vi.fn(() => { throw new Error('Runtime geometry API requests are forbidden') })
    vi.stubGlobal('fetch', fetch)
    const a = resolve('ERL', 'TAW', 'ADM'), b = resolve('ERL', 'TAW', 'ADM')
    a.parts[0][0][0] = 0
    expect(b.parts[0][0][0]).toBeGreaterThan(22)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('ships traceable captures and valid WGS84 data for every recorded part', () => {
    expect(new Set(snapshot.segments.map(segment => JSON.stringify([segment.mode, segment.lineId, segment.from, segment.to]))).size).toBe(snapshot.segments.length)
    for (const source of geometrySources) {
      expect(Number.isFinite(Date.parse(source.capturedAt))).toBe(true)
      expect(source.sha256).toMatch(/^[a-f0-9]{64}$/)
      expect(source.featureIds.length).toBeGreaterThan(0)
      expect(source.licenseUrl).toBe('https://static.csdi.gov.hk/csdi-webpage/doc/TNC')
    }
    for (const segment of snapshot.segments) {
      expect(segment.sourceIds.every(id => geometrySources.some(source => source.id === id))).toBe(true)
      for (const part of segment.geometry.coordinates) {
        expect(part.length).toBeGreaterThanOrEqual(2)
        for (const [lng, lat] of part) {
          expect(lng).toBeGreaterThan(114)
          expect(lng).toBeLessThan(114.3)
          expect(lat).toBeGreaterThan(22.2)
          expect(lat).toBeLessThan(22.5)
        }
      }
    }
  })
})
