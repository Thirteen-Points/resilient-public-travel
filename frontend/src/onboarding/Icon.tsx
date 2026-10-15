import type { Dimension } from './model'

type Name = Dimension | 'arrow' | 'back' | 'check' | 'close' | 'download' | 'route'
const paths: Record<Name, string> = {
  time: 'M12 8v4l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  transfers: 'M4 7h14l-3-3m3 3-3 3M20 17H6l3-3m-3 3 3 3',
  walking: 'm12 6 2 4 4 2M8 21l3-7m5 7-3-8-4-2 2-4M7 13l-3 2M14 3h.01',
  fare: 'M12 7v10m3-8H10a2 2 0 0 0 0 4h4a2 2 0 0 1 0 4H9M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  comfort: 'M6 13V7a3 3 0 0 1 3-3h6a3 3 0 0 1 3 3v6M4 11v6h16v-6M7 17v3m10-3v3M4 14h16',
  reliability: 'm8 12 3 3 5-6M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z',
  carbon: 'M5 19 16 8M5 16C1 5 15 3 21 3c0 6-2 19-13 15',
  freshness: 'M20 7v5h-5M4 17v-5h5m10-5A8 8 0 0 0 5 6m0 11a8 8 0 0 0 14 1',
  accessibility: 'M12 3h.01M5 8l7 2 7-2m-7 2v5m0 0-4 7m4-7 4 7',
  arrow: 'M4 12h15m-6-6 6 6-6 6',
  back: 'M20 12H5m6-6-6 6 6 6',
  check: 'm5 12 4 4L19 6',
  close: 'm6 6 12 12M6 18 18 6',
  download: 'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',
  route: 'M6 19V9a4 4 0 0 1 4-4h8M6 15l8-8M3 19a3 3 0 1 1 6 0 3 3 0 0 1-6 0ZM15 5a3 3 0 1 1 6 0 3 3 0 0 1-6 0Z',
}
export function Icon({ name, size = 20 }: { name: Name; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}
