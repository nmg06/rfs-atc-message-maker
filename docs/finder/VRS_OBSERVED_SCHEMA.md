# VRS CSV inspection — 2026-10-01

`airlines/schema-01/airlines.csv` actual header:
`Code,Name,ICAO,IATA,PositioningFlightPattern,CharterFlightPattern`.
Only nonblank three-letter ICAO rows are airline references. No radio callsign
or country column exists here; those fields remain unknown.

`model-type/schema-01/A.csv` actual header:
`ICAO,Manufacturer,Model,Engines,EngineTypeCode,EnginePlacementCode,SpeciesCode,WakeTurbulenceCode,IsActive`.
The model files are split by initial A–Z, **not** a single `model-type.csv`.
There are multiple rows per ICAO type; the importer uses active rows and a
deterministic model label. It never infers detailed variants from a generic type.

Route validation in Phase 1 uses the actual callsign validation column already
present in the MrAirspace asset. No separate VRS route mirror is needed.
