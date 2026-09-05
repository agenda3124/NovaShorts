from __future__ import annotations
import json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Queue, Empty
from engine import load_settings, log

HOST='127.0.0.1';PORT=38471
TASKS:Queue[dict]=Queue();RESULTS:Queue[dict]=Queue()

class Handler(BaseHTTPRequestHandler):
 def _send(self,code,payload):
  data=json.dumps(payload,ensure_ascii=False).encode('utf-8');self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.send_header('Access-Control-Allow-Origin','*');self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type');self.end_headers();self.wfile.write(data)
 def _ok(self):
  return self.headers.get('Authorization','')=='Bearer '+load_settings().bridge_token
 def do_OPTIONS(self):
  self.send_response(204);self.send_header('Access-Control-Allow-Origin','*');self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type');self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS');self.end_headers()
 def do_GET(self):
  if self.path=='/v1/status':return self._send(200,{'ok':True,'service':'NovaShorts Bridge','port':PORT})
  if not self._ok():return self._send(401,{'ok':False,'error':'unauthorized'})
  if self.path=='/v1/tasks':
   try:x=TASKS.get_nowait();TASKS.task_done()
   except Empty:x=None
   return self._send(200,{'ok':True,'task':x})
  if self.path=='/v1/results':
   items=[]
   while True:
    try:items.append(RESULTS.get_nowait());RESULTS.task_done()
    except Empty:break
   return self._send(200,{'ok':True,'results':items})
  return self._send(404,{'ok':False})
 def do_POST(self):
  if not self._ok():return self._send(401,{'ok':False,'error':'unauthorized'})
  n=int(self.headers.get('Content-Length','0') or 0)
  try:body=json.loads(self.rfile.read(n) or b'{}')
  except:body={}
  if self.path=='/v1/results':RESULTS.put(body);return self._send(200,{'ok':True})
  if self.path=='/v1/tasks':TASKS.put(body);return self._send(200,{'ok':True})
  return self._send(404,{'ok':False})
 def log_message(self,fmt,*args):log('bridge '+fmt%args)

def start_bridge():
 try:s=ThreadingHTTPServer((HOST,PORT),Handler)
 except OSError as e:log('Bridge bind: '+str(e));return None
 threading.Thread(target=s.serve_forever,daemon=True).start();log(f'ChromeBridge started {HOST}:{PORT}');return s
