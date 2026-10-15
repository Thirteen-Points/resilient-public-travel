export const DIMENSIONS = [
  { id: 'time', label: '出行时间', short: '时间', description: '优先选择更快到达的方案', prior: 1, color: '#60876c' },
  { id: 'transfers', label: '换乘次数', short: '换乘', description: '优先选择换乘更少的方案', prior: 1, color: '#8c9c70' },
  { id: 'walking', label: '步行距离', short: '步行', description: '优先选择步行更短的方案', prior: 1, color: '#839a92' },
  { id: 'fare', label: '出行票价', short: '票价', description: '优先选择花费更低的方案', prior: 1, color: '#b69c78' },
  { id: 'comfort', label: '乘坐舒适', short: '舒适', description: '更重视座位、空间与乘坐体验', prior: 1, color: '#988ba1' },
  { id: 'reliability', label: '到达可靠性', short: '可靠', description: '更重视稳定到达与较少延误', prior: 1, color: '#7291a0' },
  { id: 'carbon', label: '碳排放', short: '低碳', description: '优先选择碳排放更低的方案', prior: .45, color: '#598268' },
  { id: 'freshness', label: '信息新鲜度', short: '实时', description: '更重视及时更新的出行信息', prior: .45, color: '#7c9eaa' },
  { id: 'accessibility', label: '无障碍友好', short: '无障碍', description: '更重视电梯、坡道与无障碍通道', prior: .45, color: '#a0876e' },
] as const
export type Dimension = typeof DIMENSIONS[number]['id']
export type Weights = Record<Dimension, number>
type Option = { id: string; label: string; description: string; scores: Partial<Weights> }
type Question = { id: Dimension; tag: string; title: string; description: string; options: Option[]; feedback: string[] }
const options = (dimension: Dimension, labels: [string, string][], scores = [3.6, 1.8, .6]): Option[] => labels.map(([label, description], index) => ({ id: `${dimension}-${index}`, label, description, scores: { [dimension]: scores[index] } }))
export const QUESTIONS: Record<Dimension, Question> = {
  time: { id: 'time', tag: '每一分钟，都有意义', title: '快一点，还是从容一点？', description: '如果两条路线都能到达目的地，你更倾向于哪一种？', options: options('time', [['尽快到达', '愿意多换乘一次，节省约 10 分钟'], ['找一个平衡', '时间与路上的体验，同样重要'], ['慢一点也没关系', '宁愿多花些时间，享受从容的旅程']]), feedback: ['流光加速，让每一分钟更有价值', '线路以平稳节奏前进', '放慢节奏，留一点时间给沿途'] },
  transfers: { id: 'transfers', tag: '少一点切换，多一点轻松', title: '关于换乘，你怎么想？', description: '直达稍慢，换乘更快。哪种旅程更适合你？', options: options('transfers', [['直达更省心', '多花约 10 分钟，也尽量避免换乘'], ['一两次可以接受', '只要衔接顺畅，换乘不是问题'], ['快就好，不介意换乘', '愿意切换线路，换取更短的总时间']]), feedback: ['连接直达线路，减少途中的切换', '保留清晰、顺畅的换乘连接', '多条线路相连，探索更多可能'] },
  reliability: { id: 'reliability', tag: '让每一次抵达，都更安心', title: '准时这件事，有多重要？', description: '一条路线很快却偶有延误，另一条稍慢但更稳定。', options: options('reliability', [['稳稳到达最重要', '愿意多花约 8 分钟，减少延误风险'], ['速度与稳定兼顾', '接受小幅波动，但不想频繁延误'], ['更在意预计时间', '偶尔延误可以接受，优先选更快的']]), feedback: ['稳定的脉冲，描绘更可预期的旅程', '轻微波动，仍然保持从容', '延迟波纹浮现，保留更快的选择'] },
  walking: { id: 'walking', tag: '从出发到抵达，每一步都算数', title: '走多远，你觉得刚刚好？', description: '步行是旅程的一部分，也可以是需要减少的负担。', options: options('walking', [['尽量少走路', '优先选车站更近、步行更短的路线'], ['步行 5–10 分钟可以', '一小段步行，可以换来更好的路线'], ['愿意多走一段', '步行 15 分钟左右也可以接受']]), feedback: ['收拢步行半径，让目的地更近', '延展一小段步行动线', '步行半径展开，连接更多街区'] },
  fare: { id: 'fare', tag: '让预算，走在舒服的范围内', title: '票价会影响你的选择吗？', description: '同样一段旅程，你愿意为更好的体验多付一些吗？', options: options('fare', [['更经济，优先考虑', '愿意多花些时间，节省约 HK$5'], ['预算与体验平衡', '合理价差内，综合比较路线'], ['体验好，价差可接受', '更快或更舒服，可以多付约 HK$5']]), feedback: ['温暖色阶聚合，突出经济路线', '柔和的色阶，平衡预算与体验', '色彩渐变展开，保留更多选择'] },
  comfort: { id: 'comfort', tag: '路上的感受，也值得被照顾', title: '你希望旅途有多舒适？', description: '拥挤程度、座位与乘坐感受，会改变你的选择吗？', options: options('comfort', [['舒服一点很重要', '愿意稍晚到达，换取更宽松的空间'], ['适度舒适就好', '可以短暂站立，尽量避开过度拥挤'], ['能到达就好', '短程拥挤或站立，不太影响选择']]), feedback: ['线路柔化，拥挤粒子渐渐散开', '空间与效率，找到合适的节奏', '粒子轻轻聚合，保留高效连接'] },
  carbon: { id: 'carbon', tag: '每一小步，都可以更绿色', title: '低碳出行，对你重要吗？', description: '如果低碳路线多花约 10 分钟，你会怎样选择？', options: options('carbon', [['愿意为低碳多走一步', '较低的排放，是选择路线的重要因素'], ['条件合适就选低碳', '时间与票价相近时，优先绿色路线'], ['优先满足当下需要', '先考虑时间、预算与旅途体验']]), feedback: ['绿色路径生长，连接更轻盈的旅程', '绿色粒子沿着线路轻轻前进', '低碳路径保留，等待合适的旅程'] },
  freshness: { id: 'freshness', tag: '新一点的信息，多一点把握', title: '你多在意信息的及时性？', description: '路线信息更新得越及时，越能反映当下的出行情况。', options: options('freshness', [['实时更新很重要', '优先考虑信息刚刚更新的路线'], ['定期更新就可以', '近期信息足够，不必每一刻刷新'], ['参考信息也可以', '愿意结合站内公告，自行确认']]), feedback: ['数据脉冲亮起，信息节点依次刷新', '光晕缓缓更新，保持信息连接', '保留信息节点，按需查看更新'] },
  accessibility: { id: 'accessibility', tag: '让旅程，对每个人都友好', title: '无障碍通道，对你重要吗？', description: '电梯、坡道与少台阶路线，是否是你关注的出行条件？', options: options('accessibility', [['非常重要', '更重视电梯、坡道与连续无障碍通道'], ['有时需要', '带行李或同行者需要时，会优先考虑'], ['目前没有特别偏好', '通常可以使用楼梯与一般通道']]), feedback: ['电梯节点浮现，点亮友好的连接', '坡道连接点亮，为需要时做好准备', '通道节点保留，让选择更完整'] },
}
// Cover efficiency, journey effort and uncertainty with three distinct core dimensions.
export const CORE: Dimension[] = ['time', 'transfers', 'reliability']
export const STORAGE_KEY = 'rr.preferences.v1'
export const PROFILE_KEY = 'rr.weight-profile.v1'
export const EVENTS_KEY = 'rr.preference-events.v1'
export type Phase = 'welcome' | 'question' | 'summary' | 'library' | 'complete'
export type State = { version: 1; phase: Phase; queue: Dimension[]; cursor: number; answers: Partial<Record<Dimension, string | null>>; revision: number; direction: 1 | -1; pending: boolean }
export const initialState = (): State => ({ version: 1, phase: 'welcome', queue: [...CORE], cursor: 0, answers: {}, revision: 0, direction: 1, pending: false })
export type Action = { type: 'START' | 'BACK' | 'SKIP' | 'CONTINUE' | 'FINISH' | 'RESET' } | { type: 'SELECT'; option: string } | { type: 'ADVANCE'; revision: number } | { type: 'OPEN'; dimension: Dimension }
function advance(state: State): State {
  return { ...state, pending: false, direction: 1, revision: state.revision + 1, ...(state.cursor < state.queue.length - 1 ? { cursor: state.cursor + 1, phase: 'question' as const } : { phase: state.cursor < 3 ? 'summary' as const : 'library' as const }) }
}
export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'START': return { ...state, phase: 'question', direction: 1, revision: state.revision + 1 }
    case 'SELECT': {
      const id = state.queue[state.cursor]
      if (state.phase !== 'question' || !QUESTIONS[id].options.some(option => option.id === action.option)) return state
      return { ...state, answers: { ...state.answers, [id]: action.option }, pending: true, revision: state.revision + 1, direction: 1 }
    }
    case 'ADVANCE': return state.phase === 'question' && action.revision === state.revision ? advance(state) : state
    case 'SKIP': return state.phase === 'question' ? advance({ ...state, answers: { ...state.answers, [state.queue[state.cursor]]: null } }) : state
    case 'BACK': {
      if (state.phase === 'welcome') return state
      if (state.phase === 'question') return { ...state, phase: state.cursor === 0 ? 'welcome' : 'question', cursor: Math.max(0, state.cursor - 1), direction: -1, pending: false, revision: state.revision + 1 }
      return { ...state, phase: 'question', cursor: state.queue.length - 1, direction: -1, pending: false, revision: state.revision + 1 }
    }
    case 'CONTINUE': return { ...state, phase: 'library', pending: false, direction: 1, revision: state.revision + 1 }
    case 'OPEN': {
      if (!DIMENSIONS.some(dimension => dimension.id === action.dimension)) return state
      const previous = state.queue.indexOf(action.dimension)
      return { ...state, queue: previous < 0 ? [...state.queue, action.dimension] : state.queue, cursor: previous < 0 ? state.queue.length : previous, phase: 'question', pending: false, direction: 1, revision: state.revision + 1 }
    }
    case 'FINISH': return { ...state, phase: 'complete', pending: false, revision: state.revision + 1 }
    case 'RESET': return initialState()
  }
}
export function activeAnswers(state: State): State['answers'] {
  const ids = state.phase === 'welcome' ? [] : state.phase === 'question' ? state.queue.slice(0, state.cursor + 1) : state.queue
  return Object.fromEntries(ids.filter(id => state.answers[id] !== undefined).map(id => [id, state.answers[id]]))
}
export function calculateProfile(state: State) {
  const answers = activeAnswers(state)
  const observations: Partial<Record<Dimension, number[]>> = {}
  Object.entries(answers).forEach(([id, answer]) => {
    const option = QUESTIONS[id as Dimension].options.find(item => item.id === answer)
    Object.entries(option?.scores ?? {}).forEach(([dimension, score]) => (observations[dimension as Dimension] ??= []).push(score))
  })
  const raw = Object.fromEntries(DIMENSIONS.map(dimension => {
    const evidence = observations[dimension.id]
    return [dimension.id, evidence?.length ? evidence.reduce((a, b) => a + b, 0) / evidence.length : dimension.prior]
  })) as Weights
  const sum = Object.values(raw).reduce((a, b) => a + b, 0)
  const weights = Object.fromEntries(DIMENSIONS.map(dimension => [dimension.id, raw[dimension.id] / sum])) as Weights
  const evidence = Object.fromEntries(DIMENSIONS.map(dimension => [dimension.id, {
    status: observations[dimension.id]?.length ? 'collected' : answers[dimension.id] === null ? 'skipped' : 'prior',
    raw: raw[dimension.id], option: QUESTIONS[dimension.id].options.find(option => option.id === answers[dimension.id])?.label ?? null,
  }])) as Record<Dimension, { status: 'collected' | 'skipped' | 'prior'; raw: number; option: string | null }>
  const collected = DIMENSIONS.filter(dimension => evidence[dimension.id].status === 'collected').length
  return { version: 1 as const, weights, evidence, collected, total: DIMENSIONS.length, answers }
}
// Largest remainder rounding keeps the displayed percentages at exactly 100%.
export function percentages(weights: Weights): Record<Dimension, number> {
  const entries = DIMENSIONS.map(({ id }) => ({ id, value: Math.floor(weights[id] * 100), remainder: weights[id] * 100 % 1 }))
  const remaining = 100 - entries.reduce((sum, entry) => sum + entry.value, 0)
  ;[...entries].sort((a, b) => b.remainder - a.remainder).slice(0, remaining).forEach(entry => entry.value++)
  return Object.fromEntries(entries.map(entry => [entry.id, entry.value])) as Record<Dimension, number>
}
export function restoreState(value: string | null): State {
  try {
    const parsed = JSON.parse(value ?? 'null') as State | null
    if (!parsed || parsed.version !== 1 || !['welcome', 'question', 'summary', 'library', 'complete'].includes(parsed.phase) || !Array.isArray(parsed.queue) || !parsed.answers || typeof parsed.answers !== 'object') return initialState()
    if (parsed.queue.length < 3 || parsed.queue.length > 9 || new Set(parsed.queue).size !== parsed.queue.length || !CORE.every((id, index) => parsed.queue[index] === id) || !parsed.queue.every(id => DIMENSIONS.some(dimension => dimension.id === id))) return initialState()
    if (!Number.isInteger(parsed.cursor) || parsed.cursor < 0 || parsed.cursor >= parsed.queue.length) return initialState()
    const answers = Object.fromEntries(Object.entries(parsed.answers).filter(([id, answer]) => parsed.queue.includes(id as Dimension) && (answer === null || QUESTIONS[id as Dimension]?.options.some(option => option.id === answer))))
    return { version: 1, phase: parsed.phase, queue: parsed.queue, cursor: parsed.cursor, answers, pending: false, direction: 1, revision: 0 }
  } catch { return initialState() }
}
export function readState(): State {
  try { return restoreState(localStorage.getItem(STORAGE_KEY)) } catch { return initialState() }
}
export function track(event: string, detail: Record<string, unknown> = {}) {
  const item = { event, at: new Date().toISOString(), ...detail }
  try {
    const previous = JSON.parse(localStorage.getItem(EVENTS_KEY) ?? '[]')
    localStorage.setItem(EVENTS_KEY, JSON.stringify([...(Array.isArray(previous) ? previous : []), item].slice(-100)))
  } catch { /* Interaction remains available when browser storage is restricted. */ }
  window.dispatchEvent(new CustomEvent('rr:preference-event', { detail: item }))
}
