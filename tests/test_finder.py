"""Synthetic fixtures below test mechanics, never shipped as aviation evidence."""
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import csv
import contextlib
import io

from finder.database import SCHEMA, connect_readonly
from finder.search import Criteria, search
from finder.time_utils import local_to_utc, resolve_local, circular_median
from finder.mapping import use_this_flight
from finder.importer import inspect_schema, REQUIRED, distance_nm

NOW = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)


def fixture(path):
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    db.execute("INSERT INTO sources VALUES ('test','Synthetic test fixture','https://example.invalid','TEST','Tests only')")
    db.execute("INSERT INTO build_info VALUES ('last_observation','2026-09-29')")
    airports = [(1,'LFPG','CDG','Paris CDG','Paris','FR','FR-IDF','EU',49.,2.,'Europe/Paris','large_airport'),
                (2,'EGLL','LHR','London Heathrow','London','GB','GB-ENG','EU',51.,-.4,'Europe/London','large_airport'),
                (3,'LFMN','NCE','Nice','Nice','FR','FR-PAC','EU',44.,7.,'Europe/Paris','large_airport'),
                (4,'VIDP','DEL','Delhi','Delhi','IN','IN-DL','AS',28.,77.,'Asia/Kolkata','large_airport')]
    db.executemany("INSERT INTO airports VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", airports)
    db.executemany("INSERT INTO airlines VALUES (?,?,?,?,?)", [('AFR','AF','Air France',None,None),('AIC','AI','Air India',None,None)])
    db.executemany("INSERT INTO aircraft_types VALUES (?,?,?,?)", [('A20N','Airbus A320neo','Airbus','A320'),('B789','Boeing 787-9','Boeing','B787')])
    for ident, dur, origin, dest, airline, aircraft in ((1,60,1,2,'AFR','A20N'),(2,110,1,2,'AFR','A20N'),
            (3,90,1,3,'AFR','A20N'),(4,600,4,1,'AIC','B789'),(5,650,4,2,'AIC','B789')):
        vals = (ident, airline, airline+str(100+ident),origin,dest,aircraft,'[]',20,20,10,dur,dur-5,dur+5,400,
                600,30,127,'2026-09-01T12:00:00+00:00','2026-09-29T12:00:00+00:00',
                '2026-09-29T12:00:00+00:00','2026-09-29T14:00:00+00:00','test')
        db.execute('INSERT INTO flight_patterns VALUES ('+','.join('?' for _ in vals)+')',vals)
    db.commit()
    db.close()


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'aviation.sqlite'
        fixture(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def results(self, **kw):
        return search(self.path, Criteria(**kw), NOW)['results']

    def test_duration_hard_limits_and_target(self):
        self.assertEqual([2,3], [r['pattern_id'] for r in self.results(min_minutes=80,max_minutes=120)])
        self.assertEqual(2, self.results(target_minutes=120)[0]['pattern_id'])
        self.assertEqual([],self.results(min_minutes=700))

    def test_two_hours_prefers_filling_available_time(self):
        rows = self.results(max_minutes=120)
        self.assertEqual([110,90,60],[r['duration_min'] for r in rows])

    def test_city_and_callsign_queries(self):
        paris_results = self.results(origin=['Paris'])
        self.assertTrue(len(paris_results) > 0)
        self.assertTrue(all(r['origin'] == 'LFPG' for r in paris_results))
        nice_results = self.results(destination=['Nice'])
        self.assertEqual([3], [r['pattern_id'] for r in nice_results])
        afr103 = self.results(callsign='AFR103')
        self.assertEqual([3], [r['pattern_id'] for r in afr103])
        afr_all = self.results(callsign='AFR')
        self.assertEqual({1, 2, 3}, {r['pattern_id'] for r in afr_all})

    def test_airport_iata_icao_and_exclusions(self):
        self.assertTrue(all(r['origin']=='LFPG' for r in self.results(origin=['cdg'])))
        self.assertTrue(all(r['destination']=='EGLL' for r in self.results(destination=['LHR'])))
        self.assertTrue(all('EGLL' not in (r['origin'],r['destination']) for r in self.results(excluded_airports=['lhr'])))

    def test_geography_and_international(self):
        self.assertTrue(all(r['origin']=='VIDP' for r in self.results(origin_continent=['AS'])))
        self.assertEqual([3],[r['pattern_id'] for r in self.results(destination_region=['FR-PAC'])])
        self.assertNotIn(3,[r['pattern_id'] for r in self.results(international_only=True)])
        self.assertEqual([4],[r['pattern_id'] for r in self.results(origin_country=['IN'],destination_country=['FR'])])

    def test_airline_and_aircraft_filters(self):
        for airline in ('Air India','AIC','AI'):
            self.assertEqual(2,len(self.results(airline=airline)))
        for kw in ({'aircraft':'A320neo'},{'aircraft':'A20N'},{'manufacturer':'Airbus'},{'family':'A320'}):
            self.assertEqual(3,len(self.results(**kw)))
        self.assertEqual([],self.results(airline="' OR 1=1 --"))

    def test_conflicting_time_constraints(self):
        with self.assertRaisesRegex(ValueError,'TIME_INCONSISTENT'):
            self.results(departure_time='08:00',arrival_time='12:00',target_minutes=60)
        with self.assertRaisesRegex(ValueError,'ARRIVAL_BEFORE_DEPARTURE'):
            self.results(departure_time='18:00',arrival_time='07:00')

    def test_arrival_only_proposes_simulator_time(self):
        row = self.results(airline='AIC',destination=['LFPG'],arrival_date='tomorrow',arrival_time='07:00')[0]
        self.assertEqual('2026-10-01T05:00:00+00:00',row['sim_arrival_utc'])
        self.assertEqual('2026-09-30T19:00:00+00:00',row['sim_departure_utc'])

    def test_unknown_duration_and_values(self):
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE flight_patterns SET duration_min=NULL,n_complete=0 WHERE pattern_id=1')
        db.close()
        self.assertNotIn(1,[r['pattern_id'] for r in self.results()])
        for kw in ({'min_minutes':float('nan')},{'min_minutes':180,'max_minutes':60},{'real_only':False}):
            with self.assertRaises(ValueError):
                self.results(**kw)

    def test_determinism_and_no_os_timezone_dependency(self):
        old = os.environ.get('TZ')
        try:
            os.environ['TZ']='Pacific/Kiritimati'
            one=self.results(max_minutes=120)
            os.environ['TZ']='America/New_York'
            self.assertEqual(one,self.results(max_minutes=120))
        finally:
            if old is None:
                os.environ.pop('TZ',None)
            else:
                os.environ['TZ']=old

    def test_readonly_and_missing_db(self):
        with connect_readonly(self.path) as db:
            with self.assertRaises(sqlite3.OperationalError):
                db.execute('DELETE FROM flight_patterns')
        with self.assertRaisesRegex(ValueError,'DATA_UNAVAILABLE'):
            search(self.path.with_name('missing.sqlite'), Criteria(), NOW)

    def test_mapping_keeps_manual_and_unknowns(self):
        original={'fuel':'12000','arrival_runway':'27L','passengers':'200','callsign':'MANUAL','pilots':[{'name':'friend'}]}
        row=self.results(airline='AIC',destination=['LFPG'])[0]
        flight=use_this_flight(original,row)
        self.assertEqual('Air India',flight['airline'])
        self.assertEqual('LFPG',flight['arrival_icao'])
        self.assertEqual('10h00',flight['estimated_flight_time'])
        self.assertEqual('AI104',flight['flight_number'])
        for key in ('fuel','arrival_runway','passengers','pilots'):
            self.assertEqual(original[key],flight[key])
        self.assertEqual('MANUAL',use_this_flight(original,{'callsign':None})['callsign'])
        self.assertNotIn('cruise_fl',flight)
        self.assertEqual('DERIVED_GREAT_CIRCLE',flight['selected_flight']['fields']['distance'])
        self.assertNotIn('airline',original)


class TimeTests(unittest.TestCase):
    def test_paris_dst_gap(self):
        instant,warnings=local_to_utc(datetime(2026,3,29,2,30),'Europe/Paris')
        self.assertEqual('2026-03-29T01:00:00+00:00',instant.isoformat())
        self.assertIn('DST_GAP_SHIFTED',warnings)

    def test_paris_ambiguous(self):
        instant,warnings=local_to_utc(datetime(2026,10,25,2,30),'Europe/Paris')
        self.assertEqual('2026-10-25T00:30:00+00:00',instant.isoformat())
        self.assertIn('DST_AMBIGUOUS_EARLIER',warnings)

    def test_half_hour_and_date_line(self):
        instant,_=local_to_utc(datetime(2026,10,1,7),'Asia/Kolkata')
        self.assertEqual(1,instant.hour)
        self.assertEqual(30,instant.minute)
        instant,_=local_to_utc(datetime(2026,10,1,7),'Pacific/Kiritimati')
        self.assertEqual('2026-09-30T17:00:00+00:00',instant.isoformat())
        instant,warnings=local_to_utc(datetime(2026,10,4,2,15),'Australia/Lord_Howe')
        self.assertIn('DST_GAP_SHIFTED',warnings)
        self.assertEqual('2026-10-03T15:30:00+00:00',instant.isoformat())

    def test_other_zones_and_tomorrow(self):
        for zone in ('Africa/Casablanca','America/New_York'):
            instant,_=local_to_utc(datetime(2026,9,30,7),zone)
            self.assertIsNotNone(instant.tzinfo)
        instant,_=resolve_local('tomorrow','07:00','Europe/Paris',NOW)
        self.assertEqual('2026-10-01T05:00:00+00:00',instant.isoformat())
        self.assertIn(circular_median([1430,10]),[1430,10])
        self.assertEqual(0,circular_median([1430,0,10]))


class ImporterTests(unittest.TestCase):
    def test_import_pipeline_deduplicates_and_excludes_incomplete_duration(self):
        try:
            import duckdb
            import timezonefinder
        except ImportError:
            self.skipTest('Install requirements-etl.txt for full pipeline tests')
        from finder.importer import build
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            def write_csv(name, headers, rows):
                with (root/name).open('w',encoding='utf-8',newline='') as out:
                    writer=csv.writer(out)
                    writer.writerow(headers)
                    writer.writerows(rows)
            write_csv('airports.csv', ['id','icao_code','ident','type','name','iata_code','municipality','iso_country','iso_region','continent','latitude_deg','longitude_deg'],
                      [(1,'LFPG','LFPG','large_airport','Paris','CDG','Paris','FR','FR-IDF','EU',49,2),
                       (2,'EGLL','EGLL','large_airport','London','LHR','London','GB','GB-ENG','EU',51,-.4)])
            write_csv('runways.csv',['id','airport_ref','le_ident','he_ident','length_ft','width_ft','surface','lighted','closed'],[(1,1,'09L','27R',12000,150,'ASPH',1,0)])
            write_csv('airlines.csv',['ICAO','IATA','Name'],[('AFR','AF','Air France')])
            write_csv('models-A.csv',['ICAO','Manufacturer','Model','IsActive'],[('A20N','Airbus','A320neo',1)])
            values=[]
            for day in range(1,6):
                row={key:'-' for key in REQUIRED}
                row.update(ICAO_Hex='icaohex-test',AC_Type='A20N',AC_Type_Description='Airbus A320neo',Airline='AFR',Callsign='AFR123',
                           Track_Origin_FL_Ft='ground',Track_Destination_FL_Ft='ground' if day<5 else '5000',
                           Track_Origin_DateTime_UTC=f'2026-06-{day:02} 10:00:00',Track_Destination_DateTime_UTC=f'2026-06-{day:02} 11:30:00',
                           Track_Origin_ApplicableAirports="['LFPG']",Track_Destination_ApplicableAirports="['EGLL']",
                           Route_Validation_Based_on_Callsign='LFPG-EGLL')
                values.append(row)
            values.append(values[0].copy()) # exact duplicate, not another observation
            bad=values[0].copy()
            bad.update(ICAO_Hex='ambiguous',Track_Origin_ApplicableAirports="['LFPG', 'LFPB']",Route_Validation_Based_on_Callsign='nan')
            values.append(bad)
            write_csv('fixture.csv',REQUIRED,[[r[k] for k in REQUIRED] for r in values])
            conn=duckdb.connect()
            conn.execute('CREATE TABLE fixture AS SELECT * FROM read_csv(?,all_varchar=true)',[str(root/'fixture.csv')])
            conn.execute('COPY fixture TO ? (FORMAT PARQUET)',[str(root/'2026_Q2_fixture.parquet')])
            conn.close()
            with contextlib.redirect_stdout(io.StringIO()):
                build(root,root/'aviation.sqlite')
            with connect_readonly(root/'aviation.sqlite') as db:
                row=db.execute('SELECT n_obs,n_complete,duration_min FROM flight_patterns').fetchone()
                self.assertEqual((5,4,90),tuple(row))
                self.assertEqual('ok',db.execute('PRAGMA integrity_check').fetchone()[0])
                self.assertEqual(5,db.execute('SELECT count(*) FROM recent_observations').fetchone()[0])

    def test_real_schema_contract_and_rejection(self):
        try:
            import duckdb
        except ImportError:
            self.skipTest('Install requirements-etl.txt for importer tests')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'2026_Q2_test.parquet'
            db=duckdb.connect()
            db.execute('CREATE TABLE t ('+','.join('"'+key+'" VARCHAR' for key in REQUIRED)+')')
            db.execute('COPY t TO ? (FORMAT PARQUET)',[str(path)])
            self.assertEqual(len(REQUIRED),len(inspect_schema(db,path)))
            db.execute('ALTER TABLE t DROP COLUMN Airline')
            other=Path(folder)/'bad.parquet'
            db.execute('COPY t TO ? (FORMAT PARQUET)',[str(other)])
            with self.assertRaisesRegex(ValueError,'Airline'):
                inspect_schema(db,other)
            db.close()

    def test_distance_is_derived_and_symmetric(self):
        self.assertAlmostEqual(distance_nm(49,2,51,-.4),distance_nm(51,-.4,49,2))
        self.assertEqual(0,distance_nm(49,2,49,2))


if __name__=='__main__':
    unittest.main()
