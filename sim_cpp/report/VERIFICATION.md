# C++ sandbox verification record

**Scenario**: `sim_cpp/config/scenario.json` (2026-10-15; off-peak 13:00–15:00 + evening 17:00–18:00; 5 groups; 95% per-train cap; seed 20260922)

**Population**: 10,000; commuter / student / tourist / elderly / wheelchair = 2,000 each; `population_hash = 9cc88d73b34c0acc`.

**Input SHA256** (`sim_cpp/data/sim_input.json`): `6fe6a5d6c1535ac1d67454fb63cd5fdc2c9905182cb5f3eb181c720afe117664`
**C++ input hash**: `97bd81139bf358cf`
**Config hash**: `876d85a111146b6d`

## Self-test

`sim.exe --self-test` → `SELF-TEST PASS`

- 10,000 passengers; five personas × 2,000.
- Off-peak arrivals `[13:00:00, 14:59:58]`; evening arrivals `[17:00:00, 17:59:59]`.
- W1 first-draw mean `20.15 min` (target 20).
- Six route-timing validation cases pass against the Python engine's exported `query_details` ETAs (±1 s):
  - closure/standard/HUH @14:05 → 1,305 s
  - closure/standard/HUH @17:05 → 1,125 s
  - normal/standard/KOT @13:05 → 1,005 s
  - normal/standard/KOT @17:05 → 825 s
  - closure/standard/KOT @14:05 → 1,665 s
  - closure/standard/KOT @17:05 → 1,305 s

## Output verification

`python scripts/verify_cpp_sim.py --out sim_cpp/out/run1` → `VERIFY PASS`

- Five groups, each 10,000; served + censored = 10,000.
- B0/B2 fully served; no capacity denial; no train onboard above its 95% cap.
- Station queues non-negative; line load factors ≤ 1.0.
- Cross-period rates 5,000/h (off-peak) and 10,000/h (evening).
- F1/W1 forced-alight cohort exists (HUH turnaround), as required by the scenario.

## Determinism

Two independent runs (`run1` and `run2`) produced identical SHA256 for:

| file | SHA256 (prefix) |
|---|---|
| comparison.json | `232ec077d745b615` |
| B0/passengers.csv | `b7c9e79271916040` |
| F1/passengers.csv | `7ec9b6b511e69cba` |
| W1/passengers.csv | `14242826ff130157` |
| B2/passengers.csv | `1cfe9efc5a2b1c8e` |
| F2/passengers.csv | `1d3bfb8becec9429` |
| F1/station_waiting.csv | `06e6c4bcf8563144` |
| W1/station_waiting.csv | `cc464c534447cd83` |

Result: **DETERMINISM PASS**.

## Key sanity numbers

- B0 average journey 14.23 min; B2 12.82 min.
- F1: 5,701 affected, average delay 9.50 min; 633 HUH forced alights.
- W1: 6,091 affected, average delay 19.23 min; KOT peak 2,057 (1,743 policy wait), HUH peak 633.
- F2: 9,029 affected, average delay 12.57 min.
- Maximum per-train load factor 0.348; zero denied boardings.
