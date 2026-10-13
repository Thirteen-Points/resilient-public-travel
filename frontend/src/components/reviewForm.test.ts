import { describe, expect, it } from 'vitest'
import type { EventDraft } from '../api/eventApi'
import { capacityFactorForImpact, segmentsWithCapacity, validatePendingCard } from './reviewForm'

const draft: EventDraft = {
  event_type: 'signal_failure', title: 'Signal delay', summary: 'Trains are running slowly.',
  mode: 'MTR', line: 'ERL', direction: 'both',
  affected_segments: [{ from_node: 'HUH', to_node: 'EXC', impact: 'slow' }],
}
const start = '2026-10-13T15:00'

describe('pending card capacity and validation', () => {
  it('creates a slow card without a capacity entry and sends numeric factor 1', () => {
    expect(validatePendingCard(draft, '3', start, '', [''])).toBeNull()
    expect(segmentsWithCapacity(draft, [''])).toEqual([
      { from_node: 'HUH', to_node: 'EXC', impact: 'slow', capacity_factor: 1 },
    ])
    expect(capacityFactorForImpact('crowded', '')).toBe(1)
    expect(capacityFactorForImpact('closed', '')).toBe(0)
  })

  it('reports only the missing affected segment when other fields are complete', () => {
    expect(validatePendingCard({ ...draft, affected_segments: [] }, '3', start, '', []))
      .toBe('Complete: affected segment.')
  })

  it('requires a valid numeric factor for reduced capacity', () => {
    const reduced = { ...draft, affected_segments: [{ ...draft.affected_segments[0], impact: 'reduced_capacity' }] }
    expect(validatePendingCard(reduced, '3', start, '', [''])).toBe('Complete: segment 1 capacity factor.')
    expect(validatePendingCard(reduced, '3', start, '', ['0.33']))
      .toBe('Segment 1 capacity factor must be between 0 and 1 in steps of 0.05.')
    expect(validatePendingCard(reduced, '3', start, '', ['0.5'])).toBeNull()
    expect(segmentsWithCapacity(reduced, ['0.5'])[0].capacity_factor).toBe(0.5)
  })
})
