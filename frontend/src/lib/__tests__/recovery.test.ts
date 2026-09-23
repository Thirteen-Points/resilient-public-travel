import { describe, expect, it } from 'vitest'
import {
  createAiUnavailableState, createEmptyState, createErrorState, createLoadingState,
  createOfflineState, createOutOfRangeState, createStaleState, fromErrorPayload,
} from '../recovery'

const allStates = [
  createLoadingState(),
  createEmptyState('route'),
  createStaleState('08:20 HKT'),
  createOfflineState(),
  createOutOfRangeState(800),
  createAiUnavailableState(),
  createErrorState(),
]

describe('recovery states', () => {
  it('always carries a readable message, fallback, previous-result policy and next action', () => {
    for (const state of allStates) {
      expect(state.message.length).toBeGreaterThan(0)
      expect(state.fallback.length).toBeGreaterThan(0)
      expect(typeof state.keepPreviousResult).toBe('boolean')
      expect(state.nextAction.length).toBeGreaterThan(0)
    }
  })

  it('keeps the last successful result on network failure, as the contract requires', () => {
    expect(createOfflineState().keepPreviousResult).toBe(true)
    expect(createStaleState('08:20 HKT').keepPreviousResult).toBe(true)
    expect(createErrorState(new Error('boom')).keepPreviousResult).toBe(true)
  })

  it('treats empty results as honest emptiness, not as an error to hide', () => {
    const empty = createEmptyState('route candidates')
    expect(empty.kind).toBe('empty')
    expect(empty.keepPreviousResult).toBe(false)
    expect(empty.retryable).toBe(false)
    expect(empty.message).toContain('No route candidates')
  })

  it('names the nearest access point when out of the catchment', () => {
    const withNearest = createOutOfRangeState(800, { name_en: 'Tai Wai', metres: 2140.6 })
    expect(withNearest.kind).toBe('out_of_range')
    expect(withNearest.message).toContain('within 800 m')
    expect(withNearest.message).toContain('Tai Wai')
    expect(withNearest.message).toContain('2141 m')
    const withoutNearest = createOutOfRangeState(800)
    expect(withoutNearest.message).not.toContain('undefined')
    expect(withoutNearest.message).toContain('within 800 m')
  })

  it('lets users continue with preset preferences when AI is unavailable', () => {
    const state = createAiUnavailableState()
    expect(state.kind).toBe('ai_unavailable')
    expect(state.nextAction).toMatch(/preset preferences/i)
    expect(state.fallback).toMatch(/without AI/i)
  })

  it('maps the API error envelope onto the error state', () => {
    const state = fromErrorPayload({ error: { code: 'network_down', message: 'Upstream unreachable', fallback: 'Seed snapshot shown' } })
    expect(state.kind).toBe('error')
    expect(state.message).toBe('Upstream unreachable')
    expect(state.fallback).toBe('Seed snapshot shown')
    expect(state.keepPreviousResult).toBe(true)
    expect(state.retryable).toBe(true)
  })

  it('falls back to a generic but honest message for unknown throwables', () => {
    expect(createErrorState('plain string').message).toBe('Something went wrong while loading data.')
    expect(createErrorState(new Error('x')).fallback.length).toBeGreaterThan(0)
    expect(createErrorState().message).not.toBe('')
  })
})
