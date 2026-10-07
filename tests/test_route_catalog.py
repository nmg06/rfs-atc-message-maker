"""Synthetic test evidence stays in temporary databases, never in the public bundle."""
import csv
from datetime import datetime, timezone
import gzip
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from tests.test_finder import fixture
from finder.mapping import use_this_flight
from finder.search import Criteria, SearchSession, search
from scripts import enrich_observed_routes as builder

NOW = datetime(2026,10,7,tzinfo=timezone.utc)


class RouteCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base, self.out = self.root/'baseline.sqlite', self.root/'enriched.sqlite'
        fixture(self.base)
        self.source = self.root/'test.csv.gz'
        good = dict(callsign='AFR999',origin_icao='LFPG',destination_icao='EGLL',via_icaos='',
                    confidence='.97',candidate_count='1',evidence_days='5',observation_count='8',
                    first_observed_at='2026-09-02T12:00:00Z',last_observed_at='2026-10-06T12:00:00Z')
        rows = [good, dict(good,callsign='AFR998',destination_icao='LFMN'),
                dict(good,callsign='AFR997',confidence='.8'),
                dict(good,callsign='AFR996',candidate_count='2'),
                dict(good,callsign='AFR995',via_icaos='VIDP'),
                dict(good,callsign='AFR994',destination_icao='ZZZZ'),
                dict(good,callsign='ZZZ993'), dict(good,callsign='AFR992',last_observed_at='2026-10-09T12:00:00Z')]
        with gzip.open(self.source,'wt',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(good));w.writeheader();w.writerows(rows)
        with patch.object(builder,'SHA256',builder.digest(self.source)):
            self.report = builder.enrich(self.base,self.source,self.out)

    def tearDown(self):
        self.temp.cleanup()

    def test_preserves_every_existing_profile_and_rejects_weak_or_invalid_evidence(self):
        self.assertEqual(2,self.report['accepted_routes'])
        self.assertEqual(0,self.report['lost_or_changed_profiles'])
        self.assertEqual(0,self.report['unexpected_profiles'])
        before=search(self.base,Criteria(diversify=False),NOW)
        after=search(self.out,Criteria(diversify=False),NOW)
        self.assertEqual(before['results'],after['results'])
        self.assertEqual(5,self.report['preserved_flight_patterns'])

    def test_route_filters_and_unknowns(self):
        response=search(self.out,Criteria(route_catalog=True,origin=['Paris'],airline='AF'),NOW)
        self.assertEqual(2,response['available'])
        row=response['results'][0]
        self.assertIsNone(row['duration_min'])
        self.assertIsNone(row['aircraft'])
        self.assertEqual(0,row['n_complete'])
        self.assertEqual('OBSERVED_ROUTE',row['record_kind'])
        self.assertEqual(1,search(self.out,Criteria(route_catalog=True,excluded_airports=['LHR']),NOW)['available'])
        self.assertEqual(1,search(self.out,Criteria(route_catalog=True,destination_country=['GB']),NOW)['available'])
        self.assertEqual(1,search(self.out,Criteria(route_catalog=True,callsign='999'),NOW)['available'])
        with self.assertRaisesRegex(ValueError,'EXCLUDED_AIRPORT_UNKNOWN'):
            search(self.out,Criteria(route_catalog=True,excluded_airports=['ZZZZ']),NOW)

    def test_unavailable_filters_fail_explicitly(self):
        for filters in ({'rfs_only':True},{'aircraft':'A320'},{'min_minutes':60},{'departure_time':'12:00'}):
            with self.subTest(filters=filters), self.assertRaisesRegex(ValueError,'ROUTE_FILTER_UNAVAILABLE'):
                search(self.out,Criteria(route_catalog=True,**filters),NOW)
        with self.assertRaisesRegex(ValueError,'ROUTE_CATALOG_UNAVAILABLE'):
            search(self.base,Criteria(route_catalog=True),NOW)

    def test_mapping_does_not_invent_or_erase_manual_aircraft_duration_fuel_or_gate(self):
        row=search(self.out,Criteria(route_catalog=True,callsign='999'),NOW)['results'][0]
        current={'aircraft':'Airbus A350-900','estimated_flight_time':'2h00','fuel':'15000','departure_gate':'A1'}
        mapped=use_this_flight(current,row)
        for key,value in current.items():
            self.assertEqual(value,mapped[key])
        self.assertEqual('OBSERVED_ROUTE',mapped['selected_flight']['status'])
        self.assertEqual('DERIVED_FROM_CALLSIGN_PREFIX',mapped['selected_flight']['fields']['airline'])
        self.assertNotIn('estimated_flight_time',mapped['selected_flight']['fields'])
        self.assertNotIn('aircraft',mapped['selected_flight']['fields'])
        self.assertEqual('LFPG',mapped['departure_icao'])
        self.assertEqual('EGLL',mapped['arrival_icao'])

    def test_cached_pagination_is_stable_and_mutations_do_not_corrupt_it(self):
        session=SearchSession(); c=Criteria(route_catalog=True,limit=1)
        first=session.page(self.out,c,NOW)
        first['results'][0]['callsign']='MODIFIED'
        self.assertNotEqual('MODIFIED',session.page(self.out,c,NOW)['results'][0]['callsign'])
        c.offset=1
        self.assertEqual(1,len(session.page(self.out,c,NOW)['results']))
        self.assertFalse(session.page(self.out,c,NOW)['has_more'])

    def test_route_mapping_keeps_manual_aircraft_available_to_fuel_helper(self):
        from fuel.selection import resolve_aircraft
        row=search(self.out,Criteria(route_catalog=True),NOW)['results'][0]
        mapped=use_this_flight({'aircraft':'Airbus A220-300'},row)
        self.assertEqual('airbus_a220_300',resolve_aircraft(mapped)['record']['id'])

    def test_bad_checksum_and_overwrite_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'checksum'):
            builder.enrich(self.base,self.source,self.root/'other.sqlite')
        with self.assertRaisesRegex(ValueError,'new path'):
            builder.enrich(self.base,self.source,self.base)


if __name__ == '__main__':
    unittest.main()
