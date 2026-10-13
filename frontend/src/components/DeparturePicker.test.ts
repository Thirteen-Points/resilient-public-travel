import { describe, expect, it } from 'vitest'
import { advancePastHktDeparture, isPastHktDeparture, nextHktMinute } from '../lib/departureTime'

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

  it('moves a prefilled departure that expired after 65 seconds to the next legal minute', () => {
    const loadedAt = new Date('2026-10-13T07:04:00Z')
    const initial = nextHktMinute(loadedAt)
    expect(initial).toBe('2026-10-13 15:05')
    expect(advancePastHktDeparture('2026-10-13', '15:05', new Date(loadedAt.getTime() + 65_000)))
      .toEqual({ date: '2026-10-13', time: '15:06', moved: true })
  })

  it('keeps a future choice and advances a stale choice across a Hong Kong date boundary', () => {
    const now = new Date('2026-10-12T16:00:05Z')
    expect(advancePastHktDeparture('2026-10-13', '08:20', now))
      .toEqual({ date: '2026-10-13', time: '08:20', moved: false })
    expect(advancePastHktDeparture('2026-10-12', '23:59', now))
      .toEqual({ date: '2026-10-13', time: '00:01', moved: true })
    expect(advancePastHktDeparture('2026-10-13', '', now))
      .toEqual({ date: '2026-10-13', time: '', moved: false })
  })
})
