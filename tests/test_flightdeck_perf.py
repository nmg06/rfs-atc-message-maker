"""Theme switches must not replace the Qt style or change widget content."""
import os
import unittest
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QLineEdit
from appearance import apply_palette


class ThemePerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_palette_switch_reuses_style_and_preserves_input(self):
        apply_palette(self.app, True)
        style = self.app.style()
        edit = QLineEdit('AIC173')
        edit.setCursorPosition(3)
        for mode in (False, True, False):
            apply_palette(self.app, mode)
            self.assertIs(self.app.style(), style)
            self.assertEqual(edit.text(), 'AIC173')
            self.assertEqual(edit.cursorPosition(), 3)
            expected = '#0b1220' if mode else '#f1f5f9'
            self.assertEqual(self.app.palette().color(QPalette.ColorRole.Window).name(), expected)
        edit.close()

    def test_unchanged_palette_does_not_repolish(self):
        app = Mock()
        values = {}
        app.property.side_effect = lambda key: values.get(key)
        app.setProperty.side_effect = lambda key, value: values.__setitem__(key, value)
        apply_palette(app, True)
        apply_palette(app, True)
        apply_palette(app, False)
        apply_palette(app, False)
        self.assertEqual(app.setStyle.call_count, 1)
        self.assertEqual(app.setPalette.call_count, 2)


if __name__ == '__main__':
    unittest.main()
