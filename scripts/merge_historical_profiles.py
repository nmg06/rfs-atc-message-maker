"""Add historical callsign/route keys once; never replace any existing profile."""
import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.enrich_observed_routes import digest


def distinct(db, schema='main', *, timed=False):
    condition='WHERE n_obs>=3 AND duration_min IS NOT NULL' if timed else ''
    return db.execute('SELECT count(*) FROM (SELECT DISTINCT airline,callsign,origin_id,destination_id FROM '+schema+'.flight_patterns '+condition+')').fetchone()[0]


def merge(base, candidates, output):
    base,output=[Path(p).resolve() for p in (base,output)]
    if output.exists() or output==base:raise ValueError('Output must be new')
    output.parent.mkdir(parents=True,exist_ok=True);temporary=output.with_suffix('.building.sqlite')
    if temporary.exists():raise ValueError('Previous candidate exists')
    baseline=digest(base);shutil.copy2(base,temporary);db=sqlite3.connect(temporary);db.execute('PRAGMA foreign_keys=ON')
    db.execute('CREATE INDEX IF NOT EXISTS profiles_identity ON flight_patterns(airline,callsign,origin_id,destination_id)')
    report={'baseline_sha256':baseline,'sources':[],'baseline_distinct_flights':distinct(db),'baseline_timed_flights':distinct(db,timed=True)}
    try:
        for index,candidate in enumerate(candidates):
            source=Path(candidate).resolve();source_hash=digest(source)
            metadata=json.loads(source.with_suffix('.report.json').read_text(encoding='utf-8'))
            quarter=metadata['input_quarters'][0].split('_github')[0].split('_detailed')[0]
            if not quarter.startswith(('2025_Q','2024_Q')):raise ValueError('Unexpected historical quarter')
            source_id='mrairspace-'+quarter.lower().replace('_','-')
            db.execute('ATTACH DATABASE ? AS incoming',(str(source),))
            if db.execute('PRAGMA incoming.user_version').fetchone()[0]!=1:raise ValueError('Unsupported source schema')
            # Frozen OurAirports IDs must still identify the same airports.
            if db.execute('SELECT count(*) FROM incoming.airports i JOIN main.airports a ON a.id=i.id WHERE a.icao<>i.icao').fetchone()[0]:raise ValueError('Conflicting airport IDs')
            for table in ('airports','airlines','aircraft_types','runways'):
                db.execute('INSERT OR IGNORE INTO main.'+table+' SELECT * FROM incoming.'+table)
            db.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?)',(source_id,'MrAirspace / adsb.lol '+quarter,
                'https://github.com/MrAirspace/aircraft-flight-schedules/releases/tag/'+('aircraft_flight_logs_' if quarter.startswith('2024') else 'aircraft_flight_schedules_')+quarter[:4]+'_quarter'+quarter[-1],
                'ODbL-1.0','MrAirspace / adsb.lol, ODbL 1.0. Historical observed-flight profiles for '+quarter+'; not current scheduled services.'))
            # Prefer a representative with actual complete-track duration;
            # retain unknown duration when no such representative exists.
            db.execute("""CREATE TEMP TABLE chosen AS SELECT * FROM (
                SELECT p.*,row_number() OVER(PARTITION BY airline,callsign,origin_id,destination_id
                ORDER BY (duration_min IS NOT NULL) DESC,n_complete DESC,n_obs DESC,last_seen DESC,pattern_id) representative
                FROM incoming.flight_patterns p WHERE n_obs>=3 AND NOT EXISTS (
                SELECT 1 FROM main.flight_patterns old WHERE old.airline=p.airline AND old.callsign=p.callsign
                AND old.origin_id=p.origin_id AND old.destination_id=p.destination_id)) WHERE representative=1""")
            count=db.execute('SELECT count(*) FROM chosen').fetchone()[0]
            offset=db.execute('SELECT coalesce(max(pattern_id),0) FROM main.flight_patterns').fetchone()[0]
            db.execute("""INSERT INTO main.flight_patterns SELECT pattern_id+?,airline,callsign,origin_id,destination_id,
                aircraft,type_mix,n_obs,n_complete,n_active_days,duration_min,duration_p10,duration_p90,distance_nm,
                dep_local_min,dep_spread_min,weekday_mask,first_seen,last_seen,latest_departure,latest_arrival,?
                FROM chosen""",(offset,source_id))
            db.execute('INSERT INTO main.recent_observations SELECT r.pattern_id+?,r.departure_utc,r.arrival_utc,r.aircraft,r.complete FROM incoming.recent_observations r JOIN chosen c ON c.pattern_id=r.pattern_id',(offset,))
            report['sources'].append(dict(quarter=quarter,added_distinct_flights=count,source_database_sha256=source_hash,source_report=metadata))
            db.execute('DROP TABLE chosen');db.commit();db.execute('DETACH DATABASE incoming')
            if digest(source)!=source_hash:raise ValueError('Source database changed during merge')
            print(quarter+': '+str(count)+' new callsign/route keys',flush=True)
        report.update(total_distinct_flights=distinct(db),total_timed_flights=distinct(db,timed=True),total_profiles=db.execute('SELECT count(*) FROM flight_patterns').fetchone()[0])
        report['distinct_flight_ratio']=report['total_distinct_flights']/report['baseline_distinct_flights']
        report['doubled_distinct_flights']=report['distinct_flight_ratio']>=2
        db.execute('INSERT INTO build_info VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('historical_enrichment_2026_10_12',json.dumps({k:v for k,v in report.items() if k!='sources'},sort_keys=True)))
        db.commit();db.execute('ATTACH DATABASE ? AS baseline',(str(base),))
        for table in ('flight_patterns','recent_observations','observed_routes','airports','airlines','aircraft_types','runways','sources'):
            lost=db.execute('SELECT count(*) FROM (SELECT * FROM baseline.'+table+' EXCEPT SELECT * FROM main.'+table+')').fetchone()[0]
            if lost:raise ValueError('Existing rows lost or changed in '+table)
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Integrity checks failed')
        report['lost_or_changed_legacy_rows']=0;report['integrity']='ok'
    except Exception:
        db.close();temporary.unlink(missing_ok=True);raise
    db.close()
    if digest(base)!=baseline:raise ValueError('Baseline changed during merge')
    temporary.replace(output);report['candidate_sha256']=digest(output);return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--candidate',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();r=merge(a.base,a.candidate,a.output);a.report.write_text(json.dumps(r,indent=2),encoding='utf-8',newline='\n');print(json.dumps({k:v for k,v in r.items() if k!='sources'},indent=2))
