# Local Flight Finder — Phase 1

Open **Flight Finder** from the desktop header. The optional aviation database is
`finder-data/aviation.sqlite` beside the executable. **Choose local database** can
select another compatible file. No Internet, API key or account is needed to search.
Without the database, the message generator still works.

## Search

All filters are optional. Airport codes accept ICAO or IATA, multiple values comma-separated.
Countries use ISO-2 codes; continents use AF/AN/AS/EU/NA/OC/SA; regions use OurAirports
ISO-subdivision identifiers. Airline name/ICAO/IATA, aircraft code/model, manufacturer
and known aircraft families are supported. `A320neo` resolves to `A20N` and `A321neo`
to `A21N`. Minimum/maximum durations are hard limits. Maximum alone prefers flights
that use the available time. A desired duration has a tolerance of max(30 min, 15%).

Dates are explicit, times optional, zones are IANA names (`Europe/Paris`,
`Asia/Kolkata`). Arrival-only means a simulator departure is calculated backwards
from typical duration. This is never displayed as a scheduled service. Departure
and arrival together are checked against duration constraints. DST anomalies are
reported. Airport-local display uses coordinates-derived IANA zones.

Results show historical callsign/route/type, duration median and P10–P90, sample
count, freshness, source attribution, and available runways. Runways are **not**
the runways actually used by the observed flight. Distance is great-circle, not
the length of an airway route. Durations exclude taxi/preparation. Aircraft may
have varied across observations; the displayed type is the modal observed type.

**USE THIS FLIGHT** patches the existing common flight fields. Unknowns do not
erase manual values. Check old runway/gate/fuel fields and other pilots when
changing routes. The named saved flight is not changed; save the new flight when
you want it in your list. The `selected_flight` metadata travels with saved flights.

## Rebuild the real database

Use Python 3.13 and a separate environment if desired:

```powershell
python -m pip install -r requirements-etl.txt
python -m finder.fetch_data --directory ../finder-inputs
python -m finder.importer --input ../finder-inputs --output finder-data/aviation.sqlite
python -m unittest discover -s tests -v
```

The explicit download command fetches the newest Parquet release plus public
reference CSVs. It does not run at application startup. The full source file is
around 912 MB for 2026 Q2; allow extra build disk/RAM. The app only needs the much
smaller resulting SQLite, **not** the Parquet or ETL dependencies.
The importer validates schema before projection, owns flights by source quarter,
uses a 90-day window relative to the latest accepted observation, deduplicates
minute/aircraft/route keys, conservatively resolves endpoints, and excludes
incomplete tracks from duration statistics. At least 3 observations retain a
pattern; at least 3 complete tracks make it searchable by duration.

Sources and hashes are in `manifest.json` and `aviation.report.json`. The report
also records actual schema, dependency versions, counts and database integrity.
Build output is staged as `.building`; a failed build does not replace the old DB.

## Limits and deviations

This phase uses a compact version-1 desktop schema, not every future normalized
table in the planning document: source versions/manifests are stored in build_info;
country/region codes are attached directly to airports. Callsign patterns and the
last five observations are retained; no separate route_stats/FTS/livery database.
Only observed-flight mode is exposed; no live or real-schedule projection.
Required filters are deterministic and never silently relaxed. Code/name aircraft
filtering and common explicit families replace a broad fuzzy alias engine.
The score renormalizes frequency (10), recency (5), completeness (5), duration
(30 when requested), arrival (25 only when not duplicating implied duration).
Airline/aircraft criteria are hard filters in this UI, not soft preferences.
Tie-breaking is stable; at most two results per airline/route; candidate cap 20,000
is reported so the user can refine a broad search.

## Data licences

- OurAirports airport/runway/country/region references: public domain.
- MrAirspace/aircraft-flight-schedules, derived from adsb.lol: ODbL 1.0.
- Virtual Radar Server airline/model references and source route validation: CC0.
- timezone-boundary-builder / OpenStreetMap boundary data: ODbL 1.0.

The derived aviation database is distributed under ODbL 1.0. Keep this notice,
source attributions, the licence text and rebuild instructions with a public
database release. This does not automatically assign the application code the
same licence. `AC_Type_Detailed` (adsbdb-enriched) is excluded. No RFS assets are
extracted or distributed. No guarantee of coverage or current operations is made.

The separately supplied RFS Fuel Helper is integrated through the **Carburant**
button and the same current-flight state. Its exact formulas and static catalogues
live in `fuel/`; the Finder does not invent a second fuel model. Choose the aircraft
variant explicitly before calculating fuel for a selected route.

Phase 2: better autocomplete/geographical groups, richer route views and aliases,
manually verified livery compatibility, and the requested mobile/PWA version.
No online service is part of this build.

La liste d’avions PC et Android indique les profils historiques disponibles.
Voir [Cargo, petits avions et sources d’horaires officiels](CARGO_AND_SMALL_AIRCRAFT.md) pour les
chiffres vérifiés et les limites de couverture.
