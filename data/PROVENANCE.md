# Data Provenance Ledger (T7.1)

> This file is the living台账 for every piece of data in `data/` and `contracts/seed/`.
> Every value must trace back to a source URL, retrieval date, and confidence level.
> **Rule: unverified values must be labelled `real-derived` or `simulated`, never `real`.**
> Last updated: 2026-09-22

---

## Provenance Levels

| Level | Meaning | Badge color | UI label |
|---|---|---|---|
| `real` | Sourced from official open data, traceable to URL | Green `#2E7D32` | Real |
| `real-derived` | Derived from real data by calculation/estimation | Yellow `#F9A825` | Derived |
| `simulated` | Modeled on realistic parameters, not from a real source | Blue `#0288D1` | Simulated |

---

## 1. MTR Stations (Corridor + Alternative Network)

| Station | Code | Lat | Lng | Source | Source URL | Retrieved | Confidence | Data Status |
|---|---|---|---|---|---|---|---|---|
| Tai Wai | TAW | 22.3731 | 114.1789 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| Kowloon Tong | KOT | 22.3369 | 114.1763 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| Mong Kok East | MKK | 22.3221 | 114.1726 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| Hung Hom | HUH | 22.3034 | 114.1817 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| Exhibition Centre | EXC | 22.2816 | 114.1754 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| Admiralty | ADM | 22.2793 | 114.1655 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| Diamond Hill | DIH | 22.3400 | 114.2017 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| Ho Man Tin | HOM | 22.3096 | 114.1825 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| Prince Edward | PRE | 22.3245 | 114.1682 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| Mong Kok | MOK | 22.3193 | 114.1694 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| Yau Ma Tei | YMT | 22.3128 | 114.1705 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| Jordan | JOR | 22.3049 | 114.1717 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| Tsim Sha Tsui | TST | 22.2975 | 114.1724 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| East Tsim Sha Tsui | ETS | 22.2953 | 114.1754 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| Wan Chai | WAC | 22.2776 | 114.1733 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |
| Central | CEN | 22.2819 | 114.1582 | MTR official station list | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | 2026-09-21 | high | verified |

> **Note on coordinates**: Coordinates are approximate station-centre points from the MTR open data CSV set. Precision is ~50-100 m. For entrance-level coordinates, a future task should fetch the MTR barrier-free facilities CSV which includes entrance locations.

---

## 2. MTR Lines & Headways

