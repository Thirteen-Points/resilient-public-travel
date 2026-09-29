import type { Network, NetworkLine } from '../api/types'

// Presentation metadata only; shared seed contracts stay unchanged.
// MTR system-map palette; bus brands: KMB red and Citybus yellow.
const mtr: Record<string, string> = {
  ERL: '#5EB6E4', TML: '#9A3820', KTL: '#00AB4E', TWL: '#ED1D24',
  ISL: '#007DC5', TCL: '#F7943E', AEL: '#00888A', TKL: '#7D499D',
  SIL: '#B5BD00', DRL: '#F173AC',
}
const operators: Record<string, string[]> = {
  BUS_182: ['KMB', 'CTB'], BUS_982X: ['KMB', 'CTB'], BUS_985B: ['KMB', 'CTB'],
  BUS_81C: ['KMB'], GMB_481B: ['AMS'], FERRY_TST_CEN: ['STAR_FERRY'],
}
const brands: Record<string, string> = { KMB: '#D71920', CTB: '#F5C400', AMS: '#168353', STAR_FERRY: '#287857' }
const fallback = ['#7254A8', '#B15B2A', '#007F86', '#BA4680', '#506CBB', '#647A27']
export function resolveLine(network: Network, id = '') {
  return network.lines.find(line => [id, `BUS_${id}`, `GMB_${id}`, `FERRY_${id}`].includes(line.id))
}
export function lineStyle(line?: NetworkLine, identity = 'unknown') {
  const id = line?.id ?? identity
  if (line?.mode === 'MTR' && mtr[id]) return { colors: [mtr[id]], label: line.name_en, fallback: false }
  const names = line?.operator ? (Array.isArray(line.operator) ? line.operator : line.operator.split(/[+/,]/)).map(s => s.trim().toUpperCase()) : operators[id] ?? []
  const colors = names.map(name => brands[name]).filter(Boolean)
  if (colors.length) return { colors, label: `${line?.name_en ?? id} · ${names.join(' + ')}`, fallback: false }
  const hash = Array.from(id).reduce((n, char) => (n * 31 + char.charCodeAt(0)) >>> 0, 0)
  return { colors: [fallback[hash % fallback.length]], label: `${line?.name_en ?? id} · assigned colour`, fallback: true }
}
export function lineGradient(colors: string[]) {
  return `linear-gradient(135deg, ${colors.map((color, i) => `${color} ${i * 100 / colors.length}% ${(i + 1) * 100 / colors.length}%`).join(', ')})`
}
