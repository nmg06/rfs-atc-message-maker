from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from rfs_schema import MESSAGE_TYPES, empty_flight, empty_per_type
from storage import load_json, save_json
from templates import format_duration, render
from validation import emoji_count, validate


def sample_flight() -> dict:
    return {
        **empty_flight(),
        "airline": "Air India", "aircraft": "A330-900neo", "livery": "Air India",
        "callsign": "AIC186", "departure_icao": "CYVR", "departure_city": "Vancouver",
        "departure_flag": "🇨🇦", "arrival_icao": "RJAA", "arrival_city": "Tokyo Narita",
        "arrival_flag": "🇯🇵", "departure_runway": "26L", "arrival_runway": "16R",
        "departure_gate": "5", "arrival_gate": "13", "cruise_fl": "350",
        "distance": "4056.2", "estimated_flight_time": "10 h 20",
        "passengers": "290", "cargo": "10000", "fuel": "68200",
    }


def sample_data() -> dict:
    data = empty_per_type()
    data["ATC REQUEST"].update(pushback="5", server="ATC Report")
    data["AIRBORNE"].update(runway_used="26L", climb_target="to TOC", controller="Eden")
    data["ARRIVAL BOARD"].update(status="Descent", arrival_ete="~10 min", distance_remaining="20",
                                 atc_positions="GROUND & TOWER", approach="ILS")
    data["FLIGHT COMPLETED"].update(actual_flight_time="9h59m", controller="Eden")
    data["ATC ACTIVE"].update(airport_icao="EGLL", city="London Heathrow", flag="🇬🇧",
                              positions="GROUND + TOWER", duration="1h", departures="0", inbounds="0",
                              free_sentence="Flying from or into Heathrow? Send your route or callsign.")
    data["ATC OFFLINE"].update(airport_icao="EDDF", city="Frankfurt", flag="🇩🇪",
                               positions="GROUND + TOWER", duration="1h20", departures="10+", inbounds="0")
    data["DISPATCH FORM"].update(server="ATC Report")
    return data


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.flight = sample_flight()
        self.data = sample_data()

    def test_every_template_is_valid_and_under_emoji_limit(self):
        for message_type in MESSAGE_TYPES:
            with self.subTest(message_type=message_type):
                text = render(message_type, self.flight, self.data[message_type], "n1chita")
                self.assertTrue(text.strip())
                if message_type != "DISPATCH FORM":
                    self.assertLessEqual(emoji_count(text), 6)
                else:
                    self.assertEqual(emoji_count(text), 8)
                self.assertEqual([], validate(message_type, self.flight, self.data[message_type], "n1chita"))

    def test_atc_request_hides_optional_values_and_keeps_icao(self):
        self.flight["radio_callsign"] = ""
        self.flight["distance"] = ""
        self.flight["estimated_flight_time"] = ""
        text = render("ATC REQUEST", self.flight, self.data["ATC REQUEST"], "n1chita")
        self.assertIn("✈ n1chita │ A330-900neo", text)
        self.assertIn("Requesting Ground and Tower for departure at CYVR.", text)
        self.assertNotIn("RADIO", text)
        self.assertNotIn("ROUTE　　:", text)
        self.assertNotIn("ETE　　　:", text)

    def test_airborne_controller_and_no_atc_are_exclusive(self):
        data = self.data["AIRBORNE"]
        self.assertIn("@Eden", render("AIRBORNE", self.flight, data, "n1chita"))
        data["no_atc"] = True
        text = render("AIRBORNE", self.flight, data, "n1chita")
        self.assertIn("No ATC available for departure.", text)
        self.assertNotIn("@Eden", text)

    def test_arrival_center_blank_line_and_go_around(self):
        data = self.data["ARRIVAL BOARD"]
        text = render("ARRIVAL BOARD", self.flight, data, "n1chita")
        lines = text.splitlines()
        self.assertEqual("╭" + "─" * 27 + "╮", lines[0])
        self.assertEqual("ARRIVAL BOARD".center(27), lines[1])
        self.assertIn("「REQUESTING ATC REPORT」\n\n@RFS ATC", text)
        self.assertNotIn("FUEL", text)
        self.assertNotIn("STAR", text)
        self.assertNotIn("ALTITUDE", text)
        data["go_around"] = True
        text = render("ARRIVAL BOARD", self.flight, data, "n1chita")
        self.assertIn("first landing attempt unsuccessful", text)
        self.assertIn("second attempt", text)

    def test_completed_is_short_unless_detailed(self):
        data = self.data["FLIGHT COMPLETED"]
        text = render("FLIGHT COMPLETED", self.flight, data, "n1chita")
        self.assertIn("╭─────── ATC • ARRIVED ───────╮", text)
        self.assertIn("STATUS   : AT GATE 13", text)
        self.assertIn("Thanks for ATC 🙏 @Eden", text)
        self.assertNotIn("PASSENGERS", text)
        data["detailed"] = True
        self.assertIn("PASSENGERS", render("FLIGHT COMPLETED", self.flight, data, "n1chita"))

    def test_completed_preserves_icao_as_typed(self):
        self.flight["arrival_icao"] = "rjaa"
        text = render("FLIGHT COMPLETED", self.flight, self.data["FLIGHT COMPLETED"], "n1chita")
        self.assertIn("📡 rjaa • TOKYO NARITA", text)
        self.assertIn("CYVR → rjaa", text)

    def test_atc_sessions_do_not_invent_counts_or_ping(self):
        active = self.data["ATC ACTIVE"]
        text = render("ATC ACTIVE", self.flight, active, "n1chita")
        self.assertNotIn("@RFS ATC", text)
        self.assertEqual(6, emoji_count(text))
        closed = self.data["ATC OFFLINE"]
        closed["departures"] = ""
        text = render("ATC OFFLINE", self.flight, closed, "n1chita")
        self.assertNotIn("DEPARTURES", text)
        self.assertIn("Thanks to everyone who joined the session!", text)

    def test_flight_plan_and_dispatch_durations(self):
        plan = render("FLIGHT PLAN", self.flight, {}, "n1chita")
        self.assertIn("Distance : 4056.2 nm", plan)
        self.assertIn("Estimated Flight Time : 10h 20m", plan)
        dispatch = render("DISPATCH FORM", self.flight, self.data["DISPATCH FORM"], "n1chita")
        self.assertIn("Estimated Flight Time- 10:20", dispatch)
        self.assertEqual(emoji_count(dispatch), 8)
        self.assertEqual("9h59m", format_duration("9 h 59"))

    def test_missing_data_is_not_fabricated(self):
        blank = empty_flight()
        text = render("FLIGHT PLAN", blank, {}, "n1chita")
        self.assertNotIn("CYVR", text)
        self.assertNotIn("290", text)
        self.assertTrue(validate("FLIGHT PLAN", blank, {}, "n1chita"))


