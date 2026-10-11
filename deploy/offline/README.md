# P4-C offline demo

This package runs the prepared public frontend and local API without installing
anything or calling external data/AI services. The target machine must already
have Python 3.11+ and `backend/requirements.txt` installed. The ZIP does not ship
a Python runtime or a virtual environment; prepare that machine before disconnecting.

## Prepare while connected

From the release checkout, install backend requirements and run `npm ci` in
`frontend`. Then run these from the repository root:

```text
python scripts/preflight.py
python scripts/package_offline.py --build --require-media
python scripts/preflight.py --demo --require-media
```

The ZIP is `.cache/offline/resilientroute-offline.zip`. Its `offline-manifest.json`
records the build SHA, file hashes and media checks. It excludes local databases,
`.env*`, dependency directories and logs. Extract into a local directory; verify
each manifest hash before rehearsal. Prepare the Python runtime separately.
Do not use `scripts/start.bat` or `scripts/start.sh` after disconnecting: those
development launchers install dependencies.

## Start without network

Windows PowerShell, from the extracted package/repository root:

```powershell
$env:P4_PYTHON = 'C:\path\to\prepared\python.exe'
.\deploy\offline\start.ps1 -CheckOnly
.\deploy\offline\start.ps1
```

Linux/macOS:

```sh
P4_PYTHON=/path/to/prepared/python bash deploy/offline/start.sh --check-only
P4_PYTHON=/path/to/prepared/python bash deploy/offline/start.sh
```

Open `http://127.0.0.1:5173/`. The launcher first checks dependencies, frontend
file hashes and both P3 result files; then starts the API on loopback port 8000
and serves the built frontend on 5173. It refuses occupied ports. Ctrl+C stops
its own servers. Runtime state/logs live in `.cache/offline-demo/`, separate from
the production database. Set no reviewer credentials for this technical tour.

The frontend can attempt fonts/map tiles from the internet. When unreachable,
the modelled network remains usable; no basemap or live feed is promised. The
browser regression explicitly aborts all non-loopback requests and records that
condition, rather than setting the browser offline and blocking localhost too.

## Five-minute script and failure switch

| Time | Action / explanation |
|---|---|
| 0:00-1:00 | Select TAW -> ADM, departure 2026-09-22 08:20 HKT, existing Commuter/Fastest preset; query and show returned estimates. |
| 1:00-2:00 | Open Simulation, load `scn_huh_exc_closed_am_peak`; show the older M0 negative benefit unchanged. It is not the P3 shared-segment model. |
| 2:00-3:00 | Load `m2_six_station_directed_od_am_peak_p3_shared_segments`; normal case has 10,000 served in each strategy and 0% delay reduction. |
| 3:00-4:00 | Load the same ID plus `_residual_10pct`; explain this invented 10% capacity sensitivity, 9,690/9,801 served and 310/199 unmet. |
| 4:00-5:00 | Show Capacity gap & allocation and Assumptions; explain shared directed segments, units, unmet demand and simulation limits. |

If the UI/API fails, keep the error visible, stop the known launcher and switch
immediately to `deploy/offline/media/demo.webm` opened in Edge/Chromium (local
file playback, no URL). It is a silent five-minute recording of the above real
local UI, without injected results. The presenter narrates using this table.
If video playback also fails, use `deploy/offline/media/slides.pdf` in a local
PDF reader. It is a C technical backup, not the team's final pitch deck. A and
the reviewer still need to approve/replace it with the final team's PPT export.
After the failure switch, explain that screenshots/video show precomputed local
evidence; do not describe them as a live production demonstration.

## Data and boundaries

The package includes repository network/calendar/access/provenance data and
frozen simulation inputs/results. Each P3 result carries scenario/input/model
versions, timestamp, units, assumptions and `provenance: simulated`. Route
policy weights and presets are unchanged. Unavailable measurements stay missing.
`contracts/seed/sim.seed.json` remains the legacy seed fixture; select the exact
P3 IDs above for the shared-segment evidence.

The 10,000-person model uses 30 directed OD pairs, seed 20260922 and a 60-minute
window; 44 shared directed resources consume capacity once per passenger on
each traversed segment. The 10% case is a sensitivity test, not observed spare
capacity. Wheelchair berth throughput, external passenger load, train-by-train
seat propagation and multi-window carryover are not validated. See
[the result contract](../../contracts/sim-precomputed.md) and
[C acceptance record](../../docs/acceptance/p4-c-acceptance.md).

## Verify and regenerate technical media

```text
python scripts/preflight.py --demo --require-media --api-base-url http://127.0.0.1:8000 --require-offline --expected-build-sha FULL_SHA
python scripts/verify_p4.py --api-base-url http://127.0.0.1:8000
node tests/browser/p4.offline.cjs
```

Stop the launcher before the browser test; it starts its own servers on the
same ports. Install Playwright/browser/ffmpeg during preparation, set `M2_PYTHON`
and `M2_PLAYWRIGHT` to those runtimes, and use `P4_RECORD_TOUR=true` to regenerate
the five-minute WebM. It saves screenshots and actual API replies in
`.cache/p4-browser/`. `python scripts/build_offline_slides.py` uses ReportLab and
those screenshots/performance evidence to generate the backup PDF. Media
header checks only establish format; play the complete video and visually inspect
the rendered PDF before sign-off. Local, CI and production evidence are recorded
separately in [the deployment runbook](../P4-ACCEPTANCE.md).
