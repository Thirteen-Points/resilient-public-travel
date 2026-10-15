import { afterEach, describe, expect, it, vi } from 'vitest'
import { ADDITIONAL, CORE, DIMENSIONS, EVENTS_KEY, PROFILE_KEY, QUESTIONS, STORAGE_KEY, activeAnswers, calculateProfile, initialState, percentages, persistState, readState, reducer, restoreState, track, type Dimension, type State } from './model'

const answer = (state: State, index = 0): State => {
  const selected = reducer(state, { type: 'SELECT', option: QUESTIONS[state.queue[state.cursor]].options[index].id })
  return reducer(selected, { type: 'ADVANCE', revision: selected.revision })
}
const summary = (): State => CORE.reduce(state => answer(state), reducer(initialState(), { type: 'START' }))
const memoryStorage = () => {
  const values = new Map<string, string>()
  return { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => { values.set(key, value) }, removeItem: (key: string) => { values.delete(key) } }
}
afterEach(() => vi.unstubAllGlobals())

describe('questionnaire transitions', () => {
  it('collects three distinct core dimensions before offering the summary', () => {
    expect(CORE).toEqual(['time', 'transfers', 'walking'])
    const state = summary()
    expect(state.phase).toBe('summary')
    expect(calculateProfile(state).collected).toBe(3)
    expect(reducer(initialState(), { type: 'FINISH' }).phase).toBe('welcome')
  })

  it('rejects stale animation callbacks after back, reset or a new answer', () => {
    const started = reducer(initialState(), { type: 'START' })
    const selected = reducer(started, { type: 'SELECT', option: QUESTIONS.time.options[0].id })
    const back = reducer(selected, { type: 'BACK' })
    const reset = reducer(selected, { type: 'RESET' })
    const changed = reducer(selected, { type: 'SELECT', option: QUESTIONS.time.options[2].id })
    for (const state of [back, reset, changed]) expect(reducer(state, { type: 'ADVANCE', revision: selected.revision })).toBe(state)
    expect(reducer(started, { type: 'ADVANCE', revision: started.revision })).toBe(started)
    expect(reducer(started, { type: 'NEXT' })).toBe(started)
  })

  it('keeps answers on back, excludes future evidence and restores it when revisited', () => {
    const finished = summary()
    const last = reducer(finished, { type: 'BACK' })
    const previous = reducer(last, { type: 'BACK' })
    expect(previous.answers).toEqual(finished.answers)
    expect(activeAnswers(previous).walking).toBeUndefined()
    expect(calculateProfile(previous).evidence.walking.status).toBe('prior')
    expect(reducer(previous, { type: 'NEXT' })).toMatchObject({ cursor: 2, phase: 'question' })
    expect(calculateProfile(reducer(previous, { type: 'NEXT' })).evidence.walking.status).toBe('collected')
  })

  it('treats skip as uncollected neutral evidence and permits keeping a skipped answer', () => {
    const initial = reducer(initialState(), { type: 'START' })
    const skipped = reducer(initial, { type: 'SKIP' })
    expect(skipped.answers.time).toBeNull()
    expect(calculateProfile(skipped).evidence.time).toMatchObject({ status: 'skipped', raw: .5, option: null })
    const back = reducer(skipped, { type: 'BACK' })
    expect(reducer(back, { type: 'NEXT' }).cursor).toBe(1)
    expect(calculateProfile(skipped).collected).toBe(0)
  })

  it('continues through all remaining dimensions, including the extension library', () => {
    let state = reducer(summary(), { type: 'CONTINUE' })
    expect(state).toMatchObject({ phase: 'question', cursor: 3, queue: [...CORE, ...ADDITIONAL] })
    state = ADDITIONAL.reduce(current => answer(current, 1), state)
    expect(state.phase).toBe('summary')
    expect(calculateProfile(state).collected).toBe(9)
    const complete = reducer(state, { type: 'FINISH' })
    expect(complete.phase).toBe('complete')
    expect(reducer(state, { type: 'CONTINUE' })).toBe(state)
  })

  it('reopens the last answer from completion and recomputes when that answer changes', () => {
    const completed = reducer(summary(), { type: 'FINISH' })
    const back = reducer(completed, { type: 'BACK' })
    expect(back).toMatchObject({ phase: 'question', cursor: 2, direction: -1, pending: false, answers: completed.answers })
    const changed = answer(back, 2)
    expect(changed.phase).toBe('summary')
    expect(changed.answers.walking).toBe('walking-2')
    expect(calculateProfile(changed).weights.walking).toBeLessThan(calculateProfile(completed).weights.walking)
    expect(reducer(changed, { type: 'FINISH' }).phase).toBe('complete')
  })
})

