import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

import tempfile
from pathlib import Path
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from finder.ui import FinderDialog
from test_finder import fixture
from ui import RFSWindow
import storage


class FinderUiTests(unittest.TestCase):
    def test_recent_routes_display_unknown_fields_and_details_in_english(self):
        import sqlite3
        from finder.route_catalog import SCHEMA
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'aviation.sqlite'
            fixture(path)
            with sqlite3.connect(path) as db:
                db.executescript(SCHEMA)
                db.execute("INSERT INTO observed_routes VALUES (1,'AFR999','AFR',1,2,.97,5,8,'2026-09-02T12:00:00+00:00','2026-10-06T12:00:00+00:00',200,'test')")
            db.close()
            dialog=FinderDialog(None,path,'en')
            try:
                dialog.route_catalog.setChecked(True)
                self.assertFalse(dialog.rfs_only.isChecked())
                dialog.run_search()
                for _ in range(200):
                    QTest.qWait(10)
                    if dialog.worker and dialog.worker.isFinished():
                        break
                self.assertEqual(1,len(dialog.results),dialog.status.text())
                self.assertEqual('Not provided',dialog.table.item(0,2).text())
                self.assertEqual('Not provided',dialog.table.item(0,3).text())
                text=dialog.details.toPlainText()
                self.assertIn('aircraft',text.lower())
                self.assertIn('Airline inferred',text)
                self.assertNotIn('None',text)
                self.assertNotIn('0h00',text)
                self.assertNotIn('Durée',text)
            finally:
                if dialog.worker:
                    dialog.worker.wait(5000)
                dialog.close()

    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_search_select_and_existing_messages(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            path=root/'aviation.sqlite'
            fixture(path)
            original=(storage.STATE_FILE,storage.HISTORY_FILE,storage.PRESETS_FILE,storage.DESIGNS_FILE)
            storage.STATE_FILE=root/'state.json'
            storage.HISTORY_FILE=root/'history.json'
            storage.PRESETS_FILE=root/'presets.json'
            storage.DESIGNS_FILE=root/'designs.json'
            window=None
            dialog=None
            try:
                window=RFSWindow()
                window.store.state['flight']['fuel']='999'
                window.store.state['flight']['arrival_runway']='27L'
                dialog=FinderDialog(window,path,'fr')
                dialog.selected.connect(window.use_found_flight)
                dialog.fields['airline'].setText('Air India')
                dialog.fields['destination'].setText('LFPG')
                dialog.show()
                dialog.run_search()
                for _ in range(200):
                    QTest.qWait(10)
                    if dialog.worker and dialog.worker.isFinished() and dialog.results:
                        break
                self.assertEqual(1,len(dialog.results),dialog.status.text())
                self.assertIn('DISPONIBLES',dialog.details.toPlainText())
                dialog.use_flight()
                self.assertEqual('AIC104',window.store.state['flight']['callsign'])
                self.assertEqual('999',window.store.state['flight']['fuel'])
                for kind in ('ATC REQUEST','AIRBORNE','ARRIVAL BOARD','FLIGHT PLAN','DISPATCH FORM'):
                    window.message_type.setCurrentText(kind)
                    window.render_preview()
                    self.assertIn('AIC104',window.preview.toPlainText())
                    self.assertEqual('LFPG',window.store.state['flight']['arrival_icao'])
                self.assertEqual('',window.store.state['current_flight_id'])
                self.assertIn('selected_flight',storage.load_json(root/'state.json',{})['flight'])
            finally:
                if dialog:
                    if dialog.worker:
                        dialog.worker.wait(5000)
                    dialog.close()
                if window:
                    window.close()
                self.app.processEvents()
                storage.STATE_FILE,storage.HISTORY_FILE,storage.PRESETS_FILE,storage.DESIGNS_FILE=original

    def test_missing_data_does_not_break_generator(self):
        with tempfile.TemporaryDirectory() as folder:
            dialog=FinderDialog(None,Path(folder)/'missing.sqlite', 'en')
            dialog.run_search()
            for _ in range(200):
                QTest.qWait(10)
                if dialog.worker and dialog.worker.isFinished():
                    break
            self.app.processEvents()
            self.assertIn('missing',dialog.status.text().lower())
            self.assertFalse(dialog.use_button.isEnabled())
            dialog.close()
    def test_swap_endpoints_and_return_flight_buttons(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'aviation.sqlite'
            fixture(path)
            dialog = FinderDialog(None, path, 'en')
            try:
                dialog.fields['origin'].setText('LFPG')
                dialog.fields['destination'].setText('EGLL')
                dialog.swap_button.click()
                self.assertEqual('EGLL', dialog.fields['origin'].text())
                self.assertEqual('LFPG', dialog.fields['destination'].text())
                dialog.fields['origin'].setText('')
                dialog.fields['destination'].setText('')
                dialog.fields['callsign'].setText('AIC104')
                dialog.run_search()
                for _ in range(200):
                    QTest.qWait(10)
                    if dialog.worker and dialog.worker.isFinished() and dialog.results:
                        break
                self.assertEqual(1, len(dialog.results))
                self.assertTrue(dialog.return_button.isEnabled())
                self.assertTrue(dialog.next_leg_button.isEnabled())
                dialog.return_flight()
                self.assertEqual('LFPG', dialog.fields['origin'].text())
                self.assertEqual('VIDP', dialog.fields['destination'].text())
                self.assertEqual('', dialog.fields['callsign'].text())
            finally:
                if dialog.worker:
                    dialog.worker.wait(5000)
                dialog.close()
                self.app.processEvents()
