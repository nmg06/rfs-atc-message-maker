"""Provenance disclosure and exact search equivalence, using test-only fixtures."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
import finder.search as engine
from finder.database import connect_readonly
from finder.provenance import duration_provenance
from finder.mapping import use_this_flight
from finder.ui import FinderDialog
from test_finder import fixture, NOW


class ProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.sqlite'
        fixture(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def estimated(self):
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE flight_patterns SET n_complete=0,distance_nm=88.0669046027309,duration_min=29,duration_p10=28,duration_p90=30 WHERE pattern_id=1')
        db.close()
        return engine.search(self.path, engine.Criteria(max_minutes=40), NOW)

    def test_classifies_known_estimated_unknown_without_inventing(self):
        self.assertEqual('UNKNOWN', duration_provenance({'duration_min':None}))
        row={'n_complete':0,'distance_nm':88.0669046027309,'duration_min':29}
        before=deepcopy(row)
        self.assertEqual('ESTIMATED_DISTANCE_HEURISTIC', duration_provenance(row))
        self.assertEqual(before,row)
        self.assertEqual('POST_IMPORT_UNVERIFIED', duration_provenance({**row,'duration_min':31}))
        self.assertEqual('POST_IMPORT_UNVERIFIED', duration_provenance({**row,'distance_nm':float('nan')}))
        self.assertEqual('AGGREGATED_COMPLETE_TRACKS', duration_provenance({**row,'n_complete':3}))

    def test_estimate_details_in_both_languages_never_call_bounds_percentiles(self):
        response=self.estimated()
        row=response['results'][0]
        self.assertIn('DURATION_ESTIMATED_HEURISTIC',row['warnings'])
        self.assertNotIn('PARTIAL_TRACKS_EXCLUDED_FROM_DURATION',row['warnings'])
        for language,word,limit in [('fr','estimée','précision garantie'),('en','estimated','guaranteed accuracy')]:
            dialog=FinderDialog(None,self.path,language)
            dialog.query=engine.Criteria(max_minutes=40)
            dialog.present(response)
            text=dialog.details.toPlainText()
            self.assertIn(word,dialog.table.item(0,3).text())
            self.assertIn('390',text)
            self.assertIn('15 min',text)
            self.assertIn(limit,text)
            self.assertNotIn('P10',text)
            self.assertNotIn('DURATION_ESTIMATED_HEURISTIC',text)
            dialog.close()

    def test_observed_details_keep_real_percentiles(self):
        response=engine.search(self.path,engine.Criteria(max_minutes=70),NOW)
        for language,word in [('fr','observée'),('en','observed')]:
            dialog=FinderDialog(None,self.path,language)
            dialog.query=engine.Criteria(max_minutes=70)
            dialog.present(response)
            self.assertIn(word,dialog.table.item(0,3).text())
            self.assertIn('P10–P90',dialog.details.toPlainText())
            self.assertNotIn('390 kt',dialog.details.toPlainText())
            dialog.close()

    def test_external_unverified_duration_does_not_claim_matching_formula(self):
        self.estimated()
        with sqlite3.connect(self.path) as db:db.execute('UPDATE flight_patterns SET duration_min=31 WHERE pattern_id=1')
        db.close()
        response=engine.search(self.path,engine.Criteria(max_minutes=40),NOW)
        self.assertEqual('POST_IMPORT_UNVERIFIED',response['results'][0]['duration_provenance'])
        for language in ('fr','en'):
            dialog=FinderDialog(None,self.path,language);dialog.query=engine.Criteria(max_minutes=40);dialog.present(response)
            text=dialog.details.toPlainText()
            self.assertNotIn('P10',text);self.assertNotIn('390',text)
            self.assertNotIn('DURATION_POST_IMPORT_UNVERIFIED',text)
            dialog.close()

    def test_transfer_keeps_duration_origin_and_manual_fields(self):
        row=self.estimated()['results'][0]
        original={'fuel':'12345','departure_runway':'TEST','arrival_gate':'TEST','pilots':[{'name':'fixture'}]}
        before=deepcopy(original)
        flight=use_this_flight(original,row)
        self.assertEqual(before,original)
        for key in original:self.assertEqual(before[key],flight[key])
        self.assertEqual('0h29',flight['estimated_flight_time'])
        self.assertEqual('ESTIMATED_DISTANCE_HEURISTIC',flight['selected_flight']['fields']['estimated_flight_time'])
        self.assertEqual('ESTIMATED_DISTANCE_HEURISTIC',flight['selected_flight']['duration_provenance'])


class QueryEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'test.sqlite';fixture(self.path)

    def tearDown(self):self.temp.cleanup()

    def legacy_response(self,criteria):
        @contextmanager
        def former_order(path):
            with connect_readonly(path) as db:
                class Proxy:
                    def execute(self,sql,params=()):
                        return db.execute(sql.replace('ORDER BY +n_obs DESC','ORDER BY n_obs DESC'),params)
                yield Proxy()
        with patch.object(engine,'connect_readonly',former_order):
            return engine.search(self.path,criteria,NOW)

    def test_exact_response_with_target_filters_times_and_pages(self):
        for criteria in (engine.Criteria(target_minutes=600),engine.Criteria(target_minutes=120,diversify=False),
                         engine.Criteria(target_minutes=600,airline='AIC'),
                         engine.Criteria(departure_time='08:00',arrival_time='18:00'),
                         engine.Criteria(target_minutes=600,departure_time='08:00',arrival_time='18:00'),
                         engine.Criteria(origin=['LFPG'],max_minutes=120),engine.Criteria()):
            for offset in (0,1,3):
                query=replace(criteria,offset=offset,limit=1)
                with self.subTest(criteria=criteria,offset=offset):
                    self.assertEqual(self.legacy_response(query),engine.search(self.path,query,NOW))

    def test_candidate_cap_ties_and_last_page_have_exact_same_response(self):
        with sqlite3.connect(self.path) as db:
            original=list(db.execute('SELECT * FROM flight_patterns WHERE pattern_id=4').fetchone())
            rows=[]
            for ident in range(100,20205):
                row=original.copy();row[0]=ident;row[2]='AIC'+str(ident);rows.append(row)
            db.executemany('INSERT INTO flight_patterns VALUES ('+','.join('?' for _ in original)+')',rows)
        db.close()
        for offset in (0,30,19990,20000):
            query=engine.Criteria(target_minutes=600,diversify=False,limit=10,offset=offset)
            with self.subTest(offset=offset):
                response=engine.search(self.path,query,NOW)
                self.assertEqual(self.legacy_response(query),response)
                self.assertEqual(20000,response['candidates'])
                self.assertIn('CANDIDATE_LIMIT_REFINE_SEARCH',response['warnings'])
