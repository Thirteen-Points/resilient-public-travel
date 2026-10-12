import { describe, expect, it } from 'vitest'
import { isPastHktDeparture, nextHktMinute } from '../lib/departureTime'

describe('Hong Kong departure time', () => {
  it('uses Hong Kong date across a UTC day boundary', () => {
    expect(nextHktMinute(new Date('2026-10-12T15:59:30Z'))).toBe('2026-10-13 00:00')
  })

  it('rejects past departures and accepts future ones', () => {
    const now = new Date('2026-10-12T04:00:30Z')
    expect(isPastHktDeparture('2026-10-12', '11:59', now)).toBe(true)
    expect(isPastHktDeparture('2026-10-12', '12:01', now)).toBe(false)
    expect(isPastHktDeparture('2026-10-13', '00:00', now)).toBe(false)
  })
})
