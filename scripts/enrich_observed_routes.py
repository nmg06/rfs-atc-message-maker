"""Reproducible conservative enrichment of a NEW database; never edits the input."""
import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
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

SNAPSHOT = '2026-10-07'
SHA256 = 'ac314dfbee338f3b6bc5331ac4c85dbf1d9158d771d9694a304e2bb05313960c'
SOURCE = 'catchflights-' + SNAPSHOT


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def enrich(base, archive, output):
    base, archive, output = map(lambda p: Path(p).resolve(), (base, archive, output))
    if output.exists() or output == base:
        raise ValueError('Output must be a new path; the existing database is preserved')
    if digest(archive) != SHA256:
        raise ValueError('Pinned source checksum mismatch')
    baseline_hash = digest(base)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix('.building.sqlite')
    if temp.exists():
        raise ValueError('Previous candidate exists: choose another output path')
    shutil.copy2(base, temp)
    counts = Counter()
    db = sqlite3.connect(temp)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA foreign_keys=ON')
        if db.execute('PRAGMA user_version').fetchone()[0] != 1:
            raise ValueError('Unsupported baseline schema')
        db.executescript(SCHEMA)
        airports = {r['icao']: dict(r) for r in db.execute('SELECT * FROM airports') if r['icao']}
        airlines = {r[0] for r in db.execute('SELECT icao FROM airlines')}
        old_keys = {tuple(r) for r in db.execute('SELECT DISTINCT callsign,origin_id,destination_id FROM flight_patterns')}
        db.execute('INSERT INTO sources VALUES (?,?,?,?,?)', (SOURCE, 'CatchFlights observed routes ' + SNAPSHOT,
            'https://github.com/catchflights/routes/releases/tag/routes-' + SNAPSHOT, 'ODbL-1.0',
            'CatchFlights / adsb.lol / MrAirspace. ODbL 1.0; contents DBCL. Routes inferred from ADS-B evidence; aircraft and duration unavailable.'))
        with gzip.open(archive, 'rt', encoding='utf-8', newline='') as source:
            for row in csv.DictReader(source):
                counts['input_rows'] += 1
                try:
                    confidence = float(row['confidence'])
                    candidates, days, observations = (int(row[k]) for k in ('candidate_count', 'evidence_days', 'observation_count'))
                    first, last = (datetime.fromisoformat(row[k].replace('Z', '+00:00')) for k in ('first_observed_at', 'last_observed_at'))
                    if first.tzinfo is None or last.tzinfo is None or first > last or last > datetime(2026,10,8,tzinfo=timezone.utc):
                        raise ValueError('Invalid observation dates')
                except (ValueError, KeyError):
                    counts['invalid_evidence'] += 1
                    continue
                if not math.isfinite(confidence) or not .95 <= confidence <= 1 or candidates != 1 or days < 3 or observations < 3 or observations < days:
                    counts['insufficient_evidence'] += 1
                    continue
                if row['via_icaos'].strip():
                    counts['multi_leg_excluded'] += 1
                    continue
                callsign = row['callsign'].strip().upper()
                origin, destination = airports.get(row['origin_icao']), airports.get(row['destination_icao'])
                if not re.fullmatch(r'[A-Z0-9]{3,12}', callsign) or not origin or not destination or origin['id'] == destination['id']:
                    counts['invalid_route'] += 1
                    continue
                # Airline identity is an inference from the callsign prefix, not a supplied source field.
                airline = callsign[:3] if callsign[:3] in airlines else None
                if airline is None:
                    counts['unknown_airline_excluded'] += 1
                    continue
                distance = None
                if all(a[k] is not None for a in (origin,destination) for k in ('latitude','longitude')):
                    p,q = map(math.radians,(origin['latitude'],destination['latitude']))
                    x = math.sin((q-p)/2)**2 + math.cos(p)*math.cos(q)*math.sin(math.radians(destination['longitude']-origin['longitude'])/2)**2
                    distance = 6880.13 * math.asin(min(1,math.sqrt(max(0,x))))
                db.execute('INSERT INTO observed_routes(callsign,airline,origin_id,destination_id,confidence,evidence_days,n_obs,first_seen,last_seen,distance_nm,source_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (callsign,airline,origin['id'],destination['id'],confidence,days,observations,first.isoformat(),last.isoformat(),distance,SOURCE))
                counts['accepted_routes'] += 1
                if (callsign,origin['id'],destination['id']) not in old_keys:
                    counts['new_callsign_routes'] += 1
        last_seen = db.execute('SELECT max(last_seen) FROM observed_routes').fetchone()[0]
        meta = {'route_catalog_snapshot': SNAPSHOT, 'route_catalog_source_sha256': SHA256,
                'route_catalog_last_observation': last_seen, 'route_catalog_routes': counts['accepted_routes']}
        db.executemany('INSERT INTO build_info VALUES (?,?)', [(k,str(v)) for k,v in meta.items()])
        db.commit()
        db.execute('ATTACH DATABASE ? AS baseline', (str(base),))
        # Compare every legacy flight field, not only route counts.
        lost = db.execute('SELECT count(*) FROM (SELECT * FROM baseline.flight_patterns EXCEPT SELECT * FROM main.flight_patterns)').fetchone()[0]
        added = db.execute('SELECT count(*) FROM (SELECT * FROM main.flight_patterns EXCEPT SELECT * FROM baseline.flight_patterns)').fetchone()[0]
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
        if lost or added or integrity != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Candidate failed preservation or integrity checks')
        report = dict(counts, snapshot=SNAPSHOT, source_sha256=SHA256, baseline_sha256=baseline_hash,
                      preserved_flight_patterns=db.execute('SELECT count(*) FROM flight_patterns').fetchone()[0],
                      lost_or_changed_profiles=lost, unexpected_profiles=added, integrity=integrity, last_observation=last_seen)
    except Exception:
        db.close()
        temp.unlink(missing_ok=True)  # Only the new candidate owned by this invocation.
        raise
    else:
        db.close()
    if digest(base) != baseline_hash:
        raise ValueError('Baseline changed during the build; candidate not promoted')
    temp.replace(output)
    report['candidate_sha256'] = digest(output)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=ROOT/'finder/source-data/routes-observed-2026-10-07.csv.gz')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = enrich(args.base,args.source,args.output)
    args.report.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
