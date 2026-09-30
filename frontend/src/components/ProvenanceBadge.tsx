import css from './ProvenanceBadge.module.css'

/** Shared data-authenticity badge (real / real-derived / simulated). */
export function ProvenanceBadge({ value, compact = false }: { value: string; compact?: boolean }) {
  return <span className={compact ? css.compact : css.badge}>
    {value === 'real' ? 'Real station record' : value === 'real-derived' ? 'Derived estimate' : 'Simulated seed'}
  </span>
}
