"""Desktop update consent, safe actions and Android draft restoration."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from copy import deepcopy
from pathlib import Path
from threading import Event
import tempfile
import unittest
from unittest.mock import patch, Mock

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import storage
import update_dialog
from i18n import set_language
from ui import RFSWindow


class UpdatesUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        for name in ('STATE_FILE', 'HISTORY_FILE', 'PRESETS_FILE', 'DESIGNS_FILE'):
            patcher = patch.object(storage, name, self.folder / (name + '.json'))
            patcher.start(); self.addCleanup(patcher.stop)
        patcher = patch.object(storage, 'DATA_DIR', self.folder)
        patcher.start(); self.addCleanup(patcher.stop)
        self.window = RFSWindow()
        self.addCleanup(self.window.close)
        self.addCleanup(lambda: set_language('fr'))

    def test_default_is_off_manual_request_is_single_and_closing_dialog_safe(self):
        w = self.window
        self.assertFalse(w.update_preferences['enabled'])
        with patch.object(update_dialog, 'start_worker', return_value=Mock()) as worker:
            w.check_updates()
            worker.assert_not_called()
            w.open_updates()
            w.check_updates(manual=True)
            self.assertTrue(w._update_running)
            self.assertFalse(w.update_dialog.check.isEnabled())
            w.check_updates(manual=True)
            worker.assert_called_once()
            w.update_dialog.close()
            self.app.processEvents()
            self.assertIsNone(w.update_dialog)
            w._updates_finished({'status': 'unavailable', 'reason': 'network_unavailable'})
            self.assertFalse(w._update_running)
            w.open_updates()
            self.assertFalse(w.update_dialog.download.isEnabled())
            self.assertIn('ne signifie pas', w.update_dialog.status.text())

    def test_english_opt_in_persists_locally_and_no_downgrade_link(self):
        w = self.window
        w.language_combo.setCurrentIndex(w.language_combo.findData('en'))
        w.open_updates(); dialog = w.update_dialog
        self.assertEqual('Updates', dialog.windowTitle())
        self.assertIn('at most once a day', dialog.automatic.text())
        dialog.automatic.setChecked(True)
        for _ in range(200):
            QTest.qWait(20)
            if not w._update_preferences_running:
                break
        self.assertFalse(w._update_preferences_running)
        self.assertTrue(update_dialog.read_preferences()['enabled'])
        w._updates_finished({'status': 'up_to_date', 'version': '0.3.0',
            'download_url': 'https://github.com/nmg06/rfs-atc-message-maker/releases/download/v0.3.0/a.apk'})
        self.assertFalse(dialog.download.isEnabled())
        self.assertFalse(dialog.notes.isEnabled())
        with patch.object(update_dialog.QDesktopServices, 'openUrl') as opened:
            dialog.open_link(download=True)
            opened.assert_not_called()
        self.assertNotIn('Aucune', dialog.status.text())
        self.assertNotIn('rfs_updates', w.store.export_backup())

    def test_real_worker_returns_immediately_and_does_not_hold_quit(self):
        w = self.window
        started, release, done = Event(), Event(), Event()
        def slow_check(platform):
            started.set()
            release.wait(2)
            done.set()
            return {'status': 'no_release'}
        with patch.object(update_dialog.updates, 'check_for_update', side_effect=slow_check):
            with patch.object(update_dialog, 'write_preferences'):
                w.check_updates(manual=True)
                self.assertTrue(started.wait(1))
                self.assertFalse(release.is_set())
                self.assertTrue(w._update_running)
                w.close()
                release.set()
                self.assertTrue(done.wait(1))
                for _ in range(40):
                    QTest.qWait(20)
                    if not w._update_running:
                        break
        self.assertFalse(w._update_running)
        self.assertEqual('no_release', w.update_preferences['last_result']['status'])

    def test_android_saved_draft_loads_without_unsupported_type_and_reexports(self):
        w = self.window
        presentation = deepcopy(w.store.state['presentation'])
        presentation['style'] = 'Compact'
        item = {'id': 'android-draft', 'label': 'Android taxi draft',
            'flight': {'callsign': 'AFR42', 'departure_icao': 'LFPG'},
            'message_type': 'TAXI', 'pilot_name': 'Mobile pilot',
            'presentation': presentation, 'preview_edits': {'TAXI': 'Taxi original'},
            'per_type': {'TAXI': {'taxi_route': 'A B'}}}
        w.store.state['saved_flights'] = [item]
        w._refresh_saved_flights()
        w.saved_flights.setCurrentIndex(w.saved_flights.findData('android-draft'))
        self.assertEqual('ATC REQUEST', w.store.state['message_type'])
        self.assertEqual('TAXI', w.store.state['android_message_type'])
        self.assertEqual('Mobile pilot', w.pilot_name.currentText())
        self.assertEqual('Taxi original', w.store.state['preview_edits']['TAXI'])
        self.assertEqual('A B', w.store.state['per_type']['TAXI']['taxi_route'])
        with patch('ui.QInputDialog.getText', return_value=('Android taxi draft', True)):
            w.save_current_flight()
        self.assertEqual('TAXI', w.store.state['saved_flights'][0]['message_type'])
        self.assertEqual('Taxi original', w.store.state['saved_flights'][0]['preview_edits']['TAXI'])
        self.assertEqual('A B', w.store.state['saved_flights'][0]['per_type']['TAXI']['taxi_route'])
        self.assertEqual('TAXI', w.store.preview_import(w.store.export_backup())['payload']['state']['message_type'])
        w.message_type.setCurrentText('AIRBORNE')
        self.assertNotIn('android_message_type', w.store.state)


if __name__ == '__main__':
    unittest.main()
