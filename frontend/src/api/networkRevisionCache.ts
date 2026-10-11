import type { Network } from './types'

/** Geometry/calendars change with the graph revision, not each event poll. */
export class NetworkRevisionCache {
  private cached: { revision: string; network: Network } | null = null
  constructor(private readonly load: () => Promise<Network>) {}

  async get(revision: string): Promise<Network> {
    if (this.cached?.revision === revision) return this.cached.network
    const network = await this.load()
    this.cached = { revision, network }
    return network
  }
}
