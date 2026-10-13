import { describe, expect, it } from 'vitest'
import { confidenceNote, sourceLabel } from './systemCopy'
import type { Signal } from '../api/types'

describe('stored system wording', () => {
  it('renders legacy confidence metadata in English without altering its score', () => {
    const factor = { factor: 'independent_source', weight: .15, score: 1, note: '独立且同意的来源 2 个' }
    expect(confidenceNote(factor)).toBe('2 independent agreeing sources')
    expect(factor.note).toBe('独立且同意的来源 2 个')
    expect(confidenceNote({ ...factor, factor: 'admin_confirmation', score: 0, note: '修改后待重新审核' })).toBe('Human review is still required.')
    expect(confidenceNote({ ...factor, factor: 'custom' })).toBe(factor.note)
  })
  it('localizes known generated source names and preserves arbitrary original sources', () => {
    expect(sourceLabel({ source_name: 'ResilientRoute 用户上报（未经核实）' } as Signal)).toBe('ResilientRoute user report (unverified)')
    expect(sourceLabel({ source_name: '乘客现场笔记' } as Signal)).toBe('乘客现场笔记')
  })
})
