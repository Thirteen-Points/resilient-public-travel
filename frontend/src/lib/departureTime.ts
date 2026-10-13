export const hktDeparture = (date: string, time: string) => `${date}T${time}:00+08:00`

export const nextHktMinute = (now = new Date()) => new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', hour12: false,
}).format(new Date(now.getTime() + 60_000))

export const isPastHktDeparture = (date: string, time: string, now = new Date()) =>
  !Number.isFinite(Date.parse(hktDeparture(date, time))) || Date.parse(hktDeparture(date, time)) < now.getTime()

export function advancePastHktDeparture(date: string, time: string, now = new Date()) {
  const earliest = nextHktMinute(now)
  if (!Number.isFinite(Date.parse(hktDeparture(date, time))) || `${date} ${time}` >= earliest) {
    return { date, time, moved: false }
  }
  return { date: earliest.slice(0, 10), time: earliest.slice(11, 16), moved: true }
}
