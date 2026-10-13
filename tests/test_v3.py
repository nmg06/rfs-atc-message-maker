import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

from test_rfs import sample_flight,sample_data
from message_builder import compose,preview_text,clipboard_text,BUILTIN_DESIGNS
from dialogs import JokeDialog,PilotsDialog
import storage


class RevisedUxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_group_is_compact_and_selected_per_message(self):
        flight=sample_flight()
        flight['pilots']=[{'name':'Friend','callsign':'ABC2','aircraft':'A350','arrival_runway':'16L',
                           'message_types':['ARRIVAL BOARD']}]
        arrival=compose('ARRIVAL BOARD',flight,sample_data()['ARRIVAL BOARD'],'Primary')
        departure=compose('ATC REQUEST',flight,sample_data()['ATC REQUEST'],'Primary')
        self.assertIn('Primary / Friend',arrival)
        self.assertEqual(1,arrival.count('STATUS'))
        self.assertIn('Friend: RWY 16L',arrival)
        self.assertNotIn('Friend',departure)
        self.assertLess(len(arrival),1300)

    def test_preview_hides_fences_and_short_departure_omits_destination(self):
        text=compose('ATC REQUEST',sample_flight(),sample_data()['ATC REQUEST'],'Pilot',{'length':'Court'})
        shown=preview_text(text)
        self.assertNotIn('```',shown)
        self.assertNotIn(sample_flight()['arrival_icao'],shown)
        self.assertIn(sample_flight()['departure_icao'],shown)
        self.assertTrue(clipboard_text(shown).startswith('```\n'))
        self.assertTrue(clipboard_text(shown).endswith('@RFS ATC'))

    def test_designs_change_body_layout_not_just_border(self):
        bodies=[preview_text(compose('ATC REQUEST',sample_flight(),sample_data()['ATC REQUEST'],'Pilot',{'design':d})).split('\n',3)[-1]
                for d in BUILTIN_DESIGNS]
        self.assertEqual(len(BUILTIN_DESIGNS),len(set(bodies)))

    def test_pilots_remembered_without_forcing_into_every_message(self):
        with tempfile.TemporaryDirectory() as folder:
            paths={k:Path(folder)/(k+'.json') for k in ('STATE_FILE','HISTORY_FILE','PRESETS_FILE','DESIGNS_FILE')}
            with patch.multiple(storage,**paths):
                store=storage.Store()
                store.remember_pilot({'name':'Friend','callsign':'ABC2','message_types':[]})
                store.save_state()
                restored=storage.Store()
                self.assertEqual('ABC2',restored.state['pilot_library'][0]['callsign'])
                dialog=PilotsDialog(sample_flight(),'Primary',library=restored.state['pilot_library'])
                dialog.saved_pilots.setCurrentIndex(1)
                dialog.add_saved()
                self.assertEqual('Friend',dialog.values()['pilots'][0]['name'])
                dialog.close()

    def test_joke_reveals_before_accepting_input_and_on_close(self):
        dialog=JokeDialog()
        dialog.show()
        QTest.keyClicks(dialog.props[0],'4111111111111111')
        self.assertTrue(dialog.revealed)
        self.assertTrue(all(not field.text() for field in dialog.props))
        second=JokeDialog()
        second.reject()
        self.assertTrue(second.revealed)

    def test_joke_does_not_reveal_on_empty_focus_input_method(self):
        from PySide6.QtGui import QInputMethodEvent
        dialog=JokeDialog()
        dialog.show()
        self.app.processEvents()
        self.assertFalse(dialog.revealed)
        self.app.sendEvent(dialog.props[0],QInputMethodEvent())
        self.assertFalse(dialog.revealed)
        entered=QInputMethodEvent();entered.setCommitString('4')
        self.app.sendEvent(dialog.props[0],entered)
        self.assertTrue(dialog.revealed)
        self.assertTrue(all(not field.text() for field in dialog.props))
