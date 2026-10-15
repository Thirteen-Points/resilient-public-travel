/** The nine UI dimensions share one neutral prior and one normalization pass. */
export const DIMENSIONS = [
  { id: 'time', label: 'Travel time', short: 'Time', description: 'Prefer routes that get you there sooner', prior: .5, color: '#56806a' },
  { id: 'transfers', label: 'Transfers', short: 'Transfers', description: 'Prefer routes with fewer transfers', prior: .5, color: '#89966d' },
  { id: 'walking', label: 'Walking distance', short: 'Walking', description: 'Prefer routes with less walking', prior: .5, color: '#7c9b91' },
  { id: 'fare', label: 'Fare', short: 'Fare', description: 'Prefer routes that cost less', prior: .5, color: '#ae8d64' },
  { id: 'comfort', label: 'Comfort', short: 'Comfort', description: 'Prefer a calmer, more comfortable ride', prior: .5, color: '#9b8ba1' },
  { id: 'reliability', label: 'Reliability', short: 'Reliability', description: 'Prefer routes with fewer delays', prior: .5, color: '#6f919d' },
  { id: 'carbon', label: 'Carbon emissions', short: 'Low carbon', description: 'Prefer routes with lower carbon emissions', prior: .5, color: '#608b64' },
  { id: 'freshness', label: 'Live information', short: 'Live info', description: 'Prefer routes with recently updated information', prior: .5, color: '#719ba8' },
  { id: 'accessibility', label: 'Accessibility', short: 'Access', description: 'Prioritize lifts, ramps and continuous step-free access', prior: .5, color: '#a2866b' },
] as const

export type Dimension = typeof DIMENSIONS[number]['id']
export type Weights = Record<Dimension, number>
export interface Option { id: string; label: string; scores: Partial<Weights> }
export interface Question { id: Dimension; title: string; options: Option[] }
const options = (dimension: Dimension, labels: [string, string, string]): Option[] => labels.map((label, index) => ({
  id: `${dimension}-${index}`, label, scores: { [dimension]: [.95, .5, .15][index] },
}))

export const QUESTIONS: Record<Dimension, Question> = {
  time: { id: 'time', title: 'A faster route, or an easier ride?', options: options('time', ['Get there fast, even with more transfers', 'Balance time and comfort', "Take it slow, I'm not in a rush"]) },
  transfers: { id: 'transfers', title: 'How do you feel about transfers?', options: options('transfers', ['Stay direct, even if it takes longer', 'One or two transfers are fine', 'More transfers are fine if the trip is faster']) },
  walking: { id: 'walking', title: 'How much walking feels right?', options: options('walking', ['Keep walking to a minimum', 'A 5-10 minute walk is fine', "I'm happy to walk a little further"]) },
  fare: { id: 'fare', title: 'How much does the fare matter?', options: options('fare', ['Spend less, even if it takes longer', 'Balance cost and experience', 'Pay a little more for a better trip']) },
  comfort: { id: 'comfort', title: 'Is a calmer ride worth a little longer?', options: options('comfort', ['Yes, give me room to breathe', 'A little comfort is enough', 'Getting there quickly matters more']) },
  reliability: { id: 'reliability', title: 'How important is arriving on time?', options: options('reliability', ['Choose a steady route, even if slower', 'Balance speed and reliability', 'Choose the shortest estimated time']) },
  carbon: { id: 'carbon', title: 'Would you take longer for lower emissions?', options: options('carbon', ['Yes, lower emissions matter to me', 'Choose low carbon when the trip is similar', 'Focus on what I need right now']) },
  freshness: { id: 'freshness', title: 'How fresh should your travel updates be?', options: options('freshness', ['Live updates are essential', 'Recent updates are enough', 'I can check the details along the way']) },
  accessibility: { id: 'accessibility', title: 'How important is step-free access?', options: options('accessibility', ['Prioritize step-free routes', 'Helpful on some trips', 'No particular preference right now']) },
}

