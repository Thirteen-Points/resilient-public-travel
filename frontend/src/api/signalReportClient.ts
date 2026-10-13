// POST /api/signals client for the M1 user signal intake.
// Standalone helper so the report form stays decoupled from the seed data source.

export type SignalLang = 'zh-HK' | 'en'
export type SignalReportFailureKind = 'invalid' | 'unavailable' | 'unexpected'
export type SignalReportResult =
  | { ok: true; signalId: string }
  | { ok: false; kind: SignalReportFailureKind; message: string; detail?: string }

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL
  if (typeof configured !== 'string' || !configured.trim()) return DEFAULT_API_BASE_URL
  return configured.trim().replace(/\/+$/, '')
}

// FastAPI 422 bodies carry detail as a string or a list of {msg}; surface the first messages.
function firstValidationDetail(detail: unknown): string | undefined {
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  if (!Array.isArray(detail)) return undefined
  const parts = detail
    .map(item => typeof item === 'object' && item !== null && 'msg' in item && typeof item.msg === 'string' ? item.msg : '')
    .filter(Boolean)
  return parts.length ? parts.join(' · ') : undefined
}

export async function submitSignalReport(report: { rawText: string; lang: SignalLang; authorHint?: string }): Promise<SignalReportResult> {
  const authorHint = report.authorHint?.trim().slice(0, 100)
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl()}/api/signals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ raw_text: report.rawText, lang: report.lang, ...(authorHint ? { author_hint: authorHint } : {}) }),
      signal: AbortSignal.timeout(10000),
    })
  } catch {
    return { ok: false, kind: 'unavailable', message: 'Could not reach the report service. Your text is kept on this page — check the connection and try again.' }
  }
  if (response.status === 202) {
    let signalId = ''
    try {
      const body = await response.json() as { signal_id?: unknown }
      if (typeof body.signal_id === 'string') signalId = body.signal_id.trim()
    } catch { /* non-JSON body: fall through to the missing-reference error */ }
    if (signalId) return { ok: true, signalId }
    return { ok: false, kind: 'unexpected', message: 'The service accepted the request but returned no report reference. Nothing is confirmed — please try again.' }
  }
  if (response.status === 422) {
    let detail: string | undefined
    try { detail = firstValidationDetail((await response.json() as { detail?: unknown }).detail) } catch { /* non-JSON body */ }
    return { ok: false, kind: 'invalid', message: 'The service rejected this report. Check the text length and language, then submit again.', detail }
  }
  if (response.status === 503) {
    return { ok: false, kind: 'unavailable', message: 'The report service is temporarily unavailable. Your text is kept on this page — please try again shortly.' }
  }
  return { ok: false, kind: 'unexpected', message: `The report service answered with unexpected status ${response.status}. Nothing is confirmed — please try again.` }
}
