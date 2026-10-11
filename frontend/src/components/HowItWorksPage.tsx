import { useEffect } from 'react'
import type { LiveMetaSourceStatus } from '../api/liveTransitApi'
import { formatHkt } from '../data'
import { SourceStatus } from './SourceStatus'
import type { SourcesStatus, ReplanningStatus } from '../api/runtimeStatus'
import { geometrySources } from '../map/geometry'
import css from './HowItWorksPage.module.css'

/**
 * Standalone "How it works" page, rendered inside the app's page pane with
 * the map docked as a card on the right.
 *
 * Plain migration for now. Content lives in self-contained
 * <section data-reveal> blocks so a future motion pass can animate sections
 * independently without touching the data flow. All facts arrive via props;
 * the page owns no fetching of its own.
 */
export interface HowItWorksPageProps {
  seedMode: boolean
  snapshotAt: string
  networkVersion: string
  disclaimer: string
  /** API-mode source statuses; omitted in seed mode. */
  apiSources?: Array<string | LiveMetaSourceStatus>
  sourceWarning?: string
  collectorStatus?: SourcesStatus | null
  replanningStatus?: ReplanningStatus | null
  collectorWarning?: string
  replanningWarning?: string
  sourcesReadAt?: string
  onRefresh?: () => Promise<void>
  onClose: () => void
}

export function HowItWorksPage({
  seedMode, snapshotAt, networkVersion, disclaimer, apiSources, sourceWarning, collectorStatus, replanningStatus, collectorWarning, replanningWarning, sourcesReadAt, onRefresh, onClose,
}: HowItWorksPageProps) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return <div className={css.page} data-panel>
    <span className={css.kicker}>How this demo works</span>
    <h1 className={css.title}>Clarity before <span>certainty.</span></h1>

    <section data-reveal>
      <p>Plan a journey, explore its alternatives, or send a report for human review. Only effective, approved events change the public map and route estimates. Reports do not confirm an incident by themselves.</p>
      <p>{seedMode
        ? 'Route choices are fixed Tai Wai → Admiralty seed candidates. Station-search, map selection and departure input are interface demonstrations, not live timetable, geocoding or accessibility verification.'
        : 'Route queries and Agent answers use the engine with your travel preferences. Service times, fares and capacities remain modelled estimates. A connected data source does not independently verify an incident.'}</p>
    </section>

    <section data-reveal>
      <h2>Model snapshot</h2>
      <div className={css.facts}>
        <div><strong>{seedMode ? 'Seed snapshot' : 'API generated at'}</strong>{formatHkt(snapshotAt)}</div>
        <div><strong>Network</strong>{networkVersion}</div>
        <div><strong>Map-point access</strong>Within 800 m straight-line of six East Rail stations</div>
      </div>
      <p>Map selection measures straight-line distance to the six modelled East Rail station points. A point is accepted when it is within 800 m of one of them. Blue circles show this limit. The station point may differ from a usable entrance, and actual walking distance may be longer. Map-point distances are displayed separately and are excluded from station-to-station route times and walking totals.</p>
      <p className={css.disclaimer}>{disclaimer}</p>
    </section>

    <section data-reveal>
      <h2>What changes in this demo?</h2>
      {seedMode
        ? <p>The fixed seed shows one Tai Wai → Admiralty scenario. Routes and events stay at their recorded snapshot. Changing departure does not recalculate the estimates, and the Agent uses local template replies.</p>
        : <p>Approved changes automatically update the map and recalculate your journey. Review takes place in the separate administration console. If an update fails, previous results remain visible with a retry option.</p>}
    </section>

    {!seedMode && <><SourceStatus sources={apiSources} warning={sourceWarning} status={collectorStatus} replanning={replanningStatus} statusWarning={collectorWarning} replanWarning={replanningWarning} readAt={sourcesReadAt} /><button type="button" className={css.sourceRefresh} onClick={() => void onRefresh?.()}>Refresh</button></>}

    <section data-reveal>
      <h2>Paths on the map</h2>
      <p>Railway, bus and verified walking paths follow geographic snapshots from Hong Kong's Common Spatial Data Infrastructure. They keep real bends and separate source paths. Path geometry does not establish service availability, travel time or step-free access.</p>
      <p>Connections without a verified path remain dotted and schematic, including the ferry crossing and the reverse 985B connection. Missing station coordinates are never invented. Station reference points can differ slightly from generalized railway or road paths.</p>
      <p>Contains information from the Government of the Hong Kong Special Administrative Region, made available through CSDI by the Lands Department and Transport Department. <a href="https://static.csdi.gov.hk/csdi-webpage/doc/TNC" target="_blank" rel="noreferrer">Data terms</a>.</p>
      <details><summary>Path data references</summary><ul className={css.sourceList}>{geometrySources.map(source => <li key={source.id}><a href={source.url} target="_blank" rel="noreferrer">{source.label}</a> · captured {formatHkt(source.capturedAt)}</li>)}</ul></details>
      <p>Basemap: <a href="https://openfreemap.org/" target="_blank" rel="noreferrer">OpenFreeMap</a>, © OpenMapTiles, data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>. Basemap failure retains the route overlays; it does not change their recorded geometry.</p>
    </section>

    <section data-reveal className={css.credits}>
      <h2>Colour &amp; motion credits</h2>
      <p>Options A, B and C use blue, purple and teal throughout the cards and map. Transport-line chips retain <a href="https://www.mtr.com.hk/ch/customer/services/system_map.html" target="_blank" rel="noreferrer">MTR colours</a> and operator branding. A white outline identifies the selected route; symbols and text also identify disruptions.</p>
      <p>Our route companion is an adaptation of <a href="https://github.com/jeremy-prt/bloub" target="_blank" rel="noreferrer">Bloub</a>'s clock-free bot engine (MIT): resting ball, sphere-projected eyes, deterministic blink calendar, and the measured triangle silhouette, coloured with its own palette. <a href="https://github.com/Jakubantalik/Libraries.dev/tree/main/packages/border-beam" target="_blank" rel="noreferrer">BorderBeam</a> handles the focused composer. Reduced-motion preferences are respected.</p>
    </section>
  </div>
}
