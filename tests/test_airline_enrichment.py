"""Synthetic import safety cases; real Air India coverage is checked from the bundle."""
import csv
import gzip
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from scripts.enrich_airline_routes import enrich
from scripts.enrich_observed_routes import digest
from finder.route_catalog import SCHEMA
from finder.search import Criteria, search
from tests.test_finder import fixture


class AirlineEnrichmentTests(unittest.TestCase):
    def test_additive_deduplication_evidence_and_repeat_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); base=root/'base.sqlite'; fixture(base)
            db=sqlite3.connect(base); db.executescript(SCHEMA)
            db.execute("INSERT INTO observed_routes VALUES (1,'AIC900','AIC',4,1,.98,5,8,'2026-09-01T00:00:00+00:00','2026-10-01T00:00:00+00:00',400,'test')")
            db.commit(); db.close()
            good=dict(callsign='AIC901',origin_icao='VIDP',destination_icao='EGLL',via_icaos='',airline_icao='',confidence='.97',candidate_count='1',evidence_days='5',observation_count='8',first_observed_at='2026-09-02T12:00:00Z',last_observed_at='2026-10-10T12:00:00Z')
            rows=[good,good,dict(good,callsign='AIC105'),dict(good,callsign='AIC900',destination_icao='LFPG'),dict(good,callsign='AFR901'),dict(good,callsign='AIC104'),dict(good,callsign='AIC902',confidence='.8'),dict(good,callsign='AIC903',via_icaos='LFPG'),dict(good,callsign='AIC904',airline_icao='AFR'),dict(good,callsign='AIC905',last_observed_at='2026-10-12T00:00:00Z')]
            archive=root/'routes-observed-2026-10-11.csv.gz'
            with gzip.open(archive,'wt',encoding='utf-8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(good)); writer.writeheader(); writer.writerows(rows)
            manifest=root/'manifest.json'; manifest.write_text(json.dumps(dict(generated_on='2026-10-11',dataset='catchflights-observed-routes',file=archive.name,sha256=digest(archive),license={'name':'Open Database License (ODbL) v1.0'},rows=len(rows))))
            before=digest(base); output=root/'output.sqlite'
            report=enrich(base,archive,manifest,output,'AIC')
            self.assertEqual(1,report['added_routes']); self.assertEqual(3,report['duplicates_preserved'])
            self.assertEqual(1,report['conflicting_callsign_routes_excluded']); self.assertEqual(0,report['lost_or_changed_rows']); self.assertEqual(before,digest(base))
            self.assertEqual(5,report['preserved']['flight_patterns']); self.assertEqual(1,report['preserved']['observed_routes'])
            now=datetime(2026,10,11,tzinfo=timezone.utc)
            row=search(output,Criteria(airline='Air India',route_catalog=True,callsign='901'),now)['results'][0]
            self.assertEqual('AIC901',row['callsign']); self.assertIsNone(row['duration_min']); self.assertIsNone(row['aircraft'])
            second=enrich(output,archive,manifest,root/'second.sqlite','AIC')
            self.assertEqual(0,second.get('added_routes',0)); self.assertEqual(2,second['total_observed_routes'])
            with self.assertRaisesRegex(ValueError,'new path'):
                enrich(base,archive,manifest,base,'AIC')
            archive.write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError,'checksum'):
                enrich(base,archive,manifest,root/'bad.sqlite','AIC')

    def test_real_bundle_air_india_short_long_and_new_routes(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            database=Path(directory)/'aviation.sqlite'
            with gzip.open(root/'android/bundled/aviation.sqlite.gz','rb') as source:
                database.write_bytes(source.read())
            now=datetime(2026,10,11,tzinfo=timezone.utc)
            for filters in ({'max_minutes':60},{'min_minutes':900}):
                response=search(database,Criteria(airline='AIC',diversify=False,**filters),now)
                self.assertGreater(response['available'],0)
                self.assertTrue(all(row['airline']=='AIC' for row in response['results']))
            response=search(database,Criteria(airline='AI',route_catalog=True,callsign='AIC163',origin=['BOM']),now)
            self.assertEqual(1,response['available'])
            self.assertEqual(('VABB','EGLL'),(response['results'][0]['origin'],response['results'][0]['destination']))
            self.assertIsNone(response['results'][0]['duration_min'])
            db=sqlite3.connect(database)
            self.assertEqual(203627,db.execute('select count(*) from flight_patterns').fetchone()[0])
            self.assertEqual(8,db.execute("select count(*) from observed_routes where source_id='catchflights-2026-10-11' and airline='AIC'").fetchone()[0])
            self.assertEqual(0,db.execute("select count(*) from observed_routes where source_id='catchflights-2026-10-11' and airline<>'AIC'").fetchone()[0])
            db.close()
