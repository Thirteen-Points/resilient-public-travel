import { useId, useRef } from 'react'
import { gsap, useGSAP, useReducedMotion } from '../lib/motion'
import styles from './PreferenceMap.module.css'

export type MapDimension = 'time' | 'transfers' | 'walking' | 'fare' | 'comfort' | 'reliability' | 'carbon' | 'freshness' | 'accessibility'

type PreferenceMapProps = {
  dimension: MapDimension
  strength: number
  revision: number
  direction: 1 | -1
  stage: 'welcome' | 'question' | 'summary' | 'complete'
}

const routes = {
  lime: 'M-28 194H114Q142 194 142 222V296Q142 324 170 324H282Q310 324 310 352V474Q310 502 338 502H464Q492 502 492 530V772',
  mint: 'M-28 542H130Q158 542 158 514V424Q158 396 186 396H306Q334 396 334 368V154Q334 126 362 126H648',
  ivory: 'M96-24V84Q96 112 124 112H212Q240 112 240 140V598Q240 626 268 626H434Q462 626 462 654V772',
  orange: 'M648 254H458Q430 254 430 282V340Q430 368 402 368H372Q344 368 344 396V592Q344 620 316 620H-28',
  secondary: 'M-28 700H100Q128 700 128 672V264Q128 236 156 236H566Q594 236 594 208V-24',
}

const stations = [
  { x: 96, y: 60, line: 'ivory' }, { x: 172, y: 112, line: 'ivory' },
  { x: 240, y: 194, line: 'ivory' }, { x: 240, y: 324, line: 'transfer' },
  { x: 240, y: 396, line: 'transfer' }, { x: 240, y: 512, line: 'ivory' },
  { x: 240, y: 620, line: 'transfer' }, { x: 382, y: 626, line: 'ivory' },
  { x: 62, y: 194, line: 'lime' }, { x: 142, y: 264, line: 'lime' },
  { x: 310, y: 396, line: 'transfer' }, { x: 310, y: 464, line: 'lime' },
  { x: 414, y: 502, line: 'lime' }, { x: 492, y: 584, line: 'lime' },
  { x: 492, y: 692, line: 'lime' }, { x: 72, y: 542, line: 'mint' },
  { x: 158, y: 468, line: 'mint' }, { x: 334, y: 216, line: 'mint' },
  { x: 428, y: 126, line: 'mint' }, { x: 546, y: 126, line: 'mint' },
  { x: 546, y: 254, line: 'orange' }, { x: 430, y: 306, line: 'orange' },
  { x: 344, y: 502, line: 'transfer' }, { x: 344, y: 562, line: 'orange' },
  { x: 82, y: 620, line: 'orange' },
]

const effectFor: Record<MapDimension, string> = {
  time: 'time', transfers: 'transfers', walking: 'walking', fare: 'fare', comfort: 'comfort',
  reliability: 'reliability', carbon: 'carbon', freshness: 'freshness', accessibility: 'accessibility',
}

