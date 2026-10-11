import { describe, expect, it, vi } from 'vitest'
import { NetworkRevisionCache } from './networkRevisionCache'
import type { Network } from './types'

const network = { nodes: [], lines: [{ id: 'TD_1051_1', mode: 'BUS', route_number: '182' }] } as unknown as Network

describe('network polling on the expanded bus graph', () => {
  it('keeps the loaded bus graph without downloading it on unchanged polls', async () => {
    const load = vi.fn().mockResolvedValue(network)
    const cache = new NetworkRevisionCache(load)
    for (let poll = 0; poll < 10; poll++) expect(await cache.get('g_1')).toBe(network)
    expect(load).toHaveBeenCalledTimes(1)
  })

  it('loads new geometry when the graph revision changes', async () => {
    const updated = { ...network, nodes: [{ id: 'TD_STOP_859' }] } as unknown as Network
    const load = vi.fn().mockResolvedValueOnce(network).mockResolvedValueOnce(updated)
    const cache = new NetworkRevisionCache(load)
    await cache.get('g_1')
    expect(await cache.get('g_2')).toBe(updated)
    expect(await cache.get('g_2')).toBe(updated)
    expect(load).toHaveBeenCalledTimes(2)
  })

  it('keeps the last revision and retries a failed new graph download', async () => {
    const load = vi.fn().mockResolvedValueOnce(network).mockRejectedValueOnce(new Error('network unavailable')).mockResolvedValueOnce(network)
    const cache = new NetworkRevisionCache(load)
    await cache.get('g_1')
    await expect(cache.get('g_2')).rejects.toThrow('network unavailable')
    expect(await cache.get('g_1')).toBe(network)
    expect(await cache.get('g_2')).toBe(network)
    expect(load).toHaveBeenCalledTimes(3)
  })
})
