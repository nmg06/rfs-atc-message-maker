"""Derive web reference data/constants from the existing PC calculator."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fuel import calculator


def export():
    constants = {name: getattr(calculator, name) for name in (
        'TAXI_BURN_RATE_MULTIPLIER', 'TAXI_OUT_MINUTES', 'TAXI_IN_MINUTES',
        'CONTINGENCY_RATE', 'FINAL_RESERVE_MINUTES', 'ALTERNATE_CRUISE_SPEED_KT',
        'ALTERNATE_APPROACH_MINUTES')}
    data = {'aircraft': calculator.load_json('aircraft_fuel_data.json')['aircraft'],
        'destinations': calculator.load_json('airport_alternates.json')['destinations'],
        'constants': constants}
    (ROOT/'mobile/fuel-reference.js').write_text('window.FLIGHTDECK_FUEL=' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    export()
