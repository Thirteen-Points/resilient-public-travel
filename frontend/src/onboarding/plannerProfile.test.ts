import { afterEach, describe, expect, it, vi } from 'vitest'
import { validWeights, WEIGHT_CRITERIA } from '../api/preferences'
import { CORE, QUESTIONS, STORAGE_KEY, calculateProfile, initialState, reducer } from './model'
import { loadPlannerProfile, recommendationWeights } from './plannerProfile'

afterEach(() => vi.unstubAllGlobals())

describe('planner preference bridge', () => {
  it('maps only supported backend criteria and renormalizes without accessibility', () => {
    const weights = calculateProfile(initialState()).weights
    const result = recommendationWeights({ ...weights, walking: .3, fare: .2, accessibility: .4 })
    expect(Object.keys(result)).toEqual(WEIGHT_CRITERIA)
    expect(validWeights(result)).toBe(true)
    expect(result.walk / result.price).toBeCloseTo(1.5)
    expect(result).not.toHaveProperty('accessibility')
    expect(result).not.toHaveProperty('walking')
    expect(result).not.toHaveProperty('fare')
  })

  it('does not apply incomplete answers and accepts only validated completed state', () => {
    vi.stubGlobal('localStorage', { getItem: () => JSON.stringify(initialState()) })
    expect(loadPlannerProfile()).toBeUndefined()
    let state = reducer(initialState(), { type: 'START' })
    for (const id of CORE) {
      state = reducer(state, { type: 'SELECT', option: QUESTIONS[id].options[0].id })
      state = reducer(state, { type: 'ADVANCE', revision: state.revision })
    }
    const completed = reducer(state, { type: 'FINISH' })
    vi.stubGlobal('localStorage', { getItem: (key: string) => key === STORAGE_KEY ? JSON.stringify(completed) : null })
    const profile = loadPlannerProfile()!
    expect(validWeights(profile.weights)).toBe(true)
    expect(profile).toMatchObject({ mobility: 'standard', hard_flags: [] })
    expect(profile).not.toHaveProperty('max_walk_m')
  })

  it('returns normalized safe weights even for degenerate numeric inputs', () => {
    const result = recommendationWeights({ time: NaN, transfers: Infinity, walking: -2, fare: 0, comfort: 0, reliability: 0, carbon: 0, freshness: 0, accessibility: 1 })
    expect(validWeights(result)).toBe(true)
    expect(Object.values(result)).toEqual(Array(8).fill(.125))
  })
})
