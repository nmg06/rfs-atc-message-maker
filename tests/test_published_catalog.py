"""Dated schedules are distinct from observed flights; preserve unknown fields."""
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from test_finder import fixture
from finder.search import Criteria, search
from finder.mapping import use_this_flight
from scripts.install_published_services import install

NOW=datetime(2026,10,13,12,tzinfo=timezone.utc)
class PublishedTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
  self.base=self.root/'base.sqlite';fixture(self.base)
  self.source=self.root/'facts.json'
  self.facts={'schema_version':1,'sources':[{'source_id':'published-test','name':'Synthetic publication','url':'https://example.invalid','license_spdx':'TEST','attribution_text':'Tests only'}],
   'movements':[],'report':{},'services':[{'source_id':'published-test','airline':'AIC','callsign':'AIC187','flight_number':'AI187','origin':'VIDP','destination':'LFPG','aircraft_as_published':'B777','days':'1234567','valid_from':'2026-03-29','valid_to':'2026-10-24','departure_local':'08:00','arrival_local':None,'duration_min':None,'published_on':'2026-03-27','source_movements':[{'page':1,'serial':1,'direction':'departure'}],'via':['EGLL']}]}
  self.source.write_text(json.dumps(self.facts),encoding='utf-8')
  self.db=self.root/'candidate.sqlite'; install(self.base,self.source,self.db)
 def tearDown(self):self.tmp.cleanup()
 def query(self,**kw):return search(self.db,Criteria(published_catalog=True,**kw),NOW)
 def test_no_fake_observations_or_specific_variant_and_preserved_manual_fields(self):
  row=self.query()['results'][0]
  self.assertEqual(0,row['n_obs']);self.assertIsNone(row['aircraft']);self.assertIsNone(row['duration_min'])
  flight=use_this_flight({'aircraft':'Boeing 777-300ER','fuel':'80000','estimated_flight_time':'10h00','departure_gate':'A2'},row)
  self.assertEqual('Boeing 777-300ER',flight['aircraft']);self.assertEqual('80000',flight['fuel']);self.assertEqual('10h00',flight['estimated_flight_time'])
  self.assertEqual('PUBLISHED_SCHEDULE',flight['selected_flight']['status']);self.assertEqual(['EGLL'],flight['selected_flight']['via_airports'])
  self.assertEqual('AI187',flight['flight_number'])
 def test_expiry_weekday_and_no_unknown_duration_with_constraints(self):
  self.assertEqual([],self.query(departure_date='2026-10-25')['results'])
  for kw in ({'min_minutes':1},{'max_minutes':800},{'target_minutes':600},{'arrival_time':'12:00'}):
   self.assertEqual([],self.query(**kw)['results'])
  with closing(sqlite3.connect(self.db)) as db, db:db.execute("UPDATE published_services SET schedule_days='1'")
  self.assertEqual([],self.query()['results']);self.assertEqual(1,len(self.query(departure_date='2026-10-12')['results']))
 def test_idempotent_install_and_old_rows_unchanged(self):
  second=self.root/'second.sqlite'; report=install(self.db,self.source,second)
  self.assertEqual(0,report['added_services']);self.assertEqual(0,report['lost_or_changed_legacy_rows'])
  with closing(sqlite3.connect(second)) as db, db:
   self.assertEqual(5,db.execute('SELECT count(*) FROM flight_patterns').fetchone()[0])
 def test_published_block_duration_provenance(self):
  with closing(sqlite3.connect(self.db)) as db, db:db.execute('UPDATE published_services SET duration_min=105,arrival_local=?',('09:45',))
  row=self.query(max_minutes=120)['results'][0]
  self.assertEqual('DERIVED_PUBLISHED_TIMES',row['duration_provenance'])
  self.assertEqual('1h45',use_this_flight({},row)['estimated_flight_time'])
 def test_historical_unknowns_and_dedup_after_filters(self):
  with closing(sqlite3.connect(self.base)) as db, db:
   db.execute('UPDATE flight_patterns SET duration_min=NULL,n_complete=0 WHERE pattern_id=1')
   db.execute("UPDATE flight_patterns SET callsign='AFR103' WHERE pattern_id=2")
  def rows(**kw):return search(self.base,Criteria(**kw),NOW)['results']
  self.assertNotIn(1,[r['pattern_id'] for r in rows()])
  self.assertIn(1,[r['pattern_id'] for r in rows(include_unknown_duration=True)])
  for kw in ({'min_minutes':1},{'max_minutes':800},{'target_minutes':60},{'arrival_time':'12:00'}):
   self.assertNotIn(1,[r['pattern_id'] for r in rows(include_unknown_duration=True,**kw)])
  result=rows(unique_flights=True,max_minutes=100)
  self.assertEqual([3],[r['pattern_id'] for r in result])
  with closing(sqlite3.connect(self.base)) as db, db:self.assertEqual(5,db.execute('SELECT count(*) FROM flight_patterns').fetchone()[0])
 def test_full_official_facts_and_column_direction_anchors(self):
  data=json.loads((Path(__file__).resolve().parents[1]/'finder/source-data/dgca-airindia-summer-2026.json').read_text(encoding='utf-8'))
  self.assertEqual(1988,len(data['movements']));self.assertEqual(1573,len(data['services']))
  keys={(r['flight_number'],r['origin'],r['destination']) for r in data['services']}
  self.assertEqual(785,len(keys));self.assertTrue(all(r['source_movements'] for r in data['services']))
  row=next(r for r in data['services'] if r['flight_number']=='AI1701' and r['origin']=='VIDP' and r['destination']=='VABO' and r['duration_min'])
  self.assertEqual(105,row['duration_min']);self.assertEqual('05:45',row['departure_local']);self.assertEqual('07:30',row['arrival_local'])
  multi=[r for r in data['services'] if r['flight_number']=='AI187' and r['via']]
  self.assertTrue(any('LOWW' in r['via'] for r in multi));self.assertTrue(all(r['duration_min'] is None for r in multi))

