"""Prevent divergent help copies and verify the browser port against PC fuel."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from fuel.calculator import calculate_fuel, load_json
from help_content import CONTENT

ROOT = Path(__file__).resolve().parents[1]


class WebFuelHelpTests(unittest.TestCase):
    def test_generated_help_is_identical_for_phone_and_web(self):
        for folder in ('mobile', 'android/app/src/main/assets/www'):
            source = (ROOT/folder/'help-content.js').read_text(encoding='utf-8')
            self.assertEqual(CONTENT, json.loads(source.removeprefix('window.FLIGHTDECK_HELP=')[:-2]))
            for name in ('help-ui.js', 'help-ui.css'):
                self.assertEqual((ROOT/'assets'/name).read_bytes(), (ROOT/folder/name).read_bytes())

    def test_web_fuel_all_aircraft_matches_pc_components_and_unknown_arrival(self):
        node = os.environ.get('RFS_TEST_NODE') or shutil.which('node')
        if not node:
            self.skipTest('Node.js required to test browser fuel port')
        cases = []
        for aircraft in load_json('aircraft_fuel_data.json')['aircraft']:
            for hours in (.5, 5, 13.75):
                for arrival in ('EGLL', 'LFPG', 'ZZZZ'):
                    cases.append([aircraft['id'], hours, arrival])
        script = """const fs=require('fs'),vm=require('vm');
const sandbox={window:{},document:{addEventListener(){}},webT:(fr,en)=>en};
vm.createContext(sandbox);
for(const name of ['fuel-reference.js','fuel.js'])vm.runInContext(fs.readFileSync('mobile/'+name,'utf8'),sandbox);
const cases=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(cases.map(args=>sandbox.calculateSourceFuel(...args))));"""
        response = subprocess.run([node, '-e', script], input=json.dumps(cases), text=True, encoding='utf-8', cwd=ROOT, capture_output=True, check=True, timeout=30)
        results = json.loads(response.stdout)
        for args, actual in zip(cases, results):
            expected = calculate_fuel(*args)
            for key, value in expected['components_exact'].items():
                self.assertAlmostEqual(value, actual['components'][key], places=6, msg=str(args))
            self.assertAlmostEqual(expected['total_block_fuel_kg_exact'], actual['total'], places=6)
            self.assertEqual(expected['alternate'], actual['alternate'])
