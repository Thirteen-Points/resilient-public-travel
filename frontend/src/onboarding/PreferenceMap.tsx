import { useRef, type CSSProperties } from 'react'
import { gsap, useGSAP } from '../lib/motion'
import { DIMENSIONS, QUESTIONS, type Dimension, type State, calculateProfile, percentages } from './model'
import { Icon } from './Icon'
import css from './Onboarding.module.css'

const green = 'M80 388H174Q196 388 196 366V291Q196 267 220 267H331Q355 267 355 243V150Q355 128 378 128H505'
const orange = 'M128 105V193Q128 216 151 216H237Q261 216 261 240V365Q261 389 286 389H448Q474 389 474 415V464'
const blue = 'M67 302H109Q130 302 147 319L185 357Q199 371 219 371H310Q333 371 349 355L414 290Q431 273 455 273H521'
const nodes = [[80,388],[143,388],[196,328],[220,267],[288,267],[355,213],[378,128],[442,128],[505,128],[128,105],[128,162],[171,216],[237,216],[261,316],[307,389],[382,389],[448,389],[474,464],[67,302],[109,302],[219,371],[310,371],[414,290],[478,273],[521,273]]
const descriptions: Record<Dimension, string> = { time: '时间流光', transfers: '换乘连接', walking: '步行半径', fare: '预算色阶', comfort: '舒适空间', reliability: '稳定脉冲', carbon: '低碳路径', freshness: '信息光晕', accessibility: '友好通道' }

