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
