# CODEX_TASK.md — Implement Flight Finder, Phase 1

You are implementing **Phase 1** of the RFS Flight Finder inside an existing application (a companion app for the mobile game Real Flight Simulator). Read this whole file first. Then read the four spec files in `docs/finder/`:

- `RFS_FLIGHT_FINDER_SPEC.md` (architecture, scope, UI, integration)
- `DATA_SOURCES.md` (licences, limits, import notes)
- `DATABASE_SCHEMA.md` (DDL, staging rules, `SelectedFlight` contract)
- `SEARCH_ENGINE.md` (exact algorithm, formulas, tests)

If this file and those specs disagree, **stop and report the conflict** instead of choosing silently.

The spec files are written in French; this file is in English. Code, identifiers, comments and the reference locale (`en.json`) must be in English.

---

## 0. Non-negotiable rules

1. **No AI/LLM at runtime.** Search, ranking and time logic are deterministic code. No randomness. No network calls in the search path.
2. **No reverse engineering of RFS.** Do not decompile the APK, extract game files, bypass protections, scrape Rortos properties, or bulk-copy livery images. RFS compatibility data comes only from hand-maintained seed CSVs.
3. **Never invent data.** Unknown stays `null`/`UNKNOWN`. No default passenger counts, cargo, runway in use, cruise level, or durations for unobserved routes.
4. **No hardcoded UTC offsets.** Times use IANA zone ids and a pinned tz library. Never write `+1`, `+2`, `hours=1` for "France". The server's own timezone must never influence results.
5. **No API key, database file, or scoring weight in the frontend bundle.** Keys live in server environment variables only.
6. **No live-data dependency.** The Finder must work with no paid API and no outbound network at search time.
7. **Every user-visible string goes through i18n.** No hardcoded UI text anywhere. Backend returns codes + params, never prose.
8. **Finder is a separate module.** Other modules depend only on the `SelectedFlight` contract. The Finder must be removable with a feature flag without breaking anything.
9. **Do not commit datasets.** Raw Parquet/CSV and built `.sqlite` files are gitignored. Commit only code, config, schemas, and small seed CSVs.
10. **Keep the two databases separate.** `aviation.sqlite` (derived from ODbL data) and `rfs_compat.sqlite` (hand-maintained, proprietary) are different files.
11. **Do not rewrite existing Discord message templates.** Only bind their input data to `SelectedFlight`.
12. **Parameterised SQL only.** No string-concatenated queries.
13. **Small, reviewable commits.** One step below = one or more commits. Run tests before each commit.

---

## Step 0 — Audit the existing repository (do this first, change nothing)

The spec authors could **not** inspect the repository. Do not assume its framework or layout.

Produce `docs/finder/REPO_AUDIT.md` containing, from direct inspection:

- Language(s), framework(s), package manager, build tool, test runner, linter, formatter.
- Is the app client-only, or is there a backend? Where is it deployed? (Look at configs, CI, Dockerfiles, hosting files.)
- Where the Fuel logic/data lives, and the identifiers it uses for aircraft.
- Where the Discord message generators live (ATC REQUEST, AIRBORNE, ARRIVAL BOARD, FLIGHT COMPLETED, ATC ACTIVE, ATC OFFLINE), and how they take input.
- Current i18n approach if any; how UI text is currently stored.
- Current state-management pattern (store, context, etc.).
- Any existing timezone/date library.
- Conventions to follow (folder structure, naming, error handling).
- Proposed placement of: `src/.../finder` module, API routes, shared `selected-flight` module, ETL (`tools/finder_etl/`), seed data (`data/finder/seed/`), locales.

**Decision gate.** If the app has **no backend**, propose the smallest backend that can host `finder-api` (language matching the repo where possible; otherwise a small Python or Node service), explain hosting implications, and implement it only as a thin, isolated service. Do not restructure the existing app.

