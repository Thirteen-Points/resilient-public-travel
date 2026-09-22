// Provenance semantics shared by cards, badges and the map caption.
// The three levels come from contracts (docs/plan/03-contracts.md §2);
// anything outside the enum is reported as unknown, never upgraded.

import type { Provenance } from '../api/types'

export const PROVENANCE_VALUES: readonly Provenance[] = ['real', 'real-derived', 'simulated']

export const PROVENANCE_LABELS: Record<Provenance, string> = {
  'real': 'Real',
  'real-derived': 'Estimated / Derived',
  'simulated': 'Simulated',
}

/** Conservative ordering used when merging records: the weakest source decides the label. */
export const PROVENANCE_RANK: Record<Provenance, number> = {
  'real': 2,
  'real-derived': 1,
  'simulated': 0,
}

export function isProvenance(value: unknown): value is Provenance {
  return typeof value === 'string' && (PROVENANCE_VALUES as readonly string[]).includes(value)
}

export interface ProvenanceInfo {
  value: string
  label: string
  /** False when the value is outside the contract enum. */
  known: boolean
  /** True only for verified real records — estimates and simulations stay false. */
  mayBeRealData: boolean
}

export function describeProvenance(value: string | null | undefined): ProvenanceInfo {
  if (isProvenance(value)) {
    return { value, label: PROVENANCE_LABELS[value], known: true, mayBeRealData: value === 'real' }
  }
  return { value: value ?? '', label: 'Unknown', known: false, mayBeRealData: false }
}

export function worstProvenance(a: Provenance, b: Provenance): Provenance {
  return PROVENANCE_RANK[a] <= PROVENANCE_RANK[b] ? a : b
}
