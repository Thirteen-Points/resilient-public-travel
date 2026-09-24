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

```
headway_peak = 1800s (30 min) -> frequency = 3600/1800 = 2 veh/hour
capacity_per_vehicle = 137
eta_max = 0.85
capacity = 2 x 137 x 0.85 = 233 pax/hour
```

### GMB 481B - Green minibus

```
headway_peak = 900s (15 min) -> frequency = 3600/900 = 4 veh/hour
capacity_per_vehicle = 19
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

| Route | Capacity (pax/hour) | Ratio to ERL |
|---|---|---|
| ERL (normal, peak) | ~53,200 | 1.0x |
| TML (alternative) | ~42,500 | 0.8x |
| BUS 182 (full-day) | ~466 | 0.009x |
| BUS 982X (peak-only) | ~233 | 0.004x |
| GMB 481B | ~65 | 0.001x |

> One ERL train = ~20 double-decker buses. This is the core argument for the project:
> diverting MTR passengers to buses is physically impossible when buses are already 90%+ full.

## 5. Data Gaps

1. **Train capacity**: No official MTR capacity data. Values from LegCo papers (secondary).
2. **Bus capacity**: No KMB/CTB fleet type or capacity data in open APIs.
3. **Ferry capacity**: No official vessel capacity data.
4. **Actual vs theoretical**: Real-world load factors unknown. The >90% load factor for 982X is from a single web search, not continuous monitoring.
