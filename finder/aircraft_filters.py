"""Shared local aircraft catalogue and explicit OR-filter normalization."""
import re
from functools import lru_cache
from pathlib import Path
from .database import connect_readonly


def normalize_types(value):
    if isinstance(value, str):
        value = [v for v in re.split(r'[,;\s]+', value) if v]
    if not isinstance(value, list) or len(value) > 50:
        raise ValueError('AIRCRAFT_TYPES_FORMAT')
    result = []
    for item in value:
        if not isinstance(item, str) or not re.fullmatch(r'[A-Za-z0-9]{2,6}', item.strip()):
            raise ValueError('AIRCRAFT_TYPES_FORMAT')
        code = item.strip().upper()
        if code not in result:
            result.append(code)
    return result


def catalogue(path):
    """All reference types, with historical coverage before user filters.

    A reference entry is not evidence of a flight. Count only profiles eligible
    for the historical search, and leave uncovered types selectable with zero.
    Recent callsign routes have no aircraft evidence and are never counted here.
    """
    path = Path(path).resolve()
    stat = path.stat()
    return [dict(zip(('code','name','manufacturer','profile_count'), row))
            for row in _catalogue(str(path), stat.st_mtime_ns, stat.st_size)]


@lru_cache(maxsize=8)
def _catalogue(path, modified_ns, byte_count):
    # Immutable cache, invalidated when a read-only database file is replaced.
    from .rfs_catalogue import observation_name
    with connect_readonly(path) as db:
        rows = [dict(row) for row in db.execute('''
            SELECT t.icao AS code, COALESCE(NULLIF(t.model, ''), t.icao) AS name,
                   t.manufacturer, COALESCE(p.profile_count, 0) AS profile_count
            FROM aircraft_types t LEFT JOIN (
                SELECT p.aircraft, count(*) AS profile_count FROM flight_patterns p NOT INDEXED
                JOIN airlines a ON a.icao=p.airline
                JOIN airports o ON o.id=p.origin_id JOIN airports d ON d.id=p.destination_id
                WHERE p.n_obs >= 3 AND p.duration_min IS NOT NULL GROUP BY p.aircraft
            ) p ON p.aircraft = t.icao
            ORDER BY (COALESCE(p.profile_count, 0) > 0) DESC, t.manufacturer, t.model, t.icao
        ''')]
    for row in rows:
        # Use the supplied RFS name when known, without guessing a cargo variant.
        row['name'] = observation_name(row['code'], row['name'])
    return tuple((r['code'],r['name'],r['manufacturer'],r['profile_count']) for r in rows)
