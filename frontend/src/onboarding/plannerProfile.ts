import type { TravelProfile } from '../api/types'
import { calculateProfile, readState, type Weights } from './model'

// The route engine currently scores eight criteria. Accessibility remains an
// explicit hard requirement in the planner, never inferred from a soft answer.
export function recommendationWeights(weights: Weights): Record<string, number> {
  const mapped = { time: weights.time, transfers: weights.transfers, walk: weights.walking, price: weights.fare, comfort: weights.comfort, reliability: weights.reliability, carbon: weights.carbon, freshness: weights.freshness }
  const sum = Object.values(mapped).reduce((a,b) => a+b,0)
  return Object.fromEntries(Object.entries(mapped).map(([id,value]) => [id,value / sum]))
}
export function loadPlannerProfile(): (TravelProfile & { weights: Record<string, number> }) | undefined {
  const state = readState()
  if (state.phase !== 'complete') return undefined
  return { mobility: 'standard', preset: 'fastest', hard_flags: [], weights: recommendationWeights(calculateProfile(state).weights) }
}