class ValidationAndStorageTests(unittest.TestCase):
    def test_invalid_nested_state_recovers_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            save_json(path, {"flight": None, "theme": [], "recent": {"airline": "invalid"}})
            default = {"flight": {"callsign": ""}, "theme": "Sombre", "recent": {"airline": []}}
            self.assertEqual(default, load_json(path, default))

    def test_invalid_icao_fl_runway_distance(self):
        flight = sample_flight()
        flight.update(departure_icao="CYY", cruise_fl="FL900", departure_runway="99Z", distance="many")
        issues = validate("ATC REQUEST", flight, sample_data()["ATC REQUEST"], "n1chita")
        keys = {issue.field for issue in issues}
        self.assertTrue({"departure_icao", "cruise_fl", "departure_runway", "distance"} <= keys)
        self.assertEqual("CYY", flight["departure_icao"])

    def test_hidden_old_flight_values_do_not_block_atc_session(self):
        flight = sample_flight()
        flight.update(departure_icao="XXX", cruise_fl="FL900", distance="many")
        self.assertEqual([], validate("ATC ACTIVE", flight, sample_data()["ATC ACTIVE"], "n1chita"))

    def test_json_with_accents_and_corruption(self):
        with tempfile.TemporaryDirectory(prefix="RFS ATC ") as folder:
            path = Path(folder) / "réglages.json"
            value = {"airline": "Air India", "note": "Départ à 10 h 20"}
            save_json(path, value)
            self.assertEqual(value, load_json(path, {}))
            path.write_text("{incorrect", encoding="utf-8")
            self.assertEqual({}, load_json(path, {}))
            self.assertTrue(list(path.parent.glob("réglages.json.corrupt-*")))

    def test_dispatch_form_has_no_emoji_limit(self):
        from message_builder import compose
        flight = sample_flight()
        data = sample_data()["DISPATCH FORM"]
        text = render("DISPATCH FORM", flight, data, "n1chita")
        self.assertEqual(8, emoji_count(text))
        self.assertIn("🎨 Livery-", text)
        self.assertIn("⏱️ Estimated Flight Time-", text)

        custom_flight = dict(flight)
        custom_flight["livery"] = "🎨🎨🎨 Special livery ✈️✈️"
        custom_text = compose("DISPATCH FORM", custom_flight, data, "n1chita")
        self.assertGreater(emoji_count(custom_text), 8)
        self.assertIn("🎨🎨🎨 Special livery ✈️✈️", custom_text)



if __name__ == "__main__":
    unittest.main()
