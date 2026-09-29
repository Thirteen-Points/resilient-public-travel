import { useRef, useState } from 'react'
import css from './Experience.module.css'

// Known holidays in the demo corridor's September/October 2026 window.
// gov.hk/en/about/abouthk/holiday/2026.htm; not a complete holiday calendar.
const holidays: Record<string, string> = { '2026-09-26': 'Day following Mid-Autumn Festival', '2026-10-01': 'National Day', '2026-10-19': 'Day following Chung Yeung Festival' }
const isoDate = (date: Date) => date.toISOString().slice(0, 10)
export const hktDeparture = (date: string, time: string) => `${date}T${time}:00+08:00`

export function DeparturePicker({ date, time, onDate, onTime }: { date: string; time: string; onDate: (value: string) => void; onTime: (value: string) => void }) {
  const [open, setOpen] = useState(false)
  const [month, setMonth] = useState(date.slice(0, 7))
  const calendar = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const first = new Date(`${month}-01T00:00:00Z`)
  const count = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate()
  const minutes = Number(time.slice(0, 2)) * 60 + Number(time.slice(3))
  const setMinutes = (value: number) => onTime(`${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`)
  const shiftMonth = (delta: number) => setMonth(isoDate(new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + delta, 1))).slice(0, 7))
  return <section className={css.departure} aria-label="Departure in Hong Kong time">
    <div className={css.eyebrow}>LEAVE AT <span>HONG KONG · UTC+8</span></div>
    <div className={css.dateTime}><button ref={trigger} type="button" aria-expanded={open} aria-controls="departure-calendar" onClick={() => { setMonth(date.slice(0, 7)); setOpen(!open) }}><span>▦</span> {new Intl.DateTimeFormat('en-HK', { day: 'numeric', month: 'short', weekday: 'short', timeZone: 'UTC' }).format(new Date(`${date}T00:00:00Z`))}<span>{open ? '−' : '+'}</span></button><input type="time" aria-label="Departure time HKT" required value={time} onChange={e => { if (e.target.value) onTime(e.target.value) }} /></div>
    {open && <div id="departure-calendar" ref={calendar} className={css.calendar} onKeyDown={e => {
      if (e.key === 'Escape') { setOpen(false); trigger.current?.focus() }
      const delta: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }
      const target = e.target as HTMLButtonElement
      if (delta[e.key] && target.dataset.date) {
        e.preventDefault()
        const next = new Date(`${target.dataset.date}T00:00:00Z`); next.setUTCDate(next.getUTCDate() + delta[e.key])
        const value = isoDate(next); setMonth(value.slice(0, 7)); onDate(value)
        requestAnimationFrame(() => calendar.current?.querySelector<HTMLButtonElement>(`[data-date="${value}"]`)?.focus())
      }
    }}>
      <header><button type="button" aria-label="Previous month" onClick={() => shiftMonth(-1)}>←</button><strong>{first.toLocaleDateString('en-HK', { month: 'long', year: 'numeric', timeZone: 'UTC' })}</strong><button type="button" aria-label="Next month" onClick={() => shiftMonth(1)}>→</button></header>
      <div className={css.days}>{['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map(day => <span key={day}>{day}</span>)}{Array.from({ length: first.getUTCDay() }, (_, i) => <span key={`blank${i}`} />)}{Array.from({ length: count }, (_, i) => {
        const value = `${month}-${String(i + 1).padStart(2, '0')}`
        const day = (i + first.getUTCDay()) % 7
        return <button type="button" key={value} data-date={value} aria-pressed={date === value} className={day === 0 || day === 6 ? css.weekend : ''} title={holidays[value]} aria-label={`${value}${holidays[value] ? ` · ${holidays[value]}` : ''}`} onClick={() => { onDate(value); setOpen(false); trigger.current?.focus() }}>{i + 1}{holidays[value] && <i />}</button>
      })}</div>
      <p>Muted days: weekends · ● Known HK holiday<br />Holiday markers cover Sep–Oct 2026 only.</p>
    </div>}
    {holidays[date] && <p className={css.holiday}>● {holidays[date]}</p>}
    <div className={css.timeRail}><input type="range" min="0" max="1435" step="5" value={minutes} aria-label="Departure time slider" aria-valuetext={`${time} Hong Kong time`} onChange={e => setMinutes(Number(e.target.value))} /><div><span>00</span><span>06</span><span>12</span><span>18</span><span>24</span></div></div>
    <div className={css.quickTimes}>{[['08:20', 'Morning'], ['12:30', 'Midday'], ['18:30', 'Evening']].map(([value, label]) => <button key={value} type="button" aria-pressed={time === value} onClick={() => onTime(value)}>{label}<small>{value}</small></button>)}</div>
    <p className={css.micro}>Shaded bands: indicative weekday peaks, 07–10 / 17–20. Time selection is sent in HKT; seed routes remain the 22 Sep 08:20 snapshot.</p>
  </section>
}
