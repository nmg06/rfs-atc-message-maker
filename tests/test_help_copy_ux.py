"""Real user regressions: scrolling, language, optional copy and contextual help."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QPushButton
import storage
from ui import RFSWindow
from help_content import CONTENT
from help_dialog import FlightdeckHelpDialog
from i18n import set_language


class HelpCopyUxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for name in ('STATE_FILE', 'HISTORY_FILE', 'PRESETS_FILE', 'DESIGNS_FILE'):
            override = patch.object(storage, name, Path(self.temp.name)/(name+'.json'))
            override.start(); self.addCleanup(override.stop)
        self.w = RFSWindow()
        self.addCleanup(self.w.close)
        self.addCleanup(lambda: set_language('fr'))

    def test_free_copy_keeps_edited_text_warnings_and_survives_restart(self):
        w = self.w
        w.aligned.setChecked(False)
        w.preview.setPlainText('A flight I want to share as-is')
        self.assertFalse(w.can_copy)
        self.assertTrue(w.validation_problems)
        w.strict_validation.setChecked(False)
        self.assertTrue(w.can_copy)
        w.copy_message()
        self.assertEqual('A flight I want to share as-is', self.app.clipboard().text())
        self.assertEqual('A flight I want to share as-is', w.store.history[0]['message'])
        self.assertIn('issue-', w.issues.text())
        restored = RFSWindow(); self.addCleanup(restored.close)
        self.assertFalse(restored.strict_validation.isChecked())
        self.assertEqual('A flight I want to share as-is', restored.preview.toPlainText())
        restored.strict_validation.setChecked(True)
        self.assertFalse(restored.can_copy)
        restored.strict_validation.setChecked(False)
        restored.preview.setPlainText('  ')
        self.assertFalse(restored.can_copy)

    def test_warning_link_opens_and_focuses_the_actual_field(self):
        w = self.w; w.show(); self.app.processEvents()
        index = next(i for i, issue in enumerate(w.validation_problems) if issue.field == 'departure_icao')
        w.issues.linkActivated.emit(f'issue-{index}')
        self.app.processEvents()
        self.assertEqual(1, w.deck_pages.currentIndex())
        self.assertEqual(w.flight_widgets['departure_icao'], self.app.focusWidget())

    def test_aircraft_wheels_scroll_popup_not_background_or_selection(self):
        w = self.w; w.deck_nav[1].click(); w.show(); self.app.processEvents()
        aircraft = w.flight_widgets['aircraft']; aircraft.showPopup(); self.app.processEvents()
        before = aircraft.currentText(); form_before = w.form_scroll.verticalScrollBar().value()
        def wheel(target, pixels, angle):
            event = QWheelEvent(QPointF(12,12), QPointF(target.mapToGlobal(QPoint(12,12))), QPoint(0,pixels), QPoint(0,angle), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
            self.app.sendEvent(target,event); self.app.processEvents()
        bar = aircraft.options.verticalScrollBar()
        wheel(aircraft.options.viewport(),0,-120)
        self.assertGreater(bar.value(),0)
        at = bar.value(); wheel(aircraft.search,-50,0)
        self.assertGreater(bar.value(),at)
        bar.setValue(bar.maximum()); wheel(aircraft.search,0,-120)
        self.assertEqual(form_before,w.form_scroll.verticalScrollBar().value())
        self.assertEqual(before,aircraft.currentText())
        aircraft.hidePopup(); wheel(aircraft,0,-120)
        self.assertEqual(before,aircraft.currentText())

    def test_english_themes_custom_aircraft_help_and_canonical_values(self):
        w=self.w
        w.language_combo.setCurrentIndex(w.language_combo.findData('en'))
        names=[w.visual_theme_combo.itemText(i) for i in range(w.visual_theme_combo.count())]
        self.assertIn('Avionics',names); self.assertIn('Sunset',names); self.assertIn('Lavender',names)
        self.assertFalse(set(names)&{'Avionique','Océan','Aurore','Crépuscule','Forêt','Ambre','Lavande'})
        self.assertIn('Custom aircraft',[v.text() for v in w.flight_widgets['aircraft'].findChildren(QPushButton)])
        self.assertEqual('Classique',w.design_combo.currentText())
        help=FlightdeckHelpDialog(w,'preview',True); help.show(); self.app.processEvents()
        self.assertEqual(30,len(help.faq_rows)); self.assertEqual('Preview and copying',help.topics.currentText())
        help.search.setText('ETE 5'); self.app.processEvents()
        visible=[row for row in help.faq_rows if not row[0].isHidden()]
        self.assertEqual(1,len(visible)); self.assertIn('five minutes',visible[0][1]['answer']['en'])
        help.close(); self.assertTrue(w.store.state['tutorial_seen'])
        self.assertEqual(30,len(CONTENT['faq']))
        self.assertEqual(8,len(CONTENT['topics']))
        for row in CONTENT['faq']:
            for key in ('question','answer'):
                self.assertEqual({'fr','en'},set(row[key])); self.assertTrue(row[key]['en'].strip())
