import { useEffect, useRef, useState } from 'react'
import { BorderBeam } from 'border-beam'
import type { Event, Preset } from '../api/types'
import { seedDataSource } from '../api/seedDataSource'
import { formatRange } from '../data'
import { useReducedMotion, useSuccessMotion } from '../lib/motion'
import { AgentAvatar } from './AgentAvatar'
import css from './Experience.module.css'

type Message = { role: 'you' | 'agent'; text: string; preference?: Preset }
export function AgentPanel({ published, departAt, onRoutes, onBack }: { published: Event[]; departAt: string; onRoutes: (preference: Preset) => void; onBack: () => void }) {
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
