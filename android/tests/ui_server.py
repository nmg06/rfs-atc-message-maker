"""Development-only HTTP bridge to exercise the shipped UI with the real engines."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'android/app/src/main/python'), str(ROOT/'android/app/build/generated/python'), str(ROOT)]
from android_engine import Engine

temp = tempfile.TemporaryDirectory()
database = Path(temp.name)/'aviation.sqlite'
with gzip.open(ROOT/'android/bundled/aviation.sqlite.gz','rb') as src, database.open('wb') as dst:
    shutil.copyfileobj(src,dst)
engine = Engine(temp.name,database)
lock = threading.Lock()
from app_version import VERSION
update_policy = {'version':VERSION+'-flightdeck','enabled':False,'last_attempt':0,'last_result':{}}
update_requests = 0
pending_import = None

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(ROOT/'android/app/src/main/assets/www'),**kwargs)
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path.startswith('/site/'):
            from urllib.parse import urlsplit
            from scripts.prepare_site import PUBLIC_FILES
            path = urlsplit(self.path).path.removeprefix('/site/')
            if path not in PUBLIC_FILES:
                self.send_error(404)
                return
            self.path = '/' + path
            self.directory = str(ROOT)
            return super().do_GET()
        if self.path.startswith('/prototype/'):
            self.path = self.path.removeprefix('/prototype')
            self.directory = str(ROOT/'mobile')
            return super().do_GET()
        if self.path in ('/', '/index.html'):
            raw = (ROOT/'android/app/src/main/assets/www/index.html').read_text(encoding='utf-8')
            raw = raw.replace("script-src 'self'", "script-src 'self' 'unsafe-eval'")
            data = raw.encode('utf-8')
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        elif self.path == '/world-countries.js':
            raw=(ROOT/'android/app/build/generated/assets/www/world-countries.js').read_bytes()
            self.send_response(200);self.send_header('Content-Type','application/javascript');self.end_headers();self.wfile.write(raw)
        else:
            super().do_GET()
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        try:
            method=body['method'].removeprefix('native.')
            global update_requests, pending_import
            args=body.get('args',{})
            with lock:
                if method=='updatesGet':result=update_policy.copy()
                elif method=='updatesConfigure':
                    update_policy['enabled']=args['enabled'];result=update_policy.copy()
                elif method=='updatesCheck':
                    import time
                    now=int(time.time()*1000)
                    if args.get('automatic') and (not update_policy['enabled'] or now-update_policy['last_attempt']<86400000):result={'status':'skipped'}
                    else:
                        update_requests+=1;update_policy['last_attempt']=now
                        update_policy['last_result']={'status':'unavailable','reason':'offline-test'}
                        result=update_policy['last_result']
                elif method=='updatesTestCount':result={'requests':update_requests}
                elif method=='updatesOpen':raise ValueError('No checked download available')
                elif method=='import':
                    if pending_import is None:result={'cancelled':True}
                    else:result={'import_preview':engine.handle('import_preview',{'text':pending_import}),'token':'test-import'}
                elif method=='importTestSelect':pending_import=args['text'];result={}
                elif method=='importCancel':pending_import=None;result={}
                elif method=='importApply':
                    if pending_import is None or args['token']!='test-import':raise ValueError('Select a backup first')
                    result=engine.handle('import',{'text':pending_import,'mode':args['mode']});pending_import=None
                else:result=engine.handle(method,args)
            payload={'ok':True,'result':result}
        except Exception as error:payload={'ok':False,'error':str(error)}
        raw=json.dumps(payload,ensure_ascii=False).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)

server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
print(json.dumps({'port':server.server_port}),flush=True)
try:server.serve_forever()
finally:server.server_close();temp.cleanup()