**STOP and ask the maintainer** only if: (a) the repo cannot run tests, (b) there is no feasible place for a server component, or (c) existing i18n conflicts with `locales/{en,fr,ro}.json`. Otherwise proceed and record decisions in `docs/finder/DECISIONS.md`.

---

## Step 1 — Fetch one real dataset and inspect it (before writing any ETL)

Column names in the specs come from READMEs, not from real files.

1. Write `tools/finder_etl/fetch.py` that downloads into `data/finder/raw/` (gitignored):
   - OurAirports: `airports.csv`, `runways.csv`, `countries.csv`, `regions.csv` from `https://davidmegginson.github.io/ourairports-data/`.
   - VRS standing-data: CSV files from the repo `vradarserver/standing-data` (use the CSVs, **not** any compiled `.sqb`): `airlines/schema-01`, `routes/schema-01`, `model-type/schema-01`.
   - MrAirspace: the **most recent** quarterly Parquet, and the previous one if available. The README links its Releases to `MrAirspace/aircraft-flight-logs`; locate where the files actually are, record the exact URL, and do not guess.
   - Record `sha256`, size, retrieved-at for each file in `data/finder/raw/manifest.json`.
2. Run DuckDB `DESCRIBE` and sample queries on the Parquet. Write `docs/finder/MRAIRSPACE_OBSERVED_SCHEMA.md` with real column names, types, null/placeholder conventions (the README says missing values appear as `-`), the exact format of `Track_*_ApplicableAirports` (delimiter, multiple values) and `Route_Validation_Based_on_Callsign`, and value distributions for `Track_*_FL_Ft`.
3. Do the same for the VRS airline and route CSVs (columns, keys, how IATA/ICAO are stored) → `docs/finder/VRS_OBSERVED_SCHEMA.md`.
4. **Update `DATABASE_SCHEMA.md` §3 mapping table** wherever reality differs, and note each change in `DECISIONS.md`.

If network access is unavailable, stop and ask for the files to be placed in `data/finder/raw/`.

---

## Step 2 — ETL (`tools/finder_etl/`, Python ≥ 3.11 + DuckDB)

Regardless of the app's language, the ETL is Python: DuckDB's Python client and `timezonefinder` are first-class there, and the ETL is an offline build step.

Structure (adapt names, keep responsibilities):

```
tools/finder_etl/
  pyproject.toml            # pin duckdb, timezonefinder, tzdata, pyyaml, pytest
  config/finder.yaml        # thresholds (below)
  config/finder.weights.yaml
  finder_etl/
    fetch.py  load_airports.py  load_airlines.py  load_flights.py
    resolve_airports.py  aggregate.py  timezones.py  build_db.py  report.py
  tests/
data/finder/seed/           # committed, small
  aircraft_families.csv  aircraft_type_aliases.csv  continent_overrides.csv
  geo_groups.csv  geo_group_members.csv  airline_aliases.csv
  rfs_aircraft.csv  rfs_type_map.csv  rfs_liveries.csv
```

### 2.1 Config defaults (`finder.yaml`)

```yaml
window_days: 90
min_obs_pattern: 3
min_complete_for_duration: 3
min_duration_minutes: 15
max_duration_minutes: 1200
dedupe_minute_bucket: 1
recent_obs_per_pattern: 5
low_coverage_regions: []      # list of ISO2 countries/continents, filled by maintainer
```

### 2.2 Flights pipeline (implement exactly; see DATABASE_SCHEMA.md §3)

