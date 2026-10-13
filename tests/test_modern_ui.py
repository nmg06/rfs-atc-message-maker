"""Regression checks for presentation controls and Finder guidance."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QToolButton
from ui import RFSWindow
from finder.ui import FinderDialog
from finder.search import Criteria, search
from test_finder import fixture, NOW
from test_rfs import sample_flight, sample_data
import storage


class ModernUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        for name in ('STATE_FILE', 'HISTORY_FILE', 'PRESETS_FILE', 'DESIGNS_FILE'):
            p = patch.object(storage, name, folder / (name + '.json'))
            p.start()
            self.addCleanup(p.stop)
        self.window = RFSWindow()
        self.addCleanup(self.window.close)

    def test_presentation_toggle_and_language_keep_manual_message_and_flight(self):
        w = self.window
        w.store.state.update(flight=sample_flight(), per_type=sample_data())
        w._rebuild_forms()
        w.render_preview()
        w.preview.setPlainText('Manually edited flight message')
        before = deepcopy(w.store.state['flight'])
        self.assertTrue(w.presentation_panel.isHidden())
        w.presentation_toggle.click()
        self.assertFalse(w.presentation_panel.isHidden())
        w.language_combo.setCurrentIndex(w.language_combo.findData('en'))
        self.assertTrue(w.presentation_toggle.isChecked())
        self.assertFalse(w.presentation_panel.isHidden())
        self.assertEqual('Manually edited flight message', w.preview.toPlainText())
        self.assertEqual(before, w.store.state['flight'])
        self.assertIn('Message appearance', w.presentation_toggle.text())

    def test_route_summary_is_outside_scrolling_form_and_labels_have_buddies(self):
        w = self.window
        w.deck_nav[1].click()
        w.show()
        self.app.processEvents()
        self.assertFalse(w.form_scroll.isAncestorOf(w.flight_summary))
        for key, widget in w.flight_widgets.items():
            label = w.flight_form.labelForField(widget)
            if label:
                self.assertEqual(widget, label.buddy(), key)
                self.assertTrue(widget.accessibleName(), key)
        self.assertTrue(w.copy_button.isVisible())

    def test_collapsing_settings_does_not_reset_selected_design(self):
        w = self.window
        w.presentation_toggle.click()
        w.design_combo.setCurrentIndex(1)
        before = deepcopy(w.store.state['presentation'])
        w.presentation_toggle.click()
        w.render_preview()
        self.assertEqual(before, w.store.state['presentation'])
        self.assertIn(w.design_combo.itemText(1), w.presentation_summary.text())

    def test_finder_guidance_changes_with_results_and_filter_edits(self):
        db = Path(self.temp.name) / 'flights.sqlite'
        fixture(db)
        d = FinderDialog(self.window, db, language='en')
        self.addCleanup(d.close)
        self.assertIn('Choose an airline', d.empty_state.text())
        d.query = Criteria()
        d.search_revision = d.revision
        d.present(search(db, d.query, NOW))
        self.assertTrue(d.empty_state.isHidden())
        d.fields['origin'].setText('XXXX')
        self.assertFalse(d.empty_state.isHidden())
        d.query = Criteria(origin=['XXXX'])
        d.search_revision = d.revision
        d.present(search(db, d.query, NOW))
        self.assertIn('No matching profile', d.empty_state.text())
        self.assertFalse(d.use_button.isEnabled())
