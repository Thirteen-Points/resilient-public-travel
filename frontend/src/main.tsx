import React from 'react'
import ReactDOM from 'react-dom/client'
import 'leaflet/dist/leaflet.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import './styles.css'
import { EntryApp } from './onboarding/EntryApp'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <EntryApp />
  </React.StrictMode>,
)
