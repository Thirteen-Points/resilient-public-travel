import type { Event, Signal } from '../api/types'

/** Localize known system metadata from older stored records; preserve evidence text. */
export function sourceLabel(signal: Signal): string {
  if (signal.source_name === 'ResilientRoute 用户上报（未经核实）') return 'ResilientRoute user report (unverified)'
  if (signal.source_name === 'ResilientRoute 模拟社媒流') return 'ResilientRoute simulated social feed'
  if (signal.source_name === '港铁实时到站开放数据') return 'MTR real-time arrival open data'
  return signal.source_name
}

export function confidenceNote(factor: NonNullable<Event['confidence_factors']>[number]): string {
  // Already-English notes and unknown custom notes remain verbatim.
  if (!/[\u3400-\u9fff]/.test(factor.note)) return factor.note
  const active = factor.score > 0
  switch (factor.factor) {
    case 'base_signal': return 'At least one related report; the incident remains unverified.'
    case 'independent_source': {
      const count = factor.note.match(/来源\s*(\d+)\s*个/)
      return count ? `${count[1]} independent agreeing sources` : active ? 'Independent sources agree.' : 'Independent agreement is not established.'
    }
    case 'multi_source_agreement': return active ? 'At least two independent sources agree.' : 'Multiple-source agreement has not been established.'
    case 'source_authority': return active ? 'A verified official notice relates to this incident.' : 'No related verified official notice.'
    case 'official_floor': return 'Adjustment to the 0.85 confidence floor for official notices.'
    case 'stage_cap': return 'Deduction above the current confidence stage cap.'
    case 'admin_confirmation': return active ? 'Confirmed by human review.' : 'Human review is still required.'
    case 'source_conflict': return active ? 'Deduct 0.15 for conflicting evidence; verification is required.' : 'No related conflicting evidence.'
    default: return factor.note
  }
}