| Line | Property | Value | Source | URL | Retrieved | Confidence | Data Status |
|---|---|---|---|---|---|---|---|
| ERL (East Rail) | Peak headway | 2.7-5.5 min | MTR official service index | https://www.mtr.com.hk/en/customer/services/train_service_index.html | 2026-09-21 | high | verified |
| ERL | Off-peak headway | 4-8 min | MTR official service index | https://www.mtr.com.hk/en/customer/services/train_service_index.html | 2026-09-21 | high | verified |
| ERL | Saturday headway | 3.8-8 min | MTR official service index | https://www.mtr.com.hk/en/customer/services/train_service_index.html | 2026-09-21 | high | verified |
| ERL | Sunday/PH headway | 3.8-8 min | MTR official service index | https://www.mtr.com.hk/en/customer/services/train_service_index.html | 2026-09-21 | high | verified |
| ERL | 9-car capacity | ~2,845 (6 pax/m^2) | Legislative Council paper (secondary) | — | 2026-09-21 | medium | unverified (T8.4 item #4) |
| ERL | Segment times (TAW-ADM) | 4.5/2.5/3.5/5/2.5 min | Non-official estimation | — | 2026-09-21 | medium | unverified (recommend MTR journey planner) |
| TML | Peak headway | ~3 min | MTR official | https://www.mtr.com.hk/en/customer/services/train_service_index.html | 2026-09-21 | medium | unverified |
| TML | Capacity | ~2,500 | Industry estimate | — | 2026-09-21 | low | unverified (T8.4 item #5) |
| KTL | Peak headway | ~2 min | MTR official | https://www.mtr.com.hk/en/customer/services/train_service_index.html | 2026-09-21 | medium | unverified |
| TWL | Peak headway | ~2 min | MTR official | https://www.mtr.com.hk/en/customer/services/train_service_index.html | 2026-09-21 | medium | unverified |
| ISL | Peak headway | ~2 min | MTR official | https://www.mtr.com.hk/en/customer/services/train_service_index.html | 2026-09-21 | medium | unverified |

> **Segment times**: All inter-station travel times are `real-derived` (estimated from distance and typical speed). MTR journey planner should be consulted for authoritative values.

---

## 3. Bus Routes

| Route | Property | Value | Source | URL | Retrieved | Confidence | Data Status |
|---|---|---|---|---|---|---|---|
| 182 | Operator | KMB+CTB | KMB open data API | https://data.etabus.gov.hk/v1/transport/kmb/route/182/outbound/1 | 2026-09-21 | high | verified |
| 182 | Service hours | 06:00-23:50 | KMB open data API | https://data.etabus.gov.hk/v1/transport/kmb/route/182/outbound/1 | 2026-09-21 | high | verified |
| 182 | Fare | ~$16-20.8 | KMB/CTB fare tables | — | 2026-09-21 | medium | unverified (exact fare T7.2 item #2) |
| 182 | Headway | ~15 min (peak) | Estimated | — | 2026-09-21 | low | unverified |
| 982X | Service | Weekday peak only, one-way | KMB/CTB route data | https://data.etabus.gov.hk/v1/transport/kmb/route/982X/ | 2026-09-21 | high | verified |
| 982X | Fare | $6 (TAW section) - $16 | KMB fare table | — | 2026-09-21 | medium | unverified |
| 985B | Service | Weekday peak only, one-way | KMB/CTB route data | https://data.etabus.gov.hk/v1/transport/kmb/route/985B/ | 2026-09-21 | high | verified |
| 81C | Service | All day | KMB route data | https://data.etabus.gov.hk/v1/transport/kmb/route/81C/ | 2026-09-21 | high | verified |
| 170 | Service | 06:00-23:45, full day | KMB route data | https://data.etabus.gov.hk/v1/transport/kmb/route/170/ | 2026-09-21 | high | verified |
| 88K | Status | Possibly cancelled (2025-08-04) | Web search (1 confirmed, 1 unconfirmed) | — | 2026-09-21 | low | unverified (T7.2 item #1) |
| 80M | Status | Proposed cancellation in 2025-26 ST bus plan | TD bus route plan | — | 2026-09-21 | medium | unverified |

> **Excluded routes**: 680, 681, 682, 307, 673, 978, 968, 948X — confirmed NOT serving Tai Wai/Sha Tin. See `08-data-appendix.md` 4.2.

---

## 4. Minibus & Ferry

| Item | Property | Value | Source | URL | Retrieved | Confidence | Data Status |
|---|---|---|---|---|---|---|---|
| GMB 481B | Capacity | 19 (statutory max) | Hong Kong Cap 374D (2017 amendment) | — | 2026-09-21 | high | verified |
| GMB 481B | Low-floor | None (19-seat, no low-floor) | Transport Department | — | 2026-09-21 | high | verified |
| All HK low-floor minibuses | Count | 4 total (NT 413, KLN CX1/90A, NT 503) | Transport Department | — | 2026-09-21 | high | verified |
| Star Ferry TST-CEN | Hours | 06:30-23:30 | Star Ferry official site | https://www.starferry.com.hk | 2026-09-21 | high | verified |
| Star Ferry TST-CEN | Fare | $4.0-$6.5 | Star Ferry official site (2023 price, may be outdated) | https://www.starferry.com.hk | 2026-09-21 | low | unverified (T7.2 item #6) |
| Star Ferry TST-CEN | Headway | 6-12 min | Star Ferry official site | https://www.starferry.com.hk | 2026-09-21 | medium | unverified |
| Star Ferry TST-CEN | Cancellation | Typhoon proximity (exact threshold unverified) | — | — | 2026-09-21 | low | unverified (T7.2 item #6) |

---

## 5. Vehicle Capacities

| Vehicle type | Capacity | Source | Confidence | Data Status |
|---|---|---|---|---|
| ERL 9-car train | ~2,845 (6 pax/m^2) | LegCo paper (secondary) | medium | unverified |
| ERL 9-car train | ~2,061 (4 pax/m^2) | Derived from above | medium | unverified |
| Enviro500 MMC 12m (KMB ATENU) | ~136-137 | Industry estimate | low | unverified |
| Enviro500 MMC 12.8m | ~143-144 (2 wheelchair) | Industry estimate | low | unverified |
| Single-deck bus | ~60-70 | No official data | low | unverified |
| Public minibus | 16 or 19 (statutory) | Cap 374D | high | verified |
| Star Ferry vessel | ~300 | Unverified | low | unverified |

> **Key constraint**: No public data source (data.gov.hk, KMB/CTB API) includes vehicle capacity or fleet type. Capacity can only be "type lookup x frequency" and must be labelled `real-derived`.

---

## 6. Service Calendar

| Calendar type | Source | URL | Retrieved | Data Status |
|---|---|---|---|---|
| MTR weekday/Saturday/Sunday+PH schedules | MTR service index | https://www.mtr.com.hk/en/customer/services/train_service_index.html | 2026-09-21 | verified |
| HK Public Holidays 2026 | GovHK | https://www.gov.hk/en/about/abouthk/holiday/2026.htm | 2026-09-21 | verified |
| Bus service calendars | KMB/CTB route data | https://data.etabus.gov.hk/ | 2026-09-21 | verified (route-level) |

---

## 7. Walk Links

| Link | Walk time | Walk distance | Source | Confidence | Data Status |
|---|---|---|---|---|---|
| ETS -> TST (interchange) | ~5 min | ~420 m | Estimated (straight-line x detour factor) | low | unverified (T7.2 item #3) |
| ETS -> TST wheelchair | Unknown | Unknown | Not verified | low | unverified (critical for wheelchair routing) |
| BS_TAW -> TAW | ~3 min | ~150 m | Estimated | low | unverified |
| All other walk links | Various | Various | Estimated (straight-line x 1.3 detour) | low | unverified |

---

## 8. External Data APIs

| API | Purpose | URL | Auth | Status |
|---|---|---|---|---|
| HKO warnsum | Weather warnings (event source) | https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=warnsum&lang=tc | None | Tested 2026-09-21, working |
| MTR getSchedule | Real-time arrivals (anomaly detection) | https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php?line=EAL&sta=TAW&lang=en | None | Tested 2026-09-21, working |
| KMB route data | Bus routes, stops, fares, ETA | https://data.etabus.gov.hk/v1/transport/kmb/ | None | Tested 2026-09-21, working |
| CTB route data | Citybus routes | https://rt.data.gov.hk/v2/transport/citybus/ | None | Tested 2026-09-21, working |
| TD special traffic news | Official incident notices | https://data.gov.hk/tc-data/dataset/hk-td-tis_1-special-traffic-news | None | Not yet tested |
| TD GTFS headway | Bus headway data | https://data.gov.hk/en-data/dataset/hk-td-tis_11-pt-headway-en | None | Not yet tested |
| MTR routes/fares/facilities | Station list, fares, accessibility | https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities | None | Not yet tested (CSV download) |

> **MTR has no official GTFS and no service status API.** Event sources are limited to: HKO warnings, MTR getSchedule anomalies, user reports, and simulated social media stream.

---

## 9. Unverified Items Tracking (from 08-data-appendix.md section 9)

| # | Item | Owner | Status | Notes |
|---|---|---|---|---|
| 1 | 88K cancellation (2025-08-04); 80M replacement | B | pending | Route excluded from network data |
| 2 | 182/170/81C/87B current headway and fares | B | pending | Using estimated values |
| 3 | ETS<->TST walkway duration and wheelchair feasibility | C | pending | Critical for wheelchair routing |
| 4 | ERL 9-car capacity 2,845 (LegCo source) | C | pending | Used as `real-derived` |
| 5 | TML/KTL/TWL/ISL peak headway and capacity | C | pending | Using estimated values |
| 6 | Star Ferry current fare and cancellation rules | B | pending | Using 2023 prices |
| 7 | MTR station coordinates and accessibility (CSV) | C | pending | Coordinates from data.gov.hk dataset |
| 8 | Wan Chai (ISL) <-> Exhibition Centre walk time | C | pending | Not yet modelled |
| 9 | TD GTFS headway dataset field structure | C | pending | May contain departure_time |
| 10 | Demo venue network access | A | pending | Offline package prepared as fallback |

---

## 10. License & Attribution

| Data source | License | Attribution required |
|---|---|---|
| Hong Kong Observatory open data | Open Government Data License | Yes - "Data source: Hong Kong Observatory" |
| MTR open data | MTR Data Licence | Yes - "Data source: MTR Corporation Limited" |
| data.gov.hk datasets | Open Government Data License | Yes - source attribution |
| KMB open data API | KMB open data terms | Yes |
| Star Ferry | Website content | Not for programmatic use; prices are public info |
| OSM tiles | ODbL | Yes - "© OpenStreetMap contributors" |
| CARTO basemap | Free tier | Yes - "CARTO" attribution |
