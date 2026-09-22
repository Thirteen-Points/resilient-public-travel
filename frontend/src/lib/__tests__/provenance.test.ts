import { describe, expect, it } from 'vitest'
import { PROVENANCE_LABELS, describeProvenance, isProvenance, worstProvenance } from '../provenance'

describe('provenance semantics', () => {
  it('labels the three contract levels', () => {
    expect(PROVENANCE_LABELS.real).toBe('Real')
    expect(PROVENANCE_LABELS['real-derived']).toBe('Estimated / Derived')
    expect(PROVENANCE_LABELS.simulated).toBe('Simulated')
  })

  it('guards the enum without coercing unknown values', () => {
    expect(isProvenance('real')).toBe(true)
    expect(isProvenance('simulated')).toBe(true)
    expect(isProvenance('maybe')).toBe(false)
    expect(isProvenance(null)).toBe(false)
    expect(isProvenance(undefined)).toBe(false)
  })

  it('describes records without ever marking estimates or simulations as real', () => {
    expect(describeProvenance('real')).toEqual({ value: 'real', label: 'Real', known: true, mayBeRealData: true })
    expect(describeProvenance('real-derived').mayBeRealData).toBe(false)
    expect(describeProvenance('simulated').mayBeRealData).toBe(false)
    expect(describeProvenance('rumour')).toEqual({ value: 'rumour', label: 'Unknown', known: false, mayBeRealData: false })
    expect(describeProvenance(undefined)).toEqual({ value: '', label: 'Unknown', known: false, mayBeRealData: false })
  })

  it('keeps the weakest source when merging records', () => {
    expect(worstProvenance('real', 'simulated')).toBe('simulated')
    expect(worstProvenance('real', 'real-derived')).toBe('real-derived')
    expect(worstProvenance('simulated', 'simulated')).toBe('simulated')
    expect(worstProvenance('real-derived', 'simulated')).toBe('simulated')
  })
})
