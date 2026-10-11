import { Children, isValidElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { PersonaSelector } from './PersonaSelector'
import type { Persona } from '../api/types'

describe('planner persona selector', () => {
  it.each(['commuter', 'wheelchair'] as const)('marks %s as selected and keeps both native buttons keyboard accessible', value => {
    const html = renderToStaticMarkup(<PersonaSelector value={value} onSelect={() => {}} />)
    expect(html).toContain('TRAVELLER PROFILE')
    expect(html).toContain('Commuter')
    expect(html).toContain('Wheelchair')
    expect(html).not.toContain('disabled')
    expect(html.match(/aria-pressed="true"/g)).toHaveLength(1)
    expect(html.match(/<button type="button"/g)).toHaveLength(2)
  })

  it('sends the selected persona for either mouse or keyboard button activation', () => {
    const onSelect = vi.fn()
    const fieldset = PersonaSelector({ value: 'commuter', onSelect })
    const buttons = Children.toArray(fieldset.props.children).filter(isValidElement)
      .filter(element => element.type === 'button') as Array<{ props: { onClick: () => void } }>
    buttons[1].props.onClick()
    buttons[0].props.onClick()
    expect(onSelect.mock.calls.map(call => call[0] as Persona)).toEqual(['wheelchair', 'commuter'])
  })
})
