import { describe, expect, it } from 'vitest'
import { parseBusEta } from './busApi'

describe('official bus arrivals', () => {
  const mapping = { operator: 'KMB', route: '182', bound: 'O', service_type: '1', stop_id: 'stop', sequence: 11, stop_name: 'Tai Wai BBI' }
  const now = Date.parse('2026-10-12T08:20:00+08:00')
  const row = { route: '182', dir: 'O', service_type: 1, seq: 11, eta: '2026-10-12T08:24:00+08:00', data_timestamp: '2026-10-12T08:20:00+08:00' }
  it('keeps the boarding stop/direction/variant and future arrivals', () => {
    const result = parseBusEta({ data: [row, { ...row, dir: 'I' }, { ...row, seq: 12 }, { ...row, service_type: 2 }, { ...row, eta: '2026-10-12T08:19:00+08:00' }] }, mapping, now)
    expect(result.status).toBe('live')
    expect(result.arrivals.map(a => a.minutes)).toEqual([4])
  })
  it('does not show stale observations as live or infer a suspension from no arrivals', () => {
    expect(parseBusEta({ data: [{ ...row, data_timestamp: '2026-10-12T08:10:00+08:00' }] }, mapping, now).status).toBe('stale')
    expect(parseBusEta({ data: [], generated_timestamp: '2026-10-12T08:20:00+08:00' }, mapping, now).status).toBe('no_arrivals')
  })
  it('does not revive an old ETA when another row is fresh', () => {
    const result = parseBusEta({ data: [{ ...row, data_timestamp: '2026-10-12T08:10:00+08:00' }, { ...row, eta: '2026-10-12T08:25:00+08:00' }] }, mapping, now)
    expect(result.arrivals.map(a => a.minutes)).toEqual([5])
  })
})
