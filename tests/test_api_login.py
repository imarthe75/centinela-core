"""Real HTTP against a local server started by the test (no network beyond 127.0.0.1)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from centinela_core.api_login import resolve_token


class _H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        ok = body.get("correo") == "u@example.test" and body.get("password") == "good"
        if not ok:
            self.send_response(401); self.end_headers(); return
        if self.path == "/header":
            self.send_response(200); self.send_header("Authorization", "Bearer tok-header"); self.end_headers(); self.wfile.write(b"{}")
        else:
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps({"data": {"access_token": "tok-body"}}).encode())


@pytest.fixture(scope="module")
def base():
    srv = HTTPServer(("127.0.0.1", 0), _H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def _login(base, path, password, **extra):
    return {"url": base + path, "method": "POST", "json": {"correo": "u@example.test", "password": password}, **extra}


def test_token_from_json_path(base):
    assert resolve_token(_login(base, "/body", "good", token_json_path="data.access_token")) == "tok-body"


def test_token_from_header_strips_bearer(base):
    assert resolve_token(_login(base, "/header", "good", token_header="Authorization")) == "tok-header"


def test_wrong_password_returns_none(base):
    assert resolve_token(_login(base, "/body", "bad", token_json_path="data.access_token")) is None


def test_missing_json_path_returns_none(base):
    assert resolve_token(_login(base, "/body", "good", token_json_path="nope")) is None


def test_empty_login_returns_none():
    assert resolve_token({}) is None
