"""Append pinned airline route evidence to a new database, preserving existing rows."""
import argparse
from collections import Counter
import csv
from datetime import date, datetime, timedelta, timezone
import gzip
import json
import math
from pathlib import Path
import re
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from finder.route_catalog import SCHEMA
from scripts.enrich_observed_routes import digest


def enrich(base, archive, manifest, output, airline):
    base, archive, manifest, output = [Path(p).resolve() for p in (base, archive, manifest, output)]
    if output.exists() or output == base:
        raise ValueError('Output must be a new path')
    airline = airline.strip().upper()
    if not re.fullmatch(r'[A-Z]{3}', airline):
        raise ValueError('Invalid airline ICAO code')
    metadata = json.loads(manifest.read_text(encoding='utf-8'))
    snapshot = date.fromisoformat(metadata['generated_on'])
    if metadata['dataset'] != 'catchflights-observed-routes' or metadata['file'] != archive.name:
        raise ValueError('Unexpected source dataset or filename')
    if digest(archive) != metadata['sha256']:
        raise ValueError('Source checksum mismatch')
    if metadata['license']['name'] != 'Open Database License (ODbL) v1.0':
        raise ValueError('Unexpected source license')
    baseline_hash = digest(base)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.building.sqlite')
    if temporary.exists():
        raise ValueError('Previous candidate exists')
    shutil.copy2(base, temporary)
    counts = Counter()
    source_id = 'catchflights-' + snapshot.isoformat()
    cutoff = datetime.combine(snapshot + timedelta(days=1), datetime.min.time(), timezone.utc)
    db = sqlite3.connect(temporary)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA foreign_keys=ON')
        if db.execute('PRAGMA user_version').fetchone()[0] != 1:
            raise ValueError('Unsupported database schema')
        has_routes = bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='observed_routes' AND type='table'").fetchone())
        if not has_routes:
            db.executescript(SCHEMA)
        if not db.execute('SELECT 1 FROM airlines WHERE icao=?', (airline,)).fetchone():
            raise ValueError('Unknown airline')
        airports = {r['icao']: dict(r) for r in db.execute('SELECT * FROM airports') if r['icao']}
        existing = {tuple(r) for r in db.execute('SELECT callsign,origin_id,destination_id FROM flight_patterns')}
        existing.update(tuple(r) for r in db.execute('SELECT callsign,origin_id,destination_id FROM observed_routes'))
        known_callsigns = {key[0] for key in existing}
        db.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?)', (source_id,
            'CatchFlights observed routes ' + snapshot.isoformat(),
            'https://github.com/catchflights/routes/releases/tag/routes-' + snapshot.isoformat(),
            'ODbL-1.0', 'CatchFlights / adsb.lol / MrAirspace. ODbL 1.0; contents DBCL. Routes inferred from ADS-B evidence; aircraft and duration unavailable.'))
        added = []
        with gzip.open(archive, 'rt', encoding='utf-8', newline='') as source:
            for row in csv.DictReader(source):
                counts['input_rows'] += 1
                callsign = row['callsign'].strip().upper()
                if not callsign.startswith(airline):
                    continue
                counts['airline_source_rows'] += 1
                try:
                    confidence = float(row['confidence'])
                    candidates, days, observations = [int(row[k]) for k in ('candidate_count', 'evidence_days', 'observation_count')]
                    first, last = [datetime.fromisoformat(row[k].replace('Z', '+00:00')) for k in ('first_observed_at', 'last_observed_at')]
                    if first.tzinfo is None or last.tzinfo is None or first > last or last >= cutoff:
                        raise ValueError('Invalid dates')
                except (ValueError, KeyError, OverflowError):
                    counts['invalid_evidence'] += 1
                    continue
                if not math.isfinite(confidence) or not .95 <= confidence <= 1 or candidates != 1 or days < 3 or observations < days:
                    counts['insufficient_evidence'] += 1
                    continue
                if row['via_icaos'].strip():
                    counts['multi_leg_excluded'] += 1
                    continue
                if row.get('airline_icao', '').strip() not in ('', airline):
                    counts['conflicting_airline_excluded'] += 1
                    continue
                origin, destination = airports.get(row['origin_icao']), airports.get(row['destination_icao'])
                if not re.fullmatch(r'[A-Z0-9]{3,12}', callsign) or not origin or not destination or origin['id'] == destination['id']:
                    counts['invalid_route'] += 1
                    continue
                key = callsign, origin['id'], destination['id']
                if key in existing:
                    counts['duplicates_preserved'] += 1
                    continue
                if callsign in known_callsigns:
                    counts['conflicting_callsign_routes_excluded'] += 1
                    continue
                distance = None
                if all(a[k] is not None for a in (origin, destination) for k in ('latitude', 'longitude')):
                    p, q = [math.radians(a['latitude']) for a in (origin, destination)]
                    x = math.sin((q-p)/2)**2 + math.cos(p)*math.cos(q)*math.sin(math.radians(destination['longitude']-origin['longitude'])/2)**2
                    distance = 6880.13 * math.asin(min(1, math.sqrt(max(0, x))))
                db.execute('INSERT INTO observed_routes(callsign,airline,origin_id,destination_id,confidence,evidence_days,n_obs,first_seen,last_seen,distance_nm,source_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (callsign, airline, origin['id'], destination['id'], confidence, days, observations, first.isoformat(), last.isoformat(), distance, source_id))
                existing.add(key)
                known_callsigns.add(callsign)
                counts['added_routes'] += 1
                added.append(dict(callsign=callsign, origin=row['origin_icao'], destination=row['destination_icao'], confidence=confidence,
                                  evidence_days=days, observations=observations, first_seen=first.isoformat(), last_seen=last.isoformat()))
        if counts['input_rows'] != metadata['rows']:
            raise ValueError('Source row count differs from manifest')
        last_seen = db.execute('SELECT max(last_seen) FROM observed_routes').fetchone()[0]
        route_count = db.execute('SELECT count(*) FROM observed_routes').fetchone()[0]
        # The original global snapshot remains explicit; this is an airline-only append.
        updates = {'route_catalog_last_observation': last_seen, 'route_catalog_routes': str(route_count),
                   'airline_enrichment_' + airline: json.dumps(dict(snapshot=snapshot.isoformat(), source_sha256=metadata['sha256'], added=counts['added_routes']))}
        db.executemany('INSERT INTO build_info VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', updates.items())
        db.commit()
        db.execute('ATTACH DATABASE ? AS baseline', (str(base),))
        preserved = {}
        for table in ('airports', 'runways', 'airlines', 'aircraft_types', 'flight_patterns', 'recent_observations', 'sources') + (('observed_routes',) if has_routes else ()):
            lost = db.execute('SELECT count(*) FROM (SELECT * FROM baseline.' + table + ' EXCEPT SELECT * FROM main.' + table + ')').fetchone()[0]
            if lost:
                raise ValueError('Existing rows changed or lost in ' + table)
            preserved[table] = db.execute('SELECT count(*) FROM baseline.' + table).fetchone()[0]
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Database integrity check failed')
        report = dict(counts, airline=airline, snapshot=snapshot.isoformat(), source_sha256=metadata['sha256'],
                      baseline_sha256=baseline_hash, preserved=preserved, lost_or_changed_rows=0,
                      integrity=integrity, routes=added, total_observed_routes=route_count, last_observation=last_seen)
    except Exception:
        db.close()
        temporary.unlink(missing_ok=True)
        raise
    db.close()
    if digest(base) != baseline_hash:
        raise ValueError('Baseline changed during enrichment')
    temporary.replace(output)
    report['candidate_sha256'] = digest(output)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'source', 'manifest', 'output', 'report'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--airline', required=True)
    args = parser.parse_args()
    report = enrich(args.base, args.source, args.manifest, args.output, args.airline)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8', newline='\n')
    print(json.dumps(report, indent=2))
