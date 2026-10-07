"""Repeated locale changes keep real Qt dialogs translated with bounded resources."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import gc
import unittest
from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QApplication, QDialogButtonBox
from i18n import set_language


class LanguageRuntimeTests(unittest.TestCase):
    def test_repeated_languages_translate_native_controls_without_accumulating_objects(self):
        app = QApplication.instance() or QApplication([])
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        try:
            for index in range(40):
                selected = 'fr' if index % 2 == 0 else 'en'
                set_language(selected)
                app.processEvents()
                self.assertEqual('fr_FR' if selected == 'fr' else 'en_GB', QLocale().name())
                self.assertEqual('Annuler' if selected == 'fr' else 'Cancel',
                    box.button(QDialogButtonBox.StandardButton.Cancel).text().replace('&', ''))
                gc.collect()
            count = len(app.findChildren(QTranslator))
            for _ in range(200):
                set_language('en')
            app.processEvents()
            self.assertEqual(count, len(app.findChildren(QTranslator)))
            self.assertLessEqual(count, 2)
        finally:
            box.close()
            set_language('fr')
