# Synthesis — Round 006

## Agent A Findings

Page, event and route disclosures are implemented and visible in a local browser. Sources and timestamps are visible on event cards. The build and typecheck pass.

## Agent B Findings

Automatic expiry is tested through audit, SSE, graph and route recomputation. A local browser observed the event banner clear after automatic expiry. T2.6 has a safe real-provider runner but no approved ten-real-text run.

## Agent C Findings

The existing persona parse route is registered in the shared app and responds in tests and local HTTP.

## Agent D Findings

The real-model and deployed-site gates remain open. Browser expiry and backend route restoration have separate evidence.

## Agreements

- `main` at `4e95f25` is the M2 baseline. `XMQM2` contains the already merged M2 baseline but the new closeout changes are a fresh PR, not merged `main` work.
- The bundled ten samples are simulated. They cannot be counted as real T2.6 acceptance.

## Conflicts

- The old T2.6 plan names OpenAI `gpt-5.6-sol`; current provider configuration supports DeepSeek/Qwen/GLM. The team must decide the acceptance model.
- The outer `PROJECT_STATE.md` dated 2026-09-29 still describes bootstrap work and conflicts with product GitHub history. The orchestrator updates it separately.

## Unresolved Questions

- Which ten private real texts and which provider/model are approved for T2.6?
- When will the PR be reviewed and merged, and where should deployed-site checks run?

## Risks

- Real provenance means source input was received; it does not verify a user-reported transport incident.
- Local simulated and modelled data cannot certify live transport behavior.

## Important Discoveries

- The M1 demo's next-day route query cannot prove a 45-second expiry window affects routes. The expiry integration test uses a matching departure window and is the route restoration evidence.

## Recommended Next Actions

1. Review and merge the M1 and M2 PRs into `main` when ready.
2. Supply the approved T2.6 corpus/model, run real-provider metrics and semantic checks.
3. Repeat browser and API smoke tests in the deployed environment.

## Evidence levels at round close

| Item | Implemented | Tested locally | Browser/online | Merged to `main` |
|---|---|---|---|---|
| M1 chain | Yes, Round 005 | Yes | Local browser, no deployed site | No, PR #95 |
| T2.6 real-model acceptance | Runner ready; acceptance partial | Offline tests only | No real-model/browser test | No |
| Automatic expiry integration | Yes | Shared backend and local HTTP | Local browser banner/map recovery | No |
| Persona API and disclosures | Yes | API, typecheck, build | Local browser disclosures | No |
