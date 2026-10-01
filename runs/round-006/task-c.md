# Agent C Task — Round 006

## Context

The persona parser exists, but its route was absent from the shared FastAPI app.

## Objective

Register and verify the persona parse API in the shared application.

## Inputs

- `backend/app/main.py`
- `backend/app/api/persona.py`

## Files Allowed to Modify

- `backend/app/main.py`
- `backend/tests/test_persona_preparse.py`
- `runs/round-006/report-c.md`

## Tasks

1. Register the router and add shared-app API checks.
2. Run targeted and actual local HTTP checks.

## Deliverables

- `runs/round-006/report-c.md`

## Acceptance Criteria

- `/api/persona/parse` responds from `create_app()` and existing routing remains intact.
