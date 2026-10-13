import type { RouteCandidate, TransitMode } from '../api/types'

export const TRANSPORT_OPTIONS: { id: 'all' | TransitMode; label: string }[] = [
  { id: 'all', label: 'All modes' },
  { id: 'MTR', label: 'MTR' },
  { id: 'BUS', label: 'Bus' },
  { id: 'MINIBUS', label: 'Minibus' },
  { id: 'FERRY', label: 'Ferry' },
]

export function transportLabel(modes?: TransitMode[]): string {
  return modes?.length ? modes.map(mode => TRANSPORT_OPTIONS.find(option => option.id === mode)?.label ?? mode).join(' + ') : 'All modes'
}

export function routeMatchesModes(route: RouteCandidate, modes?: TransitMode[], requiredModes?: TransitMode[]): boolean {
  const rides = route.legs.filter(leg => leg.mode !== 'WALK')
  return (!modes || rides.length > 0 && rides.every(leg => modes.includes(leg.mode as TransitMode))) &&
    (!requiredModes || requiredModes.every(mode => rides.some(leg => leg.mode === mode)))
}
