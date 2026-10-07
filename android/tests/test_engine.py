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
    def test_recent_route_parity_mapping_and_restart_without_invented_duration(self):
        self.engine.state['language']='en'
        filters={'route_catalog':True,'airline':'AFR','diversify':False}
        self.engine.state['finder_filters']=filters
        response=self.engine.handle('finder',{})
        reference=search(self.database,self.engine.criteria(filters),self.engine.query_time)
        self.assertGreater(response['available'],0)
        self.assertEqual([r['route_id'] for r in reference['results']], [r['route_id'] for r in response['results']])
        row=response['results'][0]
        self.assertIsNone(row['duration_min'])
        self.assertIsNone(row['aircraft'])
        detail=self.engine.handle('finder_details',{'index':0})
        self.assertIn('Airline inferred',detail['duration']['note'])
        current=deepcopy(self.engine.state['flight'])
        self.engine.handle('finder_use',{'index':0})
        self.assertEqual(use_this_flight(current,row),self.engine.state['flight'])
        for key in ('aircraft','estimated_flight_time','fuel','departure_gate'):
            self.assertEqual(current[key],self.engine.state['flight'][key])
        reloaded=Engine(self.temp.name,self.database)
        self.assertEqual(self.engine.state['flight'],reloaded.state['flight'])
        self.assertTrue(reloaded.state['finder_filters']['route_catalog'])
        prepared=reloaded.handle('fuel_prepare',{})
        self.assertEqual('airbus_a220_300',prepared['selection']['record']['id'])
        self.assertEqual(current['estimated_flight_time'],reloaded.state['fuel_inputs']['duration'])

    def test_finder_exclusions_are_shared_validated_persisted_and_do_not_leave_stale_rows(self):
        filters = {'origin': 'VIDP', 'excluded_airports': 'vabb; BOM', 'diversify': False}
        self.engine.state['finder_filters'] = filters
        result = self.engine.handle('finder', {})
        direct = search(self.database, self.engine.criteria(filters), self.engine.query_time)
        self.assertGreater(result['available'], 0)
        self.assertEqual([r['pattern_id'] for r in direct['results']], [r['pattern_id'] for r in result['results']])
        self.assertTrue(all(r['origin'] == 'VIDP' and 'VABB' not in (r['origin'], r['destination']) for r in result['results']))
        self.engine.handle('persist', {'state': deepcopy(self.engine.state)})
        self.assertEqual(filters, Engine(self.temp.name, self.database).state['finder_filters'])
        self.engine.state['finder_filters']['excluded_airports'] = 'VABB, INVALID'
        with self.assertRaisesRegex(ValueError, r'50 (aéroports|airport)'):
            self.engine.handle('finder', {})
        self.assertEqual([], self.engine.rows)
        with self.assertRaises(ValueError):
            self.engine.handle('finder', {'more': True})
        self.engine.state['language'] = 'en'
        self.engine.state['finder_filters']['excluded_airports'] = 'ZZZA'
        with self.assertRaisesRegex(ValueError, 'not found in the local database.*ZZZA'):
            self.engine.handle('finder', {})
        self.assertEqual([], self.engine.rows)
        self.assertIn('Avoid these airports', self.engine.metadata()['finder_fields']['excluded_airports']['label'])

    def test_portable_export_preview_import_merge_and_legacy_reload(self):
        from backup_bundle import FORMAT, export_backup, parse_backup
        self.engine.handle('save_flight', {'label': 'Local flight'})
        self.engine.handle('save_preset', {'label': 'Local preset'})
        self.engine.state['preview_edits']['ATC REQUEST'] = 'Keep my local manual preview'
        self.engine.handle('persist', {})
        original = deepcopy(self.engine.value)
        exported = self.engine.handle('export', {})['text']
        self.assertEqual(FORMAT, json.loads(exported)['format'])
        preview = self.engine.handle('import_preview', {'text': exported})
        self.assertEqual({'summary', 'source'}, set(preview))
        self.assertEqual(1, preview['summary']['saved_flights'])
        self.assertEqual(original, self.engine.value)
        incoming = deepcopy(original)
        incoming['state']['flight']['callsign'] = 'OTHER DRAFT'
        incoming['state']['preview_edits']['ATC REQUEST'] = 'Other manually edited text'
        incoming['state']['saved_flights'] = []
        self.engine.handle('import', {'text': export_backup(incoming, 'windows', '0.4.2'), 'mode': 'merge'})
        self.assertEqual(original['state']['flight'], self.engine.state['flight'])
        self.assertEqual(original['state']['preview_edits'], self.engine.state['preview_edits'])
        self.assertEqual(2, len(self.engine.state['saved_flights']))
        draft = self.engine.state['saved_flights'][-1]
        self.assertEqual('OTHER DRAFT', draft['flight']['callsign'])
        self.assertEqual('Other manually edited text', draft['preview_edits']['ATC REQUEST'])
        merged = deepcopy(self.engine.value)
        self.engine.handle('import', {'text': export_backup(incoming), 'mode': 'merge'})
        self.assertEqual(merged, self.engine.value)
        self.assertEqual(merged, Engine(self.temp.name, self.database).value)
        self.assertGreaterEqual(len(list((Path(self.temp.name) / 'backups').glob('before-import-*.json'))), 2)
        self.engine.handle('load_flight', {'id': draft['id']})
        self.assertEqual('OTHER DRAFT', self.engine.state['flight']['callsign'])
        self.assertEqual('Other manually edited text', self.engine.render()['preview'])
        self.assertEqual('Other manually edited text', Engine(self.temp.name, self.database).render()['preview'])
        self.engine.handle('save_flight', {'label': 'Retained imported draft'})
        self.engine.handle('clear', {})
        self.engine.handle('load_flight', {'id': draft['id']})
        self.assertEqual('Other manually edited text', self.engine.render()['preview'])
        self.engine.handle('import', {'text': json.dumps(original)})
        self.assertEqual(original, self.engine.value)

    def test_portable_unknown_version_and_invalid_nested_preview_do_not_touch_disk(self):
        exported = json.loads(self.engine.handle('export', {})['text'])
        disk = self.engine.path.read_bytes()
        original = deepcopy(self.engine.value)
        invalid = deepcopy(exported)
        invalid['schema_version'] = 999
        bad_preview = deepcopy(exported)
        bad_preview['payload']['state']['preview_edits']['ATC REQUEST'] = []
        for value in (invalid, bad_preview):
            with self.assertRaises(ValueError):
                self.engine.handle('import', {'text': json.dumps(value)})
            self.assertEqual(disk, self.engine.path.read_bytes())
            self.assertEqual(original, self.engine.value)
        source = deepcopy(original)
        source['state']['map_settings'] = {'satellite': True, 'winds': True}
        self.engine.handle('import', {'text': __import__('backup_bundle').export_backup(source)})
        self.assertFalse(self.engine.state['map_settings']['satellite'])
        self.assertFalse(self.engine.state['map_settings']['winds'])

    def test_free_copy_retains_warnings_exact_message_and_persisted_choice(self):
        self.engine.state['presentation']['discord_aligned']=False
        self.engine.state['flight']['departure_icao']=''
        self.engine.state['preview_edits']['ATC REQUEST']='An incomplete flight as-is'
        self.assertFalse(self.engine.render()['can_copy'])
        with self.assertRaises(ValueError):self.engine.handle('copy',{})
        self.engine.state['strict_validation']=False
        self.assertTrue(self.engine.render()['issues'])
        result=self.engine.handle('copy',{})
        self.assertEqual('An incomplete flight as-is',result['text'])
        restored=Engine(self.temp.name,self.database)
        self.assertFalse(restored.state['strict_validation'])
        self.assertEqual('An incomplete flight as-is',restored.render()['clipboard'])
        restored.state['strict_validation']=True
        self.assertFalse(restored.render()['can_copy'])
        restored.state['strict_validation']=False
        restored.state['preview_edits']['ATC REQUEST']='  '
        self.assertFalse(restored.render()['can_copy'])

    def test_english_theme_metadata_and_help_flags_restore(self):
        state=self.engine.state
        state.update(language='en',tutorial_seen=True,strict_validation=False)
        self.engine.handle('save',{'state':state})
        names={v['name'] for v in self.engine.metadata()['visual_themes']}
        self.assertIn('Avionics',names);self.assertIn('Forest',names)
        self.assertFalse(names&{'Avionique','Océan','Aurore','Crépuscule','Forêt','Ambre','Lavande'})
        self.assertTrue(Engine(self.temp.name,self.database).state['tutorial_seen'])

    def test_planning_lists_real_runways_without_inventing_gate_or_assignment(self):
        self.engine.state['flight'].update(departure_icao='LFPG',arrival_icao='ZZZZ')
        result=self.engine.handle('planning',{})
        self.assertEqual('LFPG',result['departure']['airport']['icao'])
        self.assertGreater(len(result['departure']['runways']),0)
        self.assertEqual([],result['departure']['gates'])
        self.assertIsNone(result['arrival']['airport'])
        self.assertEqual([],result['arrival']['runways'])
        self.assertNotIn('assigned_runway',result['departure'])
        self.assertTrue(any(v['code']=='LFPG' for v in self.engine.handle('lookup',{'kind':'airport','query':'CDG'})['items']))
        self.assertTrue(any(v['code']=='AFR' for v in self.engine.handle('lookup',{'kind':'airline','query':'Air France'})['items']))

    def test_flight_log_counts_confirmed_sessions_and_restores_running_clock(self):
        from flight_planning import elapsed_seconds
        self.engine.state['flight'].update(departure_icao='LFPG',arrival_icao='KJFK')
        self.engine.handle('session',{'operation':'start'})
        active=deepcopy(self.engine.state['active_session'])
        self.assertEqual(0,len(self.engine.state['flight_log']))
        restarted=Engine(self.temp.name,self.database)
        self.assertEqual(active,restarted.state['active_session'])
        start=datetime.fromisoformat(active['started_at'])
        from datetime import timedelta
        self.assertEqual(3600,elapsed_seconds(active,start+timedelta(hours=1)))
        self.engine.handle('session',{'operation':'pause'})
        self.assertNotIn('started_at',self.engine.state['active_session'])
        self.engine.handle('session',{'operation':'resume'})
        self.engine.handle('session',{'operation':'finish'})
        self.assertEqual({},self.engine.state['active_session'])
        self.assertEqual(1,len(self.engine.state['flight_log']))
        self.assertEqual('LFPG',self.engine.state['flight_log'][0]['flight']['departure_icao'])
        with self.assertRaises(ValueError):self.engine.handle('session',{'operation':'finish'})
        broken=deepcopy(self.engine.value);broken['state']['flight_log'][0]['seconds']=-1
        with self.assertRaises(ValueError):self.engine.validate_backup(broken)

    def test_lightweight_updates_keep_data_and_do_not_return_full_library(self):
        state=deepcopy(self.engine.state);state['flight']['callsign']='SAVED-WITHOUT-BUTTON';state['visual_theme']='sunset'
        response=self.engine.handle('update',{'state':state})
        self.assertEqual({'render','saved'},set(response))
        self.assertEqual('SAVED-WITHOUT-BUTTON',Engine(self.temp.name,self.database).state['flight']['callsign'])
        self.assertEqual(10,len(self.engine.metadata()['visual_themes']))
        self.assertEqual({'saved':True},self.engine.handle('persist',{}))
    def test_offline_map_uses_actual_airport_coordinates_shared_arc_and_no_network(self):
        import socket
        from map_geometry import great_circle
        self.engine.state['flight'].update(departure_icao='LFPG', arrival_icao='KJFK')
        with patch.object(socket, 'socket', side_effect=AssertionError('Network forbidden')):
            result = self.engine.handle('map_route', {})
        origin, destination = [v['coordinates'] for v in result['airports']]
        # Coordinates from the verified bundled SQLite snapshot, not live data.
        self.assertEqual((49.00896, 2.554117), origin)
        self.assertEqual((40.639447, -73.779317), destination)
        self.assertEqual(great_circle(origin, destination), result['route'])
        self.assertEqual(97, len(result['route']))
        self.engine.state['flight']['arrival_icao'] = 'ZZZZ'
        missing = self.engine.handle('map_route', {})
        self.assertIsNone(missing['airports'][1]['coordinates'])
        self.assertEqual([], missing['route'])
        state = deepcopy(self.engine.state)
        state['map_settings'] = {'center':[3.5,-48], 'zoom':24, 'origin_country':'FR', 'destination_country':'RO'}
        self.engine.sync(state)
        self.assertEqual(state['map_settings'], Engine(self.temp.name, self.database).state['map_settings'])
        for field, value in [('zoom', -1), ('center', [0, 999]), ('origin_country', 'ZZ')]:
            bad = deepcopy(state);bad['map_settings'][field] = value
            with self.assertRaises(ValueError):self.engine.sync(bad)
        self.assertEqual(state['map_settings'], self.engine.state['map_settings'])

    def test_library_rename_delete_preserves_current_flight_and_survives_restart(self):
        self.engine.handle('save_flight', {'label':'Saved'})
        ident = self.engine.state['current_flight_id']
        current = deepcopy(self.engine.state['flight'])
        self.engine.handle('library', {'category':'flights','operation':'rename','id':ident,'label':'New name'})
        self.assertEqual('New name', self.engine.state['saved_flights'][0]['label'])
        self.engine.handle('library', {'category':'flights','operation':'delete','id':ident})
        self.assertEqual([], self.engine.state['saved_flights'])
        self.assertEqual('', self.engine.state['current_flight_id'])
        self.assertEqual(current, self.engine.state['flight'])
        self.engine.handle('save_preset', {'label':'First'})
        self.engine.handle('save_preset', {'label':'Second'})
        original = deepcopy(self.engine.value)
        with self.assertRaises(ValueError):
            self.engine.handle('library', {'category':'presets','operation':'rename','id':'First','label':'Second'})
        self.assertEqual(original, self.engine.value)
        self.engine.handle('library', {'category':'presets','operation':'rename','id':'First','label':'Renamed'})
        self.engine.handle('library', {'category':'presets','operation':'delete','id':'Second'})
        self.assertEqual(['Renamed'], list(self.engine.value['presets']))
        self.engine.handle('design', {'design':{'name':'Custom','guided':True,'base_design':'Carte'}})
        custom = self.engine.state['presentation']['custom_id']
        self.engine.handle('library', {'category':'designs','operation':'delete','id':custom})
        self.assertEqual('', self.engine.state['presentation']['custom_id'])
        self.engine.handle('copy', {})
        self.engine.handle('library', {'category':'history','operation':'clear'})
        self.assertEqual([], self.engine.value['history'])
        self.assertEqual(self.engine.value, Engine(self.temp.name, self.database).value)

    def test_known_pilot_preferences_and_invalid_edits_preserve_live_data(self):
        pilot = {'name':'Wing','callsign':'WING2','aircraft':'Airbus A220-300','message_types':['AIRBORNE']}
        self.engine.handle('library', {'category':'pilots','operation':'create','pilot':pilot})
        self.assertEqual(pilot, self.engine.state['pilot_library'][0])
        original = deepcopy(self.engine.value)
        with self.assertRaises(ValueError):
            self.engine.handle('library', {'category':'pilots','operation':'create','pilot':{**pilot,'name':'wing'}})
        with self.assertRaises(ValueError):
            self.engine.handle('library', {'category':'pilots','operation':'edit','id':0,'pilot':{**pilot,'callsign':42}})
        self.assertEqual(original, self.engine.value)
        self.engine.handle('library', {'category':'pilots','operation':'edit','id':0,'pilot':{**pilot,'callsign':'NEW'}})
        self.assertEqual('NEW', Engine(self.temp.name, self.database).state['pilot_library'][0]['callsign'])
        self.engine.handle('library', {'category':'pilots','operation':'delete','id':0})
        self.assertEqual([], self.engine.state['pilot_library'])

    def test_complete_pc_import_validates_all_four_files_before_replacing_data(self):
        self.engine.handle('save_flight', {'label':'Route française'})
        self.engine.handle('save_preset', {'label':'Favourite'})
        self.engine.handle('design', {'design':{'name':'Custom','guided':True,'heading':'Hello','base_design':'Carte'}})
        self.engine.handle('copy', {})
        expected = deepcopy(self.engine.value)
        files = {f'rfs_{name}.json': '\ufeff'+json.dumps(expected[key], ensure_ascii=False)
                 for name,key in [('state','state'),('history','history'),('presets','presets'),('designs','designs')]}
        self.engine.handle('clear', {})
        before = deepcopy(self.engine.value)
        with self.assertRaises(ValueError):self.engine.handle('import_pc', {'files':{'rfs_state.json':files['rfs_state.json']}})
        with self.assertRaises(ValueError):self.engine.handle('import_pc', {'files':{**files,'rfs_history.json':'{}'}})
        self.assertEqual(before, self.engine.value)
        self.engine.handle('import_pc', {'files':files})
        self.assertEqual(expected, self.engine.value)
        self.assertEqual(before, json.loads(self.engine.path.with_suffix('.before-import.json').read_text(encoding='utf-8')))
        self.assertEqual(expected, Engine(self.temp.name, self.database).value)
        legacy = deepcopy(expected['state'])
        legacy.pop('language');legacy.pop('joke_seen');legacy['finder_language'] = 'en'
        self.engine.handle('import_pc', {'files':{**files,'rfs_state.json':json.dumps(legacy)}})
        self.assertEqual('en', self.engine.state['language'])
        self.assertTrue(self.engine.state['joke_seen'])

    def test_fuel_bare_decimal_hours_and_pc_formats_are_identical(self):
        from fuel.duration import duration_hours
        for text in ('5', '2,75', '5h', '5h30', '03:00', '1:2', '25'):
            inputs = self.engine.state['fuel_inputs']
            inputs.update(aircraft='airbus_a220_300', duration=text, arrival='EGLL')
            expected = calculate_fuel('airbus_a220_300', duration_hours(text), 'EGLL')
            self.assertEqual(expected, self.engine.handle('fuel', {}))
        inputs['duration'] = '330min'
        self.assertEqual(calculate_fuel('airbus_a220_300', 5.5, 'EGLL'), self.engine.handle('fuel', {}))

    def test_finder_bare_hours_cache_and_fuel_prefill_unique_variant(self):
        from unittest.mock import patch
        from finder.search import search
        self.engine.state['finder_filters'] = {'origin':'LFPG','max_minutes':'2'}
        self.assertEqual(120, self.engine.criteria(self.engine.state['finder_filters']).max_minutes)
        with patch('finder.search.search', wraps=search) as query:
            self.engine.handle('finder', {})
            self.engine.handle('finder', {'more':True})
            self.assertEqual(1, query.call_count)
        self.engine.state['flight'].update(aircraft='Airbus A220-300', estimated_flight_time='5h',
            arrival_icao='EGLL', selected_flight={'aircraft_icao':'BCS3','fields':{'aircraft':'OBSERVED_AIRCRAFT_TYPE'}})
        prepared = self.engine.handle('fuel_prepare', {})
        self.assertEqual('airbus_a220_300', prepared['value']['state']['fuel_inputs']['aircraft'])
        self.assertEqual(12285, self.engine.handle('fuel', {})['total_block_fuel_kg_exact'])
        # Manual Fuel choices survive navigating away/back until flight context changes.
        self.engine.state['fuel_inputs']['duration'] = '6h'
        self.engine.handle('fuel_prepare', {})
        self.assertEqual('6h', self.engine.state['fuel_inputs']['duration'])
        self.engine.state['flight']['selected_flight']['aircraft_icao'] = 'B738'
        self.engine.state['flight']['aircraft'] = 'Boeing 737-800'
        self.engine.handle('fuel_prepare', {})
        self.assertEqual('', self.engine.state['fuel_inputs']['aircraft'])

    def test_fuel_prepare_clears_missing_new_flight_fields_and_keeps_manual_same_context(self):
        self.engine.handle('fuel_prepare', {})
        self.assertEqual('5h', self.engine.state['fuel_inputs']['duration'])
        self.assertEqual('EGLL', self.engine.state['fuel_inputs']['arrival'])
        self.assertEqual(12285, self.engine.handle('fuel', {})['total_block_fuel_kg_exact'])
        state = deepcopy(self.engine.state)
        state['flight'].update(estimated_flight_time='', arrival_icao='')
        self.engine.handle('fuel_prepare', {'state': state})
        self.assertEqual('', self.engine.state['fuel_inputs']['duration'])
        self.assertEqual('', self.engine.state['fuel_inputs']['arrival'])
        self.assertEqual('airbus_a220_300', self.engine.state['fuel_inputs']['aircraft'])
        with self.assertRaisesRegex(ValueError, 'Duration required'):
            self.engine.handle('fuel', {})
        state = deepcopy(self.engine.state)
        state['fuel_inputs'].update(duration='7h', arrival='LFPG')
        self.engine.handle('fuel_prepare', {'state': state})
        self.assertEqual('7h', self.engine.state['fuel_inputs']['duration'])
        self.assertEqual('LFPG', self.engine.state['fuel_inputs']['arrival'])
        reloaded = Engine(self.temp.name, self.database)
        reloaded.handle('fuel_prepare', {})
        self.assertEqual('7h', reloaded.state['fuel_inputs']['duration'])
        self.assertEqual('LFPG', reloaded.state['fuel_inputs']['arrival'])

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
        self.assertEqual(691,first['matches'])

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

    def test_extensions_share_design_emoji_custom_rules_and_validate_parallel_pilots(self):
        for kind,data in [('PUSHBACK',{'pushback':'5','direction':'Left'}),('TAXI',{'taxi_route':'A B C','hold_short':'27L'}),('ATIS',{'airport_icao':'LFPG','information':'A','qnh':'1013'})]:
            self.engine.state['message_type']=kind
            self.engine.state['per_type'][kind].update(data)
            for design in BUILTIN_DESIGNS:
                for length in ('Court','Moyen','Détaillé'):
                    for emoji in EMOJI_STYLES:
                        self.engine.state['presentation'].update(design=design,length=length,emoji_style=emoji)
                        result=self.engine.render()
                        self.assertTrue(result['can_copy'],(kind,design,length,emoji,result['issues']))
                        self.assertLessEqual(result['emojis'],6)
                        if emoji=='Sans emojis':self.assertEqual(0,result['emojis'])
            self.engine.handle('design',{'design':{'name':'Guided','guided':True,'base_design':'Carte','heading':'Heading','footer':'Footer'}})
            self.assertIn('Heading',self.engine.render()['preview'])
            self.assertIn('Footer',self.engine.render()['preview'])
            self.engine.handle('design',{'design':{'name':'Expert','template':'{{callsign}}\n{{message}}'}})
            self.assertIn('AFR123',self.engine.render()['preview'])
            self.engine.state['presentation']['custom_id']=''
        self.engine.state['message_type']='PUSHBACK'
        self.engine.state['flight'].update(departure_mode='Parallèle',pilots=[{
            'name':'Wing','callsign':'WING2','departure_runway':'27R','message_types':['PUSHBACK']}])
        rendered=self.engine.render()
        self.assertTrue(rendered['can_copy'],rendered['issues'])
        self.assertIn('WING2',rendered['preview'])
        self.assertIn('Parallel departure',rendered['preview'])
        self.engine.state['flight']['pilots'][0]['departure_runway']='27L'
        self.assertTrue(any(v['field']=='pilots' for v in self.engine.render()['issues']))
        self.engine.state['message_type']='TAXI'
        self.engine.state['flight']['departure_mode']='Indépendant'
        self.assertNotIn('WING2',self.engine.render()['preview'])
        self.engine.state['message_type']='ATIS'
        self.engine.state['per_type']['ATIS']['qnh']='9999'
        self.assertFalse(self.engine.render()['can_copy'])

    def test_finder_duration_provenance_matches_windows_without_false_percentiles(self):
        from finder.provenance import duration_provenance
        for row in ({'duration_min':75,'distance_nm':390,'n_complete':4},
                    {'duration_min':75,'distance_nm':390,'n_complete':0},
                    {'duration_min':77,'distance_nm':390,'n_complete':0}):
            details=self.engine.duration_details(row)
            self.assertEqual(duration_provenance(row),details['origin'])
            self.assertEqual(details['origin']=='AGGREGATED_COMPLETE_TRACKS', details['bounds_kind']=='observed_percentiles')
        estimated=self.engine.duration_details({'duration_min':75,'distance_nm':390,'n_complete':0})
        self.assertIn('390',estimated['note'])

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