1. Read Parquet via DuckDB `read_parquet` with **only the needed columns** (projection) and filters pushed down. Never convert to JSON. Never load whole files into pandas.
2. Quarter overlap: keep rows whose month of `Track_Origin_DateTime_UTC` belongs to the file's quarter. **Do not use `DISTINCT`/`drop_duplicates`.**
3. Placeholder handling: `'-'` and empty → NULL. Rows lacking either timestamp are rejected (count them).
4. Airport resolution per DATABASE_SCHEMA.md §3.1 (`TRACK` or `CALLSIGN_VALIDATED`, else reject). Never "repair" by guessing nearest airport.
5. Quality filters per §3.2. Require `airline_icao` to exist in `airlines`. Reject `origin == dest`. Reject duration outside `[min,max]`.
6. Dedupe linked-track duplicates by `(icao_hex, dep_utc rounded to minute, origin, dest)`.
7. Durations computed **only** from `is_complete` flights (both ends `ground`). `n_obs` counts all accepted flights; `n_complete` counts complete ones.
8. Distance: great-circle (WGS84 geodesic or haversine, document which) in nautical miles between airport coordinates.
9. Local departure time and local weekday are computed at the **origin's IANA zone on the flight's date** (so DST shifts UTC but not the airline's local schedule).
10. `dep_local_min_median` and `dep_local_min_spread` use **circular** statistics over 1440 minutes (23:50 and 00:10 must give ~00:00, not 12:00).
11. `weekday_mask` bit0 = Monday … bit6 = Sunday, local date at origin.
12. `flight_number_iata`: if callsign matches `^[A-Z]{3}[0-9]{1,4}[A-Z]?$` and the airline has an IATA code, then `iata + digits` with `flight_number_source='DERIVED_FROM_CALLSIGN'`; otherwise `NULL` / `'NONE'`. Do not guess for other shapes.
13. Patterns: group by `(airline, callsign, origin, dest)`, then split into separate patterns when local departure clusters differ by more than a configurable gap (default 90 min); `type_icao` = most frequent, `type_mix_json` if more than one.
14. Drop patterns with `n_obs < min_obs_pattern`. Keep `route_stats` with the same threshold.

### 2.3 Airports, timezones, airlines

- Load OurAirports into `airports`/`runways`/`countries`. Apply `continent_overrides.csv` to fill `continent` (keep `continent_raw`).
- Timezone: `timezonefinder.timezone_at(lng, lat)` for every airport used by an accepted flight (and all airports with `scheduled_service='yes'`). On no result: `tz_iana = NULL`. Store versions in `tz_source` and `build_info`.
- **Test the continent edge cases** (Russia, Türkiye, Georgia, Armenia, Azerbaijan, Kazakhstan, Egypt, Cyprus) and record what OurAirports returns in `DECISIONS.md`; add overrides only with a written reason.
- Airlines from VRS `airlines`; build `airline_aliases` from name/ICAO/IATA normalised (lowercase, accent-stripped).
- Aircraft types: derive `manufacturer`/`model` from `AC_Type_Description` when parseable, else from VRS `model-type`; unknown → `NULL`. Seed `aircraft_families.csv` with the obvious families (A220, A320 family, A330, A340, A350, A380, B737NG, B737 MAX, B747, B757, B767, B777, B787, E-Jet, CRJ, ATR…) **only for type codes that appear in the data**, and have the maintainer review it. Do not guess rare codes.

### 2.4 Outputs

`data/finder/build/aviation.sqlite`, `data/finder/build/rfs_compat.sqlite` (from the seed CSVs), and `data/finder/build/etl_report.json` containing: row counts per table, file size, rejects per reason, resolution mix, top airlines/routes, tool versions, tzdata version, dataset versions. `PRAGMA integrity_check` and `PRAGMA foreign_key_check` must return clean.

### 2.5 ETL tests

Use a tiny hand-written Parquet/CSV fixture: quarter-overlap handling, placeholder `-` handling, multi-airport resolution, callsign validation fallback, circular median at midnight, local weekday vs UTC weekday, DST-crossing flights, duplicate removal, rejection counters.

---

## Step 3 — Seed data for RFS compatibility (no fabrication)

Create headers and **only rows you can justify**:

- `rfs_aircraft.csv`, `rfs_type_map.csv`, `rfs_liveries.csv` with the columns in DATABASE_SCHEMA.md §5.
- Every row you add has `verified=0` and a `source` saying exactly where it came from, unless the maintainer supplies verified data.
- `rfs_liveries.csv` ships with headers only.
- Provide `tools/finder_etl/import_rfs_csv.py` to validate a maintainer-edited CSV (required `source` when `verified=1`, dates in ISO format, known `type_icao`/`airline_icao`).

Do not attempt to derive RFS data from the game, its files, or any scraping.

---

## Step 4 — Search engine (pure functions)

Implement `SEARCH_ENGINE.md` exactly, in the repo's primary backend language:

- `local_to_utc(date, time, tz)` with gap/ambiguity policy (§3.1).
- `resolve_sim_times(...)`, `next_occurrences(...)`.
- Criteria parsing/validation; candidate SQL builder with bound parameters; scoring (§7); sort/diversity (§8); relaxation (§9); response builder (§10).
- Inject the clock (`now_utc`) and tz library; never read system time or system tz inside the engine.
- Weights from `config/finder.weights.yaml`; never sent to the client.
- `search_mode: "routes"` (§6).
- `real_routes_only=false` → error code `NOT_SUPPORTED_PHASE1`.

Write the tests in SEARCH_ENGINE.md §12: unit, golden (fixture DB + 15 queries with frozen expected output), determinism (run under `TZ=America/Los_Angeles`, `TZ=Asia/Tokyo`, different locale), properties, honesty checks. DST cases are mandatory (`Europe/Paris` 2026-03-29 and 2026-10-25, plus `Asia/Kolkata`, `Australia/Lord_Howe`, `Africa/Casablanca`, `Pacific/Kiritimati`). Include the test: on 2026-09-30, "tomorrow 07:00 Europe/Paris" resolves to `2026-10-01T05:00:00Z`.

---

## Step 5 — API

Routes (names adapt to repo conventions; keep the contract):

| Route | Purpose |
|---|---|
| `POST /api/finder/search` | body = `SearchCriteria` → `SearchResponse` |
| `GET /api/finder/flight/{pattern_id}` | detail: runways (static list), tz info, freshness, recent observations, RFS compat |
| `GET /api/finder/suggest/airports?q=` | FTS5 search |
| `GET /api/finder/suggest/airlines?q=` | alias search |
| `GET /api/finder/suggest/aircraft?q=` | alias search |
| `GET /api/finder/meta` | `build_info`, dataset versions, attribution strings |
| `GET /api/finder/health` | DB open + version check |

Requirements: strict input validation with schema; rate limiting; `limit ≤ 50`; no bulk-export endpoint; CORS restricted; errors as `{code, params}`; open both SQLite files read-only; refuse to start if `PRAGMA user_version` does not match; no secrets in logs.

Stub (do not implement calls) `LiveProvider` and `FlightPlanProvider` interfaces behind feature flags, returning `NOT_ENABLED`. Phase 1 must not contact any third-party service at runtime.

---

## Step 6 — UI module + i18n

- Simple/Advanced forms and result list per SPEC §5. Autocomplete through `/suggest/*`. The user's timezone defaults to the browser's (`Intl.DateTimeFormat().resolvedOptions().timeZone`) and is changeable.
- Show: provenance/status badges, `DURATION_IS_AIRBORNE`, relaxation notices, `TIME_INCONSISTENT`, `LOW_COVERAGE_REGION`, data freshness, and the number of candidates removed by exclusions.
- Detail view shows **"Runways available"** only. Never "Actual runway".
- Never display "scheduled" for any flight. Allowed wording: "observed", "based on observed pattern".
- **USE THIS FLIGHT** writes `SelectedFlight` (DATABASE_SCHEMA.md §8). Add "Clear selected flight".
- Wrap the module in an error boundary; failure must not break other modules.
- Page "Data & licences" showing the four attribution strings from DATA_SOURCES.md §12, dataset versions and dates.

### i18n

- Files: `locales/en.json` (reference), `locales/fr.json`, `locales/ro.json`. Use the repo's i18n library if one exists; otherwise add a small ICU MessageFormat one.
- Namespaced keys, for example:

```json
{
  "finder.title": "Flight Finder",
  "finder.search.submit": "Search",
  "finder.results.count": "{count, plural, one {# flight} other {# flights}}",
  "finder.warning.TIME_INCONSISTENT": "Departure, arrival and duration do not match: the implied duration is {implied}.",
  "finder.status.OBSERVED": "Observed",
  "finder.status.ESTIMATE": "Estimate",
  "finder.rfs.VERIFIED": "RFS compatible (verified {date})",
  "finder.rfs.UNKNOWN": "RFS compatibility unknown"
}
```

- Romanian needs `one` / `few` / `other` plural categories. Provide all three where counts appear.
- Dates/times via `Intl` with explicit IANA zone and the active locale.
- Add `scripts/i18n-check`: every key in `en.json` exists in `fr.json` and `ro.json`; no unused keys; grep-based check for hardcoded user-visible strings in finder code; fail CI on violations.
- Provide reasonable fr/ro translations, flagged in the PR description as machine-drafted and needing native review.

---

## Step 7 — Integration through `SelectedFlight`

1. Create a minimal shared module `selected-flight` with the JSON Schema (`schemas/selected_flight.schema.json`), typed accessors in the repo's language, a store (using the repo's state pattern), and validation on write.
2. **Fuel adapter**: map `type_icao` to the Fuel module's aircraft ids through an explicit table (`data/finder/seed/fuel_aircraft_map.csv`, created from the audit). Unmapped → Fuel prompts the user. Pass origin/destination ICAO, distance, duration.
3. **Discord/ATC adapter**: bind airline, aircraft, callsign, departure, arrival, and runway/cruise level **only if** `status ∈ {USER_INPUT, VERIFIED}`. Fields with `ESTIMATE`, `LIKELY`, `UNKNOWN` are left empty and the UI asks for input. Escape Discord markdown and `@` mentions in every data-derived string.
4. Tests: a `SelectedFlight` with an `ESTIMATE` passenger count must never reach a generated message; unknown runway stays unknown; removing the Finder via feature flag leaves Fuel/ATC working with manual input.

