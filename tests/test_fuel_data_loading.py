from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fuel import calculator


class FuelDataLoadingTests(unittest.TestCase):
    def test_load_json_uses_next_available_catalogue_directory(self):
        reference = Path(__file__).parents[1] / 'docs' / 'fuel' / 'reference'
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder) / 'missing'
            with patch.object(calculator, 'DATA_DIR_CANDIDATES', (missing, reference)):
                calculator._read_json_text.cache_clear()
                data = calculator.load_json('aircraft_fuel_data.json')
        self.assertIn('aircraft', data)
        self.assertTrue(data['aircraft'])

    def test_load_json_raises_explicit_error_when_catalogues_are_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder) / 'missing'
            with patch.object(calculator, 'DATA_DIR_CANDIDATES', (missing,)):
                calculator._read_json_text.cache_clear()
                with self.assertRaisesRegex(FileNotFoundError, 'aircraft_fuel_data.json'):
                    calculator.load_json('aircraft_fuel_data.json')
