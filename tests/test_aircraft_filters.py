"""Multiple aircraft means OR across types, AND with other real Finder filters."""
import tempfile
from pathlib import Path
import unittest
from finder.aircraft_filters import normalize_types, catalogue
from finder.search import Criteria, SearchSession, search
from test_finder import fixture, NOW


class AircraftFilterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'aviation.sqlite'
        fixture(self.path)

    def test_multiple_types_union_preserves_every_matching_row(self):
        rows = search(self.path, Criteria(aircraft_types=['A20N','B789'], diversify=False), NOW)['results']
        self.assertEqual({1,2,3,4,5}, {r['pattern_id'] for r in rows})
        rows = search(self.path, Criteria(aircraft_types=['A20N','B789'], airline='AFR', excluded_airports=['NCE']), NOW)['results']
        self.assertEqual({1,2}, {r['pattern_id'] for r in rows})

    def test_normalize_rejects_malformed_without_silently_broadening(self):
        self.assertEqual(['A20N','B789'], normalize_types(['a20n','B789','A20N']))
        for invalid in [None, {'A320':True}, ['A20N',"' OR 1=1 --"], ['A20N']*51]:
            with self.assertRaises(ValueError):
                normalize_types(invalid)

    def test_cached_search_distinguishes_selected_types(self):
        session = SearchSession()
        for code, expected in [('A20N',{1,2,3}),('B789',{4,5})]:
            rows = session.page(self.path, Criteria(aircraft_types=[code], diversify=False), NOW)['results']
            self.assertEqual(expected,{r['pattern_id'] for r in rows})

    def test_catalogue_is_available_before_any_query_is_typed(self):
        self.assertEqual({'A20N','B789'}, {r['code'] for r in catalogue(self.path)})

    def test_coverage_counts_eligible_profiles_and_keeps_uncovered_types(self):
        import sqlite3
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO aircraft_types VALUES ('C172','Aviones Colombia 172','Aviones Colombia','C172')")
            db.execute("INSERT INTO aircraft_types VALUES ('C152','Cessna 152','Cessna','C152')")
            db.execute("UPDATE flight_patterns SET n_obs=2 WHERE pattern_id=2")
            db.execute("UPDATE flight_patterns SET duration_min=NULL WHERE pattern_id=3")
        db.close()
        rows = catalogue(self.path)
        self.assertEqual({'A20N':1,'B789':2,'C172':0,'C152':0}, {r['code']:r['profile_count'] for r in rows})
        self.assertEqual({'A20N','B789'}, {r['code'] for r in rows[:2]})
        self.assertIn('Cessna', next(r['name'] for r in rows if r['code']=='C172'))
        for row in rows:
            response=search(self.path, Criteria(aircraft_types=[row['code']],diversify=False),NOW)
            self.assertEqual(row['profile_count'], response['matches'])

    def test_fedex_alias_works_in_historical_and_recent_modes(self):
        import sqlite3
        from finder.route_catalog import SCHEMA
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO airlines VALUES ('FDX','FX','Federal Express',NULL,NULL)")
            db.execute("UPDATE flight_patterns SET airline='FDX',callsign='FDX101' WHERE pattern_id=1")
            db.executescript(SCHEMA)
            db.execute("INSERT INTO observed_routes VALUES (1,'FDX101','FDX',1,2,.99,5,8,'2026-09-02','2026-09-29',200,'test')")
        db.close()
        for recent in (False,True):
            for term in ('FedEx','fedex','FDX','Federal Express'):
                response=search(self.path, Criteria(airline=term,route_catalog=recent),NOW)
                self.assertEqual(1,response['matches'],(recent,term))
                self.assertEqual('FDX',response['results'][0]['airline'])
