# Agent 1 — C-Data

Base branch: ZYC
Working location: ZYC (direct commits; no Agent branch)
Model: gpt-6-astra, reasoning high

## Scope
Implement T3.1–T3.2, T7.1–T7.5: corridor network data package (stations, lines, walk links, bus routes, access points), coordinate verification, provenance ledger, capacity methodology, service calendar, weather impact factors, and data quality checks.

## Files
Own `data/` (network, access, calendar, weather, provenance, quality), `scripts/validate_data.py`, and `tests/test_data_integrity.py`. Do not modify `contracts/` schemas or `03-contracts.md` public interfaces. All data must carry provenance fields (`source`, `source_url`, `retrieved_at`, `license`, `confidence`, `data_status`).

## Data provenance rules
Every data item must be tagged with one of: `real` (official source, verified), `real-derived` (computed/estimated from real data, clearly labelled), `simulated` (synthetic, for demo only). No unverified data may be labelled `real`.

## Definition of done
All network nodes have coordinates within Hong Kong range; provenance ledger covers every data item with source URL and retrieval date; service calendar handles weekday/Saturday/Sunday+PH with public holidays; bus routes verified against Tai Wai service area; data validation script passes with zero errors; 34+ automated tests pass; unverified items listed with impact and resolution path.
