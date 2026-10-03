import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from PySide6.QtWidgets import QApplication
from route_map import RouteMap, airport_coordinates, great_circle, land_path


class RouteMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dateline_uses_short_arc_and_correct_endpoints(self):
        route = great_circle((35, 170), (40, -170))
        self.assertAlmostEqual(route[0][0], 35)
        self.assertAlmostEqual(route[-1][0], 40)
        self.assertAlmostEqual(route[-1][1], 190)
        self.assertLess(max(abs(b[1] - a[1]) for a, b in zip(route, route[1:])), 1)
        for pair in (((0, 0), (0, 180)), ((90, 0), (-90, 0)), ((1, 2), (1, 2))):
            self.assertTrue(all(math.isfinite(v) for p in great_circle(*pair) for v in p))

    def test_missing_invalid_coordinates_do_not_invent_route(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'map.sqlite'
            with sqlite3.connect(db) as connection:
                connection.execute('CREATE TABLE airports (icao TEXT, latitude REAL, longitude REAL)')
                connection.executemany('INSERT INTO airports VALUES (?,?,?)',
                                       [('LFPG',49.0097,2.5479), ('KJFK',40.6398,-73.7789), ('BAD',200,0)])
            connection.close()
            self.assertIsNone(airport_coordinates(str(db), 'BAD'))
            self.assertIsNone(airport_coordinates(str(db), "' OR 1=1 --"))
            widget = RouteMap()
            widget.resize(760, 330)
            widget.set_database_path(db)
            widget.set_flight({'departure_icao':'LFPG','arrival_icao':'KJFK'})
            self.assertEqual(len(widget._route), 97)
            widget.zoom(1.3)
            zoom = widget._zoom
            widget.set_flight({'departure_icao':'LFPG','arrival_icao':'KJFK','callsign':'NEW'})
            self.assertEqual(widget._zoom, zoom)
            for dark in (False, True):
                widget.set_dark(dark)
                widget.set_language('fr' if dark else 'en')
                self.assertFalse(widget.grab().isNull())
            widget.set_flight({'departure_icao':'LFPG','arrival_icao':'UNKNOWN'})
            self.assertEqual(widget._route, [])
            widget.close()

    def test_offline_land_resource_available(self):
        self.assertGreater(land_path().elementCount(), 1000)


if __name__ == '__main__':
    unittest.main()
