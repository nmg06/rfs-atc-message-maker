"""Android integration against existing Windows engines, plus real bundled SQLite."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'android/app/src/main/python'), str(ROOT / 'android/app/build/generated/python')]
from android_engine import Engine, defaults, normalise_state, atomic_json, ALL_TYPES
from message_builder import compose, preview_text, clipboard_text, validate_group, BUILTIN_DESIGNS, EMOJI_STYLES
from finder.search import Criteria, search
from finder.mapping import use_this_flight
from fuel.calculator import calculate_fuel, load_json


def flight():
    return {**defaults()['flight'], 'airline':'Air France', 'aircraft':'Airbus A220-300',
        'callsign':'AFR123', 'livery':'Air France', 'departure_icao':'LFPG', 'arrival_icao':'EGLL',
        'departure_city':'Paris', 'arrival_city':'London', 'departure_flag':'🇫🇷', 'arrival_flag':'🇬🇧',
        'departure_gate':'A12', 'arrival_gate':'B10', 'departure_runway':'27L', 'arrival_runway':'09R',
        'cruise_fl':'350', 'distance':'400', 'estimated_flight_time':'5h', 'passengers':'150',
        'cargo':'2000', 'fuel':'12285'}


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dbtemp = tempfile.TemporaryDirectory()
        cls.database = Path(cls.dbtemp.name) / 'aviation.sqlite'
        with gzip.open(ROOT/'android/bundled/aviation.sqlite.gz','rb') as src, cls.database.open('wb') as dst:
            import shutil
            shutil.copyfileobj(src,dst)

    @classmethod
    def tearDownClass(cls):
        cls.dbtemp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = Engine(self.temp.name, self.database)
        state = defaults()
        state['flight'] = flight()
        state['per_type']['ATC REQUEST'].update(pushback='5',server='ATC REPORT')
        state['per_type']['AIRBORNE'].update(climb_target='to TOC',no_atc=True)
        state['per_type']['ARRIVAL BOARD'].update(status='Final')
        state['per_type']['FLIGHT COMPLETED'].update(actual_flight_time='5h',no_atc=True)
        for kind in ('ATC ACTIVE','ATC OFFLINE'):
            state['per_type'][kind].update(airport_icao='LFPG',city='Paris',positions='Tower')
        state['per_type']['DISPATCH FORM'].update(server='ATC REPORT')
        self.engine.sync(state)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_eight_types_designs_lengths_emoji_choices_match_windows(self):
        for kind in self.engine.metadata()['windows_types']:
            for design in BUILTIN_DESIGNS:
                for length in ('Court','Moyen','Détaillé'):
                    for emoji in EMOJI_STYLES:
                        self.engine.state['message_type'] = kind
                        self.engine.state['presentation'].update(design=design,length=length,emoji_style=emoji)
                        rendered = self.engine.render()
                        s = self.engine.state
                        expected = compose(kind,s['flight'],s['per_type'][kind],s['pilot_name'],s['presentation'])
                        self.assertEqual(preview_text(expected),rendered['preview'],(kind,design,length,emoji))
                        self.assertEqual(clipboard_text(preview_text(expected).strip(),True),rendered['clipboard'])

    def test_validation_matches_group_and_go_around(self):
        for kind in self.engine.metadata()['windows_types']:
            self.engine.state['message_type']=kind
            self.engine.state['flight']['departure_icao']='BAD'
            rendered=self.engine.render()
            expected=validate_group(kind,self.engine.state['flight'],self.engine.state['per_type'][kind],self.engine.state['pilot_name'])
            self.assertTrue(all({'field':i.field,'text':i.text} in rendered['issues'] for i in expected))
        self.engine.state['message_type']='ARRIVAL BOARD'
        self.engine.state['per_type']['ARRIVAL BOARD'].update(go_around=False,procedure='Go-around',status='Descent')
        self.assertIn('Go-around',self.engine.render()['preview'])

    def test_grouped_pilots_parallel_validation_and_preferences(self):
        self.engine.state['flight'].update(departure_mode='Parallèle',pilots=[{'name':'Wing','callsign':'WING2','departure_runway':'27R','message_types':['ATC REQUEST']}])
        self.assertIn('WING2',self.engine.render()['preview'])
        self.assertFalse(any(i['field']=='pilots' for i in self.engine.render()['issues']))
        self.engine.state['flight']['pilots'][0]['departure_runway']='27L'
        self.assertTrue(any(i['field']=='pilots' for i in self.engine.render()['issues']))
        self.engine.state['message_type']='AIRBORNE'
        self.assertNotIn('WING2',self.engine.render()['preview'])

    def test_native_copy_payload_history_and_edited_preview(self):
        state=deepcopy(self.engine.state)
        state['preview_edits']['ATC REQUEST']='User preview last character Z'
        result=self.engine.handle('copy',{'state':state})
        self.assertIn('last character Z',result['text'])
        self.assertEqual(result['text'],self.engine.value['history'][0]['message'])
        self.engine.handle('copy',{})
        self.assertEqual(1,len(self.engine.value['history']))
        self.assertEqual(2,self.engine.value['history'][0]['copies'])
        state['preview_edits']['ATC REQUEST']='x'*2001
        with self.assertRaises(ValueError):self.engine.handle('copy',{'state':state})

    def test_real_finder_parity_pagination_readonly_and_mapping(self):
        self.engine.state['finder_filters']={'origin':'LFPG','max_minutes':'2h','diversify':True}
        before=hashlib.sha256(self.database.read_bytes()).hexdigest()
        first=self.engine.handle('finder',{})
        expected=search(self.database,Criteria(origin=['LFPG'],max_minutes=120,limit=100),self.engine.query_time)
        self.assertEqual([r['pattern_id'] for r in expected['results']],[r['pattern_id'] for r in first['results']])
        second=self.engine.handle('finder',{'more':True})
        self.assertEqual(100,second['offset'])
        self.assertFalse(set(r['pattern_id'] for r in first['results'])&set(r['pattern_id'] for r in second['results']))
        current=deepcopy(self.engine.state['flight'])
        row=self.engine.rows[100]
        result=self.engine.handle('finder_use',{'index':100})
        self.assertEqual(use_this_flight(current,row),result['value']['state']['flight'])
        self.assertEqual(current['fuel'],result['value']['state']['flight']['fuel'])
        self.assertEqual(current['arrival_runway'],result['value']['state']['flight']['arrival_runway'])
        self.assertEqual(before,hashlib.sha256(self.database.read_bytes()).hexdigest())
        self.assertEqual(577,first['matches'])

    def test_finder_all_criteria_and_stale_query_invalidation(self):
        converted=self.engine.criteria({'origin':'CDG, LHR','min_minutes':'1h','max_minutes':'2h30','departure_time':'08:00','departure_tz':'Europe/Paris','rfs_only':True,'family':'A320','international_only':True})
        self.assertEqual(['CDG','LHR'],converted.origin)
        self.assertEqual(150,converted.max_minutes)
        self.engine.state['finder_filters']={'origin':'LFPG'}
        self.engine.handle('finder',{})
        state=deepcopy(self.engine.state);state['finder_filters']={'origin':'ZZZZ'}
        self.engine.sync(state)
        with self.assertRaises(ValueError):self.engine.handle('finder',{'more':True})

    def test_fuel_all_63_and_reference_application(self):
        for record in load_json('aircraft_fuel_data.json')['aircraft']:
            self.engine.state['fuel_inputs']={'aircraft':record['id'],'duration':'2h45','arrival':'EGLL'}
            self.assertEqual(calculate_fuel(record['id'],2.75,'EGLL'),self.engine.handle('fuel',{}))
        self.engine.state['fuel_inputs']={'aircraft':'airbus_a220_300','duration':'5h','arrival':'EGLL'}
        self.assertEqual(12285,self.engine.handle('fuel',{})['total_block_fuel_kg_exact'])
        result=self.engine.handle('fuel_use',{})
        self.assertEqual('12285',result['value']['state']['flight']['fuel'])
        self.assertEqual('AFR123',result['value']['state']['flight']['callsign'])
        self.engine.state['fuel_inputs']['aircraft']='Airbus'
        with self.assertRaises(LookupError):self.engine.handle('fuel',{})
        self.assertIsNone(self.engine.fuel_result)

    def test_save_restart_export_import_saved_flights_and_designs(self):
        self.engine.handle('save_flight',{'label':'Test route'})
        self.engine.handle('save_preset',{'label':'Favourite'})
        self.engine.handle('design',{'design':{'name':'Custom','guided':True,'heading':'Hello','footer':'Goodbye','base_design':'Carte'}})
        expected=deepcopy(self.engine.value)
        restarted=Engine(self.temp.name,self.database)
        self.assertEqual(expected,restarted.value)
        backup=self.engine.handle('export',{})['text']
        self.engine.handle('clear',{})
        self.assertEqual(1,len(self.engine.state['saved_flights']))
        self.engine.handle('import',{'text':backup})
        self.assertEqual(expected,self.engine.value)
        self.assertTrue(self.engine.path.with_suffix('.before-import.json').exists())

    def test_corrupt_nested_backup_cannot_change_live_data(self):
        expected=deepcopy(self.engine.value)
        for key,value in [('flight',[]),('per_type',[]),('preview_edits',[]),('presentation',[])]:
            bad=deepcopy(expected);bad['state'][key]=value
            with self.assertRaises(ValueError):self.engine.handle('import',{'text':json.dumps(bad)})
            self.assertEqual(expected,self.engine.value)
        bad=deepcopy(expected);bad['state']['flight']['pilots']=[{'name':42}]
        with self.assertRaises(ValueError):self.engine.handle('import',{'text':json.dumps(bad)})
        self.assertEqual(expected,Engine(self.temp.name,self.database).value)

    def test_failed_write_keeps_previous_memory_and_disk(self):
        original=deepcopy(self.engine.value)
        state=deepcopy(self.engine.state);state['pilot_name']='changed'
        with patch('android_engine.atomic_json',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.engine.sync(state)
        self.assertEqual(original,self.engine.value)
        self.assertEqual(original,Engine(self.temp.name,self.database).value)

    def test_android_extensions_are_real_generated_text(self):
        for kind,data in [('PUSHBACK',{'pushback':'5'}),('TAXI',{'taxi_route':'A B C'}),('ATIS',{'airport_icao':'LFPG','information':'A','qnh':'1013'})]:
            self.engine.state['message_type']=kind
            self.engine.state['per_type'][kind].update(data)
            r=self.engine.render()
            self.assertIn(kind,r['preview'])
            self.assertTrue(r['can_copy'],r['issues'])

    def test_nested_saved_records_are_checked_before_import(self):
        self.engine.handle('save_flight',{'label':'Saved'})
        self.engine.handle('save_preset',{'label':'Favourite'})
        original=deepcopy(self.engine.value)
        broken=deepcopy(original)
        broken['state']['saved_flights'][0]['flight']['callsign']=42
        with self.assertRaises(ValueError):self.engine.handle('import',{'text':json.dumps(broken)})
        broken=deepcopy(original)
        broken['presets']['Favourite']['data']=[]
        with self.assertRaises(ValueError):self.engine.handle('import',{'text':json.dumps(broken)})
        self.assertEqual(original,self.engine.value)

    def test_data_sources_do_not_reset_active_finder(self):
        self.engine.state['finder_filters']={'origin':'LFPG','max_minutes':'2h'}
        self.engine.handle('finder',{})
        rows=deepcopy(self.engine.rows)
        self.assertTrue(self.engine.handle('sources',{})['sources'])
        self.assertEqual(rows,self.engine.rows)
        self.assertEqual(100,self.engine.handle('finder',{'more':True})['offset'])

    def test_no_network_needed_for_main_operations(self):
        import socket
        with patch.object(socket,'socket',side_effect=AssertionError('Network forbidden')):
            self.engine.render()
            self.engine.state['fuel_inputs']={'aircraft':'airbus_a220_300','duration':'5h','arrival':'EGLL'}
            self.engine.handle('fuel',{})
            self.engine.state['finder_filters']={'origin':'LFPG','max_minutes':'2h'}
            self.engine.handle('finder',{})
            Engine(self.temp.name,self.database)


from copy import deepcopy
if __name__=='__main__':unittest.main()
