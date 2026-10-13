import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import type { Map as MapLibreMap } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import type { Event, Network, RouteCandidate } from './api/types'
import { CORRIDOR_IDS } from './data'
import { eastRailStations } from './lib/eastRailAccess'
import { lineGradient, lineStyle, resolveLine } from './lib/lineColors'
import { resolveNetworkLineGeometry, resolveRouteLegGeometry, resolveImpactGeometry } from './map/geometry'
import css from './MapView.module.css'

/** Map occupies the journey grid cell, docks beside Updates, or hides on text pages. */
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
  const pickingRef = useRef(picking)
  const [provider, setProvider] = useState('Loading basemap')
  const [renderedRevision, setRenderedRevision] = useState('')
  const [hasSchematic, setHasSchematic] = useState(false)
  const boundsRef = useRef<L.LatLngBounds | null>(null)
  const resetRef = useRef<(animated?: boolean) => void>(() => {})
  pickerRef.current = onMapPick
  pickingRef.current = picking

  useEffect(() => {
    if (!element.current || mapRef.current) return
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
    const map = L.map(element.current, { zoomControl: false, scrollWheelZoom: true, preferCanvas: false,
      zoomSnap: .25, zoomDelta: .5, wheelPxPerZoomLevel: 100, wheelDebounceTime: 40,
      keyboard: true, touchZoom: true, minZoom: 9, maxZoom: 19,
      zoomAnimation: !motion.matches, fadeAnimation: !motion.matches, markerZoomAnimation: !motion.matches })
    const updateMotion = () => { map.options.zoomAnimation = !motion.matches; map.options.fadeAnimation = !motion.matches }
    motion.addEventListener('change', updateMotion)
    mapRef.current = map
    L.control.zoom({ position: 'bottomright' }).addTo(map)
    map.attributionControl.addAttribution('Paths: &copy; <a href="https://portal.csdi.gov.hk/" target="_blank" rel="noopener noreferrer">HKSARG / CSDI</a>')
    const corridor = network.nodes.filter(node => CORRIDOR_IDS.some(id => id === node.id) && Number.isFinite(node.lat) && Number.isFinite(node.lng)).map(node => [node.lat, node.lng] as L.LatLngTuple)
    boundsRef.current = L.latLngBounds(corridor)
    const fit = (animated = false) => {
      map.invalidateSize()
      if (!element.current?.clientWidth || !element.current.clientHeight || !boundsRef.current?.isValid()) return
      // The map owns its grid cell; panels no longer cover its useful viewport.
      map.fitBounds(boundsRef.current, { paddingTopLeft: [32, pickingRef.current ? 160 : 72], paddingBottomRight: [48, window.innerWidth < 1024 ? 160 : 80],
        maxZoom: 14, animate: animated && !motion.matches, duration: .18 })
    }
    fit()
    resetRef.current = fit
    let resizeTimer: ReturnType<typeof setTimeout> | undefined
    const resize = new ResizeObserver(() => {
      map.invalidateSize({ pan: false })
      clearTimeout(resizeTimer)
      resizeTimer = setTimeout(() => { if (element.current?.clientWidth && element.current?.clientHeight) fit() }, 200)
    })
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
          setProvider('Basemap unavailable')
        }
      })
      replace(tiles)
      deadline = setTimeout(() => { if (!disposed && active === tiles) { map.removeLayer(tiles); setProvider('Basemap unavailable') } }, 10000)
    }
    const openFreeMap = async () => {
      try {
        const [{ maplibreGL }, { setWorkerUrl }] = await Promise.all([
          import('@maplibre/maplibre-gl-leaflet'), import('maplibre-gl'),
        ])
        if (disposed) return
        setWorkerUrl(workerUrl)
        // A mobile list starts with a hidden, uninitialised Leaflet viewport.
        // Initialise the vector layer only after the first visible fit.
        map.whenReady(() => {
          if (disposed) return
          try {
            const layer = maplibreGL({ style: 'https://tiles.openfreemap.org/styles/positron', interactive: false }) as L.Layer & { getMaplibreMap: () => MapLibreMap }
            replace(layer)
            const base = layer.getMaplibreMap()
            setProvider('OpenFreeMap')
            let failures = 0
            base.on('error', () => { if (++failures === 3 && active === layer) osm() })
            base.once('style.load', () => {
              if (disposed || active !== layer) return
              for (const item of base.getStyle().layers ?? []) {
                if (item.type === 'fill' && /water/.test(item.id)) base.setPaintProperty(item.id, 'fill-color', '#DEE9E4')
                if (item.type === 'fill' && /park|landcover.*grass/.test(item.id)) base.setPaintProperty(item.id, 'fill-color', '#E8EFDE')
                if (item.type === 'background') base.setPaintProperty(item.id, 'background-color', '#F7F8F2')
                if (item.type === 'symbol' && /poi|housenumber/.test(item.id)) base.setLayoutProperty(item.id, 'visibility', 'none')
              }
            })
            base.once('idle', () => {
              if (active !== layer || disposed) return
              if (!base.queryRenderedFeatures().length) { osm(); return }
              clearTimeout(deadline)
            })
            deadline = setTimeout(() => { if (!disposed && active === layer) osm() }, 10000)
          } catch (error) { if (import.meta.env.DEV) console.warn('Vector basemap unavailable', error); osm() }
        })
      } catch (error) { if (import.meta.env.DEV) console.warn('Vector basemap unavailable', error); osm() }
    }
    const cartoUrl = import.meta.env.VITE_CARTO_TILE_URL
    if (cartoUrl) {
      let failures = 0
      replace(L.tileLayer(cartoUrl, { attribution: '&copy; OpenStreetMap contributors &copy; CARTO', maxZoom: 19 })
        .on('tileerror', () => { if (++failures === 3) void openFreeMap() }))
      setProvider('CARTO')
    } else void openFreeMap()
    return () => {
      disposed = true
      clearTimeout(deadline)
      motion.removeEventListener('change', updateMotion)
      resize.disconnect()
      clearTimeout(resizeTimer)
      map.remove()
      mapRef.current = null
      overlaysRef.current = null
    }
  }, [network])

  useEffect(() => {
    const group = overlaysRef.current
    if (!group) return
    group.clearLayers()
    let schematic = false
    const routeColours = ['#1565C0', '#6A1B9A', '#00838F']
    const draw = (points: L.LatLngExpression[], colors: string[], weight: number, opacity: number, dashed = false, selected = false, label?: string) => {
      if (points.length < 2) return
      if (selected) L.polyline(points, { color: '#FFFFFF', weight: weight + 4, opacity: 1, lineCap: 'round', lineJoin: 'round', interactive: false }).addTo(group)
      colors.forEach((color, index) => {
        const line = L.polyline(points, { color, weight: index ? weight * .48 : weight, opacity,
          dashArray: dashed ? '4 6' : undefined, lineCap: 'round', lineJoin: 'round', interactive: Boolean(label) }).addTo(group)
        if (label) line.bindTooltip(label)
      })
    }
    for (const node of picking ? eastRailStations(network) : []) {
      if (!node || !Number.isFinite(node.lat) || !Number.isFinite(node.lng)) continue
      L.circle([node.lat, node.lng], {
        radius: 800,
        color: '#1565C0', weight: 1, opacity: .3, fillColor: '#1565C0', fillOpacity: .05, interactive: false,
      }).addTo(group)
    }
    const drawnPatterns = new Set<string>()
    for (const line of network.lines) {
      const pattern = `${line.mode}:${line.stops.join(',')}`
      if (drawnPatterns.has(pattern)) continue
      drawnPatterns.add(pattern)
      for (const geometry of resolveNetworkLineGeometry(line, network)) {
        schematic ||= geometry.quality === 'schematic' || geometry.quality === 'mixed'
        geometry.parts.forEach((part, index) => draw(part, lineStyle(line).colors, 2, routes.length ? .2 : .4, geometry.partQualities[index] === 'schematic'))
      }
    }
    routes.map((route, index) => ({ route, index })).filter(({ route, index }) => index < 3 || route.route_id === selectedRouteId).sort((a, b) => Number(a.route.route_id === selectedRouteId) - Number(b.route.route_id === selectedRouteId)).forEach(({ route, index }) => {
      for (const leg of route.legs) {
        const geometry = resolveRouteLegGeometry(leg, network)
        schematic ||= geometry.quality === 'schematic' || geometry.quality === 'mixed'
        const selected = route.route_id === selectedRouteId
        const style = lineStyle(resolveLine(network, leg.line), leg.line ?? leg.mode)
        geometry.parts.forEach((part, partIndex) => draw(part, [routeColours[index % routeColours.length]], selected ? 6 : 4, selected ? 1 : .65, leg.mode === 'WALK' || geometry.partQualities[partIndex] === 'schematic', selected, `Option ${String.fromCharCode(65 + index)} · ${leg.mode === 'WALK' ? 'Walk' : style.label}${geometry.partQualities[partIndex] === 'schematic' ? ' · schematic connection' : ''}`))
      }
    })
    for (const event of published) for (const segment of event.affected_segments) {
      const geometry = resolveImpactGeometry(segment, event.line, network)
      schematic ||= geometry.quality === 'schematic' || geometry.quality === 'mixed'
      for (const part of geometry.parts) L.polyline(part, {
        color: segment.impact === 'closed' ? '#C62828' : '#F9A825',
        weight: segment.impact === 'closed' ? 6 : 4,
        lineCap: 'round', lineJoin: 'round', dashArray: segment.impact === 'closed' ? '8 6' : '2 6', interactive: false,
      }).addTo(group)
      const middle = geometry.parts[0]?.[Math.floor(geometry.parts[0].length / 2)]
      if (middle) L.marker(middle, { keyboard: false, interactive: false, icon: L.divIcon({ className: `${css.impactMarker} ${segment.impact === 'closed' ? '' : css.affectedMarker}`, html: segment.impact === 'closed' ? '×' : '!', iconSize: [24, 24], iconAnchor: [12, 12] }) }).addTo(group)
    }
    for (const node of network.nodes) {
      const id = node.id
      const corridor = CORRIDOR_IDS.some(stationId => stationId === id)
      if (!node || !Number.isFinite(node.lat) || !Number.isFinite(node.lng)) continue
      const label = document.createElement('span')
      const english = document.createElement('span')
      english.className = css.stationEnglish
      english.textContent = node.name_en
      label.append(english)
      L.circleMarker([node.lat, node.lng], {
        radius: corridor ? node.lines.length > 1 ? 7 : 5 : 4, color: node.kind === 'bus_stop' ? '#B14336' : node.kind === 'pier' ? '#287857' : '#18221D', weight: 2,
        fillColor: '#fff', fillOpacity: 1,
      }).bindTooltip(label, { permanent: corridor, direction: id === 'ADM' || id === 'MKK' ? 'left' : 'right', offset: [id === 'ADM' || id === 'MKK' ? -9 : 9, 0], className: css.stationLabel }).addTo(group)
      L.circleMarker([node.lat, node.lng], { radius: 22, opacity: 0, fillOpacity: 0 }).bindTooltip(node.name_en, { className: css.stationLabel }).addTo(group)
    }
    const points = routes.flatMap(route => route.legs.flatMap(leg => resolveRouteLegGeometry(leg, network).parts.flat()))
    if (points.length) boundsRef.current = L.latLngBounds(points)
    else boundsRef.current = L.latLngBounds(network.nodes.filter(node => CORRIDOR_IDS.some(id => id === node.id) && Number.isFinite(node.lat) && Number.isFinite(node.lng)).map(node => [node.lat, node.lng] as L.LatLngTuple))
    setHasSchematic(schematic)
    setRenderedRevision(published.map(event => `${event.event_id}@${event.version}`).join(','))
  }, [network, published, routes, selectedRouteId, picking])

  const routeKey = routes.map(route => route.route_id).join(',')
  useEffect(() => { resetRef.current(false) }, [routeKey, picking])

  // Re-fit the corridor once the mode transition has settled so it recentres in
  // whichever geometry is now active; hidden maps re-fit when shown again.
  const firstMode = useRef(true)
  useEffect(() => {
    if (firstMode.current) { firstMode.current = false; return }
    if (mode === 'hidden') return
    const timer = setTimeout(() => resetRef.current(true), window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 180)
    return () => clearTimeout(timer)
  }, [mode])

  return <div className={`${css.wrap} ${picking ? css.picking : ''} ${mode === 'docked' ? css.docked : ''} ${mode === 'hidden' ? css.hidden : ''}`}>
    <div ref={element} className={css.map} data-event-revisions={renderedRevision} tabIndex={0} aria-label="Hong Kong journey map. Arrow keys pan; plus and minus zoom. Stations can also be selected from the journey form." />
    <div className={css.tools}><button type="button" onClick={() => resetRef.current(true)} aria-label="Fit corridor on map">◎ Fit journey</button></div>
    <details className={css.legend}><summary>Map legend <span aria-hidden="true">↗</span></summary><div>
      {routes.map((route, index) => <p key={route.route_id}><b className={css.routeBadge} style={{ background: ['#1565C0', '#6A1B9A', '#00838F'][index % 3] }}>{String.fromCharCode(65 + index)}</b><span>Option {String.fromCharCode(65 + index)}{route.route_id === selectedRouteId ? ' · selected' : ''}</span></p>)}
      <p>White outline: selected route</p><p>× Red dashes: closed · ! Amber dots: affected</p><p>Dotted paths: walking or schematic connections</p>
      <details><summary>Transport lines</summary>{network.lines.map(line => { const style = lineStyle(line); return <p key={line.id}><i style={{ background: lineGradient(style.colors) }} /><span>{style.label}</span></p> })}</details>
      <p>Verified paths use CSDI geographic snapshots. Connections without a verified path are schematic.</p>
    </div></details>
    <p className={css.caption}>{provider}{hasSchematic ? ' · includes schematic connections' : ' · sourced path geometry'}</p>
    {picking && <p className={css.pickHint}>Tap within an 800 m circle around one of the six East Rail stations. Distance is measured straight-line from the station point.</p>}
  </div>
}
