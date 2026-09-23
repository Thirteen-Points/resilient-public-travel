import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import type { Event, Network, RouteCandidate } from './api/types'
import { CORRIDOR_IDS, legCoordinates, nodeIndex } from './data'
import css from './MapView.module.css'

type Props = {
  network: Network
  published: Event[]
  routes: RouteCandidate[]
  selectedRouteId: string | null
  picking: boolean
  onMapPick: (point: { lat: number; lng: number }) => void
}

export function MapView({ network, published, routes, selectedRouteId, picking, onMapPick }: Props) {
  const element = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const overlaysRef = useRef<L.LayerGroup | null>(null)
  const pickerRef = useRef(onMapPick)
  const [provider, setProvider] = useState('OpenFreeMap')
  pickerRef.current = onMapPick

  useEffect(() => {
    if (!element.current || mapRef.current) return
    const map = L.map(element.current, { zoomControl: false, scrollWheelZoom: false, preferCanvas: true })
    mapRef.current = map
    L.control.zoom({ position: 'bottomright' }).addTo(map)
    const corridor = CORRIDOR_IDS.map(id => nodeIndex(network).get(id)!).map(node => [node.lat, node.lng] as L.LatLngTuple)
    const bounds = L.latLngBounds(corridor)
    const fit = () => {
      map.invalidateSize()
      const left = element.current!.clientWidth >= 800 ? 500 : 24
      map.fitBounds(bounds, { paddingTopLeft: [left, 64], paddingBottomRight: [72, 82], maxZoom: 13 })
    }
    fit()
    const resize = new ResizeObserver(fit)
    resize.observe(element.current)
    overlaysRef.current = L.layerGroup().addTo(map)
    map.on('click', event => pickerRef.current({ lat: event.latlng.lat, lng: event.latlng.lng }))
    let disposed = false
    let active: L.Layer | undefined
    const replace = (layer: L.Layer) => {
      if (disposed) return
      if (active) map.removeLayer(active)
      active = layer.addTo(map)
      if ('bringToBack' in layer && typeof layer.bringToBack === 'function') layer.bringToBack()
    }
    const osm = () => {
      if (disposed) return
      setProvider('OpenStreetMap')
      let failures = 0
      replace(L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors', maxZoom: 19,
      }).on('tileerror', () => {
        if (++failures === 3) {
          if (active) map.removeLayer(active)
          setProvider('Schematic · offline')
        }
      }))
    }
    const openFreeMap = async () => {
      try {
        await import('@maplibre/maplibre-gl-leaflet')
        if (disposed) return
        const plugin = L as typeof L & { maplibreGL: (options: { style: string }) => L.Layer & { getMaplibreMap?: () => { on: (name: string, callback: () => void) => void } } }
        const layer = plugin.maplibreGL({ style: 'https://tiles.openfreemap.org/styles/liberty' })
        replace(layer)
        setProvider('OpenFreeMap')
        let failures = 0
        layer.getMaplibreMap?.().on('error', () => { if (++failures === 3) osm() })
      } catch { osm() }
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
        L.polyline([[a.lat, a.lng], [b.lat, b.lng]], {
          color: line.mode === 'MTR' ? '#738ca0' : '#80a0a9', weight: line.mode === 'MTR' ? 3 : 2,
          opacity: .65, dashArray: line.mode === 'MTR' ? undefined : '5 6', interactive: false,
        }).addTo(group)
      }
    }
    routes.slice(0, 3).forEach((route, index) => {
      for (const leg of route.legs) {
        const points = legCoordinates(leg, network)
        if (points.length < 2) continue
        L.polyline(points, {
          color: ['#1473bb', '#784eb6', '#169689'][index],
          weight: route.route_id === selectedRouteId ? 7 : 4,
          opacity: route.route_id === selectedRouteId ? .92 : .63,
          dashArray: leg.mode === 'WALK' ? '5 5' : undefined, interactive: false,
        }).addTo(group)
      }
    })
    for (const event of published) for (const segment of event.affected_segments) {
      const a = nodes.get(segment.from_node), b = nodes.get(segment.to_node)
      if (!a || !b) continue
      L.polyline([[a.lat, a.lng], [b.lat, b.lng]], {
        color: segment.impact === 'closed' ? '#d53c3c' : '#cb8500',
        weight: segment.impact === 'closed' ? 7 : 5,
        dashArray: segment.impact === 'closed' ? '9 6' : undefined, interactive: false,
      }).addTo(group)
    }
    for (const id of CORRIDOR_IDS) {
      const node = nodes.get(id)
      if (!node) continue
      L.circleMarker([node.lat, node.lng], {
        radius: id === 'TAW' || id === 'ADM' ? 7 : 5, color: '#264455', weight: 2,
        fillColor: '#fff', fillOpacity: 1,
      }).bindTooltip(`${node.name_en} · ${node.name_zh}`).addTo(group)
    }
  }, [network, published, routes, selectedRouteId])

  return <div className={`${css.wrap} ${picking ? css.picking : ''}`}>
    <div ref={element} className={css.map} aria-label="Hong Kong schematic network map" />
    <p className={css.caption}>ACADEMIC DEMO · Map &amp; stations schematic · {provider}</p>
    {picking && <p className={css.pickHint}>Tap near a station, within {network.meta.catchment_m} m. Or search by name.</p>}
  </div>
}
