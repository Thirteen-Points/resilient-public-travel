import type { TravelProfile } from '../api/types'
import { calculateProfile, readState, type Weights } from './model'

/** Engine criteria use walk/price; accessibility is a separate, explicit constraint. */
export function recommendationWeights(weights: Weights): Record<string, number> {
  const mapped = { time: weights.time, transfers: weights.transfers, walk: weights.walking, price: weights.fare,
    comfort: weights.comfort, reliability: weights.reliability, carbon: weights.carbon, freshness: weights.freshness }
  const safe = Object.entries(mapped).map(([id, value]) => [id, Number.isFinite(value) ? Math.max(0, value) : 0] as const)
  const sum = safe.reduce((total, [, value]) => total + value, 0)
  return Object.fromEntries(safe.map(([id, value]) => [id, sum ? value / sum : 1 / safe.length]))
}

/** Soft answers never silently activate mobility restrictions or loosen existing ones. */
export function loadPlannerProfile(): (TravelProfile & { weights: Record<string, number> }) | undefined {
  const state = readState()
  if (state.phase !== 'complete') return undefined
  const weights = recommendationWeights(calculateProfile(state).weights)
  const preset = weights.reliability > weights.time && weights.reliability > weights.transfers ? 'most_stable'
    : weights.transfers > weights.time ? 'fewest_transfers' : 'fastest'
  return { mobility: 'standard', preset, hard_flags: [], weights }
}
