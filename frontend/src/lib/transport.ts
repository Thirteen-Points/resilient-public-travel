import type { RouteCandidate, TransitMode } from '../api/types'

export const TRANSPORT_OPTIONS: { id: 'all' | TransitMode; label: string }[] = [
  { id: 'all', label: 'All modes' },
  { id: 'MTR', label: 'MTR · 地铁' },
  { id: 'BUS', label: 'Bus · 公交' },
  { id: 'MINIBUS', label: 'Minibus · 小巴' },
  { id: 'FERRY', label: 'Ferry · 渡轮' },
]

export function transportLabel(modes?: TransitMode[]): string {
  return modes?.length ? modes.map(mode => TRANSPORT_OPTIONS.find(option => option.id === mode)?.label ?? mode).join(' + ') : 'All modes'
}

export function routeMatchesModes(route: RouteCandidate, modes?: TransitMode[], requiredModes?: TransitMode[]): boolean {
  const rides = route.legs.filter(leg => leg.mode !== 'WALK')
  return (!modes || rides.length > 0 && rides.every(leg => modes.includes(leg.mode as TransitMode))) &&
    (!requiredModes || requiredModes.every(mode => rides.some(leg => leg.mode === mode)))
}
