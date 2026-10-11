import type { Persona } from '../api/types'
import css from '../App.module.css'

export function PersonaSelector({ value, onSelect }: { value: Persona; onSelect: (value: Persona) => void }) {
  return <fieldset className={css.presets}><legend>TRAVELLER PROFILE</legend>
    {(['commuter', 'wheelchair'] as const).map(persona =>
      <button key={persona} type="button" aria-pressed={value === persona}
        className={value === persona ? css.activePreset : ''} onClick={() => onSelect(persona)}>
        {persona === 'commuter' ? 'Commuter' : 'Wheelchair'}
      </button>,
    )}
  </fieldset>
}
