# Agent D Report — Round 006

## Status

`partial`: code and local checks reviewed; real-model and deployed-site claims remain open.

## Work Completed

- Reviewed changed API, acceptance, expiry test and disclosure UI against the requested M2 outcomes.
- Checked that simulated test results are separated from real-model acceptance and that browser observations do not overstate route behavior.

## Files Changed

- `runs/round-006/report-d.md` only.

## Findings and Evidence

- The bundled ten-text fixture carries `simulated` provenance and cannot satisfy T2.6. The CLI refusal is an appropriate guard; a `DEEPSEEK_API_KEY` environment variable being present is not evidence of a provider request.
- Expiry test covers audit idempotence, SSE, graph and route IDs within one shared app. The browser run covers the published banner and automatic clearing without reload. These are separate acceptance surfaces.
- The original T2.6 plan names OpenAI `gpt-5.6-sol`; the current shared C provider configuration names DeepSeek/Qwen/GLM. Model choice is an unresolved team decision.

## Validation Performed

- Reviewed code diffs and test results recorded in reports A–C; independent deployed-site or real-provider test was not performed.

## Problems, Risks, or Unresolved Questions

- T2.6 lacks approved real samples and a measured first-pass/retry/fallback record.
- The GitHub PR is reviewable work, not a `main` merge or production verification.

## Recommended Next Action

- Review the PR, provide the approved private T2.6 corpus and model choice, then complete real-provider and deployed-browser acceptance before closing M2.
