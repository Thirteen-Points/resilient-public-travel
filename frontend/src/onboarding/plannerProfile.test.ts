import { afterEach, expect, it, vi } from 'vitest'
import { calculateProfile, initialState, STORAGE_KEY } from './model'
import { loadPlannerProfile, recommendationWeights } from './plannerProfile'
afterEach(() => vi.unstubAllGlobals())
it('projects all supported criteria onto the engine contract with a unit sum', () => {
  const profile = recommendationWeights(calculateProfile(initialState()).weights)
  expect(Object.keys(profile)).toEqual(['time','transfers','walk','price','comfort','reliability','carbon','freshness'])
  expect(Object.values(profile).reduce((a,b) => a+b,0)).toBeCloseTo(1,12)
  expect(profile.accessibility).toBeUndefined()
})
it('applies only completed profiles and never infers accessibility restrictions', () => {
  let saved = initialState()
  vi.stubGlobal('localStorage', { getItem: (key: string) => key === STORAGE_KEY ? JSON.stringify(saved) : null })
  expect(loadPlannerProfile()).toBeUndefined()
  saved = { ...saved, phase: 'complete' }
  expect(loadPlannerProfile()?.weights).toBeDefined()
  expect(loadPlannerProfile()?.mobility).toBe('standard')
  expect(loadPlannerProfile()?.hard_flags).toEqual([])
})
