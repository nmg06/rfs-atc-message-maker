import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor,QPalette
from appearance import apply_palette,colourize_stylesheet,get_stylesheet
from visual_themes import THEMES,theme_colors


class VisualThemeTests(unittest.TestCase):
    def test_ten_shared_themes_have_readable_accents_in_both_modes(self):
        app=QApplication.instance() or QApplication([])
        self.assertEqual(10,len(THEMES))
        for row in THEMES:
            for dark in (True,False):
                colors=theme_colors(row[0],dark)
                apply_palette(app,dark,row[0])
                self.assertEqual(QColor(colors['accent']),app.palette().color(QPalette.ColorRole.Highlight))
                self.assertIn(colors['accent'],colourize_stylesheet(get_stylesheet(dark),dark,row[0]))
                def luminance(hex):
                    rgb=[int(hex[i:i+2],16)/255 for i in (1,3,5)]
                    linear=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in rgb]
                    return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))
                first,second=sorted([luminance(colors['accent']),luminance(colors['accent_text'])])
                self.assertGreaterEqual((second+.05)/(first+.05),4.5)
        apply_palette(app,True)
