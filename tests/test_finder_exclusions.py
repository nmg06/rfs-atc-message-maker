"""Shared exclusion semantics and real desktop input/persistence regression checks."""
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from finder.search import Criteria, SearchSession, parse_airport_codes, search
from test_finder import fixture, NOW


class ExclusionSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'aviation.sqlite'
        fixture(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_shared_parser_handles_whitespace_semicolons_case_duplicates_and_legacy_iata(self):
        self.assertEqual(['VABB', 'EGLL', 'LHR'], parse_airport_codes('vabb; EGLL  lhr,\tVABB', exclusion=True))
        self.assertEqual(['EGLL', 'LFPG'], parse_airport_codes(['egll', 'LFPG EGLL'], exclusion=True))
        self.assertEqual([], parse_airport_codes('  ', exclusion=True))
        for value in ('VABB, invalid', 'VAB1', ', ;', 'EGLL/ LFPG', 123, ['VABB', False]):
            with self.assertRaisesRegex(ValueError, 'EXCLUDED_AIRPORT_FORMAT'):
                parse_airport_codes(value, exclusion=True)

    def test_exclusions_remove_both_endpoints_and_preserve_other_filters(self):
        all_rows = search(self.path, Criteria(diversify=False), NOW)['results']
        expected = [r['pattern_id'] for r in all_rows if 'LFPG' not in (r['origin'], r['destination'])]
        actual = search(self.path, Criteria(excluded_airports=['cdg'], diversify=False), NOW)['results']
        self.assertEqual(expected, [r['pattern_id'] for r in actual])
        self.assertEqual([], search(self.path, Criteria(origin=['VIDP'], excluded_airports='LFPG; LHR'), NOW)['results'])
        keep = search(self.path, Criteria(origin=['VIDP'], excluded_airports=['EGLL'], min_minutes=500), NOW)['results']
        self.assertEqual([4], [r['pattern_id'] for r in keep])
        self.assertEqual('VIDP', keep[0]['origin'])

    def test_malformed_exclusions_never_run_an_unfiltered_query_and_unknown_codes_are_explicit(self):
        with patch('finder.search.connect_readonly') as connect:
            with self.assertRaisesRegex(ValueError, 'EXCLUDED_AIRPORT_FORMAT'):
                search(self.path, Criteria(excluded_airports=["LFPG' OR 1=1 --"]), NOW)
            connect.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'EXCLUDED_AIRPORT_UNKNOWN: ZZZA'):
            search(self.path, Criteria(excluded_airports=['EGLL', 'ZZZA']), NOW)
        self.assertEqual(5, search(self.path, Criteria(diversify=False), NOW)['available'])

    def test_pagination_reuses_filtered_population_without_requery(self):
        session = SearchSession()
        from finder.search import search as implementation
        with patch('finder.search.search', wraps=implementation) as query:
            first = session.page(self.path, Criteria(excluded_airports=['LFMN'], diversify=False, limit=1), NOW)
            second = session.page(self.path, Criteria(excluded_airports=['lfmn'], diversify=False, limit=1, offset=1), NOW)
            self.assertEqual(1, query.call_count)
        self.assertEqual(4, first['available'])
        self.assertNotEqual(first['results'][0]['pattern_id'], second['results'][0]['pattern_id'])
        self.assertTrue(all('LFMN' not in (r['origin'], r['destination']) for r in first['results'] + second['results']))


class ExclusionQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_desktop_field_is_visible_and_persists_raw_filters_including_invalid_draft(self):
        from PySide6.QtWidgets import QWidget
        from finder.ui import FinderDialog
        class Profile:
            state = {'finder_filters': {}}
            def save_state(self):
                self.saved = deepcopy(self.state)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'aviation.sqlite'
            fixture(path)
            owner = QWidget()
            owner.store = Profile()
            first = FinderDialog(owner, path, 'en')
            first.show()
            first.fields['origin'].setText('VIDP')
            first.fields['excluded_airports'].setText('EGLL LFPG')
            self.assertFalse(first.fields['excluded_airports'].isHidden())
            self.assertFalse(first.advanced_toggle.isChecked())
            self.assertIn('Avoid these airports', first.labels['excluded_airports'].text())
            self.assertEqual(['EGLL', 'LFPG'], first.criteria().excluded_airports)
            first.fields['excluded_airports'].setText('INVALID')
            first.persist_filters()
            first.close()
            second = FinderDialog(owner, path, 'fr')
            try:
                self.assertEqual('VIDP', second.fields['origin'].text())
                self.assertEqual('INVALID', second.fields['excluded_airports'].text())
                self.assertIn('Éviter', second.labels['excluded_airports'].text())
                second.run_search()
                self.assertIsNone(second.worker)
                self.assertIn('Aucun filtre', second.status.text())
                self.assertEqual([], second.results)
                self.assertFalse(second.use_button.isEnabled())
            finally:
                second.close()
                owner.close()


if __name__ == '__main__':
    unittest.main()
