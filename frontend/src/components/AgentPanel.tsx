import { useEffect, useRef, useState } from 'react'
import { BorderBeam } from 'border-beam'
import type { Event, JourneyContext, Preset } from '../api/types'
import { chat, type ChatReply } from '../api/p3Api'
import { contextKey, LatestRequest } from '../api/p3Context'
import { LiveApiError } from '../api/liveTransitApi'
import { formatHktTime } from '../lib/formatters'
import { BackendRoute } from './BackendRoute'
import { seedDataSource } from '../api/seedDataSource'
import { formatRange } from '../data'
import { useReducedMotion, useSuccessMotion } from '../lib/motion'
import { AgentAvatar } from './AgentAvatar'
import css from './Experience.module.css'

type Message = { role: 'you' | 'agent'; text: string; preference?: Preset }
export function AgentPanel({ published, context, seedMode, active, onRoutes, onBack }: { published: Event[]; context: JourneyContext; seedMode: boolean; active: boolean; onRoutes: (preference: Preset) => void; onBack: () => void }) {
  return seedMode ? <SeedAgentPanel published={published} departAt={context.departAt} onRoutes={onRoutes} onBack={onBack} /> : <LiveAgentPanel context={context} active={active} published={published} onBack={onBack} />
}

function LiveAgentPanel({ context, active, published, onBack }: { context: JourneyContext; active: boolean; published: Event[]; onBack: () => void }) {
  const [input, setInput] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState(''), [retryText, setRetryText] = useState('')
  const [messages, setMessages] = useState<Array<{ question: string; context: JourneyContext; reply: ChatReply }>>([])
  const latest = useRef(new LatestRequest()), busyRef = useRef(false)
  const key = contextKey(context)
  useEffect(() => { latest.current.cancel(); busyRef.current = false; setBusy(false); return () => latest.current.cancel() }, [key, active])
  const send = async (text = input) => {
    if (busyRef.current || !text.trim()) return
    busyRef.current = true
    const request = latest.current.begin(), frozen = structuredClone(context), question = text.trim()
    setBusy(true); setError(''); setRetryText(question); setInput('')
    try {
      const reply = await chat(frozen, question, request.signal)
      if (request.current()) setMessages(items => [...items, { question, context: frozen, reply }])
    } catch (cause) {
      if (request.current()) setError(cause instanceof LiveApiError ? `${cause.code ?? `HTTP ${cause.status}`}: ${cause.message}${cause.fallback ? ` Backend fallback instruction: ${cause.fallback}` : ''}` : cause instanceof Error ? cause.message : String(cause))
    } finally { if (request.current()) { busyRef.current = false; setBusy(false) } }
  }
  return <section className={css.agentPanel} data-panel aria-labelledby="agent-heading">
    <button type="button" className={css.textButton} onClick={onBack}>← Station planner</button>
    <div className={css.agentHeading}><AgentAvatar issue={published.length > 0} loading={busy} /><div><span className={css.eyebrow}>API JOURNEY COMPANION</span><h1 id="agent-heading">Guidance with evidence.</h1></div></div>
    <p className={css.micro}>Current journey: {context.origin} → {context.destination || 'choose a destination'} · {formatHktTime(context.departAt)} · {context.persona} · {context.preset.replaceAll('_', ' ')}</p>
    <p className={css.issueStatus}>Personalized chat pending B/C. The current endpoint accepts OD/time and uses standard mobility / fastest defaults; it does not apply profile ids or free-text preference changes. Other selections are blocked. Event conditions are current backend facts, not a pinned snapshot.</p>
    <p className={css.micro}>Answers, routes and numbers come from /api/ai/chat. Backend fallback means deterministic tools; an API failure never loads seed data.</p>
    {!messages.length && <div className={css.promptList}>{['Show the routes for my current journey', 'Explain the returned route estimates', 'What are the limitations of this journey?'].map(prompt => <button key={prompt} type="button" disabled={busy} onClick={() => void send(prompt)}>{prompt}<span>↗</span></button>)}</div>}
    <div className={css.conversation} role="log" aria-label="Agent conversation" aria-live="polite" aria-busy={busy}>{messages.map((item, index) => <div key={index}>
      <div className={css.userMessage}><span className={css.eyebrow}>YOU</span><p>{item.question}</p></div>
      <div className={css.agentMessage}><span className={css.eyebrow}>{item.reply.fallback ? 'BACKEND FALLBACK · DETERMINISTIC' : 'BACKEND ANSWER'}</span><p>{item.reply.message}</p>
        <p className={css.micro}>{item.context.origin} → {item.context.destination} · {formatHktTime(item.context.departAt)} · approved revisions at request: {item.context.eventRevisions || 'none'}</p>
        {contextKey(item.context) !== key && <p className={css.issueStatus}>Previous context — this answer may be stale. Ask again for the current journey.</p>}
        {item.reply.tool_calls.filter(call => !call.ok).map((call, i) => <p key={i} className={css.error}>Tool failure: {call.trace?.tool ?? 'backend tool'} · {call.error ?? 'unavailable'} {call.detail ?? ''}</p>)}
        {item.reply.routes.map(route => <BackendRoute key={route.route_id} route={route} />)}
        {!item.reply.routes.length && <p>No route candidates supplied by the backend. None have been added.</p>}
        <details><summary>Backend tool sources</summary>{item.reply.tool_calls.map((call, i) => <p key={i}>{call.trace?.tool ?? 'tool name not supplied'} · {call.trace?.provenance ?? 'provenance not supplied'} · source age {call.trace?.freshness_s === undefined ? 'not supplied' : `${call.trace.freshness_s}s`} · {call.ok ? 'returned' : 'failed'}</p>)}</details>
      </div></div>)}</div>
    {busy && <p role="status">Waiting for backend answer… <button type="button" className={css.textButton} onClick={() => { latest.current.cancel(); busyRef.current = false; setBusy(false); setError('CANCELLED: Request cancelled. Previous answers retained.') }}>Cancel reply</button></p>}
    {error && <div role="alert" className={css.error}><p>{error}</p><button type="button" className={css.textButton} disabled={busy} onClick={() => void send(retryText)}>Retry with current context</button></div>}
    <form onSubmit={event => { event.preventDefault(); void send() }}><label htmlFor="agent-prompt" className={css.eyebrow}>ASK ABOUT THE CURRENT JOURNEY</label><div className={css.composer}><textarea id="agent-prompt" value={input} maxLength={1200} onChange={event => setInput(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send() } }} /><button type="submit" disabled={busy || !input.trim()} aria-label="Send message">↑</button></div></form>
    <p className={css.micro}>Enter to send · Shift+Enter for a new line. Source: backend chat/tools · departure and source age above. Academic demonstration; follow official travel advice.</p>
  </section>
}

