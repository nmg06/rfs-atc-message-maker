import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
import storage
from ui import RFSWindow


class UiWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_current_flight_carries_across_messages_and_copy(self):
        original = (storage.STATE_FILE, storage.HISTORY_FILE, storage.PRESETS_FILE)
        with tempfile.TemporaryDirectory(prefix="RFS UI ") as folder:
            storage.STATE_FILE = Path(folder) / "state.json"
            storage.HISTORY_FILE = Path(folder) / "history.json"
            storage.PRESETS_FILE = Path(folder) / "presets.json"
            try:
                window = RFSWindow()
                values = {
                    "airline": "Air India", "aircraft": "A330-900neo", "callsign": "AIC186",
                    "departure_icao": "CYVR", "arrival_icao": "RJAA", "departure_gate": "5",
                    "departure_runway": "26L", "cruise_fl": "350",
                }
                for key, value in values.items():
                    widget = window.flight_widgets[key]
                    if hasattr(widget, "setCurrentText"):
                        widget.setCurrentText(value)
                    else:
                        widget.setText(value)
                window.type_widgets["pushback"].setText("5")
                window.render_preview()
                self.assertTrue(window.copy_button.isEnabled(), window.issues.text())
                window.flight_widgets["callsign"].setText("AIC187")
                window.copy_message()
                self.assertIn("CYVR", QApplication.clipboard().text())
                self.assertIn("AIC187", QApplication.clipboard().text())
                self.assertEqual(1, len(window.store.history))

                window.message_type.setCurrentText("AIRBORNE")
                self.assertEqual("Air India", window.store.state["flight"]["airline"])
                self.assertEqual("RJAA", window.store.state["flight"]["arrival_icao"])
                window.type_widgets["climb_target"].setCurrentText("to TOC")
                window.type_widgets["no_atc"].setChecked(True)
                window.render_preview()
                self.assertIn("AIC187", window.preview.toPlainText())
                self.assertTrue(window.copy_button.isEnabled(), window.issues.text())

                window.message_type.setCurrentText("ARRIVAL BOARD")
                window.flight_widgets["arrival_runway"].setText("16R")
                window.type_widgets["status"].setCurrentText("Descent")
                window.render_preview()
                self.assertIn("「REQUESTING ATC REPORT」\n\n@RFS ATC", window.preview.toPlainText())
                self.assertNotIn('```', window.preview.toPlainText())
                self.assertIn("「REQUESTING ATC REPORT」\n```\n\n@RFS ATC", window._clipboard_message())
                self.assertTrue(window.copy_button.isEnabled(), window.issues.text())
                window.new_flight()
                self.assertEqual("", window.store.state["per_type"]["ATC REQUEST"]["pushback"])
                self.assertFalse(window.store.state["per_type"]["AIRBORNE"]["no_atc"])
                self.assertEqual("", window.store.state["flight"]["callsign"])
                window.close()
            finally:
                storage.STATE_FILE, storage.HISTORY_FILE, storage.PRESETS_FILE = original


if __name__ == "__main__":
    unittest.main()
