"""Install validated, dated DGCA service facts into a new offline database."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from finder.published_catalog import SCHEMA
from scripts.enrich_observed_routes import digest


def install(base, source, output):
    base,source,output=[Path(p).resolve() for p in (base,source,output)]
    if output==base or output.exists():raise ValueError('Output must be new; baseline is preserved')
    data=json.loads(source.read_text(encoding='utf-8'))
    if data['schema_version']!=1:raise ValueError('Unsupported publication schema')
    checksum=digest(base);output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix('.building.sqlite')
    if temp.exists():raise ValueError('Previous candidate exists')
    shutil.copy2(base,temp);db=sqlite3.connect(temp);db.execute('PRAGMA foreign_keys=ON')
    try:
        db.executescript(SCHEMA)
        for row in data['sources']:
            db.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?)',tuple(row[k] for k in ('source_id','name','url','license_spdx','attribution_text')))
        airports={row[0]:row[1] for row in db.execute('SELECT icao,id FROM airports')}
        types={row[0] for row in db.execute('SELECT icao FROM aircraft_types')}
        aliases={'A320N':'A20N','A321N':'A21N','A319N':'A19N'}
        exact={'A319','A320','A321','A20N','A21N','A19N','A359','A35K','B738','B77W','B772','B788','B789'}
        before=db.execute('SELECT count(*) FROM published_services').fetchone()[0]
        for row in data['services']:
            code=aliases.get(row['aircraft_as_published'],row['aircraft_as_published'])
            code=code if code in exact and code in types else None
            key=hashlib.sha256(json.dumps({k:v for k,v in row.items() if k!='source_movements'},sort_keys=True).encode()).hexdigest()
            values=(key,row['source_id'],row['airline'],row['callsign'],row['flight_number'],airports[row['origin']],airports[row['destination']],code,row['aircraft_as_published'],row['days'],row['valid_from'],row['valid_to'],row['departure_local'],row['arrival_local'],row['duration_min'],row['published_on'],json.dumps(row['source_movements'],sort_keys=True),json.dumps(row.get('via',[])))
            db.execute('INSERT OR IGNORE INTO published_services(service_key,source_id,airline,callsign,flight_number,origin_id,destination_id,aircraft,aircraft_as_published,schedule_days,valid_from,valid_to,departure_local,arrival_local,duration_min,published_on,source_movements,via_json) VALUES ('+','.join('?' for _ in values)+')',values)
        count=db.execute('SELECT count(*) FROM published_services').fetchone()[0]
        metadata=dict(dgca_airindia_source_sha256=digest(source),dgca_airindia_services=count,dgca_airindia_movements=len(data['movements']),dgca_airindia_valid_to='2026-10-24')
        db.executemany('INSERT INTO build_info VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',[(k,str(v)) for k,v in metadata.items()])
        db.commit();db.execute('ATTACH DATABASE ? AS baseline',(str(base),))
        for table in ('flight_patterns','observed_routes'):
            if not db.execute("SELECT 1 FROM baseline.sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
                continue
            if db.execute('SELECT count(*) FROM (SELECT * FROM baseline.'+table+' EXCEPT SELECT * FROM main.'+table+')').fetchone()[0]:raise ValueError('Existing aviation rows changed')
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Database failed integrity checks')
        report=dict(source_report=data['report'],added_services=count-before,total_services=count,source_sha256=digest(source),baseline_sha256=checksum,lost_or_changed_legacy_rows=0)
    except Exception:
        db.close();temp.unlink(missing_ok=True);raise
    db.close()
    if digest(base)!=checksum:raise ValueError('Baseline changed during build')
    temp.replace(output);report['database_sha256']=digest(output);return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();r=install(a.base,a.source,a.output);a.report.write_text(json.dumps(r,indent=2),encoding='utf-8',newline='\n');print(json.dumps(r,indent=2))
