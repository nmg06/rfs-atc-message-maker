import math
import unittest

from fuel_calculator import calculate_fuel


class FuelCalculatorTests(unittest.TestCase):
    def test_known_a220_example_with_egll_alternate(self):
        result = calculate_fuel("airbus_a220_300", 5, "egll")
        self.assertEqual(result["alternate"], {"icao": "EGKK", "distance_nm": 30.0})
        self.assertEqual(result["display"]["taxi_out_kg"], "273 kg")
        self.assertEqual(result["display"]["trip_kg"], "9,750 kg")
        self.assertEqual(result["display"]["contingency_kg"], "488 kg")
        self.assertEqual(result["display"]["alternate_kg"], "618 kg")
        self.assertEqual(result["display"]["final_reserve_kg"], "975 kg")
        self.assertEqual(result["display"]["taxi_in_kg"], "182 kg")
        self.assertEqual(result["display"]["total_block_fuel"], "12,285 kg")
        self.assertTrue(math.isclose(result["total_block_fuel_kg_exact"], 12285.0))

    def test_missing_or_unknown_arrival_adds_no_alternate_fuel(self):
        self.assertIsNone(calculate_fuel("Airbus A220-300", 5)["alternate"])
        result = calculate_fuel("Airbus A220-300", 5, "ZZZZ")
        self.assertIsNone(result["alternate"])
        self.assertEqual(result["components_exact"]["alternate_kg"], 0.0)

    def test_closest_candidate_is_selected(self):
        result = calculate_fuel("Airbus A320-200", 2, "KLAX")
        self.assertEqual(result["alternate"], {"icao": "KSNA", "distance_nm": 35.0})

    def test_endurance_warning_and_input_validation(self):
        self.assertTrue(calculate_fuel("Airbus A318", 12)["exceeds_endurance"])
        with self.assertRaises(ValueError):
            calculate_fuel("Airbus A318", 0)
        with self.assertRaises(ValueError):
            calculate_fuel("Airbus A318", float("nan"))
        with self.assertRaises(LookupError):
            calculate_fuel("Unknown plane", 1)


if __name__ == "__main__":
    unittest.main()
