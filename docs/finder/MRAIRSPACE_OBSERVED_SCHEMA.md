# Actual Parquet inspection — 2026-10-01

Source: release `aircraft_flight_schedules_2026_quarter2`, asset
`2026_Q2_detailed_github.parquet`, 911,949,077 bytes. Downloaded from the current
`MrAirspace/aircraft-flight-schedules` repository. Inspected locally using
DuckDB 1.5.6 `DESCRIBE SELECT * FROM read_parquet(?)` before implementing the importer.

All 18 fields are nullable `VARCHAR` (including coordinates and UTC timestamps):

```
ICAO_Hex
Reg
AC_Type
AC_Type_Description
AC_Type_Detailed
Airline
Callsign
Track_Origin_Lat
Track_Origin_Lon
Track_Origin_FL_Ft
Track_Origin_DateTime_UTC
Track_Origin_ApplicableAirports
Track_Destination_Lat
Track_Destination_Lon
Track_Destination_FL_Ft
Track_Destination_DateTime_UTC
Track_Destination_ApplicableAirports
Route_Validation_Based_on_Callsign
```

Observed encodings: `ICAO_Hex='icaohex-000100'`; timestamp
`2026-04-04 09:58:32`; endpoint height `ground` or numeric text;
airport candidates `['LIML']` or multiple quoted codes; missing values `-`,
`nan`; route validation `VIDP-EGLL`. Times lack a suffix but the source defines
them as UTC. Multi-airport ground endpoints exist. Validation endpoints can
disagree with candidates: those ambiguous/inconsistent endpoints are rejected.
`AC_Type_Detailed` is inspected as a column name only and never imported.

The importer validates required names/types and uses explicit projection,
TRY_CAST for timestamps, quarter ownership, conservative endpoint resolution,
and complete-track-only duration statistics. Build manifest records hashes.
