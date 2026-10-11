# Seed data provenance ledger

Status: M0 offline/demo ledger, reviewed 2026-09-23 (Asia/Hong_Kong). This
ledger is intentionally conservative: a value is never promoted to `real`
merely because it looks plausible. `real-derived` means derived from a named
public/official data family or an explicitly documented estimate; it still needs
field-level operational verification before production use. `simulated` is
demo/test data and must remain labelled as such.

## Sources and verification scope

| ID | Source / URL | Checked | Scope | Status |
|---|---|---|---|---|
| S1 | MTR, [system map](https://www.mtr.com.hk/en/customer/services/system_map.html) | 2026-09-22 | station and line names/topology used by the corridor seed | topology plausibility only; coordinates and service values not certified |
| S2 | Hong Kong Transport Department, [public transport data](https://www.td.gov.hk/en/transport_in_hong_kong/public_transport/buses/) | 2026-09-22 | bus/minibus route naming context | route stop order, fares, headways and current service require re-check |
| S3 | Hong Kong Observatory, [warnings](https://www.hko.gov.hk/en/wxinfo/climat/warndb/warndb.htm) | 2026-09-22 | source family for future weather events | no live weather value is included in these seeds |
| S4 | Project-owned deterministic fixtures | 2026-09-22 | event signals, route scores, demand, simulation outputs | simulated; not an operational observation |

## M0 source access log (2026-09-22, Asia/Hong_Kong)

These are access observations, not blanket approvals to promote seed values to
`real`. Web access was checked on 2026-09-22; values below were not written into
the seeds unless the field and scope were clear.

| ID | URL | Result / fields observed | Coverage and limitation |
|---|---|---|---|
| S5 | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | **verified page**; monthly dataset; CSV resources for MTR routes/stations, fares, and barrier-free access; data dictionary link | Resource downloads were not imported in this M0 pass; no station row or fare value is promoted from page metadata alone |
| S6 | https://opendata.mtr.com.hk/data/mtr_lines_and_stations.csv | **unverified access**; tool rejected `text/csv` response | Candidate URL was actually tried; no fields were consumed |
| S7 | https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php?line=EAL&sta=TAW&lang=en | **unverified access**; tool could not access query URL | Intended fields are schedule/arrival data only; not a service-status API and no seed value consumed |
| S8 | https://data.gov.hk/en-data/dataset/hk-td-tis_11-pt-headway-en | **verified page**; biweekly dataset; 30 GTFS files plus CSV last-update file; route/stop/frequency/fare files listed | Dataset page was read, but files were not imported; no current headway or fare promoted |
| S9 | https://data.gov.hk/en-data/dataset/hk-td-tis_7-route-fares | **unverified access**; page not accessible to the checker | No route/fare fields consumed |
| S10 | https://data.gov.hk/tc-data/dataset/hk-td-tis_1-special-traffic-news | **verified page**; Transport Department, real-time frequency; XML resources and data dictionary listed | This is an incident-source candidate, not used for the simulated event seed |
| S11 | https://data.etabus.gov.hk/v1/transport/kmb/route/170/outbound/1 | **unverified access**; API URL not accessible to the checker | No KMB route/stop/ETA field consumed; never treated as capacity source |
| S12 | https://rt.data.gov.hk/v2/transport/citybus/route/CTB/182 | **unverified access**; API URL not accessible to the checker | No Citybus route/stop/ETA field consumed; never treated as capacity source |
| S13 | https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc | **verified JSON response**; `rainfall.data[].place/max/unit`, `startTime/endTime`, `temperature.data[]`, `warningMessage`, `updateTime` | Snapshot observed at `updateTime=2026-09-22T21:02:00+08:00`; weather snapshot is not embedded in the event seed and does not prove a transport incident |
| S14 | https://www.hko.gov.hk/en/wxinfo/climat/warndb/warndb.htm | **unverified access**; page not accessible to the checker | No warning status consumed |
| S15 | https://www.starferry.com.hk/en/service | **verified operator page**; Central–Tsim Sha Tsui timetable/frequency, weekday/weekend fares, wheelchair lower-deck limit, weather/marine-traffic caveat | Current fare/frequency differs from the old seed assumptions; capacity is not published, so capacity remains `real-derived`/pending and no capacity number was promoted |
| S16 | https://www.gov.hk/en/about/abouthk/holiday/2026.htm | **unverified content**; page returned no readable lines | No holiday/service-calendar value consumed |

S1 (MTR system map) was also directly readable: it lists the East Rail Line
stations including Admiralty, Exhibition Centre, Hung Hom, Mong Kok East,
Kowloon Tong and Tai Wai. This supports only line/station naming/topology and
not the seed coordinates, timings, capacities or current service state.

The MTR and Transport Department pages are accepted as official source families
because their pages identify the operator/department and describe the supplied
fields. A page being accessible does not certify a particular seed value; the
seed remains `real-derived` until the exact row, field definition, update time
and coverage are captured.

## File-level disposition

| File | Contents | Disposition |
|---|---|---|
| `contracts/seed/network.seed.json` | nodes, line topology, coordinates, service assumptions | names/topology are `real-derived`; timings, capacities, fares, accessibility and bus/ferry service are derived or pending; `meta.counts.lines=10`; GMB_481B excluded from runnable lines after manual invalid-stop confirmation |
| `contracts/seed/routes.seed.json` | eight candidate route cards for `TAW` → `ADM` | every route and leg now carries evidence IDs/fields/status; stale 982X/985B 1800-second headways were removed pending exact schedule evidence; `r_seed_008` is simulated/demo-only with unresolved destination |
| `contracts/seed/event.seed.json` | three-stage event-card progression and signals | entirely `simulated`, including the “official” signal text; it must not be presented as a real MTR alert |
| `contracts/seed/sim.seed.json` | deterministic baseline/guided comparison | entirely `simulated`; assumptions are not measured demand or capacity |

## Known pending checks

1. Confirm station coordinates and accessibility against the current official
   station/accessibility source before operational routing.
2. Confirm every bus/minibus stop sequence, direction, service calendar, fare,
   headway and vehicle capacity; do not treat `real-derived` as `real`.
3. Do not restore GMB_481B unless official route, stop sequence, direction and
   valid boarding/alighting evidence resolves the manually rejected `BS_TW`.
   Historical simulated references are not operational candidates.
4. Confirm ferry fare, capacity, accessibility and weather suspension rules.
5. Replace simulated event wording with a separately sourced, timestamped
   official notice before any public-facing live claim.
6. ERL capacity is not certified by the sources accessed here; it remains
   `real-derived` and must not be presented as an official passenger-capacity
   measurement.
7. Star Ferry fare/frequency/accessibility are now source-observable from S15,
   but the seed's ferry capacity and any stale fare/headway tuple require a
   deliberate data refresh; do not silently copy the old numbers.
8. 982X and 985B exact headway fields remain unverified after manual review;
   consumers must handle `null` and must not infer a new numeric headway.
9. The 800 m catchment is an access-point search radius, not a complete-route
   cumulative walking limit. Small buses remain out of wheelchair candidates
   unless official accessibility evidence is separately confirmed.

## Six-core coverage ledger

The six core points are `TAW`, `KOT`, `MKK`, `HUH`, `EXC`, `ADM`, producing 30
directed OD pairs. Current evidence supports only the MTR station/topology rows
and four partial bus access areas: `BS_TAW`, `BS_TIN_SUM`, `BS_HUH_TUNNEL`, and
`BS_ADM_E`. MTR street maps confirm station-area exits and access features at
MKK/KOT/EXC, but no machine-readable coordinates, access time, step-free path
continuity, or link to a seed node was captured; thus no edge was added.

The four bus route cards/line records are limited to 182 (`BS_TAW`–`BS_ADM_E`),
982X (`BS_TAW`–`BS_ADM_E`), 985B (`BS_TIN_SUM`–`BS_ADM_E`), and 81C
(`BS_TAW`–`TST`). Their evidence points to the Transport Department headway
dataset family (S8) but is marked `unverified-not-imported`; it does not certify
current stop order, direction, service calendar, fare, coordinate, or headway.
Official TD route/sequence/stop-location records are now inspected (S17–S20
below), but do not safely map every abstract seed node. No bus edge is asserted
for MKK or EXC. This is a coverage limitation, not a reason to fabricate the
missing 30 route sets.

## Field-level reconciliation (2026-09-23, Asia/Hong_Kong)

Official Transport Department files were fetched from the DATA.GOV.HK resource
URLs. `X`,`Y` are Hong Kong projected grid coordinates, not decimal
latitude/longitude. No projection, map-matching, or stop-to-seed-node snapping
was performed. Dataset resource update dates and row `LAST_UPDATE_DATE` values
are distinct.

| ID | Exact source / fields | Records checked | Disposition |
|---|---|---|---|
| S17 | [Bus route XML](https://static.data.gov.hk/td/routes-fares-xml/ROUTE_BUS.xml); `ROUTE_ID, COMPANY_CODE, ROUTE, SERVICE_MODE, SPECIAL_TYPE, JOURNEY_TIME, FULL_FARE, ORIGIN, DESTINATION, LAST_UPDATE_DATE` | 182 route 1051, KMB+CTB, Yu Chui Court–Central (Macao Ferry), R/special 0, 60 min, HK$20.8, row 2026-01-14. 81C route 1336, KMB, Yiu On–Tsim Sha Tsui East (Mody Road), R, 78 min, HK$10.2, row 2025-08-11. 982X route 8104: Yu Chui Court–Wan Chai (Fleming Road), T/special 1, 53 min, HK$20.8, row 2026-06-12. 985B route 8705: Tin Sam Village–Wan Chai (Hennessy Road), T/special 1, 47 min, HK$20.8, row 2025-04-03. | Master-record full route fare/time does not establish seed node boarding/section fare, headway or capacity. |
| S18 | [Bus route stop-sequence XML](https://static.data.gov.hk/td/routes-fares-xml/RSTOP_BUS.xml); `ROUTE_ID, ROUTE_SEQ, STOP_SEQ, STOP_ID, STOP_PICK_DROP, STOP_NAME, LAST_UPDATE_DATE` | 182 route 1051 seq 1 includes stop 859 Tai Wai BBI—Sun Chui Estate/Hung Mui Kuk Road, then Kowloon Tong Junction Road 4223 and Kowloon Tong Station 768. 81C route 1336 includes 859/4223/768. 982X route 8104 includes 6041 Tai Wai BBI—Sun Ming House, 6015 Tai Wai BBI—Tin Sam Village and Admiralty/United Centre 8051. 985B route 8705 starts at 6015, includes Western Harbour Tunnel BBI 911 and Admiralty/United Centre 8051. | Direction-specific ordered records. Existing abstract seed bus nodes are not presumed identical to these stop IDs. Resource updated 2026-08-18; row dates are distinct. |
| S19 | [Bus stop location XML](https://static.data.gov.hk/td/routes-fares-xml/STOP_BUS.xml); `STOP_ID, STOP_TYPE, X, Y, LAST_UPDATE_DATE` | 859 X=836580,Y=825686; 6042 Tai Wai Station/Che Kung Miu Road X=836629,Y=825937; 6015 X=836379,Y=825731; 768 Kowloon Tong Station X=836499,Y=821851; 8051 Admiralty/United Centre X=835065,Y=815497. XML generated 2026-09-11T17:49:16; resource updated 2026-09-12. | Grid coordinates are not WGS84 or the seed decimal coordinates. No coordinate conversion or node linkage claimed. |
| S20 | [TD public transport headway GTFS](https://data.gov.hk/en-data/dataset/hk-td-tis_11-pt-headway-en); `routes.txt, trips.txt, frequencies.txt, calendar.txt, stop_times.txt` | Routes 1051/1336 have multiple `frequencies.txt` headway bands. 982X route variants 8104/8308 have scheduled trips. | One constant per-day headway cannot accurately summarize variable bands. Exact 982X/985B departures and service exceptions need schedule/calendar joins; service IDs are not interpreted without calendar/exception rows. |
| S21 | [MTR street map index](https://www.mtr.com.hk/en/customer/services/stmap_index.html); [MKK map](https://www.mtr.com.hk/archive/en/services/maps/mkk.pdf), [KOT map](https://www.mtr.com.hk/archive/ch/services/maps/kot.pdf), [EXC map](https://www.mtr.com.hk/archive/en/services/maps/exc.pdf) | MKK/KOT maps show station exits and bus/minibus access features; KOT identifies its Public Transport Interchange; EXC map identifies exits, bus stops, ferry pier and public transport interchange. | Confirms station-area features only; no machine-readable coordinates, access time, continuous step-free path, or linkage to a seed node. No graph edge added. |
| S22 | [MTR system map](https://www.mtr.com.hk/en/customer/services/system_map.html) | Station/line names and East Rail topology for TAW, KOT, MKK, HUH, EXC and ADM. | Topology/name evidence only, not coordinates, timetable or capacity. |

### Traceability spot-check count

At least 17 record-level checks were made: route 1051 operator, origin,
destination, fare and time; 81C route/operator, destination and fare; 982X
variant, mode and fare; 985B route, origin, destination and fare; stop 859,
4223, 768, 6015 and 8051 names/sequence; plus five `X`,`Y` pairs. URLs,
fields, row IDs/dates where captured, and limitations are listed above. Exact
section fares, headways, capacity, access and calendar remain pending when not
explicitly supported.

The user manually verified that `BS_TW` is not a valid stop. `GMB_481B` has
therefore been removed from runnable `network.seed.json`; any historical
simulated route reference is not an operational candidate.

## Station-access coordinate follow-up (2026-09-23)

| ID | Source / fields | Observation | Disposition |
|---|---|---|---|
| S23 | [LandsD iGeoCom CSV resource](https://data.gov.hk/en-data/dataset/hk-landsd-openmap-development-hkms-digital-geocom/resource/d4be4d11-4566-46a4-9a1b-c05b5be443d0); `GEONAMEID, ENGLISHNAME, CLASS, TYPE, SUBCAT, EASTING, NORTHING, E_SITENAME, REV_DATE` | Downloaded CSV (SHA-256 `d9703a9717774ca6b875f076da7d1be95f8640140e5bd902691b8421befef5db`) on 2026-09-23; resource updated 2026-09-04. Exact `TYPE=MTA`/`E_SITENAME` match yielded 8 TAW + 11 KOT + 4 MKK + 14 HUH + 6 EXC + 7 ADM access records. Exact `TYPE=RSN` point records: TAW 542884 (836455,825953; 21/1/2020), KOT 544548 (836155,822006; 21/1/2020), MKK 557494 (835827,820334; 28/12/2023), HUH 544547 (836815,818227; 4/5/2023), EXC 21170932 (836107,815864; 27/7/2022), ADM 538320 (834977,815617; 27/10/2014). | All 50 MTA access rows and six official railway-station reference points are preserved with raw fields and transformed coordinates in `data/access/station_entrances.json`. These are official point records, not proof of step-free access or continuous path connections. Earlier download-failure observation was superseded after retrieving the CSV. |
| S24 | [TD GTFS specification](https://static.data.gov.hk/td/pt-headway-en/dataspec/ptheadway_dataspec.pdf), `stops.txt`: `stop_id, stop_name, stop_lat, stop_lon, location_type` | Specification defines WGS84 coordinates; location type 0 is stop and type 2 is station entrance. Current `stops.txt` parsed: 9,447 rows, all `location_type=0`; resource updated 2026-09-12. | This feed provides no station-entrance rows for the six MTR nodes; the iGeoCom MTA access features and RSN reference points above supply the station access locations instead. |

The six network station coordinate pairs now match the corresponding S23 RSN
records, transformed by the official [HK Geodetic Survey API](https://www.geodetic.gov.hk/transform/v2/?inSys=hkgrid&outSys=wgsgeog&e=836366&n=825885)
(`inSys=hkgrid`, `outSys=wgsgeog`); API documentation:
[transformation manual](https://www.geodetic.gov.hk/transform/tformAPI_manual.pdf).
The supplied Tai Wai sample returned `22.372147626,114.177825919` exactly.
Independent transformation checks were also made for one access record at
each of the six stations. The old estimate coordinates are replaced by the
official RSN point coordinates, not claimed geometric centroids. No walk links
were added, and access/step-free connectivity remains unknown.

## M1 data verification pass (2026-09-25, Asia/Hong_Kong)

Scope: the M1 demo corridor — six core stations `TAW/KOT/MKK/HUH/EXC/ADM`,
the default demo interruption segment `HUH–EXC`, alternative-route data, and
the accessibility/headway/access fields they depend on. This pass corrected
the `data/` documentation layer only; `contracts/seed/` is frozen and was not
modified. Where this pass corrects a value the seed still holds, the
divergence is listed below and must be reconciled in a deliberate
contract-freeze change.

### Sources checked

| ID | Source / URL | Result / fields observed | Coverage and limitation |
|---|---|---|---|
| S25 | MTR open-data CSVs from `https://opendata.mtr.com.hk/data/`: `mtr_lines_and_stations.csv` (SHA-256 `e0e78115...75e0c3`), `barrier_free_facilities.csv` (`f220d56a...8c66daf`), `barrier_free_facility_category.csv` (`84ba2315...5973f963`), `mtr_lines_fares.csv` (`1bb28b99...46e06f075`) | EAL stop order TAW(9)-KOT(10)-MKK(11)-HUH(12)-EXC(13)-ADM(14) both directions; line membership for all 16 modelled stations; per-station AJ facility rows (all six core have paid-area lift AJ8=Y plus step-free exits); adult Octopus/single fares for six-core and alternative OD pairs (e.g. TAW-ADM 17.1/19.0, HUH-EXC 10.6/12.5, EXC-ADM 4.9/5.0) | Monthly snapshot; station-level facilities do not establish per-entrance step-free paths, walk connectivity, or live lift state. The CSV has no coordinates. Fare rows are adult OD fares, not section fares. |
| S26 | GovHK 2026 holidays, `https://www.gov.hk/en/about/abouthk/holiday/2026.htm` | 2026-09-26 (Sat, day following the Chinese Mid-Autumn Festival), 2026-10-01 (Thu, National Day), 2026-10-19 (Mon, day following Chung Yeung Festival) — all three rows in `data/calendar.json` confirmed | Date list only; MTR service-calendar application (Sunday headways on PH) remains a documented assumption |
| S27 | Star Ferry operator page, `https://www.starferry.com.hk/en/service` | Central↔TST timetable: Mon-Fri 06:30-23:30 (bands 10/12, 6, 6/8, 10/12 min), Sat/Sun/PH 10/12, 6/8, 10/12; adult fares lower deck $4.0 weekday / $5.6 weekend, upper deck $5.0 / $6.5; wheelchair users board lower deck, max 4 per ferry; sailing times vary with maritime traffic/sea/weather | No vessel capacity published (stays unverified); no explicit typhoon-signal suspension threshold stated on the page; 10/12-min early/late bands not modelled in `headway_s` |
| S28 | MTR service index, `https://www.mtr.com.hk/en/customer/services/train_service_index.html` | EAL Admiralty–Sheung Shui headway bands: AM peak 2.7–5.5, PM 3.2, off-peak 4–8, Sat 3.8–8, Sun/PH 3.8–8 min | Band evidence only; the single `headway_s` values in the data/seed files are in-band modelling choices, not official point values. Other lines' bands not captured in this pass. |
| S29 | MTR getSchedule API, `https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php?line=EAL&sta=TAW&lang=en` | Snapshot 2026-09-24T12:25+08:00: UP ttnt 0/5/7/10, DOWN ttnt 3/6/8/12 | Operational snapshot, not a headway measurement; no value written into data files |
| S30 | iGeoCom CSV re-download (`open.hkmapservice.gov.hk` zip; inner `iGeoCOM_POI.csv` SHA-256 `d9703a97...efef5db` = the S23 file, byte-identical) | RSN rows extracted for all 16 modelled stations — six core match S23 exactly; ten non-core newly captured: DIH 541087, HOM 21070302, PRE 537817, MOK 545293, YMT 538316, JOR 537420, TST 537333, ETS 537798, WAC 545834, CEN 546117. Transformations via the official Geodetic API re-verified for the six core (exact match) and computed for the ten non-core. MTA access counts re-confirmed 8/11/4/14/6/7. | Same assurance as S23: official point records, not surveyed centroids, not walk-connectivity evidence. Non-core RSN coordinates were written to `data/network/stations.json` (documentation layer) but not to `data/access/station_entrances.json` (S23-structured, left untouched). |
| S31 | TD `ROUTE_BUS.xml` / `RSTOP_BUS.xml` / `ROUTE_GMB.xml` (`https://static.data.gov.hk/td/routes-fares-xml/`, generated 2026-09-11, fetched 2026-09-25) | Master rows + direction-specific stop sequences for every route in `data/network/bus_routes.json`: 182 (1051, $20.8), 182X (8307 中環→愉翠苑), N182 (1434, $31.2), 982X (8104/8308 AM + 8644 PM 金鐘站(東)→愉翠苑, $20.8), 985 (1174 AM + 8697 PM, $20.8), 985A (8704, $20.8), 985B (8705 田心村→灣仔(軒尼詩道), $20.8), 170 (1047/8470, $20.8), 81C (1336, $10.2), 87B (1370, $7.8), 80X (1333 秦石→觀塘碼頭), 82X (1345 濱景花園→黃大仙循環線), 83X (1348/8492 黃泥頭→觀塘碼頭), 280X (8229/8510), 88K (1380 顯徑→駿景園, row 2026-06-15 — NOT cancelled), 481B (GMB row 2003214, $12.3, row 2025-12-25). Exclusion re-check: 680/680X/681/682/682P/307/673/978/968/948X have no Tai Wai-area stops (978's only 田心 hit is the North-District place name 百福田心球場). 80M and 182P have no master rows. | Master row + stop sequence establish route/operator/OD/full-fare/stop-order, not headway, service calendar, section fares, capacity, or wheelchair features. `X,Y` in STOP_BUS remain untransformed HK grid coordinates. |
| S32 | **User-provided 982X timetable screenshots** (two direction panels, supplied in the M1 session on 2026-09-25) | Panel 1 往菲林明道 (Mon–Fri): 06:55, 07:15, 07:30, 07:39, 07:51, 08:04, 08:10 (gaps 20/15/9/12/13/6 min). Panel 2 往愉翠苑巴士總站, board code ST871 as displayed (Mon–Fri): 17:47, 17:55, 18:03, 18:11, 18:19, 18:27 (uniform 8-min gaps). Recorded verbatim in `bus_routes.json` 982X `schedule_evidence`. | The images show **no capture date and no verifiable official origin**; the times were **not** re-checked against an official source. They support only the two visible weekday panels — no off-peak, Saturday, Sunday, public-holiday, or opposite-direction claims. No provenance upgrade was made; 982X stays `real-derived` at record level and `headway_s` stays null because no single value can express the direction/time-varied gaps. OD correspondence to TD variants 8104/8644 is inferred from destinations; the screenshots do not display variant IDs. |

### Corrections applied to data/ (2026-09-25)

- `network/stations.json`: all 16 station coordinates replaced with official
  iGeoCom RSN points (S23/S30); the false "coordinates from MTR open data"
  claim removed; `accessible: true` now backed by per-station MTR barrier-free
  CSV rows (AJ codes cited in notes); BS_TAW drops 481B; BS_ADM_E drops
  985A/985B (no Admiralty-terminus master rows) and keeps 982X/985; piers
  downgraded to `real-derived` coordinates (OSM approximation) with operator
  service details verified.
- `network/lines.json`: GMB_481B removed from runnable lines (aligned with the
  seed's `missing_nodes_note`); BUS_982X/BUS_985B `weekday_peak` headways set
  to `null` with `headway_status: "unverified_exact_departures"` (aligned with
  seed); 982X full fare 16.0→20.8 and 985B 19.5→20.8 per S31; 81C fare 10.2
  added; 982X note corrected (three variants incl. PM 金鐘站(東) return);
  985B note records the 灣仔(軒尼詩道) terminus and the BS_ADM_E modelling gap;
  ERL provenance downgraded `real`→`real-derived` with field-level evidence
  notes (stop order, accessibility, headway band, fares verified; capacity and
  seg times remain estimates); KTL collapsed-stop note added; ferry
  timetable/fares/wheelchair marked verified.
- `network/bus_routes.json`: evidence basis switched from the unverifiable
  KMB API (S11) to TD XML (S31); per-route master rows, fares, boarding bays
  and corrections recorded (985B/985A/985 destinations → 灣仔(軒尼詩道); 83X →
  觀塘碼頭; 182X direction → 中環→愉翠苑; 80X/82X/280X origins specified);
  182P and 80M marked absent from master data; 88K confirmed NOT cancelled and
  excluded as a non-corridor local feeder instead; all exclusions re-verified
  against stop sequences; 481B verified via ROUTE_GMB with the runnable-network
  exclusion retained.
- `network/walk_links.json`: evidence note added — station-level lifts are
  verified but link-level step-free continuity (ETS↔TST walkway above all)
  remains unverified; no walk time changed.
- `access/access_points.json`: `ap_*` MTR-entrance `accessible` set to `null`
  (station-level evidence cannot be mapped to approximated entrances);
  481B/985A/985B removed from bus-stop line lists per S31; pointer to
  `station_entrances.json` as the authoritative access-point evidence.
- `calendar.json`: three holiday rows verified (S26); Mid-Autumn name aligned
  to the official GovHK string; ERL/BUS_182/BUS_170/GMB_481B operating-hours
  provenance downgraded to `real-derived` (MTR first/last-train page under
  maintenance 2026-09-25; KMB API unverifiable); ferry hours verified.

### Divergences from frozen contracts/seed (recorded, not reconciled here)

1. `network.seed.json` BUS_982X `fare_hkd [6.0, 16.0]` vs data/ `[6.0, 20.8]`;
   BUS_985B `[19.5, 19.5]` vs data/ `[20.8, 20.8]` — S31 master fares.
2. `network.seed.json` BUS_985B still models alighting at BS_ADM_E; current
   official 985B AM terminus is 灣仔(軒尼詩道) — modelling gap in both layers,
   contract stops untouched.
3. `routes.seed.json`/`sim.seed.json` are unchanged and keep their own
   simulated/evidence dispositions.
4. `network.seed.json` BUS_982X `headway_status` reads
   `unverified_exact_departures` while data/ now reads
   `no_single_headway_applicable_unverified_official` and additionally holds
   the S32 directional departures in `bus_routes.json` — the seed has no
   per-trip schedule field, so the divergence is informational only; the
   seed's null headways remain correct and were not touched.

### Gaps remaining after this pass (not fabricable from these sources)

1. 982X departures: only the two weekday panels of S32 are documented, from
   user-provided screenshots with no capture date or verifiable official
   origin — not operator-verified. No off-peak, Saturday, Sunday or
   public-holiday service evidence exists for 982X, so `headway_s` stays null
   and nothing beyond the panels may be claimed. 985B exact departures remain
   entirely unknown — do not infer.
2. Bus section fares (182 $16 claim, 982X $6 claim) — need stop-level fare
   tables (TD fare-stop files), not master full fares.
3. Star Ferry vessel capacity; typhoon suspension threshold.
4. Walk continuity: ETS↔TST walkway, WAC↔EXC ~700 m claim, all bus-stop walk
   links — no walk link promoted to verified.
5. Per-entrance step-free mapping for the abstract access points; live lift
   outage state is dynamic and unmodelled.
6. MTR first/last train times (page under maintenance on 2026-09-25).
7. Wheelchair suitability of KMB/CTB bus fleets per line (low-floor assumption
   unverified); 985B/985A/982X carry `accessible: true` at line level only.
8. ERL `seg_time_s` per-segment values remain estimates; the official ~17 min
   TAW→ADM end-to-end claim was not re-verified in this pass.
9. TML/KTL/TWL/ISL headway bands not re-verified against a current official
   page in this pass (only EAL was captured, S28).

## 2026-10-11: modelled first/last boarding windows

The earlier gap about MTR first/last trains is now partly addressed. The
`service_hours` values in `contracts/seed/network.seed.json` and
`data/network/lines.json` are **boarding windows at the first modelled stop**
in the listed direction; `service_hours_reverse` is at the last modelled stop
for the reverse direction. The route engine shifts a window to an intermediate
boarding stop using the modelled segment times. Those segment times and the
headway grid remain estimates, so these fields do not constitute an official
per-station timetable. Special holiday extensions and unplanned changes are
not modelled. A train already boarded may finish after the last boarding time.

| Line | Forward window / source | Reverse window / source |
| --- | --- | --- |
| ERL | Tai Wai toward Admiralty 05:40–00:31, [MTR Tai Wai](https://www.mtr.com.hk/en/customer/services/service_hours_search.php?query_type=search&station=67) | Admiralty toward Sheung Shui 06:04–00:22, [MTR Admiralty](https://www.mtr.com.hk/en/customer/services/service_hours_search.php?query_type=search&station=2) |
| TML | Tai Wai toward Tuen Mun 05:58–00:14, [MTR Tai Wai](https://www.mtr.com.hk/en/customer/services/service_hours_search.php?query_type=search&station=67); used conservatively for the modelled East Tsim Sha Tsui direction | East Tsim Sha Tsui toward Wu Kai Sha 06:01–00:45, [MTR East Tsim Sha Tsui](https://www.mtr.com.hk/en/customer/services/service_hours_search.php?query_type=search&station=80) |
| KTL | Diamond Hill toward Whampoa 05:59–00:37, [MTR Diamond Hill](https://www.mtr.com.hk/en/customer/services/service_hours_search.php?query_type=search&station=11) | Ho Man Tin 06:15–00:40 is a conservative **modelled estimate** from [MTR Yau Ma Tei](https://www.mtr.com.hk/en/customer/services/service_hours_search.php?query_type=search&station=5) toward Tiu Keng Leng (06:14–00:44) and the modelled 3.5-minute Ho Man Tin–Yau Ma Tei segment; it needs station-level verification |
| TWL | Yau Ma Tei toward Central 06:01–00:50, [MTR Yau Ma Tei](https://www.mtr.com.hk/en/customer/services/service_hours_search.php?query_type=search&station=5) | Central toward Tsuen Wan 06:06–00:54, [MTR Central](https://www.mtr.com.hk/en/customer/services/service_hours_search.php?query_type=search&station=1) |
| ISL | Central toward Chai Wan 06:07–00:58, [MTR Central](https://www.mtr.com.hk/en/customer/services/service_hours_search.php?query_type=search&station=1) | Wan Chai toward Kennedy Town 06:03–00:54, [MTR Wan Chai](https://www.mtr.com.hk/en/customer/services/service_hours_search.php?query_type=search&station=27) |
| SIL | Admiralty toward South Horizons 06:11–01:05, [MTR Admiralty](https://www.mtr.com.hk/en/customer/services/service_hours_search.php?query_type=search&station=2) | South Horizons toward Admiralty 06:00–00:42, [MTR South Horizons](https://www.mtr.com.hk/en/customer/services/service_hours_search.php?query_type=search&station=89); SIL has only one modelled stop and yields no routing edge |

MTR warns that last-train entry gates may close five minutes before the
published departure. The model checks whether a passenger can board at the
computed platform time; it does not model gate-entry or transfer walking time
beyond the existing graph links. The fixed frontend seed uses the same windows
to remove cards that would board a closed service, while keeping its journey
durations explicitly illustrative. Services without a configured window are
not globally blocked at night; an actual overnight line may still be returned.
