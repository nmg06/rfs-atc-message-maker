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