export const CORE: Dimension[] = ['time', 'transfers', 'walking']
export const ADDITIONAL: Dimension[] = ['fare', 'comfort', 'reliability', 'carbon', 'freshness', 'accessibility']
export const STORAGE_KEY = 'rr.preferences.v2'
export const PROFILE_KEY = 'rr.weight-profile.v2'
export const EVENTS_KEY = 'rr.preference-events.v2'
export type Phase = 'welcome' | 'question' | 'summary' | 'complete'
export interface State {
  version: 2
  phase: Phase
  queue: Dimension[]
  cursor: number
  answers: Partial<Record<Dimension, string | null>>
  revision: number
  direction: 1 | -1
  pending: boolean
}
export const initialState = (): State => ({ version: 2, phase: 'welcome', queue: [...CORE], cursor: 0, answers: {}, revision: 0, direction: 1, pending: false })
export type Action = { type: 'START' | 'BACK' | 'SKIP' | 'CONTINUE' | 'FINISH' | 'RESET' | 'NEXT' }
  | { type: 'SELECT'; option: string }
  | { type: 'ADVANCE'; revision: number }

function advance(state: State): State {
  return { ...state, pending: false, direction: 1, revision: state.revision + 1,
    ...(state.cursor < state.queue.length - 1 ? { cursor: state.cursor + 1, phase: 'question' as const } : { phase: 'summary' as const }) }
}

/** Pure transitions; delayed ADVANCE actions are invalidated by every navigation. */
export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'START': return state.phase === 'welcome' ? { ...state, phase: 'question', direction: 1, revision: state.revision + 1 } : state
    case 'SELECT': {
      const id = state.queue[state.cursor]
      if (state.phase !== 'question' || !QUESTIONS[id].options.some(option => option.id === action.option)) return state
      return { ...state, answers: { ...state.answers, [id]: action.option }, pending: true, revision: state.revision + 1, direction: 1 }
    }
    case 'ADVANCE': return state.phase === 'question' && state.pending && action.revision === state.revision ? advance(state) : state
    case 'NEXT': return state.phase === 'question' && !state.pending && state.answers[state.queue[state.cursor]] !== undefined ? advance(state) : state
    case 'SKIP': return state.phase === 'question' ? advance({ ...state, answers: { ...state.answers, [state.queue[state.cursor]]: null } }) : state
    case 'BACK': {
      if (state.phase === 'welcome') return state
      return { ...state, phase: state.phase === 'question' && state.cursor === 0 ? 'welcome' : 'question',
        cursor: state.phase === 'summary' || state.phase === 'complete' ? state.queue.length - 1 : Math.max(0, state.cursor - 1),
        direction: -1, pending: false, revision: state.revision + 1 }
    }
    case 'CONTINUE': return state.phase === 'summary' && state.queue.length === CORE.length
      ? { ...state, queue: [...CORE, ...ADDITIONAL], cursor: CORE.length, phase: 'question', pending: false, direction: 1, revision: state.revision + 1 } : state
    case 'FINISH': return state.phase === 'summary' ? { ...state, phase: 'complete', pending: false, direction: 1, revision: state.revision + 1 } : state
    case 'RESET': return { ...initialState(), revision: state.revision + 1 }
  }
}

/** Saved future answers remain available for revisiting, but do not affect earlier steps. */
export function activeAnswers(state: State): State['answers'] {
  const ids = state.phase === 'welcome' ? [] : state.phase === 'question' ? state.queue.slice(0, state.cursor + 1) : state.queue
  return Object.fromEntries(ids.filter(id => state.answers[id] !== undefined).map(id => [id, state.answers[id]]))
}

export interface Evidence { status: 'collected' | 'skipped' | 'prior'; raw: number; option: string | null; source: string }
export interface PreferenceProfile {
  version: 2
  weights: Weights
  evidence: Record<Dimension, Evidence>
  collected: number
  total: number
  answers: State['answers']
}
export function calculateProfile(state: State): PreferenceProfile {
  const answers = activeAnswers(state)
  const observations: Partial<Record<Dimension, number[]>> = {}
  for (const [id, answer] of Object.entries(answers)) {
    const option = QUESTIONS[id as Dimension].options.find(item => item.id === answer)
    for (const [dimension, score] of Object.entries(option?.scores ?? {})) {
      ;(observations[dimension as Dimension] ??= []).push(score)
    }
  }
  const raw = Object.fromEntries(DIMENSIONS.map(({ id, prior }) => {
    const values = observations[id]
    return [id, values?.length ? values.reduce((sum, score) => sum + score, 0) / values.length : prior]
  })) as Weights
  const sum = Object.values(raw).reduce((total, value) => total + value, 0)
  const weights = Object.fromEntries(DIMENSIONS.map(({ id }) => [id, raw[id] / sum])) as Weights
  const evidence = Object.fromEntries(DIMENSIONS.map(({ id }) => {
    const option = QUESTIONS[id].options.find(item => item.id === answers[id])
    const status: Evidence['status'] = observations[id]?.length ? 'collected' : answers[id] === null ? 'skipped' : 'prior'
    return [id, { status, raw: raw[id], option: option?.label ?? null,
      source: option?.label ?? (status === 'skipped' ? 'Skipped · neutral weight' : 'Not collected · neutral weight') }]
  })) as Record<Dimension, Evidence>
  return { version: 2, weights, evidence, collected: DIMENSIONS.filter(({ id }) => evidence[id].status === 'collected').length, total: DIMENSIONS.length, answers }
}