class LegacySchemaTests(unittest.TestCase):
 def test_legacy_registration_schema_is_opt_in_and_year_restricted(self):
  from unittest.mock import Mock
  from finder.importer import inspect_schema, REQUIRED
  names=[x for x in REQUIRED if x not in ('ICAO_Hex','Track_Origin_FL_Ft','Track_Destination_FL_Ft')]+['Reg']
  connection=Mock();connection.execute.return_value.fetchall.return_value=[(x,'VARCHAR') for x in names]
  with self.assertRaisesRegex(ValueError,'Unsupported'):inspect_schema(connection,Path('2024_Q4_github.parquet'))
  self.assertEqual(set(names),set(inspect_schema(connection,Path('2024_Q4_github.parquet'),legacy_2024=True)))
  with self.assertRaisesRegex(ValueError,'2024'):inspect_schema(connection,Path('2025_Q4_detailed_github.parquet'),legacy_2024=True)

class MergeHistoricalTests(unittest.TestCase):
 def test_append_new_key_once_keep_old_duration_variants_and_unknown_duration(self):
  from scripts.merge_historical_profiles import merge
  from scripts.enrich_observed_routes import digest
  from finder.route_catalog import SCHEMA as ROUTES
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);base=root/'base.sqlite';incoming=root/'incoming.sqlite'
   fixture(base);fixture(incoming)
   for path in (base,incoming):
    with closing(sqlite3.connect(path)) as db,db:db.executescript(ROUTES)
   with closing(sqlite3.connect(incoming)) as db,db:
    db.execute("UPDATE flight_patterns SET callsign='NEW600',n_complete=0,duration_min=NULL WHERE pattern_id IN (1,2)")
   incoming.with_suffix('.report.json').write_text(json.dumps({'input_quarters':['2024_Q4_github.parquet'],'sources':[]}),encoding='utf-8')
   before=digest(base);target=root/'merged.sqlite';report=merge(base,[incoming],target)
   self.assertEqual(before,digest(base));self.assertEqual(0,report['lost_or_changed_legacy_rows']);self.assertEqual(1,report['sources'][0]['added_distinct_flights'])
   with closing(sqlite3.connect(target)) as db:
    self.assertEqual(6,db.execute('SELECT count(*) FROM flight_patterns').fetchone()[0])
    self.assertEqual(1,db.execute("SELECT count(*) FROM flight_patterns WHERE callsign='NEW600'").fetchone()[0])
    self.assertIsNone(db.execute("SELECT duration_min FROM flight_patterns WHERE callsign='NEW600'").fetchone()[0])
   with self.assertRaisesRegex(ValueError,'new'):merge(base,[incoming],base)
