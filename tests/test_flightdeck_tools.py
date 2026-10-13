import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from fuel.ui import FuelDialog
from finder.ui import FinderDialog
from finder.search import Criteria
from test_finder import fixture


class FlightdeckToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_aircraft_popup_filters_without_changing_selection_and_escape_cancels(self):
        dialog = FuelDialog({})
        picker = dialog.aircraft
        self.assertFalse(picker.isEditable())
        picker.setCurrentIndex(picker.findData('airbus_a220_300'))
        selected = picker.currentData()
        picker.showPopup()
        picker.search.setText('Boeing')
        self.assertGreater(picker.options.count(), 0)
        self.assertTrue(all('Boeing' in picker.options.item(i).text() for i in range(picker.options.count())))
        QTest.keyClick(picker.search, Qt.Key.Key_Return)
        self.assertEqual(selected, picker.currentData())
        QTest.keyClick(picker.search, Qt.Key.Key_Escape)
        self.assertFalse(picker.popup.isVisible())
        self.assertEqual(selected, picker.currentData())
        dialog.close()

    def test_aircraft_keyboard_explicit_choice_and_empty_search(self):
        dialog = FuelDialog({})
        picker = dialog.aircraft
        picker.showPopup()
        picker.search.setText('no such aircraft')
        self.assertEqual(0, picker.options.count())
        self.assertIsNone(picker.currentData())
        picker.search.setText('Airbus A220')
        QTest.keyClick(picker.search, Qt.Key.Key_Down)
        expected = picker.itemData(picker.options.currentItem().data(Qt.ItemDataRole.UserRole))
        QTest.keyClick(picker.options, Qt.Key.Key_Return)
        self.assertEqual(expected, picker.currentData())
        self.assertFalse(picker.popup.isVisible())
        dialog.close()

    def test_more_button_appends_selects_new_rows_and_preserves_existing_items(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'aviation.sqlite'
            fixture(path)
            dialog = FinderDialog(None, path, 'en')
            dialog.show()
            def wait():
                for _ in range(300):
                    QTest.qWait(10)
                    if dialog.worker and dialog.worker.isFinished() and dialog.search_button.isEnabled():
                        return
                self.fail('Finder worker did not finish')
            try:
                with patch.object(dialog, 'criteria', return_value=Criteria(limit=2, diversify=False)):
                    dialog.run_search()
                    wait()
                    self.assertEqual(2, len(dialog.results))
                    first_item = dialog.table.item(0, 0)
                    first_ids = [r['pattern_id'] for r in dialog.results]
                    dialog.more_button.click()
                    wait()
                    self.assertEqual(4, len(dialog.results))
                    self.assertEqual(2, dialog.table.currentRow())
                    self.assertIs(first_item, dialog.table.item(0, 0))
                    self.assertEqual(first_ids, [r['pattern_id'] for r in dialog.results[:2]])
                    self.assertIn('2 profiles added', dialog.status.text())
                    dialog.more_button.click()
                    wait()
                    self.assertEqual(5, len(dialog.results))
                    self.assertEqual(4, dialog.table.currentRow())
                    self.assertFalse(dialog.more_button.isEnabled())
            finally:
                if dialog.worker:
                    dialog.worker.wait(5000)
                dialog.close()
