"""Local-only REST API + dashboard. Python standard library; zero cloud services."""
from __future__ import annotations
import argparse, json, mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from . import __version__
from .decision import decide
from .examples import EXAMPLES
from .benchmark import benchmark
from .ollama import enrich

ROOT=Path(__file__).resolve().parent.parent
MAX_BYTES=128*1024
class Handler(BaseHTTPRequestHandler):
    def _json(self,obj,status=200):
        data=json.dumps(obj,ensure_ascii=False,allow_nan=False).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(data)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/api/health':return self._json({'ok':True,'name':'ENOSH-SDL','version':__version__,'mode':'dry_run'})
        if path=='/api/examples':return self._json(EXAMPLES)
        if path in ('/','/index.html'):
            data=(ROOT/'index.html').read_bytes()
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
            return
        self._json({'error':'not found'},404)
    def do_POST(self):
        path=urlparse(self.path).path
        if path not in ('/api/decide','/api/benchmark','/api/batch'):return self._json({'error':'not found'},404)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<1 or size>MAX_BYTES:raise ValueError('Body size invalid or >128 KB')
            payload=json.loads(self.rfile.read(size).decode('utf-8'))
            if not isinstance(payload,dict):raise ValueError('JSON object required')
            if path=='/api/decide':
                observation=payload.get('observation',payload)
                if not isinstance(observation,dict):raise ValueError('Observation object required')
                backend=str(payload.get('backend','heuristic'))
                if backend=='ollama': observation=enrich(observation,model=str(payload.get('model','qwen3:8b')))
                elif backend!='heuristic':raise ValueError('Unknown semantic backend')
                result=decide(observation,energy_weight=float(payload.get('energy_weight',0.18)),policy=str(payload.get('policy','sdl')))
                result['semantic_backend']=backend
            elif path=='/api/benchmark':
                result=benchmark(int(payload.get('n',200)),int(payload.get('seed',24)),float(payload.get('energy_weight',0.18)),float(payload.get('k',8)))
            else:
                observations=payload.get('observations',[])
                if not isinstance(observations,list) or len(observations)>100:raise ValueError('observations must be a list of at most 100 objects')
                result={'decisions':[decide(item) for item in observations]}
            return self._json(result)
        except (ValueError,TypeError,KeyError,json.JSONDecodeError,OverflowError) as e:
            return self._json({'error':str(e)},400)
    def log_message(self,format,*args):pass # avoid logging user text; local demo

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765)
    a=p.parse_args()
    if not 1024<=a.port<=65535:p.error('port must be 1024..65535')
    srv=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
    print(f'ENOSH-SDL v{__version__}: http://127.0.0.1:{a.port}/ (Ctrl+C to stop)',flush=True)
    try:srv.serve_forever()
    except KeyboardInterrupt:pass
    finally:srv.server_close()
if __name__=='__main__':main()
