/** The nine UI dimensions share one neutral prior and one normalization pass. */
export const DIMENSIONS = [
  { id: 'time', label: '出行时间', short: '时间', description: '优先选择更快到达的路线', prior: .5, color: '#56806a' },
  { id: 'transfers', label: '换乘次数', short: '换乘', description: '优先选择换乘更少的路线', prior: .5, color: '#89966d' },
  { id: 'walking', label: '步行距离', short: '步行', description: '优先选择步行更短的路线', prior: .5, color: '#7c9b91' },
  { id: 'fare', label: '出行票价', short: '票价', description: '优先选择花费更低的路线', prior: .5, color: '#ae8d64' },
  { id: 'comfort', label: '乘坐舒适', short: '舒适', description: '优先选择更舒适的路线', prior: .5, color: '#9b8ba1' },
  { id: 'reliability', label: '到达可靠性', short: '可靠', description: '优先选择延误更少的路线', prior: .5, color: '#6f919d' },
  { id: 'carbon', label: '碳排放', short: '低碳', description: '优先选择排放更低的路线', prior: .5, color: '#608b64' },
  { id: 'freshness', label: '信息新鲜度', short: '实时', description: '优先选择信息更新更及时的路线', prior: .5, color: '#719ba8' },
  { id: 'accessibility', label: '无障碍友好', short: '无障碍', description: '更重视电梯、坡道与连续无障碍通道', prior: .5, color: '#a2866b' },
] as const

export type Dimension = typeof DIMENSIONS[number]['id']
export type Weights = Record<Dimension, number>
export interface Option { id: string; label: string; scores: Partial<Weights> }
export interface Question { id: Dimension; title: string; options: Option[] }
const options = (dimension: Dimension, labels: [string, string, string]): Option[] => labels.map((label, index) => ({
  id: `${dimension}-${index}`, label, scores: { [dimension]: [.95, .5, .15][index] },
}))

export const QUESTIONS: Record<Dimension, Question> = {
  time: { id: 'time', title: '快一点，还是从容一点？', options: options('time', ['尽快到达，多换乘也可以', '时间与体验，同样重要', '慢一点也没关系']) },
  transfers: { id: 'transfers', title: '关于换乘，你怎么想？', options: options('transfers', ['尽量直达，稍慢也值得', '一两次换乘，可以接受', '只要更快，多换几次也可以']) },
  walking: { id: 'walking', title: '走多远，你觉得刚刚好？', options: options('walking', ['尽量少走路', '步行 5–10 分钟可以', '愿意多走一段']) },
  fare: { id: 'fare', title: '票价会影响你的选择吗？', options: options('fare', ['更经济，慢一点也值得', '预算与体验平衡', '体验更好，价差可以接受']) },
  comfort: { id: 'comfort', title: '舒适一点，值得多花时间吗？', options: options('comfort', ['值得，尽量避开拥挤', '适度舒适就好', '更在意尽快到达']) },
  reliability: { id: 'reliability', title: '准时抵达，对你有多重要？', options: options('reliability', ['稳定最重要，稍慢也可以', '速度与稳定兼顾', '更在意预计时间']) },
  carbon: { id: 'carbon', title: '你愿意为低碳多花一点时间吗？', options: options('carbon', ['愿意，低碳很重要', '条件相近时，优先低碳', '优先满足当下需要']) },
  freshness: { id: 'freshness', title: '你多在意信息的及时性？', options: options('freshness', ['实时更新很重要', '近期更新就可以', '愿意自行确认信息']) },
  accessibility: { id: 'accessibility', title: '无障碍通道，对你重要吗？', options: options('accessibility', ['非常重要，优先无障碍通道', '有时需要', '目前没有特别偏好']) },
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
      source: option?.label ?? (status === 'skipped' ? '已跳过 · 中性权重' : '未采集 · 中性权重') }]
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
