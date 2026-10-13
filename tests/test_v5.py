"""Regression coverage for the user's theme, feedback link and design edits."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
import storage
from ui import RFSWindow
from dialogs import UnifiedDesignDialog
from report_dialog import ReportDialog, GOOGLE_FORMS_URL
from message_builder import compose
from validation import emoji_count
from i18n import set_language
from test_rfs import sample_flight, sample_data

class V5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.paths = patch.multiple(storage, **{k:self.root/(k+'.json') for k in ('STATE_FILE','HISTORY_FILE','PRESETS_FILE','DESIGNS_FILE')})
        self.paths.start()
        set_language('fr')

    def tearDown(self):
        for widget in self.app.topLevelWidgets():
            widget.close()
        self.app.processEvents()
        self.paths.stop()
        self.temp.cleanup()

    def test_help_opens_exact_form_only_after_click(self):
        with patch('report_dialog.QDesktopServices.openUrl', return_value=True) as open_url:
            window = RFSWindow()
            open_url.assert_not_called()
            window.help_menu.actions()[0].trigger()
            open_url.assert_called_once()
            self.assertEqual(GOOGLE_FORMS_URL, open_url.call_args.args[0].toString())
            self.assertIn('1FAIpQLSf5Btz-JubaPy9n8g2kpYvFSojD6ngSq3ruS0KEAzgxcUpHAw', GOOGLE_FORMS_URL)

    def test_minimal_respects_emoji_choice_and_route_flags(self):
        flight = sample_flight()
        flight.update(departure_flag='🇫🇷', arrival_flag='🇬🇧')
        for style in ('Aviation','Alternatif'):
            text = compose('ARRIVAL BOARD', flight, sample_data()['ARRIVAL BOARD'], 'Pilot', {'design':'Minimal','emoji_style':style})
            self.assertIn('🇫🇷', text)
            self.assertIn('🇬🇧', text)
            self.assertGreater(emoji_count(text), 1)
            self.assertLessEqual(emoji_count(text), 6)
        text = compose('ARRIVAL BOARD', flight, sample_data()['ARRIVAL BOARD'], 'Pilot', {'design':'Minimal','emoji_style':'Sans emojis'})
        self.assertEqual(0, emoji_count(text))

    def test_guided_conversion_keeps_next_flight_dynamic(self):
        window = RFSWindow()
        window.store.state.update(flight=sample_flight(), per_type=sample_data(), message_type='ATC REQUEST')
        dialog = UnifiedDesignDialog({'guided':True,'heading':'Hello','footer':'Bye','base_design':'Carte'}, window)
        dialog.convert_to_advanced()
        self.assertEqual('Hello\n\n{{message}}\n\nBye', dialog.template.toPlainText())
        window.store.state['flight']['callsign'] = 'NEW456'
        dialog.refresh()
        self.assertIn('NEW456', dialog.preview.toPlainText())

    def test_report_preview_consent_and_browser_failure(self):
        dialog = ReportDialog()
        dialog.title.setText('Example')
        image = self.root / 'example.png'
        image.write_bytes(b'fixture')
        with patch('report_dialog.QFileDialog.getOpenFileNames', return_value=([str(image)], '')):
            dialog.add_images()
        self.assertFalse(dialog.consent.isChecked())
        self.assertEqual([], json.loads(dialog.preview.toPlainText())['attachments'])
        dialog.consent.setChecked(True)
        self.assertEqual(['image-1.png'], json.loads(dialog.preview.toPlainText())['attachments'])
        with patch('report_dialog.QDesktopServices.openUrl', return_value=False):
            dialog.open_google_forms()
        self.assertIn('Impossible', dialog.status.text())

    def test_save_failure_is_not_reported_as_success(self):
        with patch('pathlib.Path.replace', side_effect=OSError('read only')):
            with self.assertRaises(OSError):
                storage.save_json(self.root/'example.json', {'name':'example'})

    def test_touchpad_pixels_scroll_without_changing_combo(self):
        window = RFSWindow()
        window.deck_nav[1].click()
        window.show()
        self.app.processEvents()
        combo = window.flight_widgets['airline']
        before = combo.currentText()
        bar = window.form_scroll.verticalScrollBar()
        bar.setValue(0)
        event = QWheelEvent(QPointF(8,8), QPointF(combo.mapToGlobal(QPoint(8,8))), QPoint(0,-35), QPoint(), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False)
        QApplication.sendEvent(combo, event)
        self.assertEqual(before, combo.currentText())
        self.assertGreater(bar.value(), 0)