function SeedAgentPanel({ published, departAt, onRoutes, onBack }: { published: Event[]; departAt: string; onRoutes: (preference: Preset) => void; onBack: () => void }) {
  const [state, setState] = useState<'idle' | 'loading' | 'answer'>('idle')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [focused, setFocused] = useState(false)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const busy = useRef(false)
  const alive = useRef(true)
  const reply = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()
  useSuccessMotion(reply, revision)
  useEffect(() => { alive.current = true; return () => { alive.current = false; clearTimeout(timer.current) } }, [])
  useEffect(() => { if (revision) reply.current?.scrollIntoView({ block: 'nearest', behavior: reduced ? 'instant' : 'smooth' }) }, [revision, reduced])
  const send = (text = input, simulateError = false) => {
    if (busy.current || !text.trim()) return
    busy.current = true; setState('loading'); setError(''); setInput('')
    setMessages(items => [...items, { role: 'you', text: text.trim() }])
    timer.current = setTimeout(async () => {
      try {
        if (simulateError) throw new Error('Simulated reply failure')
        const preference: Preset = /walking|walk|步行|少走/i.test(text) ? 'least_walking' : /stable|reliab|稳定|穩定/i.test(text) ? 'most_stable' : 'fastest'
        const asksRoute = /route|tai wai|admiralty|journey|walk|stable|路线|路線|大圍|金鐘|少走/i.test(text)
        let answer: Message
        if (asksRoute) {
          const routes = await seedDataSource.getRoutes({ origin: 'TAW', destination: 'ADM', departAt, preset: preference })
          const route = routes[0]
          answer = route ? { role: 'agent', preference, text: `For the modelled Tai Wai → Admiralty journey, the ${preference.replaceAll('_', ' ')} seed candidate is ${formatRange(route.total.time_range_s)}, with ${route.total.walk_m} m walking and ${route.total.transfers} transfer(s). ${route.explain}\n${route.warnings.join(' ')}\nSource: routes.seed.json · fixed 22 Sep 2026, 08:20 HKT snapshot. Your chosen departure does not recalculate this estimate.` } : { role: 'agent', text: 'There is no usable route in this seed. Try the station planner.' }
        } else if (/issue|happen|disrupt|update|service|中断|中斷|情况|情況|延误|延誤/i.test(text)) {
          answer = { role: 'agent', text: published.length ? `The active published demo record says: ${published.map(event => `${event.title}. ${event.summary} Confidence ${Math.round(event.confidence * 100)}%.`).join('\n')}\nSource: reviewed event.seed.json scenario, effective at the demo snapshot. This is simulated, not a live service bulletin.` : 'No active published disruption exists in the current demo state. Pending reports are excluded. This does not confirm normal real-world service; check official announcements.' }
        } else {
          answer = { role: 'agent', text: 'I can demonstrate the published disruption summary or compare the fixed Tai Wai → Admiralty route candidates. Try “What is the service update?” or “Tai Wai to Admiralty with less walking”. Other journeys and open-ended AI answers are not connected.' }
        }
        if (!alive.current) return
        setMessages(items => [...items, answer]); setState('answer'); setRevision(n => n + 1)
      } catch {
        if (alive.current) { setState('idle'); setError('The demo reply could not be prepared. Your transport alert status has not changed. Please try again.') }
      } finally { busy.current = false }
    }, reduced ? 250 : 950)
  }
  return <section className={css.agentPanel} data-panel aria-labelledby="agent-heading">
    <button type="button" className={css.textButton} onClick={onBack}>← Station planner</button>
    <div className={css.agentHeading}><AgentAvatar issue={published.length > 0} loading={state === 'loading'} /><div><span className={css.eyebrow}>YOUR JOURNEY COMPANION</span><h1 id="agent-heading">A little guidance.<br />A clearer way.</h1></div></div>
    <div className={published.length ? css.issueStatus : css.calmStatus}>{published.length ? '▲ Published disruption in this scenario' : '● No active published disruption'}</div>
    <p className={css.micro}>Seed conversation · template replies · no live AI. Traffic status is evaluated at the demo snapshot.</p>
    {!messages.length && <div className={css.promptList} data-enter>{['What is the service update?', 'Tai Wai to Admiralty, less walking', 'Show the most stable route'].map(prompt => <button key={prompt} type="button" onClick={() => send(prompt)}>{prompt}<span>↗</span></button>)}</div>}
    <div className={css.conversation} role="log" aria-label="Agent conversation" aria-live="polite" aria-busy={state === 'loading'}>{messages.map((message, i) => <div key={i} ref={i === messages.length - 1 && message.role === 'agent' ? reply : undefined} className={message.role === 'you' ? css.userMessage : css.agentMessage}><span className={css.eyebrow}>{message.role === 'you' ? 'YOU' : 'RR AGENT · SEED'}</span><p>{message.text}</p>{message.preference && <button type="button" className={css.textButton} onClick={() => onRoutes(message.preference!)}>Inspect these seed routes →</button>}</div>)}</div>
    {state === 'loading' && <p role="status" className={css.loadingLabel}>Preparing a seed reply<span aria-hidden="true"> · · ·</span></p>}
    {error && <p role="alert" className={css.error}>{error}</p>}
    <form onSubmit={e => { e.preventDefault(); send() }}>
      <label htmlFor="agent-prompt" className={css.eyebrow}>ASK ABOUT YOUR JOURNEY</label>
      <BorderBeam size="sm" colorVariant="forest" staticColors theme="light" strength={.24} glowSize={.5} brightness={.8} duration={5} active={focused && !reduced} borderRadius={18} style={{ width: '100%' }}>
        <div className={css.composer}><textarea id="agent-prompt" placeholder="Tell me where you’re heading…" maxLength={1200} value={input} onChange={e => setInput(e.target.value)} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send() } }} /><button type="submit" disabled={state === 'loading' || !input.trim()} aria-label="Send message">↑</button></div>
      </BorderBeam>
    </form>
    <p className={css.micro}>Enter to send · Shift+Enter for a new line. Academic demonstration; follow official travel advice.</p>
    <details className={css.demoControls}><summary>Demo controls</summary><button type="button" disabled={state === 'loading'} onClick={() => send('Demonstrate a reply error', true)}>Simulate reply error</button></details>
  </section>
}
