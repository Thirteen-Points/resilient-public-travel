# Fare database

The route engine reads SQLite `backend/app/data/fares.sqlite3`. Set
`FARE_DB_PATH` to override it; otherwise it is placed beside the configured
`DB_PATH`. Persist it on the backend disk and back it up using SQLite tools.
It is runtime data and is excluded from Git and demo archives.

The first startup imports `data/network/fares.json` only if the database has
no service bindings. Existing database prices survive restart, changes to
that bootstrap file, and redeployment. The bootstrap covers the planning
graph so an offline first launch works without an internet connection.

## Official imports

Run from the repository root with backend dependencies installed:

```powershell
python -m scripts.refresh_fares --download
```

This downloads the complete MTR fares/stations CSVs, TD bus route/stop/section
XMLs and Star Ferry's Central–Tsim Sha Tsui XLSX. Amounts are parsed from the
sources; the importer contains no price constants. For previously downloaded
sources or offline operation:

```powershell
python -m scripts.refresh_fares --source-dir .cache --database backend/app/data/fares.sqlite3
```

Expected file names are `mtr_lines_fares.csv`, `mtr_lines_and_stations.csv`,
`ROUTE_BUS.xml`, `RSTOP_BUS.xml`, `FARE_BUS.xml`, and `starferry_fares.xlsx`.
All prices and stop mappings are replaced in one transaction. Malformed
data rolls back the import. Run this command whenever official fare data
changes; no recurring scheduler is configured by this change.

## Tables and prices

| Table | Stores |
| --- | --- |
| `fare_prices` | Service, origin/destination, direction, passenger/payment class, day/deck, validity dates, integer cents, source |
| `fare_catalog` | Official services/operators, including services outside the planning graph |
| `fare_locations` | MTR station identifiers and names |
| `fare_services` | Planning-line bindings to official pricing services and ticket groups |
| `fare_stop_aliases` / `fare_alias_evidence` | Modelled bus nodes mapped to direction-specific official stop sequences and IDs |
| `fare_interchanges` | Ticket-group walking interchanges and time limits |
| `fare_sources` | Official URLs, SHA-256 checksums and import timestamps |
| `fare_meta` | Revision used to invalidate route caches |

Amounts are integer HKD cents. Runtime queries select tariffs applicable to
the Hong Kong journey date. `valid_from` is inclusive, `valid_until` exclusive;
the latest applicable `valid_from` wins. An empty start date means the source
does not supply a verified historical effective date. Current official
snapshots are not an archive of historical fares.

The current importer loads adult ordinary-class Octopus MTR fares, adult bus
fares and adult Star Ferry upper/lower-deck weekday/weekend/PH fares. It does
not infer discounts, passes, first class or personal eligibility. MTR line
changes share one entry/exit ticket; only the explicitly configured ETS/TST
Octopus interchange joins an out-of-gate walk into that ticket within 30
minutes. Other walks or modes end the ticket. Wheelchair routes use the
lower-deck adult ferry rate; concession eligibility is not assumed.

## Inspect and maintain

`GET /api/fares/status` reports the real database revision, mode counts,
graph bindings and source metadata. `GET /api/fares/lookup` reads a stored
fare including source/validity, e.g.:

```text
/api/fares/lookup?service_id=mtr:octopus&origin=TAW&destination=ADM&payment=octopus&at=2026-10-12T08:20:00%2B08:00
/api/fares/lookup?service_id=bus:1051&origin=20&destination=25&direction=1&at=2026-10-12T08:20:00%2B08:00
/api/fares/lookup?service_id=FERRY_TST_CEN&origin=*&destination=*&day_type=weekday&deck=upper&at=2026-10-12T08:20:00%2B08:00
```

Bus origins/destinations here are official `ON_SEQ`/`OFF_SEQ`, not modelled
nodes. The routing engine resolves the node aliases automatically. Missing
prices return unavailable; they never become a fixed fare or zero.

Changing a SQL price increments the revision. The next route query reads the
new version and price without restarting the process. Use `FareStore.price`
inside a transaction for a dated override; insert a new `valid_from` rather
than rewriting older tariffs when the effective date is known. Public fare
endpoints are read-only; updates use the backend importer or controlled SQL.

After updating the database, regenerate the fixed offline UI snapshot with
`python -m scripts.update_seed_fares`. Offline cards contain derived results
at their fixed journey date; live API calculations use the database directly.
