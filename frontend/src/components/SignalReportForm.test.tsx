import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { submitSignalReport } from '../api/signalReportClient'
import { SignalReportForm } from './SignalReportForm'

afterEach(() => vi.unstubAllGlobals())

describe('public signal report source hint', () => {
  it('renders an optional input with an honest explanation and a 100 character limit', () => {
    const html = renderToStaticMarkup(<SignalReportForm />)
    expect(html).toContain('Source hint (optional)')
    expect(html).toContain('it does not verify your report')
    expect(html).toMatch(/id="signal-source-hint"[^>]*maxLength="100"/)
    expect(html).not.toMatch(/id="signal-source-hint"[^>]*required/)
  })

  it('omits an empty source hint from the request body', async () => {
    const fetcher = vi.fn(async (_url: string, _options: RequestInit) => new Response(JSON.stringify({ signal_id: 'report-one' }), { status: 202 }))
    vi.stubGlobal('fetch', fetcher)
    await submitSignalReport({ rawText: 'East Rail report', lang: 'en', authorHint: '   ' })
    const body = JSON.parse(String(fetcher.mock.calls[0][1].body))
    expect(body).toEqual({ raw_text: 'East Rail report', lang: 'en' })
  })

  it('sends a filled source hint truncated to 100 characters', async () => {
    const fetcher = vi.fn(async (_url: string, _options: RequestInit) => new Response(JSON.stringify({ signal_id: 'report-two' }), { status: 202 }))
    vi.stubGlobal('fetch', fetcher)
    await submitSignalReport({ rawText: 'East Rail report', lang: 'en', authorHint: 'a'.repeat(101) })
    const body = JSON.parse(String(fetcher.mock.calls[0][1].body))
    expect(body).toEqual({ raw_text: 'East Rail report', lang: 'en', author_hint: 'a'.repeat(100) })
  })
})
