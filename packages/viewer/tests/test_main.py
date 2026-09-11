"""The healthcheck command, against a stand-in server."""

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from sfmview.main import health


def serve(status: int, body: bytes):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status if self.path == "/api/health" else 404)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.mark.parametrize(("status", "body", "code"), [
    (200, json.dumps({"status": "ok", "live": False}).encode(), 0),
    (200, json.dumps({"status": "down"}).encode(), 1),
    (200, b"not json", 1),
    (500, b"", 1),
])
def test_health_reads_the_answer(status, body, code):
    server = serve(status, body)
    try:
        # 0.0.0.0, as inside a container, is asked on the loopback.
        assert health(["--host", "0.0.0.0", "--port", str(server.server_port)]) == code
    finally:
        server.shutdown()


def test_health_fails_when_nothing_listens():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert health(["--host", "127.0.0.1", "--port", str(port)]) == 1
