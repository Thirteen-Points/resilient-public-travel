import { useEffect, useReducer, useRef, useState, type KeyboardEvent } from 'react'
import { gsap, useGSAP } from '../lib/motion'
import { Icon } from './Icon'
import { PreferenceMap } from './PreferenceMap'
import { CORE, DIMENSIONS, PROFILE_KEY, QUESTIONS, STORAGE_KEY, calculateProfile, percentages, readState, reducer, track, type Action, type Dimension, type State } from './model'
import css from './Onboarding.module.css'

function Profile({ state }: { state: State }) {
  const profile = calculateProfile(state)
  const rounded = percentages(profile.weights)
  const ranked = [...DIMENSIONS].sort((a, b) => profile.weights[b.id] - profile.weights[a.id])
  return <div className={css.profile}>
    <div className={css.profileTop}><span>你的偏好权重</span><span>{profile.collected} / 9 维已采集</span></div>
    {ranked.map(dimension => <div className={css.weightRow} key={dimension.id}>
      <span>{dimension.label}<small>{profile.evidence[dimension.id].status === 'collected' ? profile.evidence[dimension.id].option : profile.evidence[dimension.id].status === 'skipped' ? '已跳过 · 默认先验' : '待了解 · 默认先验'}</small></span>
      <div className={css.weightTrack}><i style={{ transform: `scaleX(${profile.weights[dimension.id] / Math.max(...Object.values(profile.weights))})`, background: dimension.color }} /></div><strong>{rounded[dimension.id]}<small>%</small></strong>
    </div>)}
    <details className={css.explanation}><summary>这份画像是怎样生成的？</summary><p>每个选项映射到相应维度的重视分值（0.6、1.8 或 3.6）。未采集的核心维度采用 1，扩展维度采用 0.45 的默认先验。每次选择后，将全部九维分值除以总分，得到总和为 1 的权重；这里显示的百分比总和为 100%。</p><p>回退后，仅使用当前题及之前的答案重算；后续选项保留，继续作答后才重新计入。权重表示相对重视程度，可以随时修改。保存后，八个可评分维度用于路线推荐；无障碍偏好不会自动限制路线，请在规划页明确设置实际的通道需求。</p></details>
  </div>
}

const profileTitles: Record<Dimension, string> = { time: '效率，是你的出行关键词。', transfers: '少换乘，让旅程更轻松。', walking: '少走一点，轻松多一点。', fare: '精打细算，也能从容出发。', comfort: '舒服的旅程，值得多一点时间。', reliability: '安心抵达，比什么都重要。', carbon: '你的旅程，自带一抹绿色。', freshness: '及时的信息，让你更有把握。', accessibility: '友好的连接，让旅程更顺畅。' }

