import type { EventDraft } from '../api/eventApi'

export function capacityFactorForImpact(impact: string, entered = ''): number | null {
  if (impact === 'closed') return 0
  if (impact === 'slow' || impact === 'crowded') return 1
  if (impact !== 'reduced_capacity' || !entered.trim()) return null
  const factor = Number(entered)
  return Number.isFinite(factor) && factor >= 0 && factor <= 1 && Math.abs(factor * 20 - Math.round(factor * 20)) < 1e-9
    ? factor : null
}

export function validatePendingCard(draft: EventDraft, severity: string, start: string, end: string, factors: string[]): string | null {
  const missing: string[] = []
  if (!draft.title.trim()) missing.push('title')
  if (!draft.summary.trim()) missing.push('summary')
  if (!draft.mode) missing.push('mode')
  if (!draft.line) missing.push('line')
  if (!draft.direction) missing.push('direction')
  if (!severity.trim()) missing.push('severity')
  if (!start.trim()) missing.push('start time')
  if (!draft.affected_segments.length) missing.push('affected segment')
  draft.affected_segments.forEach((segment, index) => {
    if (!segment.from_node) missing.push(`segment ${index + 1} From station`)
    if (!segment.to_node) missing.push(`segment ${index + 1} To station`)
    if (segment.impact === 'reduced_capacity' && !factors[index]?.trim()) missing.push(`segment ${index + 1} capacity factor`)
  })
  if (missing.length) return `Complete: ${missing.join(', ')}.`
  if (!Number.isInteger(Number(severity)) || Number(severity) < 1 || Number(severity) > 5) return 'Severity must be a whole number from 1 to 5.'
  const startAt = Date.parse(`${start}:00+08:00`)
  if (!Number.isFinite(startAt)) return 'Choose a valid start time in Hong Kong time.'
  if (end && (!Number.isFinite(Date.parse(`${end}:00+08:00`)) || Date.parse(`${end}:00+08:00`) <= startAt)) return 'End time must be after start time.'
  for (const [index, segment] of draft.affected_segments.entries()) {
    if (segment.from_node === segment.to_node) return `Segment ${index + 1} needs two different stations.`
    if (capacityFactorForImpact(segment.impact, factors[index]) === null) return `Segment ${index + 1} capacity factor must be between 0 and 1 in steps of 0.05.`
  }
  return null
}

export function segmentsWithCapacity(draft: EventDraft, factors: string[]) {
  return draft.affected_segments.map((segment, index) => {
    const capacityFactor = capacityFactorForImpact(segment.impact, factors[index])
    if (capacityFactor === null) throw new Error(`Invalid capacity factor for segment ${index + 1}`)
    return { ...segment, capacity_factor: capacityFactor }
  })
}
