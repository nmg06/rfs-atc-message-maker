"""Optional offline route evidence. Never supplies invented aircraft or durations."""
from .database import connect_readonly

SCHEMA = """
CREATE TABLE observed_routes (
 route_id INTEGER PRIMARY KEY, callsign TEXT NOT NULL,
 airline TEXT REFERENCES airlines(icao), origin_id INTEGER NOT NULL REFERENCES airports(id),
 destination_id INTEGER NOT NULL REFERENCES airports(id), confidence REAL NOT NULL,
 evidence_days INTEGER NOT NULL, n_obs INTEGER NOT NULL,
 first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, distance_nm REAL,
 source_id TEXT NOT NULL REFERENCES sources(source_id),
 UNIQUE(callsign, origin_id, destination_id));
CREATE INDEX observed_route_airline ON observed_routes(airline);
CREATE INDEX observed_route_origin ON observed_routes(origin_id);
CREATE INDEX observed_route_destination ON observed_routes(destination_id);
CREATE VIEW v_observed_routes AS SELECT r.*, a.name AS airline_name, a.iata AS airline_iata,
 o.icao AS origin, o.iata AS origin_iata, o.name AS origin_name,
 o.municipality AS origin_city, o.country AS origin_country, o.region AS origin_region,
 o.continent AS origin_continent, o.tz_iana AS origin_tz,
 d.icao AS destination, d.iata AS destination_iata, d.name AS destination_name,
 d.municipality AS destination_city, d.country AS destination_country, d.region AS destination_region,
 d.continent AS destination_continent, d.tz_iana AS destination_tz
 FROM observed_routes r LEFT JOIN airlines a ON r.airline=a.icao
 JOIN airports o ON r.origin_id=o.id JOIN airports d ON r.destination_id=d.id;
"""


def search_routes(path, criteria, now, *, include_population=False):
    from .search import parse_airport_codes
    # Unknown fields must never pass filters as if known, or silently be ignored.
    if any(getattr(criteria, key) for key in ('aircraft', 'aircraft_types', 'manufacturer', 'family',
            'rfs_only', 'rfs_aircraft_id', 'min_minutes', 'max_minutes', 'target_minutes',
            'departure_time', 'arrival_time')):
        raise ValueError('ROUTE_FILTER_UNAVAILABLE')
    where, params = ['1=1'], []
    for endpoint in ('origin', 'destination'):
        queries = getattr(criteria, endpoint)
        if queries:
            parts = []
            for term in queries:
                parts.append(f'({endpoint}_icao = ? COLLATE NOCASE OR {endpoint}_iata = ? COLLATE NOCASE '
                             f'OR instr(lower({endpoint}_city),lower(?)) > 0 OR instr(lower({endpoint}_name),lower(?)) > 0)')
                params.extend([term] * 4)
            # View exposes ICAO as origin/destination, not origin_icao.
            where.append('(' + ' OR '.join(parts).replace(endpoint + '_icao', endpoint) + ')')
        for suffix in ('country', 'continent', 'region'):
            values = getattr(criteria, endpoint + '_' + suffix)
            if values:
                where.append(f'UPPER({endpoint}_{suffix}) IN ({",".join("?" for _ in values)})')
                params.extend(v.upper() for v in values)
    if criteria.airline.strip():
        term = criteria.airline.strip()
        where.append('(airline = ? COLLATE NOCASE OR airline_iata = ? COLLATE NOCASE OR instr(lower(airline_name),lower(?)) > 0)')
        params.extend([term] * 3)
    if criteria.callsign.strip():
        where.append('instr(upper(callsign),upper(?)) > 0')
        params.append(criteria.callsign.strip())
    if criteria.international_only:
        where.append('origin_country <> destination_country')
    excluded = parse_airport_codes(criteria.excluded_airports, exclusion=True)
    with connect_readonly(path) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='observed_routes' AND type='table'").fetchone():
            raise ValueError('ROUTE_CATALOG_UNAVAILABLE')
        if excluded:
            markers = ','.join('?' for _ in excluded)
            known = {code for row in db.execute(f'SELECT icao,iata FROM airports WHERE icao IN ({markers}) OR iata IN ({markers})', excluded * 2) for code in row if code}  # nosec B608: only fixed SQL fragments/column names and ? markers; user values bound separately.
            unknown = [code for code in excluded if code not in known]
            if unknown:
                raise ValueError('EXCLUDED_AIRPORT_UNKNOWN: ' + ', '.join(unknown))
            for endpoint in ('origin', 'destination'):
                where.append(f'{endpoint}_id NOT IN (SELECT id FROM airports WHERE icao IN ({markers}) OR iata IN ({markers}))')  # nosec B608: only fixed SQL fragments/column names and ? markers; user values bound separately.
                params.extend(excluded * 2)
        order = 'confidence DESC,evidence_days DESC,last_seen DESC,n_obs DESC,callsign,origin,destination'
        filtered = 'SELECT * FROM v_observed_routes WHERE ' + ' AND '.join(where)  # nosec B608: only fixed SQL fragments/column names and ? markers; user values bound separately.
        matches = db.execute('SELECT count(*) FROM (' + filtered + ')', params).fetchone()[0]  # nosec B608: only fixed SQL fragments/column names and ? markers; user values bound separately.
        if criteria.diversify:
            # SQLite ranks keys before fetching a page: do not materialize every route in Python.
            filtered = ('SELECT * FROM (SELECT *,ROW_NUMBER() OVER (PARTITION BY airline,origin_id,destination_id ORDER BY ' +  # nosec B608: only fixed SQL fragments/column names and ? markers; user values bound separately.
                        order + ') AS route_rank FROM (' + filtered + ')) WHERE route_rank <= ' +
                        ('10' if criteria.airline else '3'))
        available = db.execute('SELECT count(*) FROM (' + filtered + ')', params).fetchone()[0] if criteria.diversify else matches  # nosec B608: only fixed SQL fragments/column names and ? markers; user values bound separately.
        sql = filtered + ' ORDER BY ' + order
        page_params = params
        if not include_population:
            sql += ' LIMIT ? OFFSET ?'
            page_params = params + [criteria.limit, criteria.offset]
        rows = [dict(row) for row in db.execute(sql, page_params)]
        build = dict(db.execute('SELECT key,value FROM build_info'))
        build['last_observation'] = build.get('route_catalog_last_observation', '')
        sources = [dict(row) for row in db.execute('SELECT * FROM sources WHERE source_id IN (SELECT DISTINCT source_id FROM observed_routes)')]
    results = []
    for row in rows:
        row.update(record_kind='OBSERVED_ROUTE', pattern_id=None, aircraft=None, aircraft_model=None,
                   aircraft_display=None, duration_min=None, duration_p10=None, duration_p90=None,
                   type_mix='[]', n_complete=0, latest_departure=None, latest_arrival=None,
                   sim_departure_utc=None, sim_arrival_utc=None, score=row['confidence'] * 100,
                   subscores={'confidence': row['confidence']}, warnings=['ROUTE_EVIDENCE_NOTICE'])
        results.append(row)
    response = dict(results=results[criteria.offset:criteria.offset + criteria.limit] if include_population else results,
                    warnings=['HISTORICAL_NOT_SCHEDULED', 'ROUTE_EVIDENCE_NOTICE'], available=available,
                    diversity_dropped=matches-available, offset=criteria.offset,
                    has_more=criteria.offset+criteria.limit < available, candidates=matches, matches=matches,
                    sources=sources, build=build, now_utc=now.isoformat(), implied_minutes=None)
    if include_population:
        response['_population'] = results
    return response
