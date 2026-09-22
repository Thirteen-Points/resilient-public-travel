// Pure recovery-state model for the P13 recovery panel. Every degraded
// situation renders a readable message, an explicit fallback, whether the
// last successful result stays on screen, and a suggested next action —
// a failure is never hidden behind a blank page. Shape mirrors the API error
// envelope { error: { code, message, fallback } } (03-contracts §4).

export type RecoveryKind = 'loading' | 'empty' | 'stale' | 'offline' | 'out_of_range' | 'ai_unavailable' | 'error'

export interface RecoveryState {
  kind: RecoveryKind
  message: string
  fallback: string
  keepPreviousResult: boolean
  nextAction: string
  retryable: boolean
}

export function createLoadingState(subject = 'snapshot'): RecoveryState {
  return {
    kind: 'loading',
    message: `Loading the latest ${subject}…`,
    fallback: 'Any data already on screen stays visible while loading',
    keepPreviousResult: true,
    nextAction: 'Wait a moment, or retry if nothing appears',
    retryable: true,
  }
}

export function createEmptyState(subject: string): RecoveryState {
  return {
    kind: 'empty',
    message: `No ${subject} available for this query.`,
    fallback: 'Guidance back to the modelled corridor (Tai Wai → Admiralty)',
    keepPreviousResult: false,
    nextAction: 'Try the modelled origin–destination pair in the station form',
    retryable: false,
  }
}

export function createStaleState(lastUpdatedText: string): RecoveryState {
  return {
    kind: 'stale',
    message: `Data may be out of date — last updated ${lastUpdatedText}.`,
    fallback: 'Previous data is kept on screen with a stale badge',
    keepPreviousResult: true,
    nextAction: 'Refresh once the connection returns',
    retryable: true,
  }
}

export function createOfflineState(): RecoveryState {
  return {
    kind: 'offline',
    message: 'Network unavailable — showing the last successful result.',
    fallback: 'Last successful data is kept on screen; the demo can also run from the bundled seed snapshot',
    keepPreviousResult: true,
    nextAction: 'Check the connection and retry',
    retryable: true,
  }
}

/**
 * Out of the access catchment. When the nearest modelled access point is
 * known it is named so the user gets a concrete anchor, not just a refusal.
 */
export function createOutOfRangeState(catchmentM: number, nearest?: { name_en: string; metres: number }): RecoveryState {
  const anchor = nearest
    ? ` The nearest modelled access point is ${nearest.name_en}, about ${Math.round(nearest.metres)} m away.`
    : ''
  return {
    kind: 'out_of_range',
    message: `No modelled access point within ${catchmentM} m of the selected point.${anchor}`,
    fallback: 'Station search instead of map selection',
    keepPreviousResult: true,
    nextAction: 'Search by station name, or pick a point closer to a modelled station',
    retryable: false,
  }
}

export function createAiUnavailableState(): RecoveryState {
  return {
    kind: 'ai_unavailable',
    message: 'AI assistance is unavailable right now.',
    fallback: 'Preset preferences and deterministic seed routes keep working without AI',
    keepPreviousResult: true,
    nextAction: 'Continue with your preset preferences, or retry AI later',
    retryable: true,
  }
}

export function createErrorState(cause?: unknown): RecoveryState {
  const envelope = extractErrorEnvelope(cause)
  return {
    kind: 'error',
    message: envelope?.message ?? 'Something went wrong while loading data.',
    fallback: envelope?.fallback ?? 'Last successful data is kept on screen',
    keepPreviousResult: true,
    nextAction: 'Retry the request; if it persists, continue with the seed snapshot',
    retryable: true,
  }
}

/** Accepts the API error envelope `{"error":{"code","message","fallback"}}` and unknown throwables. */
export function fromErrorPayload(payload: unknown): RecoveryState {
  return createErrorState(payload)
}

function extractErrorEnvelope(cause: unknown): { code?: string; message?: string; fallback?: string } | null {
  if (typeof cause !== 'object' || cause === null) return null
  const error = (cause as { error?: unknown }).error
  if (typeof error !== 'object' || error === null) return null
  const { code, message, fallback } = error as { code?: unknown; message?: unknown; fallback?: unknown }
  return {
    code: typeof code === 'string' ? code : undefined,
    message: typeof message === 'string' ? message : undefined,
    fallback: typeof fallback === 'string' ? fallback : undefined,
  }
}
