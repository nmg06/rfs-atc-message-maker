"""Build-time bounded range download of public MrAirspace release datasets."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import urllib.request


def download(entry, directory, *, workers=6, chunk_bytes=4*1024*1024):
    url, name, size = entry['url'], entry['file'], entry['bytes']
    if not re.fullmatch(r'(?:2025_Q[1-4]_detailed|2024_Q[1-4])_github\.parquet', name):
        raise ValueError('Unexpected dataset name')
    tag=('aircraft_flight_logs_' if name.startswith('2024') else 'aircraft_flight_schedules_')+name[:4]+'_quarter'+name[6]
    expected_url='https://github.com/MrAirspace/aircraft-flight-schedules/releases/download/'+tag+'/'+name
    if url != expected_url or not isinstance(size,int) or not 0<size<2_000_000_000:
        raise ValueError('Unexpected source URL or size')
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    target=directory/name; meta=directory/(name+'.source.json')
    if target.exists():
        if not meta.exists(): raise ValueError('Existing source has no verified metadata')
        known=json.loads(meta.read_text())
        with target.open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
        if target.stat().st_size!=size or actual!=known['sha256']: raise ValueError('Existing source checksum mismatch')
        return known
    partial=directory/(name+'.range.part')
    if partial.exists(): raise ValueError('Previous ranged candidate exists; preserve it and choose another cache')
    with partial.open('xb') as f:f.truncate(size)
    lock=threading.Lock(); completed=0; started=time.monotonic()
    def fetch(start):
        end=min(size-1,start+chunk_bytes-1); last_error=None
        for attempt in range(3):
            try:
                req=urllib.request.Request(url,headers={'User-Agent':'RFS-Flightdeck-build-data','Range':f'bytes={start}-{end}'})
                with urllib.request.urlopen(req,timeout=35) as response:
                    if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{size}':
                        raise ValueError('Source does not honour exact byte range')
                    block=response.read(end-start+2)
                if len(block)!=end-start+1: raise ValueError('Truncated source chunk')
                with lock,partial.open('r+b') as output:
                    output.seek(start); output.write(block)
                return len(block)
            except (OSError,ValueError) as error:last_error=error
        raise last_error
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(fetch,start) for start in range(0,size,chunk_bytes)]
        for future in as_completed(futures):
            completed+=future.result()
            if completed//(64*1024*1024) != (completed-chunk_bytes)//(64*1024*1024):
                print(f'{name}: {completed//1024//1024} / {size//1024//1024} MiB',flush=True)
    with partial.open('rb') as f: checksum=hashlib.file_digest(f,'sha256').hexdigest()
    if entry.get('sha256') and checksum!=entry['sha256']: raise ValueError('Pinned checksum mismatch')
    result=dict(entry,sha256=checksum,seconds=round(time.monotonic()-started,1))
    partial.replace(target);meta.write_text(json.dumps(result,indent=2),encoding='utf-8',newline='\n')
    print('Verified source',name,checksum,flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args(); entries=json.loads(args.plan.read_text())
    for entry in entries:download(entry,args.directory)
