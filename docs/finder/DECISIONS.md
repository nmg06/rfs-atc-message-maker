# Phase 1 decisions

- Keep PySide6 and existing Store/templates. Use a separate read-only SQLite aviation database; DuckDB and timezonefinder are build-time tools, not mandatory app imports.
- Sources: current `MrAirspace/aircraft-flight-schedules` Releases, OurAirports, VRS CC0 reference data, timezone-boundary-builder through timezonefinder. Inspect actual schemas before writing source adapters. Exclude `AC_Type_Detailed` and do not query adsbdb.
- Local-only Phase 1. No live APIs, LLM, server, PWA, RFS extraction or livery scraping. No new fuel model.
- Explicit minimum/maximum duration are hard limits. A target duration is a scored preference within its tolerance. Never relax explicit filters silently. Inconsistent simultaneous departure/arrival/duration constraints produce a visible error.
- Simulated chosen times and historical observations are separate. All datetime arithmetic uses UTC with IANA conversions. DST gaps shift to the first valid local minute; ambiguous times choose the earlier UTC instant and display a warning.
- Unknown fields stay unknown. Available runways are references, never selected automatically. Mapping retains existing manual fields and warns the user to review them; selection starts an unsaved flight instead of mutating a named saved flight.
- Finder UI text is centralized with English reference and French/Romanian overlays. Existing French generator UI is retained.
- Huge Parquet inputs remain external. A distributable derived database requires source attribution and ODbL information. Repository/build source excludes private JSON state.
- Phase 1 omits real-schedule projection, relaxation, livery compatibility and public services. Historical ADS-B coverage is not a guarantee of present-day airline operations.
