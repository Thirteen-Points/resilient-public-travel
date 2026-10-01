import type { Event, Signal } from '../api/types'
import css from './Disclosures.module.css'

const zh = '本平台为学术演示，非官方应急指引。路线、服务影响及运力可能为推算或模拟结果。出行请以官方公告为准。'
const en = 'Academic demo, not official guidance. Routes, impacts and capacity may be estimated or simulated. Follow official announcements.'

export function PageDisclosure({ seedMode }: { seedMode: boolean }) {
  return <footer className={css.page}>
    <span lang="zh-CN">{zh}</span><span lang="en">{en}</span>
    {seedMode && <span lang="en">Fixed demo samples do not describe current transport conditions.</span>}
  </footer>
}

export function CardDisclosure({ seedMode }: { seedMode: boolean }) {
  return <p className={css.card}>
    <span lang="zh-CN">学术演示，非官方指引；影响、路线及运力可能为推算或模拟，请以官方公告为准。</span>
    <span lang="en">Academic demo, not official guidance. Impacts, routes and capacity may be estimated or simulated. Follow official announcements.</span>
    {seedMode && <span lang="en">Demo sample; not current service information.</span>}
  </p>
}

function timestamp(value: string) {
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return 'Time unavailable / 时间暂不可用'
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Hong_Kong', year: 'numeric', month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).format(date) + ' HKT (UTC+08:00)'
}

function sourceUrl(value?: string | null) {
  if (!value) return null
  try {
    const url = new URL(value)
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null
  } catch { return null }
}

export function EventSources({ event, signals }: { event: Event; signals: Signal[] }) {
  const byId = new Map(signals.map(signal => [signal.signal_id, signal]))
  return <div className={css.sources}>
    <p>事件更新时间 / Event updated: {timestamp(event.updated_at)} · 事件数据等级 / Event data type: {event.provenance}</p>
    {event.signals.length ? event.signals.map(id => {
      const signal = byId.get(id)
      const validUrl = sourceUrl(signal?.raw_url)
      return signal ? <p key={id}>来源 / Source: {signal.source_name} · 信号接收时间 / Signal received: {timestamp(signal.received_at)} · 来源数据等级 / Source data type: {signal.provenance}{signal.provenance === 'simulated' ? ' · 模拟来源 / Simulated source' : ''}{signal.source_type === 'user' ? ' · 用户上报，尚未核实 / Unverified user report' : ''} · {validUrl ? <a href={validUrl} target="_blank" rel="noopener noreferrer">查看来源 / View source</a> : '未提供来源链接 / No source link provided'}</p>
        : <p key={id}>来源详情暂不可用 / Source details unavailable (signal ID: {id})</p>
    }) : <p>未提供来源详情 / No source details provided</p>}
  </div>
}
