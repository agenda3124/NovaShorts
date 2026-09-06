from __future__ import annotations

import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty, Queue

from engine import load_settings, log

HOST = '127.0.0.1'
PORT = 38471
TASKS: Queue[dict] = Queue()
RESULTS: Queue[dict] = Queue()
_BACKLOG: deque[dict] = deque()
_BACKLOG_LOCK = threading.Lock()


def _task_id(item: dict) -> str:
    try:
        return str((item or {}).get('task', {}).get('task_id') or '')
    except Exception:
        return ''


def _take_backlog(task_ids: set[str]) -> list[dict]:
    matched = []
    with _BACKLOG_LOCK:
        keep = deque()
        while _BACKLOG:
            item = _BACKLOG.popleft()
            if _task_id(item) in task_ids:
                matched.append(item)
            else:
                keep.append(item)
        _BACKLOG.extend(keep)
    return matched


def wait_for_results(task_ids, timeout: float = 45.0) -> list[dict]:
    """Wait only for the requested bridge task ids without stealing other jobs' results."""
    pending = {str(x) for x in task_ids if x}
    if not pending:
        return []
    out = []
    end = time.time() + max(0.5, float(timeout))

    cached = _take_backlog(pending)
    for item in cached:
        tid = _task_id(item)
        if tid in pending:
            pending.discard(tid)
            out.append(item)

    while pending and time.time() < end:
        try:
            item = RESULTS.get(timeout=min(0.6, max(0.05, end - time.time())))
            RESULTS.task_done()
        except Empty:
            continue
        tid = _task_id(item)
        if tid in pending:
            pending.discard(tid)
            out.append(item)
        else:
            with _BACKLOG_LOCK:
                _BACKLOG.append(item)
    return out


def wait_for_result(task_id: str, timeout: float = 30.0) -> dict | None:
    rows = wait_for_results([task_id], timeout)
    return rows[0] if rows else None


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.end_headers()
        self.wfile.write(data)

    def _ok(self):
        return self.headers.get('Authorization', '') == 'Bearer ' + load_settings().bridge_token

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.end_headers()

    def do_GET(self):
        if self.path == '/v1/status':
            return self._send(200, {'ok': True, 'service': 'NovaShorts Bridge', 'port': PORT})
        if not self._ok():
            return self._send(401, {'ok': False, 'error': 'unauthorized'})
        if self.path == '/v1/tasks':
            try:
                x = TASKS.get_nowait()
                TASKS.task_done()
            except Empty:
                x = None
            return self._send(200, {'ok': True, 'task': x})
        if self.path == '/v1/results':
            items = []
            while True:
                try:
                    items.append(RESULTS.get_nowait())
                    RESULTS.task_done()
                except Empty:
                    break
            return self._send(200, {'ok': True, 'results': items})
        return self._send(404, {'ok': False})

    def do_POST(self):
        if not self._ok():
            return self._send(401, {'ok': False, 'error': 'unauthorized'})
        n = int(self.headers.get('Content-Length', '0') or 0)
        try:
            body = json.loads(self.rfile.read(n) or b'{}')
        except Exception:
            body = {}
        if self.path == '/v1/results':
            RESULTS.put(body)
            return self._send(200, {'ok': True})
        if self.path == '/v1/tasks':
            TASKS.put(body)
            return self._send(200, {'ok': True})
        return self._send(404, {'ok': False})

    def log_message(self, fmt, *args):
        log('bridge ' + fmt % args)


def start_bridge():
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        log('Bridge bind: ' + str(e))
        return None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log(f'ChromeBridge started {HOST}:{PORT}')
    return server
