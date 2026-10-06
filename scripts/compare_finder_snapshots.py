"""Read-only integrity, retained route keys and search timings for real snapshots."""
from __future__ import annotations
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from finder.search import Criteria, SearchSession
from finder.rfs_catalogue import SUPPORTED_TYPES


def connect(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    return db


def route_keys(db, searchable=False):
    where = " WHERE duration_min IS NOT NULL AND n_complete>=3" if searchable else ""
    return set(db.execute("SELECT callsign,o.icao,d.icao FROM flight_patterns p "
                          "JOIN airports o ON o.id=p.origin_id JOIN airports d ON d.id=p.destination_id" + where))


def duration_keys(db):
    return set(db.execute("SELECT callsign,o.icao,d.icao FROM flight_patterns p "
                          "JOIN airports o ON o.id=p.origin_id JOIN airports d ON d.id=p.destination_id "
                          "WHERE duration_min IS NOT NULL"))


def summary(path, *, require_observed_durations=True):
    db = connect(path)
    try:
        invalid_duration = db.execute("SELECT count(*) FROM flight_patterns WHERE duration_min IS NOT NULL AND n_complete<3").fetchone()[0]
        if invalid_duration and require_observed_durations:
            raise ValueError("Duration without three complete observations")
        info = dict(db.execute("SELECT key,value FROM build_info"))
        return {"bytes": Path(path).stat().st_size,
                "patterns": db.execute("SELECT count(*) FROM flight_patterns").fetchone()[0],
                "total_searchable_patterns": db.execute("SELECT count(*) FROM flight_patterns WHERE duration_min IS NOT NULL").fetchone()[0],
                "searchable_patterns": db.execute("SELECT count(*) FROM flight_patterns WHERE n_complete>=3 AND duration_min IS NOT NULL").fetchone()[0],
                "rfs_searchable_patterns": db.execute("SELECT count(*) FROM flight_patterns WHERE n_complete>=3 AND duration_min IS NOT NULL AND aircraft IN (" + ','.join('?' for _ in SUPPORTED_TYPES) + ")", SUPPORTED_TYPES).fetchone()[0],
                "recent_observations": db.execute("SELECT count(*) FROM recent_observations").fetchone()[0],
                "first_seen": db.execute("SELECT min(first_seen) FROM flight_patterns").fetchone()[0],
                "last_seen": db.execute("SELECT max(last_seen) FROM flight_patterns").fetchone()[0],
                "integrity": db.execute("PRAGMA integrity_check").fetchone()[0],
                "foreign_key_errors": len(db.execute("PRAGMA foreign_key_check").fetchall()),
                "non_observed_duration_profiles": invalid_duration,
                "build_info": {k: info[k] for k in ("raw_rows","retained_observations","last_observation","built_at","window_days") if k in info}}
    finally:
        db.close()


def timing(path, criteria, now):
    measurements = []
    cached = []
    first = None
    for _ in range(3):
        session = SearchSession()
        start = time.perf_counter()
        first = session.page(path, criteria, now)
        measurements.append(time.perf_counter() - start)
        start = time.perf_counter()
        session.page(path, replace(criteria, offset=100), now)
        cached.append(time.perf_counter() - start)
    return {"filters": vars(criteria), "matches": first["matches"], "available": first["available"],
            "first_page_median_seconds": round(statistics.median(measurements), 6),
            "first_page_max_seconds": round(max(measurements), 6),
            "cached_next_page_median_seconds": round(statistics.median(cached), 6)}


def compare(before, after, report, compressed=None, *, allow_overlay=False):
    before, after = Path(before), Path(after)
    old_db, new_db = connect(before), connect(after)
    try:
        old_keys, new_keys = route_keys(old_db), route_keys(new_db)
        old_searchable, new_searchable = route_keys(old_db, True), route_keys(new_db, True)
        old_all_durations = duration_keys(old_db)
        new_all_durations = duration_keys(new_db)
        missing = old_keys - new_keys
        missing_searchable = old_searchable - new_searchable
        missing_all_durations = old_all_durations - new_all_durations
        if missing or missing_searchable:
            raise ValueError(f"Lost old route keys: {len(missing)}; lost searchable: {len(missing_searchable)}")
        if not allow_overlay and missing_all_durations:
            pass  # Documented legacy duration difference without overlay
        new_only = new_searchable - old_searchable
        new_by_airline = {}
        examples = []
        for row in new_db.execute("SELECT airline,callsign,o.icao,d.icao,aircraft,n_complete,duration_min,first_seen,last_seen FROM flight_patterns p JOIN airports o ON o.id=p.origin_id JOIN airports d ON d.id=p.destination_id WHERE duration_min IS NOT NULL AND n_complete>=3 ORDER BY n_complete DESC,callsign"):
            if tuple(row[1:4]) in new_only:
                new_by_airline.setdefault(row[0], set()).add(tuple(row[1:4]))
                if row[0] in ("AFR","BAW","DLH","THY","QFA","UAE") and len(examples)<20:
                    examples.append(dict(zip(("airline","callsign","origin","destination","aircraft","complete_observations","duration_min","first_seen","last_seen"),row)))
        result = {"before": summary(before, require_observed_durations=False), "after": summary(after, require_observed_durations=not allow_overlay),
                  "route_keys_before": len(old_keys), "route_keys_after": len(new_keys),
                  "new_route_keys": len(new_keys-old_keys), "lost_route_keys": len(missing),
                  "searchable_route_keys_before": len(old_searchable), "searchable_route_keys_after": len(new_searchable),
                  "new_searchable_route_keys": len(new_only), "lost_searchable_route_keys": len(missing_searchable),
                  "all_duration_route_keys_before": len(old_all_durations), "all_duration_route_keys_after": len(new_all_durations),
                  "lost_duration_route_keys": len(missing_all_durations),
                  "legacy_estimated_only_route_keys": len(old_all_durations-old_searchable),
                  "legacy_estimated_routes_without_observed_duration_after": len(old_all_durations-new_searchable),
                  "new_searchable_routes_by_airline": {k:len(v) for k,v in sorted(new_by_airline.items())},
                  "new_historical_examples": examples}
    finally:
        old_db.close()
        new_db.close()
    now = datetime(2026,10,6,12,tzinfo=timezone.utc)
    criteria = [Criteria(airline="Air France", limit=100),
                Criteria(airline="AFR", min_minutes=600, limit=100),
                Criteria(origin_country=["FR"],destination_country=["RO"],limit=100),
                Criteria(origin=["LFPG"],max_minutes=120,limit=100),
                Criteria(rfs_only=True,limit=100)]
    result["search_timings"] = [{"before": timing(before,c,now), "after": timing(after,c,now)} for c in criteria]
    if compressed:
        compressed = Path(compressed)
        with after.open("rb") as src, compressed.open("wb") as raw, gzip.GzipFile(filename="",fileobj=raw,mode="wb",mtime=0) as dst:
            while block := src.read(4*1024*1024):
                dst.write(block)
        result["compressed_bytes"] = compressed.stat().st_size
    report = Path(report)
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("new_searchable_routes_by_airline","new_historical_examples")},indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before",type=Path,required=True)
    parser.add_argument("--after",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--gzip",type=Path,dest="compressed")
    parser.add_argument("--allow-overlay",action="store_true",help="Allow verified legacy estimates overlay")
    args = parser.parse_args()
    compare(args.before,args.after,args.report,args.compressed,allow_overlay=args.allow_overlay)
