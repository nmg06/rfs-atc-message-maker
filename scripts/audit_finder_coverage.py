"""Read-only audit of actual offline Finder coverage; no flights are generated."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from finder.database import connect_readonly
from finder.aircraft_filters import catalogue


def audit(path):
    path = Path(path).resolve()
    checksum = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b''):
            checksum.update(chunk)
    types = catalogue(path)
    with connect_readonly(path) as db:
        totals = dict(db.execute("SELECT count(*) AS historical_profiles, count(distinct aircraft) AS observed_types, min(first_seen) AS first_observation, max(last_seen) AS last_observation FROM flight_patterns").fetchone())
        operators = [dict(r) for r in db.execute("SELECT airline AS code, airline_name AS name, count(*) AS searchable_profiles FROM v_pattern_search WHERE n_obs>=3 AND duration_min IS NOT NULL AND airline IN ('FDX','UPS','CLX','GTI','BOX','DHK','GEC','MTN') GROUP BY airline ORDER BY count(*) DESC, airline")]
        recent = dict(db.execute('SELECT count(*) AS routes, max(last_seen) AS last_observation FROM observed_routes').fetchone()) if db.execute("SELECT 1 FROM sqlite_master WHERE name='observed_routes'").fetchone() else None
    return {
        'database_sha256': checksum.hexdigest(), 'totals': totals,
        'reference_types':len(types),
        'types_with_searchable_profiles':sum(r['profile_count']>0 for r in types),
        'searchable_historical_profiles':sum(r['profile_count'] for r in types),
        'example_operators':operators,
        'example_aircraft':[r for r in types if r['code'] in ('C172','C208','SR22','C152','C510','PC12','DHC6','LJ35','B350','TBM9')],
        'recent_route_evidence':recent,
        'count_definition':'Historical route/callsign/aircraft profiles, before other user filters, diversification and result limits. Not individual flights or current published schedules.',
        'limits':[
            'Aircraft reference entries do not guarantee flight evidence.',
            'Recent route evidence has no aircraft or duration and is excluded from aircraft counts.',
            'Cargo/passenger subvariants sharing an ICAO type remain unknown.',
            'Historical importer requires a known operator, different endpoint airports, 15-1200 minute tracks and repeated evidence; general aviation and circuits are underrepresented.'
        ]
    }


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.database)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:result[k] for k in ('database_sha256','reference_types','types_with_searchable_profiles','searchable_historical_profiles')},ensure_ascii=False))
