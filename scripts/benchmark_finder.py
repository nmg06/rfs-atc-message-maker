"""Compare the previous public Flightdeck search and the optimized engine."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from finder.search import Criteria, SearchSession, search


def benchmark(previous, database):
    spec = importlib.util.spec_from_file_location('finder.previous_search', previous)
    old = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = old
    spec.loader.exec_module(old)
    now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    rows = []
    for criteria in [Criteria(airline='Air France', limit=100), Criteria(airline='AF', limit=100),
                     Criteria(airline='AFR', min_minutes=600, limit=100),
                     Criteria(origin_country=['FR'], destination_country=['RO'], limit=100),
                     Criteria(origin=['LFPG'], max_minutes=120, limit=100)]:
        start = time.perf_counter()
        expected = old.search(database, old.Criteria(**vars(criteria)), now)
        before = time.perf_counter() - start
        session = SearchSession()
        start = time.perf_counter()
        actual = session.page(database, criteria, now)
        after = time.perf_counter() - start
        assert expected == actual, f"Search parity failed: {vars(criteria)}"
        next_page = replace(criteria, offset=100)
        expected_next = old.search(database, old.Criteria(**vars(next_page)), now)
        start = time.perf_counter()
        cached_next = session.page(database, next_page, now)
        cached = time.perf_counter() - start
        assert expected_next == cached_next, 'Pagination parity failed'
        rows.append({'filters': vars(criteria), 'before_seconds': round(before, 4),
                     'after_seconds': round(after, 4), 'cached_page_seconds': round(cached, 5),
                     'matches': actual['matches'], 'available': actual['available'], 'exact_parity': True})
    output = ROOT / 'docs/finder-performance.json'
    output.write_text(json.dumps(rows, indent=2), encoding='utf-8')
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--previous', required=True)
    parser.add_argument('--database', type=Path, required=True)
    args = parser.parse_args()
    benchmark(args.previous, args.database)
