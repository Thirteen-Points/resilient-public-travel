# C-Sim sequential journey timeline handoff

This module is internal to C-Sim. It does not change the public route contract,
route preference weights, or route scoring.

## Current input boundary

- Each transit leg receives absolute, timezone-aware departures and an explicit
  departure source.
- A departure source supplies timing only. In particular, MTR Next Train does
  not supply capacity, load, or boarding-denial evidence.
- When no verified capacity/load signal is available, each transit leg must
  receive an explicit `boarding.kind = assumption` object. Offline fixtures and
  their assumptions must remain `provenance: simulated`; there is no implicit
  denial-probability default.
- Walking time, minimum transfer time, waiting time, boarding denials, and ride
  time advance one shared clock. A missed connection therefore changes all
  downstream eligible departures.

## Minimal future integration proposal

Without changing the existing public route candidate contract, a C-Route
adapter can provide C-Sim with per-leg absolute departures plus source and
provenance metadata. C-Data/B can separately provide a versioned capacity/load
signal, or the caller can supply an explicit simulated boarding assumption.
Those two inputs must remain distinct.

If A/AI needs the three scenario explanations, introduce a separate versioned
internal explanation response containing scenario role, per-leg timing,
missed-service reasons, assumptions, and provenance. Do not add these fields to
the existing public route candidate without contract-owner agreement.
