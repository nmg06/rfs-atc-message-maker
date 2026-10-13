"""Exercise the adjacent fuel shortcut through actual Qt button clicks."""
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton
from fuel.ui import FuelDialog
from i18n import set_language
from ui import RFSWindow
from validation import Issue
import storage


class FuelShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_shortcut_prefills_current_flight_not_arrival_ete_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = {key: Path(folder) / (key + '.json')
                     for key in ('STATE_FILE', 'HISTORY_FILE', 'PRESETS_FILE', 'DESIGNS_FILE')}
            with patch.multiple(storage, **paths):
                window = RFSWindow()
                try:
                    window.store.state['flight'].update(aircraft='Airbus A220-300',
                        estimated_flight_time='5h30', arrival_icao='EGLL', fuel='100', callsign='TEST123')
                    window.store.state['per_type']['ARRIVAL BOARD']['arrival_ete'] = '5min'
                    window.message_type.setCurrentText('ARRIVAL BOARD')
                    window._rebuild_forms()
                    # A fresh edit must be read, even before the save timer fires.
                    window.flight_widgets['fuel'].setText('777')
                    before = deepcopy(window.store.state['flight'])
                    observed = []

                    def capture(dialog):
                        observed.append((dialog.aircraft.currentData(), dialog.hours.text(), dialog.arrival.text()))
                        return 0

                    button = window.findChild(QPushButton, 'calculateCurrentFlightFuel')
                    self.assertIsNotNone(button)
                    with patch.object(FuelDialog, 'exec', capture):
                        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                    self.assertEqual([('airbus_a220_300', '5.5', 'EGLL')], observed)
                    self.assertEqual(before, window.store.state['flight'])
                    # Wrapping the row must not lose validation labels or input focus.
                    field = window.flight_widgets['fuel']
                    with patch('ui.validate_group', return_value=[Issue('fuel', 'Test fuel warning')]):
                        window._refresh_validation()
                    label = window.flight_form.labelForField(field._form_row)
                    self.assertIs(label.buddy(), field)
                    self.assertIn('⚠', label.text())
                    self.assertEqual('Test fuel warning', field.accessibleDescription())
                    with patch('ui.validate_group', return_value=[]):
                        window._refresh_validation()
                    self.assertNotIn('⚠', label.text())

                    # Generic aircraft codes must still require an explicit variant.
                    window.store.state['flight'].update(aircraft='A320', estimated_flight_time='')
                    observed.clear()
                    with patch.object(FuelDialog, 'exec', capture):
                        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                    self.assertEqual([(None, '', 'EGLL')], observed)
                finally:
                    window.close()
                    set_language('fr')

    def test_shortcut_is_present_on_every_desktop_fuel_field_in_english(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = {key: Path(folder) / (key + '.json')
                     for key in ('STATE_FILE', 'HISTORY_FILE', 'PRESETS_FILE', 'DESIGNS_FILE')}
            with patch.multiple(storage, **paths):
                window = RFSWindow()
                try:
                    window.store.state['language'] = 'en'
                    set_language('en')
                    for kind in ('ARRIVAL BOARD', 'FLIGHT COMPLETED', 'FLIGHT PLAN'):
                        window.message_type.setCurrentText(kind)
                        window._rebuild_forms()
                        button = window.findChild(QPushButton, 'calculateCurrentFlightFuel')
                        self.assertIn('fuel', window.flight_widgets)
                        self.assertEqual('Calculate fuel', button.text())
                    window.message_type.setCurrentText('ATC REQUEST')
                    window.length_combo.setCurrentText('Détaillé')
                    window._rebuild_forms()
                    self.assertIn('fuel', window.flight_widgets)
                    self.assertEqual('Calculate fuel', window.findChild(QPushButton, 'calculateCurrentFlightFuel').text())
                finally:
                    window.close()
                    set_language('fr')


if __name__ == '__main__':
    unittest.main()
