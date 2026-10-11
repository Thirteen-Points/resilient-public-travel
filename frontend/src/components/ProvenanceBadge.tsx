import css from './ProvenanceBadge.module.css'

/** Shared data-authenticity badge (real / real-derived / simulated). */
export function ProvenanceBadge({ value, compact = false }: { value: string; compact?: boolean }) {
  const known = value === 'real' || value === 'real-derived' || value === 'simulated'
  return <span className={`${css.badge} ${compact ? css.compact : ''}`} data-provenance={known ? value : 'unknown'}>
    {value === 'real' ? 'Real record' : value === 'real-derived' ? 'Derived estimate' : value === 'simulated' ? 'Simulated seed' : 'Source unverified'}
  </span>
}
