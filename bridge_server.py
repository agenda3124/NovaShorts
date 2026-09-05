from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty, Queue

from nova_core import load_settings, log

HOST = "127.0.0.1"
PORT = 38471
TASKS: Queue[dict] = Queue()
RESULTS: Queue[dict] = Queue()


class Handler(BaseHTTPRequestHandler):
    server_version = "NovaShortsBridge/1.5"

    def _authorized(self) -> bool:
        s = load_settings()
        auth = self.headers.get("Authorization", "")
        return bool(s.bridge_token) and auth == f"Bearer {s.bridge_token}"

    def _json(self, status: int, payload: dict):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path == "/v1/status":
            return self._json(200, {"ok": True, "service": "NovaShorts Chrome Bridge", "port": PORT})
        if not self._authorized():
            return self._json(401, {"ok": False, "error": "unauthorized"})
        if self.path == "/v1/tasks":
            try:
                task = TASKS.get_nowait()
                TASKS.task_done()
            except Empty:
                task = None
            return self._json(200, {"ok": True, "task": task})
        if self.path == "/v1/results":
            items = []
            while True:
                try:
                    items.append(RESULTS.get_nowait())
                    RESULTS.task_done()
                except Empty:
                    break
            return self._json(200, {"ok": True, "results": items})
        return self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        if not self._authorized():
            return self._json(401, {"ok": False, "error": "unauthorized"})
        length = int(self.headers.get("Content-Length", "0") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            body = {}
        if self.path == "/v1/results":
            RESULTS.put(body)
            return self._json(200, {"ok": True})
        if self.path == "/v1/tasks":
            TASKS.put(body)
            return self._json(200, {"ok": True})
        return self._json(404, {"ok": False, "error": "not_found"})

    def log_message(self, fmt, *args):
        log("bridge " + (fmt % args))


def start_bridge() -> ThreadingHTTPServer | None:
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        log(f"ChromeBridge bind failed: {e}")
        return None
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    log(f"ChromeBridge started at {HOST}:{PORT}")
    return server