export function PreferenceMap({ state }: { state: State }) {
  const scope = useRef<HTMLDivElement>(null)
  const profile = calculateProfile(state)
  const weights = percentages(profile.weights)
  const ranked = [...DIMENSIONS].sort((a, b) => profile.weights[b.id] - profile.weights[a.id])
  const dimension = state.phase === 'question' ? state.queue[state.cursor] : ranked[0].id
  const question = QUESTIONS[dimension]
  const answer = question.options.findIndex(option => option.id === profile.answers[dimension])
  const intensity = answer < 0 ? 1 : 3 - answer
  const isWelcome = state.phase === 'welcome'
  useGSAP(() => {
    const media = gsap.matchMedia()
    media.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.fromTo('[data-map-feedback]', { y: state.direction * 8, opacity: .35 }, { y: 0, opacity: 1, duration: .6, ease: 'power3.out' })
      const path = scope.current?.querySelector<SVGPathElement>('[data-flow]')
      if (path) gsap.fromTo(path, { strokeDashoffset: state.direction === -1 ? -70 : 70 }, { strokeDashoffset: 0, duration: dimension === 'time' ? 2.8 / intensity : 4.5, repeat: -1, ease: 'none' })
      if (dimension === 'transfers') gsap.fromTo('[data-transfer]', { scale: .8, opacity: .35, transformOrigin: 'center', transformBox: 'fill-box' }, { scale: 1, opacity: 1, duration: .65, stagger: .1, ease: 'back.out(1.5)' })
      if (['walking', 'time', 'reliability', 'freshness'].includes(dimension)) gsap.fromTo('[data-ring]', { scale: .55, opacity: .7, transformOrigin: 'center', transformBox: 'fill-box' }, { scale: 1.35, opacity: 0, duration: dimension === 'reliability' && intensity === 3 ? 2.4 : 3, repeat: -1, stagger: .65, ease: 'power1.out' })
      if (dimension === 'carbon') gsap.fromTo('[data-carbon]', { strokeDashoffset: 900 }, { strokeDashoffset: 0, duration: .8, ease: 'power2.out' })
      if (dimension === 'comfort') gsap.fromTo('[data-particle]', { x: 0, opacity: .65 }, { x: intensity * 4, opacity: .25, duration: 1.8, yoyo: true, repeat: -1, stagger: .14, ease: 'sine.inOut' })
      if (dimension === 'accessibility') gsap.fromTo('[data-access]', { y: 8, opacity: 0 }, { y: 0, opacity: 1, duration: .6, stagger: .12, ease: 'power3.out' })
    })
    return () => media.revert()
  }, { scope, dependencies: [dimension, answer, state.direction, state.phase], revertOnUpdate: true })

  return <aside className={css.mapPanel} aria-label="根据出行偏好变化的抽象地铁地图">
    <div ref={scope} className={css.mapScene} data-dimension={dimension} style={{ '--map-intensity': intensity } as CSSProperties}>
      <div className={css.mapTop}><span><i /> YOUR JOURNEY, REIMAGINED</span><span>偏好实时映射</span></div>
      <div className={css.mapHeading}><h2>选择不同，<br /><span>路线也不同。</span></h2><p>让城市的脉络，慢慢贴近你的节奏。</p></div>
      <svg className={css.topology} viewBox="0 0 600 550" role="img" aria-labelledby="map-title map-description">
        <title id="map-title">个性化出行拓扑示意图</title><desc id="map-description">抽象街区与三条地铁线路。当前展示{descriptions[dimension]}反馈；此图为偏好示意，不代表真实路线。</desc>
        <defs><pattern id="map-grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="#cbd6cb" strokeWidth=".65" /></pattern><linearGradient id="fare-gradient"><stop stopColor="#b49470" /><stop offset="1" stopColor="#7c997e" /></linearGradient></defs>
        <rect x="35" y="55" width="530" height="450" fill="url(#map-grid)" opacity=".32" />
        <g className={css.blocks}>
          <path d="M54 69h147v112H54Z" fill="#dce3d2" /><path d="M217 69h104v164H217Z" fill="#e9e6da" /><path d="M337 69h209v152H337Z" fill="#d8e0d4" />
          <path d="M54 197h150v113H54Z" fill="#e6e4d8" /><path d="M217 250h103v94H217Z" fill="#d4dfd3" /><path d="M335 236h211v110H335Z" fill="#e5e3d5" />
          <path d="M54 330h145v153H54Z" fill="#d9e1d7" /><path d="M215 357h127v126H215Z" fill="#e6e2d5" /><path d="M358 363h188v120H358Z" fill="#d9e1d2" />
        </g>
        <path d="M-5 455Q105 460 208 430T390 436T610 418" fill="none" stroke="#c9d9d8" strokeWidth="36" opacity=".85" /><path d="M-5 455Q105 460 208 430T390 436T610 418" fill="none" stroke="#eaf0e9" strokeWidth="1.5" strokeDasharray="4 9" />
        <g fill="#667768" fontSize="10" fontFamily="inherit" letterSpacing="2"><text x="68" y="89">北区 NORTH</text><text x="395" y="199">花园区 GARDENS</text><text x="232" y="334">中心区 CENTRAL</text><text x="72" y="480">西岸 WEST</text><text x="389" y="481">海湾区 BAY</text></g>
        <g fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d={orange} stroke="#b79972" strokeWidth="6" opacity={dimension === 'transfers' && intensity === 3 ? .35 : .72} className={css.route} />
          <path d={blue} stroke="#8c9da1" strokeWidth="5" opacity=".58" />
          <path d={green} stroke="#557a61" strokeWidth={dimension === 'comfort' ? 9 : 7} className={css.route} />
          {dimension === 'fare' && <path d={green} stroke="url(#fare-gradient)" strokeWidth="9" className={css.priceRoute} />}
          {dimension === 'carbon' && <path data-carbon d={green} stroke="#4e7958" strokeWidth="10" strokeDasharray="900" />}
          <path data-flow d={green} stroke="#e5efbc" strokeWidth="3" strokeDasharray="9 61" />
          <path d="M505 128h28v47" stroke="#779a78" strokeWidth="2" strokeDasharray="3 5" opacity={dimension === 'walking' ? 1 : .35} />
          {dimension === 'walking' && <path d={`M533 175v${intensity === 3 ? 12 : intensity === 2 ? 38 : 72}`} stroke="#60876c" strokeWidth="2" strokeDasharray="3 5" />}
        </g>
        <g fill="#eef1e8" stroke="#7b8e7d" strokeWidth="2">{nodes.map(([x,y], i) => <circle key={i} cx={x} cy={y} r={i === 0 || i === 8 ? 6 : 3.5} />)}</g>
        <g data-transfer fill="#edf0e6" stroke="#5c7460" strokeWidth="2.2"><circle cx="196" cy="371" r="7" /><circle cx="261" cy="267" r="7" /><circle cx="435" cy="389" r="7" /></g>
        <circle cx="80" cy="388" r="12" fill="#557a61" /><circle cx="80" cy="388" r="4" fill="#f4f5df" /><circle cx="505" cy="128" r="10" fill="#557a61" /><circle cx="505" cy="128" r="4" fill="#f4f5df" />
        <g fill="#354e3a" fontSize="11" fontFamily="inherit"><text x="61" y="416">出发地</text><text x="486" y="108">目的地</text></g>
        {['time', 'walking', 'reliability', 'freshness'].includes(dimension) && <g fill="none" stroke="#739673" strokeWidth="1.5"><circle data-ring cx={dimension === 'walking' ? 533 : 261} cy={dimension === 'walking' ? 175 : 267} r={dimension === 'walking' ? 16 + (4 - intensity) * 14 : 24} /><circle data-ring cx={dimension === 'walking' ? 533 : 261} cy={dimension === 'walking' ? 175 : 267} r={dimension === 'walking' ? 16 + (4 - intensity) * 14 : 24} /></g>}
        {dimension === 'comfort' && <g fill="#728972">{[0,1,2,3,4,5,6].map(i => <circle key={i} data-particle cx={227 + i * 15} cy={250 + (i % 2) * 33} r="2" />)}</g>}
        {dimension === 'carbon' && <g fill="#5d855e"><circle cx="174" cy="388" r="9" /><path d="M170 390q0-9 8-9-1 9-8 9Z" fill="#e4edcf" /></g>}
        {dimension === 'accessibility' && <g>{[[196,371],[261,267],[505,128]].map(([x,y],i) => <g data-access key={i} transform={`translate(${x-11} ${y-35})`}><rect width="22" height="24" rx="6" fill="#f9faf2" stroke="#708372" /><path d="m6 9 3-3 3 3m-3-3v12m4-3 3 3 3-3" fill="none" stroke="#52735b" strokeWidth="1.5" /></g>)}</g>}
        {dimension === 'freshness' && <g fill="#6c9290">{[0,1,2].map(i => <circle data-ring key={i} cx={220 + i * 67} cy="267" r="9" />)}</g>}
      </svg>
      <div className={css.mapFeedback} data-map-feedback><span className={css.feedbackIcon}><Icon name={isWelcome ? 'carbon' : dimension} size={19} /></span><div><span>{isWelcome ? '为你，重新连接城市' : descriptions[dimension]}</span><p>{isWelcome ? '你的每个选择，都会让路线更贴近你。' : answer >= 0 ? question.feedback[answer] : profile.answers[dimension] === null ? '已跳过，暂以默认先验描绘路线。' : '选一个答案，看看线路如何回应。'}</p></div><i /></div>
      <div className={css.mapLegend}><span><i style={{ background: '#557a61' }} />偏好路线</span><span><i style={{ background: '#b79972' }} />可选连接</span><span><i style={{ background: '#8c9da1' }} />城市脉络</span><small>抽象示意 · 非真实路线</small></div>
    </div>
    <div className={css.mapNotes}><div><span>01 / 动态回应</span><p>每个选择，都有回响。</p></div><div><span>02 / 为你而行</span><p>{isWelcome ? '一份属于你的出行画像。' : `${ranked[0].short} ${weights[ranked[0].id]}% · 偏好正在成形。`}</p></div></div>
  </aside>
}