/** Largest remainder rounding guarantees that displayed integer shares sum to 100. */
export function percentages(weights: Weights): Record<Dimension, number> {
  const sum = DIMENSIONS.reduce((total, { id }) => total + Math.max(0, Number.isFinite(weights[id]) ? weights[id] : 0), 0)
  const entries = DIMENSIONS.map(({ id }) => {
    const exact = sum ? Math.max(0, Number.isFinite(weights[id]) ? weights[id] : 0) / sum * 100 : 100 / DIMENSIONS.length
    return { id, value: Math.floor(exact), remainder: exact % 1 }
  })
  const remaining = 100 - entries.reduce((total, entry) => total + entry.value, 0)
  ;[...entries].sort((a, b) => b.remainder - a.remainder).slice(0, remaining).forEach(entry => entry.value++)
  return Object.fromEntries(entries.map(entry => [entry.id, entry.value])) as Record<Dimension, number>
}

const object = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === 'object' && !Array.isArray(value)
const isDimension = (value: unknown): value is Dimension => DIMENSIONS.some(({ id }) => id === value)

/** Validate control flow as well as value types; browser storage is untrusted input. */
export function restoreState(value: string | null): State {
  try {
    const parsed: unknown = JSON.parse(value ?? 'null')
    if (!object(parsed) || parsed.version !== 2 || !['welcome', 'question', 'summary', 'complete'].includes(String(parsed.phase)) || !Array.isArray(parsed.queue) || !object(parsed.answers)) return initialState()
    const queue = parsed.queue
    const expected = queue.length === CORE.length ? CORE : [...CORE, ...ADDITIONAL]
    if (queue.length !== expected.length || !queue.every((id, index) => isDimension(id) && id === expected[index])) return initialState()
    if (typeof parsed.cursor !== 'number' || !Number.isInteger(parsed.cursor) || parsed.cursor < 0 || parsed.cursor >= queue.length) return initialState()
    const answers = parsed.answers
    if (Object.entries(answers).some(([id, answer]) => !isDimension(id) || !queue.includes(id) || !(answer === null || typeof answer === 'string' && QUESTIONS[id].options.some(option => option.id === answer)))) return initialState()
    if (parsed.phase === 'welcome' && parsed.cursor !== 0) return initialState()
    if ((parsed.phase === 'summary' || parsed.phase === 'complete') && (parsed.cursor !== queue.length - 1 || queue.some(id => answers[id] === undefined))) return initialState()
    if (parsed.phase === 'question' && queue.slice(0, parsed.cursor).some(id => answers[id] === undefined)) return initialState()
    return { version: 2, phase: parsed.phase as Phase, queue: queue as Dimension[], cursor: parsed.cursor,
      answers: { ...answers } as State['answers'], pending: false, direction: 1, revision: 0 }
  } catch { return initialState() }
}

export function readState(): State {
  try { return restoreState(localStorage.getItem(STORAGE_KEY)) } catch { return initialState() }
}

/** Returns false for private-mode/quota failures without blocking the questionnaire. */
export function persistState(state: State): boolean {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    if (state.phase === 'complete') localStorage.setItem(PROFILE_KEY, JSON.stringify(calculateProfile(state)))
    else localStorage.removeItem(PROFILE_KEY)
    return true
  } catch { return false }
}

export type PreferenceEvent = 'start' | 'answer' | 'skip' | 'back' | 'continue' | 'complete' | 'reset' | 'next' | 'dismiss' | 'export'
export function track(event: PreferenceEvent, detail: Record<string, unknown> = {}): void {
  const item = { ...detail, event, at: new Date().toISOString() }
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(EVENTS_KEY) ?? '[]')
    const previous = Array.isArray(parsed) ? parsed.filter(row => object(row) && typeof row.event === 'string' && typeof row.at === 'string') : []
    localStorage.setItem(EVENTS_KEY, JSON.stringify([...previous, item].slice(-100)))
  } catch { /* Storage is optional; state transitions remain available. */ }
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('rr:preference-event', { detail: item }))
}