describe('normalized and explainable weights', () => {
  it('normalizes all nine dimensions together and explains explicit, skipped and default values', () => {
    let state = reducer(initialState(), { type: 'START' })
    state = answer(state)
    state = reducer(state, { type: 'SKIP' })
    const profile = calculateProfile(state)
    expect(Object.values(profile.weights).reduce((sum, value) => sum + value, 0)).toBeCloseTo(1, 12)
    expect(profile.evidence.time).toMatchObject({ status: 'collected', option: QUESTIONS.time.options[0].label, raw: .95 })
    expect(profile.evidence.transfers.status).toBe('skipped')
    expect(profile.evidence.accessibility.status).toBe('prior')
    expect(profile.weights.time).toBeGreaterThan(profile.weights.transfers)
    expect(Object.values(percentages(profile.weights)).reduce((sum, value) => sum + value, 0)).toBe(100)
  })

  it('keeps exact integer totals for every combination of three core answers', () => {
    for (let a = 0; a < 3; a++) for (let b = 0; b < 3; b++) for (let c = 0; c < 3; c++) {
      const state = answer(answer(answer(reducer(initialState(), { type: 'START' }), a), b), c)
      const shares = percentages(calculateProfile(state).weights)
      expect(Object.values(shares).reduce((sum, value) => sum + value, 0)).toBe(100)
      expect(Object.values(shares).every(Number.isInteger)).toBe(true)
    }
  })
})

describe('validated optional persistence', () => {
  it('restores interrupted answers without replaying pending auto advance', () => {
    const selected = reducer(reducer(initialState(), { type: 'START' }), { type: 'SELECT', option: QUESTIONS.time.options[0].id })
    const restored = restoreState(JSON.stringify(selected))
    expect(restored).toMatchObject({ phase: 'question', pending: false, answers: selected.answers })
    expect(reducer(restored, { type: 'NEXT' }).cursor).toBe(1)
    expect(restoreState(JSON.stringify(summary())).phase).toBe('summary')
  })

  it('rejects malformed, obsolete and bypassed questionnaire state', () => {
    const invalid = [null, 'not json', JSON.stringify({ ...summary(), version: 1 }), JSON.stringify({ ...summary(), answers: [] }),
      JSON.stringify({ ...summary(), queue: ['time', 'time', 'walking'] }), JSON.stringify({ ...summary(), cursor: 99 }),
      JSON.stringify({ ...summary(), phase: 'complete', answers: { time: 'time-0' } }), JSON.stringify({ ...summary(), answers: { time: 'walking-0' } })]
    invalid.forEach(value => expect(restoreState(value)).toEqual(initialState()))
  })

  it('persists the completed profile and omits it for incomplete sessions', () => {
    vi.stubGlobal('localStorage', memoryStorage())
    expect(persistState(summary())).toBe(true)
    expect(localStorage.getItem(PROFILE_KEY)).toBeNull()
    expect(persistState(reducer(summary(), { type: 'FINISH' }))).toBe(true)
    expect(readState().phase).toBe('complete')
    expect(JSON.parse(localStorage.getItem(PROFILE_KEY)!).weights).toEqual(calculateProfile(summary()).weights)
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!).version).toBe(2)
  })

  it('keeps interactions available when storage access fails and bounds the event log', () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('private mode') }, setItem: () => { throw new Error('quota') } })
    expect(readState()).toEqual(initialState())
    expect(persistState(summary())).toBe(false)
    expect(() => track('skip', { dimension: 'time' })).not.toThrow()
    vi.stubGlobal('localStorage', memoryStorage())
    for (let index = 0; index < 110; index++) track('answer', { index })
    const events = JSON.parse(localStorage.getItem(EVENTS_KEY)!)
    expect(events).toHaveLength(100)
    expect(events[0].index).toBe(10)
    expect(events[99].event).toBe('answer')
  })

  it('rejects unknown dimensions instead of retaining injected keys', () => {
    const state = { ...summary(), answers: { ...summary().answers, injected: 'time-0' } }
    expect(restoreState(JSON.stringify(state))).toEqual(initialState())
    const all = DIMENSIONS.map(({ id }) => id)
    expect(all).toEqual(expect.arrayContaining(['carbon', 'freshness', 'accessibility'] as Dimension[]))
  })
})
