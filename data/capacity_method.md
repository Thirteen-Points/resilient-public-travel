# Capacity Calculation Methodology (T7.3)

> This document explains how vehicle and line capacities are derived.
> All capacities are `real-derived` unless explicitly marked `real` (e.g. minibus statutory limit).
> A reviewer should be able to reproduce any line's hourly capacity from this document.
>
> **2026-09-25 (M1) status note**: the ERL headway *band* is now officially
> verified (MTR service index: Admiralty–Sheung Shui AM peak 2.7–5.5 min, PM
> 3.2, off-peak 4–8, Sat/Sun/PH 3.8–8) — the 180 s/162 s point values used
> below are in-band modelling choices, not official point measurements. Star
> Ferry adult fares were verified the same day (lower $4.0/$5.6, upper
> $5.0/$6.5); its vessel capacity remains unpublished and unverified. No
> official capacity source was found for MTR trains, buses or the ferry in
> this pass, so every `capacity_per_vehicle` stays `real-derived`/unverified.
> Green minibus 19-seat statutory maximum unchanged (Cap 374D). GMB_481B is
> excluded from the runnable network (endpoint invalid); its 65 pax/hour
> worked example is illustrative only.

---

## 1. Formula

```
capacity_r (pax/hour) = frequency (veh/hour) x capacity_per_vehicle x eta_max
```

Where:
- `frequency` = 3600 / headway_s (vehicles per hour)
- `capacity_per_vehicle` = from vehicle type lookup table (see §2)
- `eta_max` = 0.85 (target maximum load factor, from contracts §2)

## 2. Vehicle Type Lookup Table

| Vehicle type | Capacity (pax) | Source | Confidence | Data Status |
|---|---|---|---|---|
| ERL 9-car train (R-Stock) | 2,845 (6 pax/m^2) / 2,061 (4 pax/m^2) | LegCo paper (secondary source) | medium | unverified |
| TML/KTL/TWL/ISL train | ~2,500 (estimated from similar rolling stock) | Industry estimate | low | unverified |
| SIL 3-car train | ~1,000 | Industry estimate | low | unverified |
| Enviro500 MMC 12m (KMB ATENU) | ~136-137 (59 seated upper + ~31 lower + ~46 standing) | Industry estimate | low | unverified |
| Enviro500 MMC 12.8m | ~143-144 (incl. 2 wheelchair positions) | Industry estimate | low | unverified |
| Single-deck bus | ~60-70 | No official data | low | unverified |
| Public minibus | 16 or 19 (statutory maximum, no standing) | Cap 374D (2017-07-07) | high | verified |
| Star Ferry vessel | ~300 | Unverified | low | unverified |

> **Key constraint**: No public data source (data.gov.hk, KMB/CTB API) includes vehicle capacity or fleet type. Capacity can only be "type lookup x frequency" and must be labelled `real-derived`.

## 3. Worked Examples

### ERL (East Rail Line) - Normal Operation

```
headway_peak = 180s (3 min) -> frequency = 3600/180 = 20 veh/hour
capacity_per_vehicle = 2845
eta_max = 0.85
capacity = 20 x 2845 x 0.85 = 48,365 pax/hour

With 2.7 min headway (minimum): 3600/162 = 22.2 veh/hour
capacity = 22.2 x 2845 x 0.85 = 53,200 pax/hour (matches PPT claim)
```

### BUS 182 - Cross-harbour bus

```
headway_peak = 900s (15 min) -> frequency = 3600/900 = 4 veh/hour
capacity_per_vehicle = 137
eta_max = 0.85
capacity = 4 x 137 x 0.85 = 466 pax/hour
```

### BUS 982X - Peak-only cross-harbour

> **RETIRED FIGURE (2026-09-25).** The older version of this example assumed a
> fixed 30-minute headway (`1800 s` -> 2 veh/h -> **233 pax/hour**). That
> assumption is contradicted by the weekday departure times now recorded in
> `data/network/bus_routes.json` (982X `schedule_evidence`, user-provided
> timetable screenshots) and MUST NOT be used as an M1 demo capacity
> conclusion. 982X gaps are direction- and time-dependent, so no single
> headway-based hourly capacity exists for this route.

What the recorded weekday departures actually support (illustrative
in-window arithmetic only — basis, direction, window and assumptions stated;
nothing here is an all-day or official figure):

