"""Extract every dated AIC airport movement from the pinned official DGCA PDFs."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3

SOURCES=[('DGCA-AirIndia-SS2026.pdf','107983dc72d381e6897a5a333556946adcc98daef82e954d52cec1fc402c3086','2026-03-18','domestic','AirIndiaLtd_SS_2026.pdf'),
         ('DGCA-AirIndia-International-SS2026.pdf','ed7de90c8f8bfe2a587b2c2fe5c3ba385146be3c4a575e8b5f690b841e69778d','2026-03-27','international','AirIndiaflightSchedule-INT.pdf')]
BASE_URL='https://public-prd-dgca.s3.ap-south-1.amazonaws.com/InventoryList/airOperation/certification/scheduled/domestic/'
HEADING_CODES=dict(zip(['Ahmedabad','Amritsar','Aurangabad','Bangalore','Bhopal','Bhubneshwar','Bhuj','Chandigarh','Chennai','Coimbatore','Dehradun','Delhi','GOA MOPA','Goa','Guwahati','Halwara','Hyderabad','Indore','Jaipur','Jammu','Jamnagar','Jodhpur','Kochi','Kolkata','Leh','Lucknow','Madurai','Mumbai','Nagpur','Patna','Port Blair','Pune','Raipur','Rajkot','Srinagar','Tirupati','Trivandrum','Udaipur','Vadodara','Varanasi','Vijayawada','Vizag'],
['AMD','ATQ','IXU','BLR','BHO','BBI','BHJ','IXC','MAA','CJB','DED','DEL','GOX','GOI','GAU','HWR','HYD','IDR','JAI','IXJ','JGA','JDH','COK','CCU','IXL','LKO','IXM','BOM','NAG','PAT','IXZ','PNQ','RPR','HSR','SXR','TIR','TRV','UDR','BDQ','VNS','VGA','VTZ']))
ROW=re.compile(r'^\s*(?P<serial>\d+)\s+AI\s+(?P<number>\d+[A-Z]?)\s+AIC\s+(?P<aircraft>[A-Z0-9-]+)\s+(?P<days>[1-7]+)\s+(?P<other>[A-Z]{3}(?:/[A-Z]{3})*)\s+(?P<time>\d{2}:\d{2})\s+(?P<from>\d{2}/\d{2}/\d{4})\s+(?P<to>\d{2}/\d{2}/\d{4})\s*$')


def extract(directory, database):
    from pypdf import PdfReader
    import pdfplumber
    def read_pages(path):
        reader=PdfReader(path)
        with pdfplumber.open(path) as document:
            for page,physical in zip(reader.pages,document.pages):
                yield page.extract_text(extraction_mode='layout').splitlines(),physical.extract_words()
    db=sqlite3.connect(database); db.row_factory=sqlite3.Row
    airports={row['iata']:dict(row) for row in db.execute('SELECT * FROM airports WHERE iata IS NOT NULL')}
    db.close(); movements=[]; report=Counter(); sources=[]
    for name,expected,published,kind,remote in SOURCES:
        path=Path(directory)/name
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=expected:raise ValueError('Pinned DGCA PDF checksum mismatch')
        source_id='dgca-aic-ss2026-'+kind
        reader=PdfReader(path);heading=None;boundary=90
        for page_number,(lines,words) in enumerate(read_pages(path),1):
            physical_rows=defaultdict(list)
            for word in words:physical_rows[round(word['top'],1)].append(word)
            directions={}
            for parts in physical_rows.values():
                parts.sort(key=lambda w:w['x0']);labels=[w['text'] for w in parts]
                if 'AI' not in labels or 'AIC' not in labels:continue
                airports_in_row=[w for w in parts if 350<w['x0']<580 and re.fullmatch(r'[A-Z]{3}(?:/[A-Z]{3})*',w['text'])]
                times=[w['text'] for w in parts if re.fullmatch(r'\d{2}:\d{2}',w['text'])]
                dates=[w['text'] for w in parts if re.fullmatch(r'\d{2}/\d{2}/\d{4}',w['text'])]
                if len(airports_in_row)!=1 or len(times)!=1 or len(dates)!=2:raise ValueError('Ambiguous physical PDF row')
                key=(labels[0],labels[labels.index('AI')+1],airports_in_row[0]['text'],times[0],*dates)
                directions[key]='arrival' if airports_in_row[0]['x0']<480 else 'departure'
            column=next((line for line in lines if 'Arrival From' in line and 'Departure To' in line), None)
            if column: boundary=column.index('Departure To')
            for line in lines:
                text=line.strip()
                if text in HEADING_CODES:heading=text;continue
                if not re.match(r'^\s*\d+\s+AI\s+\d+',line):continue
                report['source_movement_rows']+=1
                match=ROW.fullmatch(line)
                if not match or not heading:raise ValueError(f'Unparsed movement at {name}:{page_number}: {line}')
                data=match.groupdict();own=HEADING_CODES[heading]
                if heading=='Rajkot' and any(re.search(r'\bRAJ\b',line) for line in lines):own='RAJ'
                legs=data['other'].split('/')
                if own not in airports or any(code not in airports for code in legs):
                    raise ValueError(f'Unresolved published airport: {heading}/{own}/{data["other"]}')
                row_key=tuple(data[k] for k in ('serial','number','other','time','from','to'))
                if row_key not in directions:raise ValueError('Text row does not match its physical PDF columns')
                direction=directions[row_key]
                origin,destination=(legs[0],own) if direction=='arrival' else (own,legs[-1])
                via=legs[1:] if direction=='arrival' else legs[:-1]
                number=re.sub(r'^0+(?=\d)', '', data['number'])
                valid_from=datetime.strptime(data['from'],'%d/%m/%Y').date().isoformat()
                valid_to=datetime.strptime(data['to'],'%d/%m/%Y').date().isoformat()
                days=''.join(sorted(set(data['days'])))
                if valid_to<valid_from:raise ValueError('Invalid schedule validity')
                hour,minute=map(int,data['time'].split(':'))
                if not 0<=hour<24 or not 0<=minute<60:raise ValueError('Invalid published time')
                movements.append(dict(flight_number='AI'+number,callsign='AIC'+number,airline='AIC',origin=airports[origin]['icao'],destination=airports[destination]['icao'],origin_iata=origin,destination_iata=destination,
                    via=[airports[code]['icao'] for code in via],flight_number_as_published='AI'+data['number'],aircraft_as_published=data['aircraft'],days=days,valid_from=valid_from,valid_to=valid_to,direction=direction,local_time=data['time'],source_id=source_id,source_page=page_number,source_serial=int(data['serial']),published_on=published))
        sources.append(dict(source_id=source_id,name='DGCA approved Air India '+kind+' summer schedule 2026',url=BASE_URL+remote,license_spdx='LicenseRef-DGCA-Public-Schedule-Facts',attribution_text='Directorate General of Civil Aviation, Government of India. Published '+published+'. Approved schedules are not proof of actual operation; verify operational changes with Air India.',sha256=digest,pages=len(reader.pages)))
    # Join complementary airport movements only for identical route, days,
    # aircraft and validity. No foreign departure/arrival time is fabricated.
    groups=defaultdict(list)
    for row in movements:
        key=tuple(row[k] for k in ('source_id','flight_number','origin','destination','aircraft_as_published','days','valid_from','valid_to'))
        groups[key+(tuple(row['via']),)].append(row)
    services=[]
    for key,rows in sorted(groups.items()):
        departures={row['local_time'] for row in rows if row['direction']=='departure'}
        arrivals={row['local_time'] for row in rows if row['direction']=='arrival'}
        dep=next(iter(departures)) if len(departures)==1 else None
        arr=next(iter(arrivals)) if len(arrivals)==1 else None
        # Retain conflicting publication rows separately rather than guessing.
        variants=[(dep,arr)] if len(departures)<=1 and len(arrivals)<=1 else [(row['local_time'],None) if row['direction']=='departure' else (None,row['local_time']) for row in rows]
        for dep,arr in sorted(set(variants),key=str):
            record={k:rows[0][k] for k in ('flight_number','callsign','airline','origin','destination','aircraft_as_published','days','valid_from','valid_to','source_id','published_on')}
            record['via']=rows[0]['via']
            record.update(departure_local=dep,arrival_local=arr,duration_min=None,source_movements=[{'page':r['source_page'],'serial':r['source_serial'],'direction':r['direction']} for r in rows])
            if dep and arr and rows[0]['source_id'].endswith('domestic'):
                d,a=[int(value[:2])*60+int(value[3:]) for value in (dep,arr)]
                # Overnight pairings need shifted days/dates; preserve unknown.
                if 15<=a-d<=600:record['duration_min']=a-d;report['published_time_pairs_with_duration']+=1
            services.append(record)
    report.update(normalised_service_rows=len(services),distinct_flight_route_pairs=len({(r['flight_number'],r['origin'],r['destination']) for r in services}),distinct_flight_numbers=len({r['flight_number'] for r in services}),source_pages=sum(s['pages'] for s in sources))
    return dict(schema_version=1,sources=sources,movements=movements,services=services,report=dict(report))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--database',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=extract(args.directory,args.database);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8',newline='\n');print(json.dumps(result['report'],indent=2))
