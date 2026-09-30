import { afterEach, describe, expect, it, vi } from 'vitest'
import { getEvents, getPublishedEvents, reviewEvent } from '../eventApi'
import { getReviewToken, setReviewToken } from '../reviewerSession'
import { seedDataSource } from '../seedDataSource'

afterEach(() => { setReviewToken(''); vi.unstubAllGlobals() })
describe('public and reviewer access boundaries', () => {
  it('reads public events at the selected time without attaching a reviewer credential', async () => {
    setReviewToken('temporary-test-value')
    const fetcher = vi.fn(async (_url: string, _options: { headers: Record<string, string>; body: string }) => new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetcher)
    await getPublishedEvents('2026-09-30T18:30:00+08:00')
    expect(fetcher.mock.calls[0][0]).toContain('at=2026-09-30T18%3A30%3A00%2B08%3A00')
    expect(fetcher.mock.calls[0][0]).not.toContain('temporary-test-value')
    expect(fetcher.mock.calls[0][1].headers).not.toHaveProperty('x-review-token')
  })
  it('does not make protected requests without a connected reviewer', async () => {
    const fetcher = vi.fn()
    vi.stubGlobal('fetch', fetcher)
    await expect(getEvents()).rejects.toThrow('Connect a reviewer session')
    expect(fetcher).not.toHaveBeenCalled()
  })
  it('sends edits under the backend contract using only a header credential', async () => {
    setReviewToken('temporary-test-value')
    const event = (await seedDataSource.getEvents()).events[0]
    const fetcher = vi.fn(async (_url: string, _options: { headers: Record<string, string>; body: string }) => new Response(JSON.stringify(event), { status: 200 }))
    vi.stubGlobal('fetch', fetcher)
    await reviewEvent(event, 'edit')
    const [url, options] = fetcher.mock.calls[0]
    const body = JSON.parse(options.body)
    expect(url).not.toContain('temporary-test-value')
    expect(options.headers['x-review-token']).toBe('temporary-test-value')
    expect(body.action).toBe('edit')
    expect(body.edits.title).toBe(event.title)
    expect(body).not.toHaveProperty('changes')
    expect(body).not.toHaveProperty('reason')
    setReviewToken('')
    expect(getReviewToken()).toBe('')
  })
})
