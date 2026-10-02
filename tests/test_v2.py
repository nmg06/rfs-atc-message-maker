from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QPlainTextEdit
from test_rfs import sample_flight, sample_data
from message_builder import compose, validate_group, DEFAULT_PRESENTATION, apply_custom
from rfs_schema import MESSAGE_TYPES, FLIGHT_TYPES
from validation import emoji_count
from history_utils import duplicate_index
from country_data import COUNTRIES
from country_picker import CountryPicker, flag_for
from dialogs import PilotsDialog
import storage
from ui import RFSWindow


class BuilderTests(unittest.TestCase):
    def test_all_designs_lengths_and_templates(self):
        for kind in MESSAGE_TYPES:
            for design in ("Classique", "Carte", "Tableau ATC", "Bulletin", "Minimal"):
                for length in ("Court", "Moyen", "Détaillé"):
                    with self.subTest(kind=kind, design=design, length=length):
                        text = compose(kind, sample_flight(), sample_data()[kind], "n1chita", {"design": design, "length": length})
                        self.assertTrue(text.startswith("```\n"))
                        if kind != "DISPATCH FORM":
                            self.assertLessEqual(emoji_count(text), 6)
                        self.assertLessEqual(len(text), 2000)
                        if kind == "ATC ACTIVE":
                            self.assertNotIn("@RFS ATC", text)

    def test_parallel_and_independent_pilots_across_all_flight_messages(self):
        flight = sample_flight()
        flight["pilots"] = [
            {"name": "PilotTwo", "callsign": "TEST2", "aircraft": "A350", "departure_runway": "26R", "arrival_runway": "16L"},
            {"name": "PilotThree", "callsign": "TEST3", "aircraft": "B787", "departure_runway": "25", "arrival_runway": "34R"},
        ]
        for kind in FLIGHT_TYPES:
            with self.subTest(kind=kind):
                data = sample_data()[kind]
                text = compose(kind, flight, data, "n1chita", {"length": "Court"})
                for value in ("PilotTwo", "PilotThree", "TEST2", "TEST3", "A350", "B787"):
                    self.assertIn(value, text)
                self.assertNotIn("Parallel", text)
                if kind != "DISPATCH FORM":
                    self.assertLessEqual(emoji_count(text), 6)
                self.assertLessEqual(text.count("@RFS ATC"), 1)
                self.assertEqual([], validate_group(kind, flight, data, "n1chita"))
        flight["arrival_mode"] = "Parallèle"
        text = compose("ARRIVAL BOARD", flight, sample_data()["ARRIVAL BOARD"], "n1chita")
        self.assertIn("Parallel arrival", text)
        self.assertIn("RWY 16L", text)
        flight["pilots"][0]["arrival_runway"] = "RWY 16R"
        self.assertTrue(any("distincte" in i.text for i in validate_group("ARRIVAL BOARD", flight, sample_data()["ARRIVAL BOARD"], "n1chita")))

    def test_go_around_procedure_overrides_old_descent_status(self):
        data = sample_data()["ARRIVAL BOARD"]
        data.update(procedure="Go-around", status="")
        text = compose("ARRIVAL BOARD", sample_flight(), data, "n1chita")
        self.assertIn("Go-around in progress", text)
        self.assertNotIn("Descent", text)
        self.assertEqual([], validate_group("ARRIVAL BOARD", sample_flight(), data, "n1chita"))

    def test_centered_box_and_mentions_outside_code_block(self):
        text = compose("ARRIVAL BOARD", sample_flight(), sample_data()["ARRIVAL BOARD"], "n1chita")
        self.assertIn("│" + "ARRIVAL BOARD".center(27) + "│", text)
        self.assertTrue(text.endswith("```\n\n@RFS ATC"))

    def test_custom_templates_are_local_substitution_only(self):
        text = compose("AIRBORNE", sample_flight(), sample_data()["AIRBORNE"], "n1chita",
                       custom_design={"template": "{{pilot}} / {{callsign}}\n{{message}}\n{{arrival_ete}}"})
        self.assertIn("n1chita / AIC186", text)
        self.assertNotIn("{{", text)
        with self.assertRaises(ValueError):
            apply_custom("{{unknown}}", {})

    def test_history_keeps_operational_changes_but_merges_typos(self):
        entry = {"date": "2026-09-30T20:00:00", "message_type": "ARRIVAL BOARD", "pilot_name": "n1chita",
                 "flight": sample_flight(), "data": sample_data()["ARRIVAL BOARD"],
                 "message": compose("ARRIVAL BOARD", sample_flight(), sample_data()["ARRIVAL BOARD"], "n1chita")}
        corrected = deepcopy(entry)
        corrected["message"] = corrected["message"].replace("Narita", "Naritai")
        self.assertEqual(0, duplicate_index([entry], corrected))
        corrected["flight"]["arrival_runway"] = "16L"
        self.assertIsNone(duplicate_index([entry], corrected))
        corrected = deepcopy(entry)
        corrected["message"] += "!"
        corrected["date"] = "2026-10-01T20:00:00"
        self.assertIsNone(duplicate_index([entry], corrected))


class UiV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_flags_theme_copy_feedback_and_persistence(self):
        self.assertEqual(249, len(COUNTRIES))
        with TemporaryDirectory() as folder:
            paths = {key: Path(folder) / (key + ".json") for key in ("STATE_FILE", "HISTORY_FILE", "PRESETS_FILE", "DESIGNS_FILE")}
            with patch.multiple(storage, **paths):
                window = RFSWindow()
                window.store.state["flight"] = sample_flight()
                window.store.state["per_type"] = sample_data()
                window._rebuild_forms()
                window.render_preview()
                window.copy_message()
                self.assertEqual("✓ Message copié !", window.copy_button.text())
                window.copy_message()
                self.assertEqual(1, len(window.store.history))
                self.assertEqual(2, window.store.history[0]["copies"])
                self.assertLess(self.app.palette().color(QPalette.ColorRole.Base).lightness(), 80)
                self.assertEqual(QPlainTextEdit.LineWrapMode.WidgetWidth, window.preview.lineWrapMode())
                picker = window.flight_widgets["departure_flag"]
                self.assertIsInstance(picker, CountryPicker)
                picker.setEditText("France")
                self.assertEqual("🇫🇷", window.store.state["flight"]["departure_flag"])
                dialog = PilotsDialog(window.store.state["flight"], "n1chita", window)
                dialog.add_pilot({"name": "PilotTwo", "callsign": "TEST2"})
                self.assertEqual(1, len(dialog.values()["pilots"]))
                self.assertEqual("Indépendant", dialog.values()["arrival_mode"])
                window.store.state["flight"].update(dialog.values())
                window.store.save_design("test", {"name": "Local", "template": "{{message}}"})
                window.close()
                restored = storage.Store()
                self.assertEqual("TEST2", restored.state["flight"]["pilots"][0]["callsign"])
                self.assertEqual("Local", restored.designs["test"]["name"])


if __name__ == "__main__":
    unittest.main()
