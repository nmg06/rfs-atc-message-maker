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
sys.path[:0] = [str(ROOT/'android/app/src/main/python'), str(ROOT/'android/app/build/generated/python')]
from android_engine import Engine

temp = tempfile.TemporaryDirectory()
database = Path(temp.name)/'aviation.sqlite'
with gzip.open(ROOT/'android/bundled/aviation.sqlite.gz','rb') as src, database.open('wb') as dst:
    shutil.copyfileobj(src,dst)
engine = Engine(temp.name,database)
lock = threading.Lock()

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(ROOT/'android/app/src/main/assets/www'),**kwargs)
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path == '/world-countries.js':
            raw=(ROOT/'android/app/build/generated/assets/www/world-countries.js').read_bytes()
            self.send_response(200);self.send_header('Content-Type','application/javascript');self.end_headers();self.wfile.write(raw)
        else:
            super().do_GET()
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        try:
            method=body['method'].removeprefix('native.')
            with lock:result=engine.handle(method,body.get('args',{}))
            payload={'ok':True,'result':result}
        except Exception as error:payload={'ok':False,'error':str(error)}
        raw=json.dumps(payload,ensure_ascii=False).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)

server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
print(json.dumps({'port':server.server_port}),flush=True)
try:server.serve_forever()
finally:server.server_close();temp.cleanup()