export function Onboarding() {
  const [state, dispatch] = useReducer(reducer, undefined, readState)
  const [storageWarning, setStorageWarning] = useState(false)
  const content = useRef<HTMLDivElement>(null)
  const title = useRef<HTMLHeadingElement>(null)
  const profile = calculateProfile(state)
  const question = QUESTIONS[state.queue[state.cursor]]
  const answer = state.answers[question.id]
  const ranked = [...DIMENSIONS].sort((a, b) => profile.weights[b.id] - profile.weights[a.id])
  const balanced = profile.weights[ranked[0].id] - profile.weights[ranked[1].id] < .035
  const summaryTitle = profile.collected === 0 ? '从均衡出发，慢慢了解你。' : balanced ? '兼顾多一点，旅程刚刚好。' : profileTitles[ranked[0].id]

  function send(action: Action) {
    const events: Record<string, string> = { START: 'start', SELECT: 'answer', SKIP: 'skip', BACK: 'back', CONTINUE: 'continue', FINISH: 'complete', OPEN: 'open_question', RESET: 'restart' }
    if (events[action.type]) track(events[action.type], { dimension: question.id, ...(action.type === 'SELECT' ? { option: action.option } : {}), ...(action.type === 'OPEN' ? { dimension: action.dimension } : {}), ...(action.type === 'FINISH' ? { weights: profile.weights, collected: profile.collected } : {}) })
    dispatch(action)
  }

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...state, pending: false }))
      localStorage.setItem(PROFILE_KEY, JSON.stringify({ ...calculateProfile(state), completed: state.phase === 'complete', updatedAt: new Date().toISOString() }))
      setStorageWarning(false)
    } catch { setStorageWarning(true) }
  }, [state])

  useEffect(() => {
    if (!state.pending || state.phase !== 'question') return
    const timer = window.setTimeout(() => dispatch({ type: 'ADVANCE', revision: state.revision }), 750)
    return () => window.clearTimeout(timer)
  }, [state.pending, state.revision, state.phase])

  useEffect(() => {
    if (state.phase !== 'welcome') title.current?.focus({ preventScroll: true })
  }, [state.phase, state.cursor])

  useGSAP(() => {
    const media = gsap.matchMedia()
    media.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.fromTo('[data-content]', { y: state.direction * 12, opacity: 0 }, { y: 0, opacity: 1, duration: .55, ease: 'power3.out' })
      gsap.fromTo('[data-stagger]', { y: state.direction * 8, opacity: 0 }, { y: 0, opacity: 1, duration: .5, stagger: .06, delay: .05, ease: 'power3.out' })
    })
    return () => media.revert()
  }, { scope: content, dependencies: [state.phase, state.cursor], revertOnUpdate: true })

  function optionKeys(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (!['ArrowDown', 'ArrowUp', 'ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? question.options.length - 1 : (index + (event.key === 'ArrowUp' || event.key === 'ArrowLeft' ? -1 : 1) + question.options.length) % question.options.length
    content.current?.querySelector<HTMLButtonElement>(`[data-option="${next}"]`)?.focus()
  }
  function download() {
    const blob = new Blob([JSON.stringify({ ...profile, completed: state.phase === 'complete', exportedAt: new Date().toISOString() }, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'resilientroute-preferences.json'; anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    track('export_profile')
  }
  const step = state.phase === 'welcome' ? 0 : state.phase === 'question' && state.cursor < 3 ? 1 : 2
  const liveText = state.phase === 'question' ? `${state.cursor < 3 ? `核心第 ${state.cursor + 1} 题，共 3 题` : '补充偏好'}：${question.title}${state.pending ? ` 已选择${question.options.find(option => option.id === answer)?.label}，即将进入下一步。` : ''} 当前已采集 ${profile.collected} 个维度。` : state.phase === 'summary' ? `初步画像已生成，已采集 ${profile.collected} 个维度。` : state.phase === 'complete' ? '出行偏好画像已完成。' : state.phase === 'library' ? '选择想继续了解的偏好维度。' : '欢迎使用 ResilientRoute 出行偏好引导。'

  return <div className={css.shell} onKeyDown={event => { if (event.key === 'Escape' && state.phase === 'question') { event.preventDefault(); send({ type: 'BACK' }) } }}>
    <a className={css.skipLink} href="#preference-content">跳到引导内容</a>
    <header className={css.header}>
      <a className={css.brand} href="?view=preferences" aria-label="ResilientRoute 出行偏好首页">rr<span>.</span></a>
      <nav aria-label="主导航"><a href="?view=planner">出行规划</a><a href="?view=preferences" aria-current="page">我的偏好</a></nav>
      <span className={css.headerBadge}><i /> 为你而行</span>
    </header>
    <main className={css.main}>
      <section className={css.left} id="preference-content" tabIndex={-1} aria-label="出行偏好引导">
        <div className={css.breadcrumb}><span>RESILIENT ROUTE</span><span>/</span><span>认识你的旅程</span></div>
        <ol className={css.steps} aria-label="引导进度">{['初次见面', '偏好探索', '专属画像'].map((label, index) => <li key={label} aria-current={step === index ? 'step' : undefined} className={index <= step ? css.activeStep : ''}><span>{index < step ? <Icon name="check" size={12} /> : `0${index + 1}`}</span>{label}{index < 2 && <i />}</li>)}</ol>
        <div ref={content} className={css.content}>
          {state.phase === 'welcome' && <div data-content className={css.welcome}>
            <span className={css.eyebrow}><i /> 很高兴，与你同行</span>
            <h1 ref={title} tabIndex={-1}>每段旅程，<br /><span>都更懂你。</span></h1>
            <p className={css.lead}>好的路线，不只有一个标准。<br />用几个简单的选择，找到属于你的出行节奏。</p>
            <div className={css.welcomeFacts}><span><Icon name="time" size={16} />约 30 秒</span><span><Icon name="transfers" size={16} />3 个小问题</span><span><Icon name="check" size={16} />随时可修改</span></div>
            <button className={css.primary} onClick={() => send({ type: 'START' })}>开始认识我的偏好<Icon name="arrow" size={19} /></button>
            <p className={css.startNote}>没有标准答案，跟随你的第一感觉就好。</p>
            <div className={css.welcomeDimensions}><span>我们会慢慢了解</span><div>{DIMENSIONS.slice(0,6).map(dimension => <span key={dimension.id}><Icon name={dimension.id} size={15} />{dimension.short}</span>)}</div></div>
          </div>}
          {state.phase === 'question' && <div data-content className={css.question}>
            <div className={css.questionMeta}><span><Icon name={question.id} size={16} />{DIMENSIONS.find(d => d.id === question.id)?.label}</span><span>{state.cursor < 3 ? `0${state.cursor + 1} / 03` : '补充偏好'}</span></div>
            <div className={css.progressTrack} role="progressbar" aria-label="核心问卷进度" aria-valuemin={0} aria-valuemax={3} aria-valuenow={Math.min(state.cursor,3)}><i style={{ transform: `scaleX(${Math.min(state.cursor,3) / 3})` }} /></div>
            <span className={css.questionTag}>{question.tag}</span><h1 ref={title} tabIndex={-1} id="question-title">{question.title}</h1><p className={css.questionDescription} id="question-description">{question.description}</p>
            <div className={css.options} role="radiogroup" aria-labelledby="question-title" aria-describedby="question-description">
              {question.options.map((option,index) => <button data-stagger data-option={index} key={option.id} className={`${css.option} ${answer === option.id ? css.selected : ''}`} role="radio" aria-checked={answer === option.id} onKeyDown={event => optionKeys(event,index)} onClick={() => send({ type: 'SELECT', option: option.id })}><span className={css.optionNumber}>0{index+1}</span><span><strong>{option.label}</strong><small>{option.description}</small></span><i className={css.radio}>{answer === option.id && <Icon name="check" size={12} />}</i></button>)}
            </div>
            <div className={css.questionHint}>{state.pending ? <><i className={css.savingDot} />已记录，正走向下一步…</> : answer === null ? '上次跳过了这题，可补充或继续。' : answer !== undefined ? '上次的选择已保留，可修改或继续。' : '选择后自动进入下一题 · 方向键浏览，Enter 选择'}</div>
            <div className={css.questionActions}><button onClick={() => send({ type: 'BACK' })}><Icon name="back" size={16} />上一题</button>{answer !== undefined && !state.pending && <button onClick={() => dispatch({ type: 'ADVANCE', revision: state.revision })}>保留并继续<Icon name="arrow" size={16} /></button>}<button onClick={() => send({ type: 'SKIP' })}>暂时跳过<Icon name="arrow" size={16} /></button></div>
            {state.cursor >= 3 && <button className={css.libraryBack} onClick={() => send({ type: 'CONTINUE' })}>返回题库，稍后继续</button>}
          </div>}
          {(state.phase === 'summary' || state.phase === 'complete') && <div data-content className={css.summary}>
            <span className={css.eyebrow}><Icon name="check" size={16} />{state.phase === 'complete' ? '你的偏好，已准备就绪' : '初步画像，已经成形'}</span>
            <h1 ref={title} tabIndex={-1}>{summaryTitle}</h1><p className={css.summaryLead}>{profile.collected === 0 ? '你可以先使用默认画像，或继续回答几个问题。' : `已了解你的 ${profile.collected} 个偏好维度，其余保留默认先验。`}<br />这份画像会随着你的选择，变得更贴近你。</p>
            <Profile state={state} />
            <div className={css.summaryActions}>{state.phase === 'complete' ? <a className={css.primary} href="?view=planner">开始规划我的旅程<Icon name="arrow" size={18} /></a> : <button className={css.primary} onClick={() => send({ type: 'FINISH' })}>完成，保存我的偏好<Icon name="check" size={18} /></button>}<button className={css.secondary} onClick={() => send({ type: 'CONTINUE' })}>继续完善<Icon name="arrow" size={18} /></button></div>
            <div className={css.summaryLinks}><button onClick={() => send({ type: 'BACK' })}><Icon name="back" size={14} />回看答案</button><button onClick={download}><Icon name="download" size={14} />导出画像</button></div>
          </div>}
          {state.phase === 'library' && <div data-content className={css.library}>
            <span className={css.eyebrow}>再了解你，多一点</span><h1 ref={title} tabIndex={-1}>好的旅程，<br /><span>也藏在细节里。</span></h1><p className={css.summaryLead}>选择你在意的方面，按自己的节奏继续。<br />已采集 {profile.collected} / 9 维 · 每个问题只需一个选择。</p>
            <div className={css.libraryLabel}>更多出行考量 <span>选答</span></div>
            <div className={css.libraryGrid}>{DIMENSIONS.filter(dimension => !CORE.includes(dimension.id)).map(dimension => <button data-stagger key={dimension.id} onClick={() => send({ type: 'OPEN', dimension: dimension.id })}><Icon name={dimension.id} size={21} /><span><strong>{dimension.label}</strong><small>{profile.evidence[dimension.id].status === 'collected' ? '已了解 · 可以修改' : profile.evidence[dimension.id].status === 'skipped' ? '已跳过 · 可以补充' : dimension.description}</small></span><Icon name={profile.evidence[dimension.id].status === 'collected' ? 'check' : 'arrow'} size={15} /></button>)}</div>
            <div className={css.libraryLabel}>回看核心偏好</div><div className={css.coreReview}>{CORE.map(id => <button key={id} onClick={() => send({ type: 'OPEN', dimension: id })}><Icon name={id} size={14} />{DIMENSIONS.find(d => d.id === id)?.short}<span>{profile.evidence[id].status === 'collected' ? '已了解' : '待补充'}</span></button>)}</div>
            <button className={css.primary} onClick={() => send({ type: 'FINISH' })}>完成，保存我的偏好<Icon name="check" size={18} /></button><button className={css.libraryBack} onClick={() => send({ type: 'BACK' })}>返回上一题</button>
          </div>}
        </div>
        <div className={css.privacy}><Icon name="shield" size={15} /><span>{storageWarning ? '当前浏览器无法保存进度，可在完成后导出画像。' : '偏好保存在此浏览器，仅用于了解你的出行选择。'}</span></div>
      </section>
      <PreferenceMap state={state} />
    </main>
    <footer className={css.footer}><span>RESILIENT ROUTE <i>·</i> 让每一段旅程，更有把握。</span><span>你的节奏，你的路线。</span></footer>
    <div className={css.srOnly} role="status" aria-live="polite" aria-atomic="true">{liveText}</div>
  </div>
}
