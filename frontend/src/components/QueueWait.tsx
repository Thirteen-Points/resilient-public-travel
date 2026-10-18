import type { RouteCandidate } from '../api/types'

export function QueueWait({ route }: { route: RouteCandidate }) {
  const seconds = route.total.queue_delay_s
  if (seconds === undefined) return null
  return <span data-queue-delay={seconds}>Includes {(seconds / 60).toFixed(1)} min extra queueing · model estimate</span>
}
