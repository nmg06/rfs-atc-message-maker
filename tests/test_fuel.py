from copy import deepcopy
import importlib.util
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

from PySide6.QtWidgets import QApplication
from fuel.calculator import calculate_fuel,load_json,DISCLAIMER
from fuel.ui import FuelDialog
from ui import RFSWindow
import storage


class FuelTests(unittest.TestCase):
    def test_supplied_a220_5h_egll_example(self):
        result=calculate_fuel('airbus_a220_300',5,'egll')
        self.assertEqual({'icao':'EGKK','distance_nm':30.0},result['alternate'])
        self.assertEqual({'taxi_out_kg':273.,'trip_kg':9750.,'contingency_kg':487.5,'alternate_kg':617.5,
                          'final_reserve_kg':975.,'taxi_in_kg':182.},result['components_exact'])
        self.assertEqual(12285.,result['total_block_fuel_kg_exact'])
        self.assertEqual('12,285 kg',result['display']['total_block_fuel'])
        self.assertEqual('488 kg',result['display']['contingency_kg'])
        self.assertEqual('618 kg',result['display']['alternate_kg'])

    def test_invalid_inputs_and_ambiguous_variants(self):
        for value in (0,-1,float('nan'),float('inf'),True,'5'):
            with self.assertRaises(ValueError):
                calculate_fuel('airbus_a220_300',value)
        for aircraft in ('Unknown plane','A320','Airbus'):
            with self.assertRaises(LookupError):
                calculate_fuel(aircraft,5)
        for burn in (None,0,-1,float('nan'),True):
            data=load_json('aircraft_fuel_data.json')
            data['aircraft'][0]['cruise_burn_kg_h']=burn
            with self.assertRaises(ValueError):
                calculate_fuel(data['aircraft'][0]['id'],5,aircraft_data=data)

    def test_unknown_arrival_alternates_and_endurance(self):
        for airport in (None,'','ZZZZ'):
            result=calculate_fuel('airbus_a220_300',5,airport)
            self.assertIsNone(result['alternate'])
            self.assertEqual(0,result['components_exact']['alternate_kg'])
            self.assertEqual(0,result['alternate_time_hours'])
            self.assertIn('0 kg',result['alternate_explanation'])
        result=calculate_fuel('Airbus A320-200',2,'KLAX')
        self.assertEqual({'icao':'KSNA','distance_nm':35.0},result['alternate'])
        self.assertTrue(calculate_fuel('Airbus A318',12)['exceeds_endurance'])

    def test_provenance_and_all_63_match_reference(self):
        reference=Path(__file__).parents[1]/'docs/fuel/reference/fuel_calculator.py'
        spec=importlib.util.spec_from_file_location('fuel_reference',reference)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        data=load_json('aircraft_fuel_data.json')
        self.assertEqual(63,len(data['aircraft']))
        self.assertEqual(64,len(load_json('airport_alternates.json')['destinations']))
        for record in data['aircraft']:
            result=calculate_fuel(record['id'],2.75,'EGLL')
            expected=module.calculate_fuel(record['id'],2.75,'EGLL')
            self.assertEqual(expected['components_exact'],result['components_exact'])
            self.assertEqual(expected['total_block_fuel_kg_exact'],result['total_block_fuel_kg_exact'])
            self.assertEqual(record,result['provenance']['aircraft_record'])
            self.assertEqual(DISCLAIMER,result['warning'])


class FuelUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_explicit_variant_and_application_to_current_flight(self):
        with tempfile.TemporaryDirectory() as folder:
            paths={k:Path(folder)/(k+'.json') for k in ('STATE_FILE','HISTORY_FILE','PRESETS_FILE','DESIGNS_FILE')}
            with patch.multiple(storage,**paths):
                window=RFSWindow()
                window.store.state['flight'].update(aircraft='A320',arrival_icao='EGLL',callsign='TEST123')
                dialog=FuelDialog(window.store.state['flight'],window)
                dialog.selected.connect(window.use_fuel_result)
                self.assertIsNone(dialog.aircraft.currentData())
                dialog.hours.setText('5')
                dialog.calculate()
                self.assertFalse(dialog.apply_button.isEnabled())
                dialog.aircraft.setCurrentIndex(dialog.aircraft.findData('airbus_a220_300'))
                dialog.calculate()
                self.assertEqual('12,285 kg',dialog.table.item(6,1).text())
                self.assertIn('EGKK',dialog.provenance.toPlainText())
                dialog.use_result()
                flight=window.store.state['flight']
                self.assertEqual('12285',flight['fuel'])
                self.assertEqual('TEST123',flight['callsign'])
                self.assertEqual(12285,flight['fuel_calculation']['total_block_fuel_kg_exact'])
                window.close()
                self.assertEqual('12285',storage.Store().state['flight']['fuel'])
