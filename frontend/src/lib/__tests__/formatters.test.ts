import { describe, expect, it } from 'vitest'
import {
  EN_DASH, MISSING, formatDistance, formatEtaRange, formatFare, formatFreshness,
  formatHktTime, formatProvenance, missingFareReason,
} from '../formatters'

describe('formatEtaRange', () => {
  it('formats a seconds range with an en dash, never a hyphen', () => {
    const text = formatEtaRange([1860, 2280])
    expect(text).toBe(`31${EN_DASH}38 min`)
    expect(text).not.toContain('-')
  })

  it('accepts minute ranges explicitly', () => {
    expect(formatEtaRange([31, 38], 'min')).toBe(`31${EN_DASH}38 min`)
  })

  it('renders equal bounds as-is instead of collapsing them', () => {
    expect(formatEtaRange([1800, 1800])).toBe(`30${EN_DASH}30 min`)
  })

  it('returns the missing marker for absent or invalid ranges', () => {
    expect(formatEtaRange(null)).toBe(MISSING)
    expect(formatEtaRange(undefined)).toBe(MISSING)
    expect(formatEtaRange([Number.NaN, 300])).toBe(MISSING)
    expect(formatEtaRange([100] as unknown as [number, number])).toBe(MISSING)
  })
})

describe('formatFare', () => {
  it('formats seed fares with two decimals', () => {
    expect(formatFare(12.5)).toBe('HK$12.50')
    expect(formatFare(6)).toBe('HK$6.00')
    expect(formatFare(20.8)).toBe('HK$20.80')
  })

  it('never invents HK$0 for missing fares and explains why', () => {
    expect(formatFare(null)).toBe(MISSING)
    expect(formatFare(undefined)).toBe(MISSING)
    expect(formatFare(Number.NaN)).toBe(MISSING)
    expect(formatFare(null)).not.toBe('HK$0.00')
    expect(missingFareReason(null)).toBe('Fare not provided by the data source')
    expect(missingFareReason(undefined)).toBe('Fare not modelled for this journey')
    expect(missingFareReason(Number.POSITIVE_INFINITY)).toBe('Fare value is not a valid number')
    expect(missingFareReason(12.5)).toBeNull()
  })
})

describe('formatDistance', () => {
  it('formats metres without converting units', () => {
    expect(formatDistance(420)).toBe('420 m')
    expect(formatDistance(1250.4)).toBe('1250 m')
    expect(formatDistance(0)).toBe('0 m')
  })

  it('returns the missing marker for unknown or negative distances', () => {
    expect(formatDistance(null)).toBe(MISSING)
    expect(formatDistance(undefined)).toBe(MISSING)
    expect(formatDistance(Number.NaN)).toBe(MISSING)
    expect(formatDistance(-5)).toBe(MISSING)
  })
})

describe('formatHktTime', () => {
  it('renders an explicit HKT timestamp', () => {
    expect(formatHktTime('2026-09-22T08:20:00+08:00')).toMatch(/22 Sept? 2026.*08:20 HKT$/)
  })

  it('converts other time zones into Hong Kong time', () => {
    // 00:20 UTC is 08:20 HKT on the same day.
    expect(formatHktTime('2026-09-22T00:20:00Z')).toMatch(/22 Sept? 2026.*08:20 HKT$/)
  })

  it('returns the missing marker for absent or unparseable timestamps', () => {
    expect(formatHktTime(null)).toBe(MISSING)
    expect(formatHktTime('')).toBe(MISSING)
    expect(formatHktTime('not-a-timestamp')).toBe(MISSING)
  })
})

describe('formatProvenance', () => {
  it('maps the three contract levels to honest labels', () => {
    expect(formatProvenance('real')).toBe('Real')
    expect(formatProvenance('real-derived')).toBe('Estimated / Derived')
    expect(formatProvenance('simulated')).toBe('Simulated')
  })

  it('never upgrades unknown values', () => {
    expect(formatProvenance('guess')).toBe('Unknown')
    expect(formatProvenance(undefined)).toBe('Unknown')
    expect(formatProvenance('')).toBe('Unknown')
  })
})

describe('formatFreshness', () => {
  it('distinguishes live, old and stale data', () => {
    expect(formatFreshness(45)).toEqual({ tier: 'live', text: 'Updated 45 s ago' })
    expect(formatFreshness(600)).toEqual({ tier: 'recent', text: 'Updated 10 min ago' })
    const stale = formatFreshness(7200)
    expect(stale.tier).toBe('stale')
    expect(stale.text).toContain('Stale')
    expect(stale.text).toContain('2 h')
  })

  it('reports unknown freshness instead of guessing an age', () => {
    expect(formatFreshness(null)).toEqual({ tier: 'unknown', text: 'Freshness unknown' })
    expect(formatFreshness(undefined)).toEqual({ tier: 'unknown', text: 'Freshness unknown' })
    expect(formatFreshness(Number.NaN)).toEqual({ tier: 'unknown', text: 'Freshness unknown' })
    expect(formatFreshness(-10)).toEqual({ tier: 'unknown', text: 'Freshness unknown' })
  })

  it('honours custom thresholds for demo pacing', () => {
    expect(formatFreshness(400, { liveMaxS: 500, staleMinS: 1800 }).tier).toBe('live')
    expect(formatFreshness(400, { liveMaxS: 300, staleMinS: 1800 }).tier).toBe('recent')
  })
})
