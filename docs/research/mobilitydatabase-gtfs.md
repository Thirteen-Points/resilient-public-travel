# Hong Kong GTFS / Mobility Database inspection

Inspected on 2026-10-11 following the supplied [Mobility Database feed mdb-1924](https://mobilitydatabase.org/feeds/gtfs/mdb-1924).

## Existing use

This project had already inspected the upstream Transport Department feed: `data/PROVENANCE.md` S8, S20 and S24 record the dataset page, variable headway bands and stop coordinates. It had not implemented a full GTFS importer into the route engine, and there was no direct Mobility Database integration. The existing small runnable network remains a curated model.

## Download inspected

- Publisher: Hong Kong Government Transport Department.
- Official producer URL: https://static.data.gov.hk/td/pt-headway-en/gtfs.zip
- Archive SHA-256: `4316a8d9e3a82b326603bcba18ce60406eb861e8adb0c045973f4063d6b0fbbe`.
- 2,470 route records, 9,461 stop records, 82,675 trip records.
- Ten files: agency, calendar, calendar_dates, fare_attributes, fare_rules, frequencies, routes, stops, stop_times and trips.
- Route-type counts: 2,404 bus-type records, 59 ferry records, 6 tram/light-rail records and 1 funicular record. These are GTFS records, not a count of distinct passenger-facing routes.

Green minibuses have `agency_id=GMB` and `route_type=3`, so a mode adapter must identify GMB separately from other bus agencies. This feed has no heavy-rail route-type records; keep the existing MTR data source.

The feed includes route `2003214`, green minibus 481B, described as Tsuen Wan Market Street–Tai Wai (Tung Lo Wan Hill Road), supplementary service. A sampled seven-stop trip starts at stop `20007253` (Tung Lo Wan Hill Road, 22.38041, 114.18072) and ends at `20002178` (Tsuen Wan Market Street, 22.37166, 114.11698). Its sampled frequency band is 22:35–23:00 with a 1,500-second headway. That single sample is not a complete service timetable.

The invalid historical node `BS_TW` must not be reused. Any minibus integration should use official stop identifiers and complete stop sequences, establish service-calendar joins and actual connections to the modelled network, and retain unknown accessibility. This inspection does not reactivate 481B in the runnable network.

## Implications for integration

Join routes → trips → stop_times → stops for actual patterns and coordinates; join trips → calendar/calendar_dates and frequencies for service availability and time bands. Read fare_attributes/fare_rules with operator-specific fare rules, rather than assuming a single flat fare. Preserve provenance and snapshot identity, and make import/update failures visible.

This is aggregate GTFS Schedule data, not a live arrival feed. Stop coordinates do not establish walkable or step-free connections. The catalog currently reports a validation error; resolve the corresponding full validation report before claiming a validated complete import. No automatic full-network import was added during this frontend fix.

The downloaded archive and inspection output are in `.cache/hk-gtfs.zip` and `.cache/hk-gtfs-inspection.json`. The compact inspection output is also retained beside this note as `hk-gtfs-2026-10-11.json`.

## Frontend fix delivered

The planner now exposes All modes / MTR / Bus / Minibus / Ferry, searches all modelled stations, bus stops and piers, and shows the complete returned candidate list. `required_modes` filters the engine before route diversity and ranking, so selecting Ferry retains necessary rail/bus/walking feeders. The fixed seed applies the same filter. Missing verified minibus service is displayed explicitly instead of silently returning a rail journey.
