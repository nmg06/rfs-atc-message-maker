import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from finder.search import Criteria, SearchSession, search
from finder.duration import parse_minutes, parse_finder_hours
from finder.ui import FinderDialog
from fuel.selection import resolve_aircraft
from fuel.ui import FuelDialog
from route_map import RouteMap, country_at, country_paths, inverse_mercator, mercator_y
from map_online import checked_url, parse_wind, tailwind, wind_components, wind_url, tile_url
from test_finder import fixture

NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)


class FinderCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'aviation.sqlite'
        fixture(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_cached_pages_are_exact_and_isolated_without_requery(self):
        session, criteria = SearchSession(), Criteria(limit=2, diversify=False)
        with patch('finder.search.search', wraps=search) as query:
            first = session.page(self.path, criteria, NOW)
            first['results'][0]['callsign'] = 'edited'
            for offset in (2, 4, 0):
                page = replace(criteria, offset=offset)
                self.assertEqual(search(self.path, page, NOW), session.page(self.path, page, NOW))
            self.assertEqual(1, query.call_count)
            session.page(self.path, replace(criteria, airline='AIC'), NOW)
            self.assertEqual(2, query.call_count)

    def test_database_change_invalidates_population(self):
        session, criteria = SearchSession(), Criteria(limit=2, diversify=False)
        before = session.page(self.path, criteria, NOW)
        with sqlite3.connect(self.path) as db:
            db.execute('DELETE FROM flight_patterns WHERE pattern_id=?', (before['results'][0]['pattern_id'],))
        db.close()
        self.assertEqual(before['matches']-1, session.page(self.path, criteria, NOW)['matches'])


class NewFlightdeckUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_duration_units_and_cached_more_less_keep_items(self):
        self.assertEqual(600, parse_finder_hours('10'))
        self.assertEqual(630, parse_finder_hours('10,5'))
        self.assertEqual(90, parse_finder_hours('90min'))
        self.assertEqual(10, parse_minutes('10'))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'aviation.sqlite'
            fixture(path)
            dialog = FinderDialog(None, path, 'fr')
            dialog.fields['min_minutes'].setText('10')
            self.assertEqual(600, dialog.criteria().min_minutes)
            self.assertEqual(60, dialog.criteria().time_tolerance)
            query = Criteria(limit=2, diversify=False)
            dialog.query, dialog.query_time = query, NOW
            dialog.search_revision = dialog.revision
            dialog.present(dialog.session.page(path, query, NOW))
            first = dialog.table.item(0, 0)
            with patch('finder.search.search', side_effect=AssertionError('Must use cache')):
                dialog.run_search(more=True)
                self.assertEqual(4, dialog.visible_count)
                dialog.show_less()
                self.assertEqual(2, dialog.visible_count)
                self.assertTrue(dialog.table.isRowHidden(2))
                dialog.run_search(more=True)
                self.assertEqual(4, dialog.visible_count)
                self.assertIs(first, dialog.table.item(0, 0))
            dialog.close()

    def test_unique_observed_type_prefills_fuel_and_ambiguous_does_not(self):
        flight = {'aircraft':'Airbus A220-300', 'estimated_flight_time':'5h', 'arrival_icao':'EGLL',
                  'selected_flight': {'aircraft_icao':'BCS3', 'fields':{'aircraft':'OBSERVED_AIRCRAFT_TYPE'}}}
        resolved = resolve_aircraft(flight)
        self.assertEqual('airbus_a220_300', resolved['record']['id'])
        dialog = FuelDialog(flight)
        self.assertEqual('airbus_a220_300', dialog.aircraft.currentData())
        dialog.calculate()
        self.assertEqual(12285, dialog.result['total_block_fuel_kg_exact'])
        dialog.close()
        flight['selected_flight']['aircraft_icao'] = 'B738'
        flight['aircraft'] = 'Boeing 737-800'
        resolved = resolve_aircraft(flight)
        self.assertIsNone(resolved['record'])
        self.assertGreater(len(resolved['candidates']), 1)
        dialog = FuelDialog(flight)
        self.assertIsNone(dialog.aircraft.currentData())
        dialog.close()

    def test_flight_picker_all_aircraft_and_deferred_theme_save(self):
        import storage
        from ui import RFSWindow
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.multiple(storage, DATA_DIR=root, STATE_FILE=root/'state.json',
                    HISTORY_FILE=root/'history.json', PRESETS_FILE=root/'presets.json', DESIGNS_FILE=root/'designs.json'):
                window = RFSWindow()
                picker = window.flight_widgets['aircraft']
                self.assertEqual(63, sum(picker.itemData(i) is not None for i in range(picker.count())))
                window.flight_widgets['callsign'].setText('TEST123')
                picker.setCurrentIndex(picker.findData('airbus_a220_300'))
                self.assertEqual('airbus_a220_300', window.store.state['flight']['fuel_aircraft_id'])
                self.assertEqual('TEST123', window.store.state['flight']['callsign'])
                picker.setCurrentText('Historic aircraft retained')
                self.assertEqual('Historic aircraft retained', window.store.state['flight']['aircraft'])
                with patch.object(window, 'save_state') as save:
                    window.toggle_theme()
                    self.assertFalse(save.called)
                    self.assertTrue(window.save_timer.isActive())
                window.close()

    def test_boundaries_deep_zoom_projection_and_country_selection(self):
        self.assertGreater(len(country_paths()), 200)
        for point, expected in (((48.85, 2.35), 'FR'), ((44.43, 26.1), 'RO'), ((39.93, 32.85), 'TR'), ((-33.86, 151.21), 'AU')):
            self.assertEqual(expected, country_at(*point)[0])
        self.assertIsNone(country_at(0, -30))
        for latitude in (-80, -45, 0, 48, 80):
            self.assertAlmostEqual(latitude, inverse_mercator(mercator_y(latitude)))
        with patch('map_online.download', side_effect=AssertionError('Default map must stay offline')):
            widget = RouteMap()
            widget.resize(800, 350)
            controls = widget.create_country_controls()
            widget.set_country(0, 'FR')
            widget.set_country(1, 'RO')
            selected = []
            widget.countries_selected.connect(lambda a,b: selected.append((a,b)))
            widget.find_countries_button.click()
            self.assertEqual([('FR','RO')], selected)
            widget.zoom(100)
            self.assertGreater(widget._zoom, 24)
            self.assertFalse(widget.grab().isNull())
            self.assertFalse(widget.online.pending)
            background = widget._background
            widget.grab()
            self.assertIs(background, widget._background)
            controls.close()
            widget.close()


class WeatherTests(unittest.TestCase):
    def test_wind_from_direction_and_tail_head_components(self):
        east, north = wind_components(100, 270)
        self.assertAlmostEqual(100, east)
        self.assertAlmostEqual(0, north)
        self.assertAlmostEqual(100, tailwind(100, 270, 90))
        self.assertAlmostEqual(-100, tailwind(100, 270, 270))
        self.assertAlmostEqual(0, tailwind(100, 270, 0))

    def test_real_response_contract_timestamp_units_null_and_host_restrictions(self):
        sample = {'latitude':48.85, 'longitude':2.35, 'utc_offset_seconds':0,
                  'hourly_units':{'wind_speed_250hPa':'kn'},
                  'hourly': {'time':['2026-10-03T12:00'], 'wind_speed_250hPa':[80],
                             'wind_direction_250hPa':[270], 'geopotential_height_250hPa':[10400]}}
        result = parse_wind(json.dumps(sample), 250)
        self.assertEqual('2026-10-03T12:00:00+00:00', result['samples'][0]['time'])
        sample['hourly']['wind_speed_250hPa'] = [None]
        with self.assertRaises(ValueError): parse_wind(json.dumps(sample), 250)
        for url in ('http://api.open-meteo.com/x','https://evil.test/x', 'file:///etc/passwd'):
            with self.assertRaises(ValueError): checked_url(url)
        self.assertIn('wind_speed_250hPa', wind_url([(48,2)], 250))
        with self.assertRaises(ValueError): wind_url([(48,2)], 123)
        with self.assertRaises(ValueError): tile_url(16, 0, 0)

    def test_disabled_wind_ignores_stale_reply(self):
        app = QApplication.instance() or QApplication([])
        widget = RouteMap()
        widget._wind_key = (250, ((48,2),))
        widget._wind_ready(widget._wind_key, {'samples':[1]}, '')
        self.assertIsNone(widget._wind)
        widget.close()
