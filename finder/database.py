"""Read-only runtime database and versioned build schema."""
from pathlib import Path
import sqlite3
from contextlib import contextmanager

SCHEMA = """
PRAGMA user_version=1;
PRAGMA foreign_keys=ON;
CREATE TABLE sources (source_id TEXT PRIMARY KEY, name TEXT, url TEXT, license_spdx TEXT, attribution_text TEXT);
CREATE TABLE build_info (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE airports (
 id INTEGER PRIMARY KEY, icao TEXT UNIQUE, iata TEXT, name TEXT NOT NULL,
 municipality TEXT, country TEXT, region TEXT, continent TEXT,
 latitude REAL, longitude REAL, tz_iana TEXT, type TEXT);
CREATE TABLE runways (
 id INTEGER PRIMARY KEY, airport_id INTEGER REFERENCES airports(id),
 le_ident TEXT, he_ident TEXT, length_ft INTEGER, width_ft INTEGER,
 surface TEXT, lighted INTEGER, closed INTEGER);
CREATE TABLE airlines (icao TEXT PRIMARY KEY, iata TEXT, name TEXT, radio_callsign TEXT, country TEXT);
CREATE TABLE aircraft_types (icao TEXT PRIMARY KEY, model TEXT, manufacturer TEXT, family TEXT);
CREATE TABLE flight_patterns (
 pattern_id INTEGER PRIMARY KEY, airline TEXT REFERENCES airlines(icao), callsign TEXT,
 origin_id INTEGER NOT NULL REFERENCES airports(id), destination_id INTEGER NOT NULL REFERENCES airports(id),
 aircraft TEXT REFERENCES aircraft_types(icao), type_mix TEXT,
 n_obs INTEGER NOT NULL, n_complete INTEGER NOT NULL, n_active_days INTEGER,
 duration_min REAL, duration_p10 REAL, duration_p90 REAL, distance_nm REAL,
 dep_local_min INTEGER, dep_spread_min INTEGER, weekday_mask INTEGER,
 first_seen TEXT, last_seen TEXT, latest_departure TEXT, latest_arrival TEXT,
 source_id TEXT REFERENCES sources(source_id));
CREATE TABLE recent_observations (
 pattern_id INTEGER REFERENCES flight_patterns(pattern_id), departure_utc TEXT,
 arrival_utc TEXT, aircraft TEXT, complete INTEGER);
CREATE INDEX pattern_route ON flight_patterns(origin_id,destination_id);
CREATE INDEX pattern_airline ON flight_patterns(airline,aircraft);
CREATE INDEX pattern_dest ON flight_patterns(destination_id);
CREATE INDEX pattern_aircraft ON flight_patterns(aircraft);
CREATE INDEX pattern_duration ON flight_patterns(duration_min);
CREATE INDEX pattern_ranking ON flight_patterns(n_obs DESC, last_seen DESC);
CREATE INDEX runway_airport ON runways(airport_id);
CREATE INDEX airport_iata ON airports(iata);
CREATE VIEW v_pattern_search AS SELECT p.*,
 a.name AS airline_name, a.iata AS airline_iata,
 t.model AS aircraft_model, t.manufacturer, t.family,
 o.icao AS origin, o.iata AS origin_iata, o.name AS origin_name,
 o.municipality AS origin_city, o.country AS origin_country,
 o.region AS origin_region, o.continent AS origin_continent, o.tz_iana AS origin_tz,
 d.icao AS destination, d.iata AS destination_iata, d.name AS destination_name,
 d.municipality AS destination_city, d.country AS destination_country,
 d.region AS destination_region, d.continent AS destination_continent, d.tz_iana AS destination_tz
 FROM flight_patterns p JOIN airlines a ON p.airline=a.icao
 JOIN aircraft_types t ON p.aircraft=t.icao
 JOIN airports o ON p.origin_id=o.id JOIN airports d ON p.destination_id=d.id;
"""


@contextmanager
def connect_readonly(path: Path):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError("DATA_UNAVAILABLE")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA trusted_schema=OFF")
    try:
        if connection.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ValueError("UNSUPPORTED_DATABASE_VERSION")
        yield connection
    finally:
        connection.close()
