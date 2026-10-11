import { useEffect } from 'react'
import type { LiveMetaSourceStatus } from '../api/liveTransitApi'
import { formatHkt } from '../data'
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
  catchmentM: number
  disclaimer: string
  /** API-mode source statuses; omitted in seed mode. */
  apiSources?: Array<string | LiveMetaSourceStatus>
  onClose: () => void
}

export function HowItWorksPage({
  seedMode, snapshotAt, networkVersion, catchmentM, disclaimer, apiSources, onClose,
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
      <p>Network, event, route and simulation seeds load through a shared data-source boundary. The map displays modelled nodes, schematic links, and only effective published events. Unreviewed reports remain visible on the Updates screen but do not modify routing.</p>
      <p>{seedMode
        ? 'Route choices are fixed Tai Wai → Admiralty seed candidates. Station-search, map selection and departure input are interface demonstrations, not live timetable, geocoding or accessibility verification.'
        : 'Route queries use the backend engine. Service times, fares and capacities remain modelled estimates. The Agent conversation uses local templates.'}</p>
    </section>

    <section data-reveal>
      <h2>Model snapshot</h2>
      <div className={css.facts}>
        <div><strong>Snapshot</strong>{formatHkt(snapshotAt)}</div>
        <div><strong>Network</strong>{networkVersion}</div>
        <div><strong>Map-point access</strong>Up to {Math.min(catchmentM, 800)} m walking to East Rail</div>
      </div>
      <p>Map selection checks OpenStreetMap pedestrian routes to modelled East Rail station points. Blue map circles show straight-line search bounds, not walking coverage. A point is accepted only when a pedestrian route measures 800 m or less. The station point may differ from a usable entrance; confirm access on site. Map-point access walks are shown separately and are excluded from train route time and walking totals. If pedestrian routing is unavailable, choose a station by name.</p>
      <p className={css.disclaimer}>{disclaimer}</p>
    </section>

    <section data-reveal>
      <h2>What changes in this demo?</h2>
      {seedMode
        ? <p>Review decisions live only in this browser session. Publishing replaces the previous incident stage and updates the map overlay and Agent alert. Routes remain fixed seed estimates. The selected departure is sent as an HKT query value; there is no timetable recalculation or live Agent API.</p>
        : <p>Review decisions are saved by the event API. Published-event and graph changes trigger route recalculation. Missing services and stale data are shown explicitly.</p>}
    </section>

    {!seedMode && <section data-reveal>
      <h2>API sources</h2>
      <ul className={css.sourceList}>
        {(apiSources ?? []).map((source, index) => <li key={index}>
          {typeof source === 'string' ? source : `${source.name}${source.last_ok ? ` · last successful update ${formatHkt(source.last_ok)}` : ' · update time unavailable'}`}
        </li>)}
      </ul>
    </section>}

    <section data-reveal className={css.credits}>
      <h2>Colour &amp; motion credits</h2>
      <p>Lines follow <a href="https://www.mtr.com.hk/ch/customer/services/system_map.html" target="_blank" rel="noreferrer">MTR colours</a> and local operator branding. Joint bus services show both colours; unknown services receive a stable assigned colour. Geometry remains schematic.</p>
      <p>Our route companion is an adaptation of <a href="https://github.com/jeremy-prt/bloub" target="_blank" rel="noreferrer">Bloub</a>'s clock-free bot engine (MIT): resting ball, sphere-projected eyes, deterministic blink calendar, and the measured triangle silhouette, coloured with its own palette. <a href="https://github.com/Jakubantalik/Libraries.dev/tree/main/packages/border-beam" target="_blank" rel="noreferrer">BorderBeam</a> handles the focused composer. Reduced-motion preferences are respected.</p>
    </section>
  </div>
}
