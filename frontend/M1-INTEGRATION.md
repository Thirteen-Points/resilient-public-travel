# Role A · M1 integration handoff

## Running modes

- Default: API mode, using `VITE_API_BASE_URL` or `http://127.0.0.1:8000`.
- `?data=seed`: explicit fixed-fixture demo. The header switches modes by reloading the page; unsaved UI state is discarded. Seed review stays local and routes stay fixed.
- API failure never silently switches to seed data. Existing data is retained with a stale/unavailable notice. A successful review write is not reported as failed merely because its following refresh failed.
- The public Report screen mounts ZCode's `SignalReportForm`. Acceptance means an unverified signal was received, not that an event was created or published.

## Integration implemented by main agent

- App wiring for the three ZCode components/clients: report form, live transit client, async review console.
- `eventApi.ts`: event list, published events, per-event evidence and review requests; SSE change notifications trigger authoritative reads.
- `useLiveSession.ts`: API loading, SSE with 3-second polling, stale notices, graph/published-event change detection and current-query recomputation. The latest query wins; evidence requests do not block route recomputation.
- Server confidence factors and audit history are shown when supplied. Source freshness is only shown when returned by the API.
- API review requires saving edited fields before publication. Only server responses update review status; no optimistic approval or inferred confidence increase.

## B handoff: endpoints still required in the checked-in backend

| Endpoint | Frontend expectation |
| --- | --- |
| `GET /api/events` | `Event[]` |
| `GET /api/events/published` | Effective published `Event[]`; backend owns time-window/status policy |
| `GET /api/events/{id}/signals` | Related `Signal[]` only; additive endpoint selected during planning |
| `POST /api/events/{id}/review` | Updated `Event` including authoritative status and audit history |
| `GET /api/stream/events` | Event increments; default messages or named `event` / `event_updated` notifications |

Proposed review body (requires B agreement; it is not yet an implemented backend contract):

```json
{
  "action": "approve | edit | reject",
  "actor": "admin_demo",
  "changes": {
    "title": "...",
    "summary": "...",
    "line": "...",
    "severity": 3,
    "window": {"start": "...", "end": null},
    "affected_segments": []
  },
  "reason": "..."
}
```

`changes` is sent only for `edit`; `reason` only when provided. Actor is a demo identifier, not authentication. B must enforce validation, state transitions and confidence thresholds. Ambiguous write failures require reading the event before retrying. Signal intake currently persists a signal; aggregation and confidence updates remain B work.

## C handoff

- Existing graph/network, graph/snapshot, meta and route-query endpoints are consumed.
- Publication must update the engine snapshot. The frontend re-queries when snapshot/affected edges or published events change; it cannot apply closures inside the engine.
- The engine determines feasible candidate count. Frontend displays the first three and never manufactures eight candidates.
- Resolve `updated` semantics between review and routing; the frontend uses the published-events endpoint as the authority.

## Remaining acceptance

TypeScript static checking passed during integration. No runtime tests or end-to-end timing run was performed. With B/C services ready, verify report → aggregation/confidence → review → graph change → route/map refresh, including the ≤5-second target, missing evidence, request failure and reconnect. The present backend cannot demonstrate the complete chain yet.
