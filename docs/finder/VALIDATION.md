# Real-data validation — 2026-10-01

- Input: `2026_Q2_detailed_github.parquet`, current MrAirspace Releases repository.
- Raw rows: 14,040,611. Accepted before window/dedup: 4,120,896.
- Retained observations: 4,078,484. Patterns: 135,554.
- Searchable patterns (at least 3 complete tracks): 59,552. Airports: 19,786.
- Latest accepted departure: 2026-06-30 23:59:59 UTC.
- SQLite integrity check: `ok`; foreign-key check: no violations.
- SQLite size: 81,182,720 bytes. Raw 912 MB Parquet is not bundled in the executable.
- Build uses 1 GB DuckDB limit and per-airline aggregation. Native CSV batch ingestion
  avoids slow large Python-bound inserts. Intermediate tables are dropped after use.

Real search checks:

- LFPG + A320neo + around 120 min: 4 matches, including observed Iberia LFPG–LEMD.
- LFPG + available 120 min: 224 matches before result limit/diversity. Top results
  use about 116–117 min; the shortest route is not blindly preferred.
- Air India + Airbus + 570–660 min + exclude EGLL: no eligible match.
- Air India + A321neo: no eligible match with three complete observations.
  This is a dataset/coverage result, not evidence that the airline does not operate such routes.

`preview_finder.py` reproduces the searches and own-widget screenshots. The GUI was
inspected in dark mode with readable controls, result table, provenance and available
runways. Offscreen Qt on this Windows environment lacks usable font discovery;
visual QA uses the native Windows Qt platform, not the tofu-glyph offscreen capture.

Runtime searches never fetch live data. All observations are labelled historical,
stale data is signalled, and proposed simulator times are explicitly distinguished.