| Direction (weekday, user screenshots) | Window | Trips | In-window trip rate | Gaps |
|---|---|---|---|---|
| 愉翠苑 -> 灣仔(菲林明道) | 06:55–08:10 (75 min) | 7 | 7 / 1.25 h ≈ 5.6 veh/h (average) | 20/15/9/12/13/6 min |
| 金鐘(東) -> 愉翠苑巴士總站 | 17:47–18:27 (40 min) | 6 | 6 / (2/3) h = 9 veh/h (within window) | uniform 8 min |

Assumptions if one insists on an in-window bucket: `capacity_per_vehicle`
137 (industry estimate, unverified), `eta_max` 0.85, and the trip rate
treated as constant across the window — which is false for the AM direction
(6–20 min gaps). Under those assumptions the AM direction averages
≈ 5.6 × 137 × 0.85 ≈ **650 pax/hour across its 75-min window**, and the PM
direction ≈ 9 × 137 × 0.85 ≈ **1,050 pax/hour within its 40-min window**.
These are NOT transferable: the windows are shorter than an hour, the
screenshots are user-provided and not verified against an official source,
and there is no evidence for off-peak, Saturday, Sunday, public-holiday or
opposite-direction service. Demo wording must cite direction, window and
assumptions, or omit the number entirely.

### GMB 481B - Green minibus

> **HISTORICAL / HYPOTHETICAL EXAMPLE ONLY — NOT IN THE RUNNABLE NETWORK
> (2026-09-25).** GMB_481B has been removed from runnable
> `network.lines`/`contracts/seed` (endpoint `BS_TW` manually confirmed
> invalid; official stop sequence unverified). The arithmetic below is kept
> solely to illustrate the minibus statutory-capacity method and the
> wheelchair exclusion. It must NOT be mixed into any current M1 demo
> capacity conclusion, and the route is not an operational candidate.

```
headway_peak = 900s (15 min) -> frequency = 3600/900 = 4 veh/hour  (headway estimate, unverified)
capacity_per_vehicle = 19 (statutory maximum, real)
eta_max = 0.85
capacity = 4 x 19 x 0.85 = 65 pax/hour (non-accessible, wheelchair excluded)
```

### FERRY TST-CEN - Star Ferry

```
headway_peak = 360s (6 min) -> frequency = 3600/360 = 10 veh/hour
capacity_per_vehicle = 300
eta_max = 0.85
capacity = 10 x 300 x 0.85 = 2,550 pax/hour
```

## 4. Key Insight for Demo

> **2026-09-25 caveat.** The two bus rows below are NOT comparable
> all-day capacity claims. The 182 figure rests on an *estimated* headway
> (TD GTFS shows variable bands), and the 982X row is a directional
> in-window illustration from user-provided, unverified screenshots — see
> §3 before quoting either. GMB 481B is a historical/hypothetical example
> for a route that is NOT in the runnable network.

| Route | Capacity (pax/hour) | Basis | Ratio to ERL |
|---|---|---|---|
| ERL (normal, peak) | ~53,200 | in-band headway model + LegCo secondary capacity | 1.0x |
| TML (alternative) | ~42,500 | estimated headway + estimated capacity | 0.8x |
| BUS 182 (full-day) | ~466 | estimated 15-min peak headway x 137 x 0.85 | 0.009x |
| BUS 982X | ~650 AM (07:00-ish window, to Wan Chai) / ~1,050 PM (17:47–18:27 window, to Yu Chui Court) | user-screenshot departures, in-window average only — not all-day, not officially verified | ≤0.02x |
| GMB 481B | ~65 | **historical example only — NOT in runnable network** | 0.001x |

> One ERL train = ~20 double-decker buses. This is the core argument for the project:
> diverting MTR passengers to buses is physically impossible when buses are already 90%+ full.

## 5. Data Gaps

1. **Train capacity**: No official MTR capacity data. Values from LegCo papers (secondary).
2. **Bus capacity**: No KMB/CTB fleet type or capacity data in open APIs.
3. **Ferry capacity**: No official vessel capacity data.
4. **Actual vs theoretical**: Real-world load factors unknown. The >90% load factor for 982X is from a single web search, not continuous monitoring.
5. **982X schedule provenance (2026-09-25)**: the weekday directional departures recorded in `bus_routes.json` come from user-provided timetable screenshots with no capture date or verifiable official origin shown; they have not been re-checked against an official source. No off-peak, Saturday, Sunday or public-holiday evidence exists for 982X, and no departure evidence at all exists for 985B.