export function PreferenceMap({ dimension, strength, revision, direction, stage }: PreferenceMapProps) {
  const scope = useRef<HTMLDivElement>(null)
  const reducedMotion = useReducedMotion()
  const instance = useId().replace(/:/g, '')
  const id = (name: string) => `journey-${instance}-${name}`
  const value = Math.min(1, Math.max(0, strength))

  useGSAP(() => {
    if (!scope.current) return
    const q = gsap.utils.selector(scope)
    const effect = q(`[data-map-effect="${effectFor[dimension]}"]`)
    const overview = stage === 'welcome' || stage === 'summary' || stage === 'complete'
    const timeline = gsap.timeline({ defaults: { ease: 'power2.out' } })

    gsap.set(q('[data-map-effect]'), { opacity: 0 })
    gsap.set(q('[data-map-route]'), { opacity: overview ? .92 : .55 })
    gsap.set(q('[data-map-node]'), { scale: 1, transformOrigin: '50% 50%' })

    if (reducedMotion) {
      gsap.set(overview ? q('[data-map-overview]') : effect, { opacity: .8 })
      gsap.set(q('[data-map-flow]'), { opacity: overview || dimension === 'time' ? .7 : 0 })
      return
    }

    timeline.fromTo(q('[data-map-city]'), { x: direction * 4, opacity: .7 }, { x: 0, opacity: 1, duration: .7 }, 0)
    if (overview) {
      timeline.to(q('[data-map-route]'), { opacity: 1, stagger: .07, duration: .8 }, 0)
      timeline.fromTo(q('[data-map-node]'), { scale: .75, opacity: .45 }, { scale: 1, opacity: 1, stagger: .018, duration: .6 }, .1)
      timeline.to(q('[data-map-overview]'), { opacity: stage === 'welcome' ? .65 : 1, duration: 1 }, .1)
      timeline.fromTo(q('[data-map-flow]'), { strokeDashoffset: direction * 360, opacity: 0 }, { strokeDashoffset: -direction * 360, opacity: .65, duration: 3.6, ease: 'none' }, .1)
      if (stage !== 'welcome') timeline.fromTo(q('[data-summary-ring]'), { scale: .35, opacity: .7 }, { scale: 1.7, opacity: 0, duration: 1.8, stagger: .25, transformOrigin: '50% 50%' }, .15)
      return
    }

    timeline.to(effect, { opacity: .75 + value * .25, duration: .55 }, .05)
    switch (dimension) {
      case 'time':
        timeline.fromTo(q('[data-time-ring]'), { scale: .6, opacity: .6 }, { scale: 1 + value * .4, opacity: .15, duration: 1.8, stagger: .18, transformOrigin: '50% 50%' }, .05)
        timeline.fromTo(q('[data-time-flow]'), { strokeDashoffset: direction * 500 }, { strokeDashoffset: -direction * 200, duration: 2.5 - value, ease: 'none' }, .1)
        break
      case 'transfers':
        timeline.fromTo(q('[data-transfer-node]'), { scale: .45, opacity: 0 }, { scale: 1, opacity: 1, duration: .55, stagger: direction === 1 ? .14 : -.14, transformOrigin: '50% 50%', ease: 'back.out(1.6)' }, .05)
        timeline.fromTo(q('[data-transfer-link]'), { strokeDashoffset: direction * 70, opacity: .15 }, { strokeDashoffset: 0, opacity: .9, duration: 1.1 }, .2)
        break
      case 'walking':
        timeline.fromTo(q('[data-walk-radius]'), { scale: .35, opacity: 0 }, { scale: 1 - value * .2, opacity: .8, duration: 1.2, transformOrigin: '50% 50%' }, 0)
        timeline.fromTo(q('[data-walk-path]'), { strokeDashoffset: direction * 120 }, { strokeDashoffset: 0, duration: 1.5, ease: 'none' }, .1)
        break
      case 'fare':
        timeline.fromTo(q('[data-fare-zone]'), { scale: .85, opacity: 0 }, { scale: 1, opacity: .35 + value * .3, stagger: .15, duration: 1.1, transformOrigin: '50% 50%' }, .05)
        break
      case 'comfort':
        timeline.fromTo(q('[data-comfort-wave]'), { y: direction * 10, opacity: 0 }, { y: 0, opacity: .8, duration: 1.3, stagger: .1, ease: 'sine.inOut' }, .05)
        timeline.fromTo(q('[data-comfort-dot]'), { y: 5, opacity: .15 }, { y: -5, opacity: .9, duration: 1.2, stagger: .1, yoyo: true, repeat: 1, ease: 'sine.inOut' }, .1)
        break
      case 'reliability':
        timeline.fromTo(q('[data-reliable-ring]'), { scale: .7, opacity: 0 }, { scale: 1, opacity: .9, duration: .9, stagger: .16, transformOrigin: '50% 50%' }, 0)
        timeline.fromTo(q('[data-reliable-dot]'), { opacity: .2 }, { opacity: 1, stagger: .13, duration: .4, yoyo: true, repeat: 1 }, .2)
        break
      case 'carbon':
        timeline.fromTo(q('[data-carbon-path]'), { strokeDashoffset: direction * 700 }, { strokeDashoffset: 0, duration: 1.7, ease: 'power1.inOut' }, .05)
        timeline.fromTo(q('[data-carbon-leaf]'), { scale: .25, opacity: 0 }, { scale: 1, opacity: .85, duration: .7, stagger: .17, transformOrigin: '50% 50%' }, .6)
        break
      case 'freshness':
        timeline.fromTo(q('[data-data-ring]'), { scale: .25, opacity: .9 }, { scale: 1.35, opacity: .08, duration: 1.7, stagger: .18, transformOrigin: '50% 50%' }, .05)
        timeline.fromTo(q('[data-data-dot]'), { scale: .5, opacity: .1 }, { scale: 1, opacity: 1, duration: .5, stagger: .1, transformOrigin: '50% 50%' }, .2)
        break
      case 'accessibility':
        timeline.fromTo(q('[data-access-path]'), { strokeDashoffset: direction * 600 }, { strokeDashoffset: 0, duration: 1.4 }, .05)
        timeline.fromTo(q('[data-access-node]'), { scale: .4, opacity: 0 }, { scale: 1, opacity: 1, duration: .7, stagger: .13, transformOrigin: '50% 50%', ease: 'back.out(1.5)' }, .25)
        break
    }
  }, { scope, dependencies: [dimension, value, revision, direction, stage, reducedMotion], revertOnUpdate: true })

  return (
    <div ref={scope} className={styles.map} aria-hidden="true" data-stage={stage} data-dimension={dimension}>
      <svg className={styles.canvas} viewBox="0 0 620 740" fill="none" preserveAspectRatio="xMidYMid slice">
        <defs>
          <pattern id={id('grid')} width="34" height="34" patternUnits="userSpaceOnUse"><path d="M34 0H0V34" stroke="#d6f3dc" strokeOpacity=".045" strokeWidth="1" /></pattern>
          <radialGradient id={id('light')}><stop stopColor="#5a8060" stopOpacity=".4" /><stop offset="1" stopColor="#123e3c" stopOpacity="0" /></radialGradient>
          <linearGradient id={id('river')} x1="400" y1="0" x2="620" y2="740" gradientUnits="userSpaceOnUse"><stop stopColor="#1a514c" /><stop offset="1" stopColor="#24625a" /></linearGradient>
          <linearGradient id={id('carbon')} x1="100" y1="650" x2="500" y2="100" gradientUnits="userSpaceOnUse"><stop stopColor="#82c79e" /><stop offset="1" stopColor="#e1f3ac" /></linearGradient>
        </defs>
        <rect width="620" height="740" fill="#123e3c" />
        <rect width="620" height="740" fill={`url(#${id('grid')})`} />
        <ellipse cx="240" cy="350" rx="420" ry="440" fill={`url(#${id('light')})`} />
        <g data-map-city>
          <path d="M490-20C457 67 453 129 482 197C519 285 522 343 486 427C455 500 505 583 579 606C624 620 651 665 652 760H710V-20Z" fill={`url(#${id('river')})`} />
          <path d="M492-20C460 64 464 132 490 193C525 278 531 344 494 429C463 500 514 577 583 600C629 616 658 661 660 760" stroke="#95c0a7" strokeOpacity=".12" />
          <path d="M-20 12H63V144H-20Z" fill="#1d5148" /><path d="M121 18H211V78H121Z" fill="#274e40" />
          <path d="M264 16H308V98H264Z" fill="#244e42" /><path d="M358 28H424V98H358Z" fill="#315b46" />
          <path d="M-20 220H100V304H-20Z" fill="#24564a" /><path d="M168 145H213V297H168Z" fill="#234f43" />
          <path d="M265 151H308V297H265Z" fill="#284f43" /><path d="M359 157H405V227H359Z" fill="#235449" />
          <path d="M-20 337H91V489H-20Z" fill="#1d4c43" /><path d="M8 350H78V478H8Z" stroke="#75967a" strokeOpacity=".13" />
          <path d="M174 350H211V370H174Z" fill="#3d654b" /><path d="M269 348H287V370H269Z" fill="#43694e" />
          <path d="M182 423H213V514H182Z" fill="#365f48" /><path d="M264 424H284V477H264Z" fill="#315b46" />
          <path d="M365 406H411V470H365Z" fill="#284f41" /><path d="M-20 565H116V592H-20Z" fill="#375e49" />
          <path d="M147 568H212V591H147Z" fill="#254e40" /><path d="M268 529H316V590H268Z" fill="#1c4a40" />
          <path d="M367 529H459V598H367Z" fill="#294f41" /><path d="M156 650H213V754H156Z" fill="#2d5745" />
          <path d="M263 652H431V754H263Z" fill="#1b4b42" /><path d="M287 676H405V754H287Z" stroke="#6c9575" strokeOpacity=".14" />
          <path d="M26 652H100V675H26Z" fill="#315944" />
          <path d="M358 283H405V327H358Z" fill="#345d47" />
          <path d="M176 165V275M280 174V274M42 365V467M170 664V726M301 688H390" stroke="#c5ddae" strokeOpacity=".07" strokeWidth="2" />
          <path d="M385 165V214M377 189H395M386 552V578M374 565H399" stroke="#b6cf9e" strokeOpacity=".15" strokeWidth="3" />
        </g>

        <g data-map-effect="fare" opacity="0">
          <circle data-fare-zone cx="240" cy="396" r="250" fill="#dbf198" fillOpacity=".065" stroke="#dbf198" strokeOpacity=".25" />
          <circle data-fare-zone cx="240" cy="396" r="165" fill="#dbf198" fillOpacity=".09" stroke="#dbf198" strokeOpacity=".3" />
          <circle data-fare-zone cx="240" cy="396" r="86" fill="#dbf198" fillOpacity=".14" stroke="#dbf198" strokeOpacity=".4" />
        </g>
        <path d={routes.secondary} stroke="#8bafa0" strokeOpacity=".14" strokeWidth="2" />
        <g className={styles.routes}>
          <path data-map-route d={routes.ivory} stroke="#e9eddb" strokeWidth="4" />
          <path data-map-route d={routes.orange} stroke="#dea581" strokeWidth="4" />
          <path data-map-route d={routes.mint} stroke="#83bfae" strokeWidth="4" />
          <path data-map-route d={routes.lime} stroke="#d8ef9a" strokeWidth="5" />
        </g>

        <g data-map-overview opacity="0"><path data-map-flow d={routes.lime} stroke="#f2ffd3" strokeWidth="7" strokeDasharray="55 680" strokeLinecap="round" opacity="0" /><circle data-summary-ring cx="240" cy="324" r="35" stroke="#d8ef9a" strokeWidth="1" opacity="0" /><circle data-summary-ring cx="310" cy="396" r="35" stroke="#d8ef9a" strokeWidth="1" opacity="0" /></g>
        <g data-map-effect="time" opacity="0">
          {[68, 112, 156].map(r => <circle key={r} data-time-ring cx="240" cy="324" r={r} stroke="#d8ef9a" strokeWidth="1" strokeOpacity=".65" />)}
          <path data-time-flow d={routes.lime} stroke="#f3ffd3" strokeWidth="8" strokeDasharray="80 540" strokeLinecap="round" />
        </g>
        <g data-map-effect="walking" opacity="0">
          <circle data-walk-radius cx="240" cy="396" r="94" fill="#d8ef9a" fillOpacity=".06" stroke="#d8ef9a" strokeOpacity=".45" strokeDasharray="2 8" />
          <path data-walk-path d="M240 396L205 428L205 466L178 494L136 494" stroke="#f1efd9" strokeWidth="3" strokeDasharray="2 9" strokeLinecap="round" />
          <circle cx="136" cy="494" r="5" fill="#e7edce" />
        </g>
        <g data-map-effect="transfers" opacity="0">
          <path data-transfer-link d="M240 324V396H310L344 368" stroke="#f2f5d8" strokeWidth="7" strokeDasharray="70 12" strokeLinecap="round" />
          {[[240, 324], [240, 396], [310, 396], [344, 368]].map(([x, y]) => <g data-transfer-node key={`${x}-${y}`}><circle cx={x} cy={y} r="18" fill="#123e3c" stroke="#d8ef9a" strokeWidth="1.5" /><circle cx={x} cy={y} r="7" fill="#d8ef9a" /></g>)}
        </g>
        <g data-map-effect="comfort" opacity="0">
          {[0, 1, 2].map(i => <path key={i} data-comfort-wave d={`M161 ${445 + i * 18}C191 ${426 + i * 18} 209 ${426 + i * 18} 239 ${445 + i * 18}S287 ${464 + i * 18} 317 ${445 + i * 18}`} stroke="#bde1ba" strokeOpacity={.6 - i * .12} strokeWidth="1.5" strokeLinecap="round" />)}
          {[[191, 362], [280, 552], [385, 452], [277, 267], [92, 459]].map(([x, y]) => <circle key={`${x}-${y}`} data-comfort-dot cx={x} cy={y} r="3" fill="#d8ef9a" />)}
        </g>
        <g data-map-effect="reliability" opacity="0">
          <circle data-reliable-ring cx="310" cy="396" r="56" stroke="#d8ef9a" strokeWidth="1" strokeDasharray="2 6" />
          <circle data-reliable-ring cx="310" cy="396" r="69" stroke="#d8ef9a" strokeOpacity=".35" />
          <path d="M294 396L305 407L326 383" stroke="#d8ef9a" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          {[264, 310, 356].map(x => <circle key={x} data-reliable-dot cx={x} cy="486" r="3" fill="#d8ef9a" />)}
        </g>
        <g data-map-effect="carbon" opacity="0">
          <path data-carbon-path d={routes.mint} stroke={`url(#${id('carbon')})`} strokeWidth="7" strokeDasharray="700 700" strokeLinecap="round" />
          {[[158, 468], [334, 216], [428, 126]].map(([x, y]) => <g key={`${x}-${y}`} data-carbon-leaf><circle cx={x} cy={y} r="21" fill="#214d3e" stroke="#cde8a0" strokeOpacity=".4" /><path d={`M${x - 7} ${y + 6}Q${x - 10} ${y - 9} ${x + 9} ${y - 9}Q${x + 10} ${y + 8} ${x - 7} ${y + 6}ZM${x - 7} ${y + 6}L${x + 3} ${y - 3}`} stroke="#d8ef9a" strokeWidth="1.5" /></g>)}
        </g>
        <g data-map-effect="freshness" opacity="0">
          {[32, 52, 74].map(r => <circle key={r} data-data-ring cx="334" cy="216" r={r} stroke="#b9e2cf" strokeWidth="1.5" />)}
          {[[334, 216], [334, 286], [334, 347], [310, 396], [240, 396]].map(([x, y]) => <circle key={`${x}-${y}`} data-data-dot cx={x} cy={y} r="6" fill="#d5f0bf" />)}
        </g>
        <g data-map-effect="accessibility" opacity="0">
          <path data-access-path d="M96 116H212Q232 116 232 142V598Q232 634 268 634H434" stroke="#f3efdb" strokeWidth="2" strokeDasharray="600 600" />
          {[[172, 112], [240, 324], [240, 396], [240, 512], [382, 626]].map(([x, y]) => <g key={`${x}-${y}`} data-access-node><rect x={x - 14} y={y - 14} width="28" height="28" rx="8" fill="#204b40" stroke="#d8ef9a" strokeWidth="1.5" /><path d={`M${x - 5} ${y}H${x + 5}M${x} ${y - 5}V${y + 5}`} stroke="#e4f4b4" strokeWidth="2" strokeLinecap="round" /></g>)}
        </g>

        <g className={styles.stations}>
          {stations.map(({ x, y, line }) => <g key={`${x}-${y}`} data-map-node>
            {line === 'transfer' && <circle cx={x} cy={y} r="10" fill="#123e3c" stroke="#e4ecd3" strokeWidth="2" />}
            <circle cx={x} cy={y} r={line === 'transfer' ? 4 : 5} fill="#123e3c" stroke={line === 'lime' ? '#d8ef9a' : line === 'mint' ? '#92cbb7' : line === 'orange' ? '#e2ad89' : '#e9eddb'} strokeWidth="2.5" />
          </g>)}
        </g>
        <g className={styles.origin}>
          <circle cx="240" cy="324" r="29" fill="#d8ef9a" fillOpacity=".08" />
          <circle cx="240" cy="324" r="20" fill="#d8ef9a" fillOpacity=".1" />
          <circle cx="240" cy="324" r="11" fill="#d8ef9a" />
          <circle cx="240" cy="324" r="4" fill="#234b3b" />
        </g>
        <g opacity=".5"><circle cx="555" cy="670" r="22" stroke="#b2cfb2" strokeOpacity=".3" /><path d="M555 655L561 676L555 672L549 676Z" fill="#c6debc" /></g>
        <path d="M31 37H47M39 29V45M567 39H583M575 31V47M31 703H47M39 695V711" stroke="#b5cea7" strokeOpacity=".3" strokeWidth="1" />
      </svg>
      <div className={styles.grain} />
      <div className={styles.vignette} />
    </div>
  )
}
