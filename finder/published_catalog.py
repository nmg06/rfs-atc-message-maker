"""Separate published timetable facts; never represented as ADS-B observations."""
SCHEMA = """
CREATE TABLE IF NOT EXISTS published_services (
 publication_id INTEGER PRIMARY KEY, service_key TEXT NOT NULL UNIQUE,
 source_id TEXT NOT NULL REFERENCES sources(source_id), airline TEXT NOT NULL REFERENCES airlines(icao),
 callsign TEXT NOT NULL, flight_number TEXT NOT NULL,
 origin_id INTEGER NOT NULL REFERENCES airports(id), destination_id INTEGER NOT NULL REFERENCES airports(id),
 aircraft TEXT REFERENCES aircraft_types(icao), aircraft_as_published TEXT NOT NULL,
 schedule_days TEXT NOT NULL, valid_from TEXT NOT NULL, valid_to TEXT NOT NULL,
 departure_local TEXT, arrival_local TEXT, duration_min REAL, published_on TEXT NOT NULL,
 source_movements TEXT NOT NULL,via_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS published_airline ON published_services(airline);
CREATE INDEX IF NOT EXISTS published_callsign ON published_services(callsign);
CREATE VIEW IF NOT EXISTS v_published_search AS SELECT
 NULL AS pattern_id, p.airline,p.callsign,p.origin_id,p.destination_id,p.aircraft,'[]' AS type_mix,
 0 AS n_obs,0 AS n_complete,0 AS n_active_days,p.duration_min,NULL AS duration_p10,NULL AS duration_p90,
 NULL AS distance_nm,NULL AS dep_local_min,NULL AS dep_spread_min,0 AS weekday_mask,
 p.valid_from||'T00:00:00+00:00' AS first_seen,p.published_on||'T00:00:00+00:00' AS last_seen,
 NULL AS latest_departure,NULL AS latest_arrival,p.source_id,
 a.name AS airline_name,a.iata AS airline_iata,t.model AS aircraft_model,t.manufacturer,t.family,
 o.icao AS origin,o.iata AS origin_iata,o.name AS origin_name,o.municipality AS origin_city,
 o.country AS origin_country,o.region AS origin_region,o.continent AS origin_continent,o.tz_iana AS origin_tz,
 d.icao AS destination,d.iata AS destination_iata,d.name AS destination_name,d.municipality AS destination_city,
 d.country AS destination_country,d.region AS destination_region,d.continent AS destination_continent,d.tz_iana AS destination_tz,
 'PUBLISHED_SCHEDULE' AS record_kind,p.publication_id,p.flight_number,p.aircraft_as_published,
 p.schedule_days,p.valid_from,p.valid_to,p.departure_local,p.arrival_local,p.published_on,p.source_movements,p.via_json
 FROM published_services p JOIN airlines a ON p.airline=a.icao
 JOIN airports o ON p.origin_id=o.id JOIN airports d ON p.destination_id=d.id
 LEFT JOIN aircraft_types t ON p.aircraft=t.icao;
"""
