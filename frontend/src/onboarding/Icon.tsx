import type { CSSProperties } from 'react'
import type { Dimension } from './model'
const paths: Record<Dimension | 'arrow' | 'check' | 'back' | 'shield' | 'download', string> = {
  time: 'M12 8v4l3 2M20 12a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
  transfers: 'M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4',
  walking: 'm13 9-3 4 4 3-1 5m-3-8-3 5M7 11l4-3 4 3 4 1M14 4a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Z',
  fare: 'M4 6h15v14H4V6Zm0 0V4h12v2m0 6h5v4h-5v-4Z',
  comfort: 'M7 4v9h10V4M5 11v7h14v-7M7 18v3m10-3v3M7 8h10',
  reliability: 'm7 12 3 3 7-7M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z',
  carbon: 'M5 19C1 10 9 4 20 4c0 11-6 18-15 15Zm0 0L16 8',
  freshness: 'M20 8a8 8 0 0 0-14-2L3 9m0-6v6h6M4 16a8 8 0 0 0 14 2l3-3m0 6v-6h-6',
  accessibility: 'M13 5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Zm-2 3v7h6l3 5m-9-9h5M8 12a5 5 0 1 0 6 8',
  arrow: 'M4 12h15m-6-6 6 6-6 6', check: 'm5 12 4 4L19 6', back: 'M20 12H5m6-6-6 6 6 6', shield: 'M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Zm-4 9 3 3 5-6', download: 'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',
}
export function Icon({ name, size = 20, style }: { name: keyof typeof paths; size?: number; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}><path d={paths[name]} /></svg>
}
