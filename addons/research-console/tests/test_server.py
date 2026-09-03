from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch


ADDON = Path(__file__).resolve().parents[1]
PLUGIN = ADDON.parents[1]
FAKE_CODEX = Path(__file__).resolve().parent / "fake_codex.py"
sys.path.insert(0, str(ADDON))

from research_console.codex_bridge import CodexBridge, discover_preflight  # noqa: E402
from research_console.server import _resolve_workspace, create_server  # noqa: E402


TOKEN = "test-token-with-more-than-24-characters"


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        with patch.dict(os.environ, {"FAKE_RESEARCH_GUARD_PLUGIN_ROOT": str(PLUGIN)}):
            bridge = CodexBridge(discover_preflight((sys.executable, str(FAKE_CODEX))))
        self.server = create_server(bridge, TOKEN, self.workspace, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temporary.cleanup()

    def request(self, path: str, *, token: str | None = TOKEN, body: dict | None = None, origin: str | None = None):
        headers = {}
        if token is not None:
            headers["X-Research-Guard-Token"] = token
        if origin:
            headers["Origin"] = origin
        data = None
        method = "GET"
        if body is not None:
            method = "POST"
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        return urllib.request.urlopen(request, timeout=30)

    def test_static_shell_has_security_headers_and_no_token_requirement(self) -> None:
        with self.request("/", token=None) as response:
            html = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("Research Console", html)
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_console_requires_explicit_workspace_and_never_controls_browser(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(Exception, "--workspace"):
                _resolve_workspace(None)
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_WORKSPACE": temporary}, clear=True
        ):
            workspace, source = _resolve_workspace(None)
        self.assertEqual(workspace, Path(temporary))
        self.assertEqual(source, "environment")
        server_source = (ADDON / "research_console" / "server.py").read_text(encoding="utf-8")
        self.assertNotIn("webbrowser", server_source)
        self.assertNotIn("arguments.open", server_source)

    def test_api_requires_token_and_rejects_cross_origin(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as missing:
            self.request("/api/status", token=None)
        try:
            self.assertEqual(missing.exception.code, 401)
        finally:
            missing.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as origin:
            self.request("/api/chat", body={"message": "test"}, origin="https://malicious.example")
        try:
            self.assertEqual(origin.exception.code, 403)
        finally:
            origin.exception.close()

    def test_status_and_streamed_chat_use_real_http_contract(self) -> None:
        with self.request("/api/status") as response:
            status = json.loads(response.read())
        self.assertEqual(status["status"], "READY")
        self.assertEqual(status["resource"]["maximum_parallel_runs"], 1)
        self.assertFalse(status["resource"]["gpu_allowed"])

        body = {
            "message": "Find a linked source.",
            "workspace": str(self.workspace),
            "sandbox": "read-only",
            "focus": ["literature-citations"],
            "locale": "en",
            "thread_id": None,
        }
        with patch.dict(os.environ, {"FAKE_RESEARCH_GUARD_PLUGIN_ROOT": str(PLUGIN)}):
            with self.request("/api/chat", body=body) as response:
                self.assertEqual(response.headers.get_content_type(), "application/x-ndjson")
                events = [json.loads(line) for line in response.read().decode("utf-8").splitlines() if line]
        self.assertEqual(events[0]["kind"], "run")
        self.assertTrue(any(item.get("kind") == "thread" for item in events))
        self.assertTrue(any(item.get("kind") == "assistant" for item in events))
        self.assertEqual(events[-1]["kind"], "done")
        self.assertTrue(events[-1]["success"])


if __name__ == "__main__":
    unittest.main()