---

## Step 8 — Documentation and operations

- `docs/finder/README.md`: how to run the ETL, rebuild, deploy the two SQLite files, roll back, refresh cadence (OurAirports monthly, MrAirspace per new quarter).
- Add a CI job: lint, unit tests, ETL fixture tests, i18n check, a grep that **fails** if `.sqlite`, `.parquet`, or an API key pattern appears in the frontend build output.
- `docs/finder/DECISIONS.md`: every deviation from the specs, with reason.

---

## Definition of done (Phase 1)

All ten acceptance criteria in `RFS_FLIGHT_FINDER_SPEC.md` §12 pass, plus:

- `etl_report.json` exists from a real build, with actual sizes and reject counts.
- Test suite green: ETL fixtures, engine unit/golden/determinism/property tests, integration tests.
- No string literal visible to users outside `locales/`.
- No third-party network call in the search path (verify with a test that runs with networking blocked).
- `git status` shows no dataset or database files tracked.

---

## Explicitly out of scope for this task

Live/Today checks, AeroDataBox/FlightAware calls, Flight Plan Database calls, liveries data, "likely runway" from wind, virtual/estimated routes, offline search in the client, accounts/authentication, any modification of existing Discord templates or of the Fuel calculation logic.

---

## When to stop and ask

- The Parquet columns are materially different from the README (missing time or airport fields).
- The repository contains secrets or data that suggest a different deployment model.
- A licence question arises that is not covered in `DATA_SOURCES.md` §12.
- A choice would affect the `SelectedFlight` contract.

Otherwise: decide, write the decision in `DECISIONS.md`, and continue.
