import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import type { Map as MapLibreMap } from 'maplibre-gl'
import type { Event, Network, RouteCandidate } from './api/types'
import { CORRIDOR_IDS, legCoordinates, nodeIndex } from './data'
import { lineGradient, lineStyle, resolveLine } from './lib/lineColors'
import css from './MapView.module.css'

/** Map footprint across screens: full-bleed behind a floating panel, a
    right-hand card beside page content, or faded out for plain pages. */
export type MapMode = 'full' | 'docked' | 'hidden'

type Props = {
  network: Network
  published: Event[]
  routes: RouteCandidate[]
  selectedRouteId: string | null
  picking: boolean
  onMapPick: (point: { lat: number; lng: number }) => void
  mode?: MapMode
}

export function MapView({ network, published, routes, selectedRouteId, picking, onMapPick, mode = 'full' }: Props) {
  const element = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const overlaysRef = useRef<L.LayerGroup | null>(null)
  const pickerRef = useRef(onMapPick)
  const [provider, setProvider] = useState('Loading basemap')
  const [zoom, setZoom] = useState(12)
  const resetRef = useRef<(animated?: boolean) => void>(() => {})
  pickerRef.current = onMapPick

  useEffect(() => {
    if (!element.current || mapRef.current) return
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
    const map = L.map(element.current, { zoomControl: false, scrollWheelZoom: true, preferCanvas: true,
      zoomSnap: .25, zoomDelta: .5, wheelPxPerZoomLevel: 100, wheelDebounceTime: 40,
      keyboard: true, touchZoom: true, minZoom: 9, maxZoom: 19,
      zoomAnimation: !motion.matches, fadeAnimation: !motion.matches, markerZoomAnimation: !motion.matches })
    const updateMotion = () => { map.options.zoomAnimation = !motion.matches; map.options.fadeAnimation = !motion.matches }
    motion.addEventListener('change', updateMotion)
    mapRef.current = map
    L.control.zoom({ position: 'bottomright' }).addTo(map)
    const corridor = CORRIDOR_IDS.map(id => nodeIndex(network).get(id)!).map(node => [node.lat, node.lng] as L.LatLngTuple)
    const bounds = L.latLngBounds(corridor)
    const fit = (animated = false) => {
      map.invalidateSize()
      // Full-bleed mode reserves the left panel area; the docked card is small
      // and needs near-uniform padding or the corridor sits off-centre.
      const wide = element.current!.clientWidth >= 800 && element.current!.clientHeight >= 500
      const pad = wide ? { topLeft: [500, 64] as [number, number], bottomRight: [72, 82] as [number, number] }
        : { topLeft: [22, 22] as [number, number], bottomRight: [22, 22] as [number, number] }
      map.fitBounds(bounds, { paddingTopLeft: pad.topLeft, paddingBottomRight: pad.bottomRight,
        maxZoom: 13, animate: animated && !motion.matches, duration: .5 })
    }
    fit()
    resetRef.current = fit
    fit()
    resetRef.current = fit
    setZoom(map.getZoom())
    map.on('zoomend', () => setZoom(map.getZoom()))
    const resize = new ResizeObserver(() => map.invalidateSize({ pan: false }))
    resize.observe(element.current)
    overlaysRef.current = L.layerGroup().addTo(map)
    map.on('click', event => pickerRef.current({ lat: event.latlng.lat, lng: event.latlng.lng }))
    let disposed = false
    let deadline: ReturnType<typeof setTimeout> | undefined
    let active: L.Layer | undefined
    const replace = (layer: L.Layer) => {
      if (disposed) return
      clearTimeout(deadline)
      if (active) map.removeLayer(active)
      active = layer.addTo(map)
      if ('bringToBack' in layer && typeof layer.bringToBack === 'function') layer.bringToBack()
    }
    const osm = () => {
      if (disposed) return
      setProvider('OpenStreetMap')
      let failures = 0
      const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors', maxZoom: 19,
      }).on('tileload', () => clearTimeout(deadline)).on('tileerror', () => {
        if (++failures === 3) {
          clearTimeout(deadline)
          if (active) map.removeLayer(active)
          setProvider('Schematic · offline')
        }
      })
      replace(tiles)
      deadline = setTimeout(() => { if (!disposed && active === tiles) { map.removeLayer(tiles); setProvider('Schematic · basemap unavailable') } }, 10000)
    }
    const openFreeMap = async () => {
      try {
        await import('@maplibre/maplibre-gl-leaflet')
        if (disposed) return
        const plugin = L as typeof L & { maplibreGL: (options: { style: string }) => L.Layer & { getMaplibreMap: () => MapLibreMap } }
        const layer = plugin.maplibreGL({ style: 'https://tiles.openfreemap.org/styles/liberty' })
        replace(layer)
        setProvider('OpenFreeMap')
        let failures = 0
        layer.getMaplibreMap?.().on('error', () => { if (++failures === 3 && active === layer) osm() })
        layer.getMaplibreMap().once('idle', () => {
          if (active !== layer || disposed) return
          // A style can finish loading with only a background if its sources fail.
          if (!layer.getMaplibreMap().queryRenderedFeatures().length) { osm(); return }
          clearTimeout(deadline)
        })
        deadline = setTimeout(() => { if (!disposed && active === layer) osm() }, 10000)
      } catch { osm() }
    }
    const cartoUrl = import.meta.env.VITE_CARTO_TILE_URL
    if (cartoUrl) {
      let failures = 0
      replace(L.tileLayer(cartoUrl, { attribution: '&copy; OpenStreetMap contributors &copy; CARTO', maxZoom: 19 })
        .on('tileerror', () => { if (++failures === 3) void openFreeMap() }))
      setProvider('CARTO')
    } else osm()
    return () => {
      disposed = true
      clearTimeout(deadline)
      motion.removeEventListener('change', updateMotion)
      resize.disconnect()
      map.remove()
      mapRef.current = null
      overlaysRef.current = null
    }
  }, [network])

  useEffect(() => {
    const group = overlaysRef.current
    if (!group) return
    group.clearLayers()
    const draw = (points: L.LatLngExpression[], colors: string[], weight: number, opacity: number, dashed = false, selected = false, label?: string) => {
      if (selected) L.polyline(points, { color: '#fffef4', weight: weight + 5, opacity: .95, interactive: false }).addTo(group)
      colors.forEach((color, index) => {
        const line = L.polyline(points, { color, weight: index ? weight * .48 : weight, opacity,
          dashArray: dashed ? '5 6' : undefined, lineCap: 'round', interactive: Boolean(label) }).addTo(group)
        if (label) line.bindTooltip(label)
      })
    }
    const nodes = nodeIndex(network)
    for (const id of CORRIDOR_IDS) {
      const node = nodes.get(id)
      if (!node) continue
      L.circle([node.lat, node.lng], {
        radius: node.catchment_m ?? network.meta.catchment_m,
        color: '#2576af', weight: 1, opacity: .24, fillColor: '#3b9fcb', fillOpacity: .055, interactive: false,
      }).addTo(group)
    }
    for (const line of network.lines) {
      for (let i = 0; i < line.stops.length - 1; i++) {
        const a = nodes.get(line.stops[i]), b = nodes.get(line.stops[i + 1])
        if (!a || !b) continue // Never invent absent seed coordinates.
        draw([[a.lat, a.lng], [b.lat, b.lng]], lineStyle(line).colors, line.mode === 'MTR' ? 3 : 3.5, .48, line.mode !== 'MTR')
      }
    }
    routes.slice(0, 3).map((route, index) => ({ route, index })).sort((a, b) => Number(a.route.route_id === selectedRouteId) - Number(b.route.route_id === selectedRouteId)).forEach(({ route, index }) => {
      for (const leg of route.legs) {
        const points = legCoordinates(leg, network)
        if (points.length < 2) continue
        const selected = route.route_id === selectedRouteId
        const style = lineStyle(resolveLine(network, leg.line), leg.line ?? leg.mode)
        draw(points, leg.mode === 'WALK' ? ['#67796B'] : style.colors, selected ? 8 : 4.5, selected ? 1 : .55, leg.mode === 'WALK', selected, `Option ${'ABC'[index]} · ${leg.mode === 'WALK' ? 'Walk' : style.label}`)
      }
    })
    for (const event of published) for (const segment of event.affected_segments) {
      const a = nodes.get(segment.from_node), b = nodes.get(segment.to_node)
      if (!a || !b) continue
      L.polyline([[a.lat, a.lng], [b.lat, b.lng]], {
        color: segment.impact === 'closed' ? '#d53c3c' : '#cb8500',
        weight: segment.impact === 'closed' ? 7 : 5,
        dashArray: segment.impact === 'closed' ? '9 6' : '2 8', interactive: false,
      }).addTo(group)
    }
    for (const id of CORRIDOR_IDS) {
      const node = nodes.get(id)
      if (!node) continue
      L.circleMarker([node.lat, node.lng], {
        radius: id === 'TAW' || id === 'ADM' ? 7 : 5, color: '#264455', weight: 2,
        fillColor: '#fff', fillOpacity: 1,
      }).bindTooltip(`${node.name_en} · ${node.name_zh}`, { permanent: true, direction: id === 'ADM' || id === 'MKK' ? 'left' : 'right', offset: [id === 'ADM' || id === 'MKK' ? -9 : 9, 0], className: css.stationLabel }).addTo(group)
    }
  }, [network, published, routes, selectedRouteId])

  // Re-fit the corridor once the mode transition has settled so it recentres in
  // whichever geometry is now active; hidden maps re-fit when shown again.
  const firstMode = useRef(true)
  useEffect(() => {
    if (firstMode.current) { firstMode.current = false; return }
    if (mode === 'hidden') return
    const timer = setTimeout(() => resetRef.current(true), 620)
    return () => clearTimeout(timer)
  }, [mode])

  return <div className={`${css.wrap} ${picking ? css.picking : ''} ${mode === 'docked' ? css.docked : ''} ${mode === 'hidden' ? css.hidden : ''}`}>
    <div ref={element} className={css.map} tabIndex={0} aria-label="Hong Kong schematic network map. Scroll to zoom around the pointer; use arrow keys to pan and plus or minus to zoom." />
    <div className={css.tools}><button type="button" onClick={() => resetRef.current(true)} aria-label="Fit corridor on map">◎ Fit corridor</button><span>Zoom {zoom.toFixed(2)}</span></div>
    <details className={css.legend}><summary>Network colours <span>↗</span></summary><div>{network.lines.map(line => { const style = lineStyle(line); return <p key={line.id}><i style={{ background: lineGradient(style.colors) }} /><span>{style.label}</span></p> })}<p><i style={{ background: lineStyle(undefined, 'unmapped').colors[0] }} /><span>Unknown line · assigned colour (example)</span></p><hr /><p>Bold + white outline: selected candidate</p><p>Red dashes: closed · amber dots: affected</p><p>Scroll at your pointer to zoom. Pinch or use + / −. All paths are schematic.</p></div></details>
    <p className={css.caption}>ACADEMIC DEMO · Map &amp; stations schematic · {provider}</p>
    {picking && <p className={css.pickHint}>Tap near a station, within {network.meta.catchment_m} m. Or search by name.</p>}
  </div>
}
