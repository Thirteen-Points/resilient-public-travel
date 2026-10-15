import { describe, expect, it } from 'vitest'
import { CORE, DIMENSIONS, QUESTIONS, activeAnswers, calculateProfile, initialState, percentages, reducer, restoreState, type Dimension, type State } from './model'

function answer(state: State, option = 0) {
  const next = reducer(state, { type: 'SELECT', option: QUESTIONS[state.queue[state.cursor]].options[option].id })
  return reducer(next, { type: 'ADVANCE', revision: next.revision })
}
function coreCompleted() { return CORE.reduce(state => answer(state), reducer(initialState(), { type: 'START' })) }
describe('preference questionnaire state and evidence', () => {
  it('uses three distinct core dimensions and reaches the summary after three answers', () => {
    expect(new Set(CORE).size).toBe(3)
    expect(coreCompleted().phase).toBe('summary')
    expect(calculateProfile(coreCompleted()).collected).toBe(3)
  })
  it('skips without manufacturing evidence and retains normalized default priors', () => {
    const skipped = CORE.reduce(state => reducer(state, { type: 'SKIP' }), reducer(initialState(), { type: 'START' }))
    const profile = calculateProfile(skipped)
    expect(skipped.phase).toBe('summary')
    expect(profile.collected).toBe(0)
    CORE.forEach(id => expect(profile.evidence[id].status).toBe('skipped'))
    expect(profile.evidence.time.raw).toBe(1)
    expect(profile.evidence.carbon.raw).toBe(.45)
    expect(Object.values(profile.weights).reduce((a,b) => a+b,0)).toBeCloseTo(1,12)
  })
  it('retains later answers while removing their influence on backtracking', () => {
    const completed = coreCompleted()
    const second = reducer(reducer(completed, { type: 'BACK' }), { type: 'BACK' })
    expect(second.answers.reliability).toBe('reliability-0')
    expect(activeAnswers(second).reliability).toBeUndefined()
    expect(calculateProfile(second).evidence.reliability.status).toBe('prior')
    const third = answer(second, 2)
    expect(third.cursor).toBe(2)
    expect(third.answers.reliability).toBe('reliability-0')
    expect(calculateProfile(third).evidence.reliability.status).toBe('collected')
    expect(calculateProfile(third).evidence.transfers.raw).toBe(.6)
  })
  it('ignores stale auto-advance events after back, skip or a changed selection', () => {
    const started = reducer(initialState(), { type: 'START' })
    const selected = reducer(started, { type: 'SELECT', option: 'time-0' })
    const back = reducer(selected, { type: 'BACK' })
    expect(reducer(back, { type: 'ADVANCE', revision: selected.revision })).toEqual(back)
    const changed = reducer(selected, { type: 'SELECT', option: 'time-2' })
    expect(reducer(changed, { type: 'ADVANCE', revision: selected.revision })).toEqual(changed)
    const skipped = reducer(selected, { type: 'SKIP' })
    expect(reducer(skipped, { type: 'ADVANCE', revision: selected.revision })).toEqual(skipped)
  })
  it('unifies all nine dimensions and does not duplicate reopened questions', () => {
    let state = reducer(coreCompleted(), { type: 'CONTINUE' })
    const additional: Dimension[] = ['carbon', 'freshness', 'accessibility', 'walking', 'fare', 'comfort']
    additional.forEach(id => { state = answer(reducer(state, { type: 'OPEN', dimension: id })) })
    expect(state.phase).toBe('library')
    expect(calculateProfile(state).collected).toBe(9)
    expect(Object.values(calculateProfile(state).weights).reduce((a,b) => a+b,0)).toBeCloseTo(1,12)
    expect(Object.values(percentages(calculateProfile(state).weights)).reduce((a,b) => a+b,0)).toBe(100)
    expect(reducer(state, { type: 'OPEN', dimension: 'carbon' }).queue).toHaveLength(9)
  })
  it('makes a stronger response increase the relative weight of its dimension', () => {
    const state = reducer(initialState(), { type: 'START' })
    const high = calculateProfile(reducer(state, { type: 'SELECT', option: 'time-0' }))
    const low = calculateProfile(reducer(state, { type: 'SELECT', option: 'time-2' }))
    expect(high.weights.time).toBeGreaterThan(low.weights.time)
    DIMENSIONS.forEach(({id}) => expect(high.weights[id]).toBeGreaterThan(0))
  })
  it('recovers refreshes without resurrecting timers and rejects corrupted storage', () => {
    const selected = reducer(reducer(initialState(), { type: 'START' }), { type: 'SELECT', option: 'time-0' })
    const restored = restoreState(JSON.stringify(selected))
    expect(restored.pending).toBe(false)
    expect(restored.answers.time).toBe('time-0')
    for (const value of ['{broken', 'null', JSON.stringify({ ...selected, cursor: 100 }), JSON.stringify({ ...selected, queue: [...CORE, 'constructor'] }), JSON.stringify({ ...selected, queue: ['time','time','reliability'] })]) expect(restoreState(value)).toEqual(initialState())
  })
})
