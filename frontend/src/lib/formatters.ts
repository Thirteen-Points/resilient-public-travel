// Display formatters shared by route cards, event cards and the sources
// footer. Pure and locale-stable: en dash for ranges, metric units, HKT
// timestamps. Unknown values render as an em dash with a reason — never 0.

import { PROVENANCE_LABELS, isProvenance } from './provenance'

/** Em dash used wherever a value is unknown; the reason lives beside it. */
export const MISSING = '—'

export const EN_DASH = '–'

const hasNumber = (value: number | null | undefined): value is number =>
  typeof value === 'number' && Number.isFinite(value)

/**
 * Format a travel-time range, e.g. `31–38 min`.
 * @param range [lower, upper] in seconds (default) or minutes
 */
export function formatEtaRange(range: [number, number] | null | undefined, unit: 's' | 'min' = 's'): string {
  if (!Array.isArray(range) || range.length !== 2 || !hasNumber(range[0]) || !hasNumber(range[1])) return MISSING
  const scale = unit === 's' ? 1 / 60 : 1
  // Inverted bounds are a data problem flagged by the normalizers; render as-is.
  return `${Math.round(range[0] * scale)}${EN_DASH}${Math.round(range[1] * scale)} min`
}

/** Format a fare, e.g. `HK$12.50`. Missing fares never become HK$0. */
export function formatFare(hkd: number | null | undefined): string {
  if (!hasNumber(hkd)) return MISSING
  return `HK$${hkd.toFixed(2)}`
}

/** Why a fare shows as `—`: the three honest flavours of missing. */
export function missingFareReason(hkd: number | null | undefined): string | null {
  if (hkd === null) return 'Fare not provided by the data source'
  if (hkd === undefined) return 'Fare not modelled for this journey'
  if (typeof hkd !== 'number' || !Number.isFinite(hkd)) return 'Fare value is not a valid number'
  return null
}

/** Format a walking/access distance in metres (e.g. `420 m`); never converts to miles. */
export function formatDistance(metres: number | null | undefined): string {
  if (!hasNumber(metres) || metres < 0) return MISSING
  return `${Math.round(metres)} m`
}

const hktFormatter = new Intl.DateTimeFormat('en-HK', {
  timeZone: 'Asia/Hong_Kong', day: 'numeric', month: 'short', year: 'numeric',
  hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
})

/** Format an ISO timestamp in Hong Kong time with an explicit HKT suffix. */
export function formatHktTime(iso: string | null | undefined): string {
  if (typeof iso !== 'string' || iso === '') return MISSING
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) return MISSING
  return `${hktFormatter.format(parsed)} HKT`
}

/** real → Real, real-derived → Estimated / Derived, simulated → Simulated, anything else → Unknown. */
export function formatProvenance(value: string | null | undefined): string {
  return isProvenance(value) ? PROVENANCE_LABELS[value] : 'Unknown'
}

export type FreshnessTier = 'live' | 'recent' | 'stale' | 'unknown'

export interface FreshnessInfo {
  tier: FreshnessTier
  text: string
}

export const FRESHNESS_THRESHOLDS = {
  /** Up to this age data counts as live. */
  liveMaxS: 300,
  /** At this age data starts being flagged as stale. */
  staleMinS: 1800,
}

function formatAge(totalSeconds: number): string {
  if (totalSeconds < 60) return `${Math.round(totalSeconds)} s`
  if (totalSeconds < 3600) return `${Math.round(totalSeconds / 60)} min`
  if (totalSeconds < 86400) {
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.round((totalSeconds % 3600) / 60)
    return minutes > 0 ? `${hours} h ${minutes} min` : `${hours} h`
  }
  return `${Math.round(totalSeconds / 86400)} d`
}

/**
 * Distinguish live, merely old, stale and unknown data from the seed's
 * `freshness_s` (seconds elapsed since the value was computed).
 */
export function formatFreshness(freshnessS: number | null | undefined, thresholds = FRESHNESS_THRESHOLDS): FreshnessInfo {
  if (!hasNumber(freshnessS) || freshnessS < 0) return { tier: 'unknown', text: 'Freshness unknown' }
  const age = formatAge(freshnessS)
  if (freshnessS <= thresholds.liveMaxS) return { tier: 'live', text: `Updated ${age} ago` }
  if (freshnessS <= thresholds.staleMinS) return { tier: 'recent', text: `Updated ${age} ago` }
  return { tier: 'stale', text: `Stale — updated ${age} ago` }
}
