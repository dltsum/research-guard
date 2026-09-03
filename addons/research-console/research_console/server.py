from __future__ import annotations

import argparse
import json
import mimetypes
import os
import secrets
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import chain
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from . import __version__
from .codex_bridge import BridgeError, CodexBridge
from .contracts import ContractError, MAX_REQUEST_BYTES, normalize_chat_request, public_focus_options


STATIC_ROOT = Path(__file__).resolve().parent / "static"
STATIC_ROUTES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.js": "app.js",
    "/styles.css": "styles.css",
    "/mark.svg": "mark.svg",
}


class ConsoleHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(
        self,
        address: tuple[str, int],
        bridge: CodexBridge,
        token: str,
        default_workspace: Path,
    ) -> None:
        self.bridge = bridge
        self.auth_token = token
        self.default_workspace = default_workspace
        super().__init__(address, ConsoleHandler)


class ConsoleHandler(BaseHTTPRequestHandler):
    server: ConsoleHTTPServer
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *args: Any) -> None:
        return

    def _security_headers(self) -> None:
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")

    def _send_json(self, status: int, value: dict[str, Any]) -> None:
        body = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        supplied = self.headers.get("X-Research-Guard-Token", "")
        return bool(supplied) and secrets.compare_digest(supplied, self.server.auth_token)

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        try:
            parsed = urlsplit(origin)
            port = parsed.port
        except ValueError:
            return False
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            return False
        return port == self.server.server_port

    def _require_api_access(self) -> bool:
        if not self._authorized():
            self._send_json(HTTPStatus.UNAUTHORIZED, {"status": "ERROR", "code": "TOKEN_REQUIRED", "message": "The local UI token is missing or invalid."})
            return False
        if not self._same_origin():
            self._send_json(HTTPStatus.FORBIDDEN, {"status": "ERROR", "code": "ORIGIN_REJECTED", "message": "The request origin is not this localhost console."})
            return False
        return True

    def _read_json(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
        if content_type != "application/json":
            raise ContractError("CONTENT_TYPE_INVALID", "API requests must use application/json.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ContractError("CONTENT_LENGTH_INVALID", "The request Content-Length is invalid.") from exc
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ContractError("REQUEST_SIZE_INVALID", f"The request body must be between 1 and {MAX_REQUEST_BYTES:,} bytes.", http_status=413)
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContractError("JSON_INVALID", "The request body is not valid UTF-8 JSON.") from exc
        if not isinstance(value, dict):
            raise ContractError("JSON_OBJECT_REQUIRED", "The request body must be a JSON object.")
        return value

    def do_OPTIONS(self) -> None:
        self._send_json(HTTPStatus.METHOD_NOT_ALLOWED, {"status": "ERROR", "code": "CORS_DISABLED", "message": "Cross-origin API access is disabled."})

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/status":
            if not self._require_api_access():
                return
            value = self.server.bridge.public_status(self.server.default_workspace)
            value["ui"] = {"name": "Research Console", "version": __version__}
            value["focus_options"] = public_focus_options()
            self._send_json(HTTPStatus.OK, value)
            return
        if path == "/healthz":
            self._send_json(HTTPStatus.OK, {"status": "UP", "service": "research-guard-ui"})
            return
        relative = STATIC_ROUTES.get(path)
        if relative is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"status": "ERROR", "code": "NOT_FOUND", "message": "The requested resource does not exist."})
            return
        target = STATIC_ROOT / relative
        if not target.is_file():
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"status": "ERROR", "code": "STATIC_ASSET_MISSING", "message": "A required UI asset is missing."})
            return
        body = target.read_bytes()
        media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix == ".js":
            media_type = "text/javascript"
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", f"{media_type}; charset=utf-8" if media_type.startswith(("text/", "image/svg")) else media_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in {"/api/chat", "/api/cancel", "/api/shutdown"}:
            self._send_json(HTTPStatus.NOT_FOUND, {"status": "ERROR", "code": "NOT_FOUND", "message": "The requested API route does not exist."})
            return
        if not self._require_api_access():
            return
        try:
            value = self._read_json()
            if path == "/api/cancel":
                run_id = str(value.get("run_id") or "").strip()
                cancelled = bool(run_id) and self.server.bridge.cancel(run_id)
                self._send_json(HTTPStatus.OK if cancelled else HTTPStatus.NOT_FOUND, {
                    "status": "CANCEL_REQUESTED" if cancelled else "RUN_NOT_FOUND",
                    "run_id": run_id,
                })
                return
            if path == "/api/shutdown":
                self._send_json(HTTPStatus.OK, {"status": "SHUTTING_DOWN"})
                threading.Thread(target=self.server.shutdown, name="rg-ui-shutdown", daemon=True).start()
                return

            request = normalize_chat_request(value, self.server.default_workspace)
            stream = self.server.bridge.stream(request)
            first = next(stream)
        except (ContractError, BridgeError) as exc:
            self._send_json(exc.http_status, {"status": "ERROR", "code": exc.code, "message": str(exc)})
            return
        except StopIteration:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"status": "ERROR", "code": "EMPTY_CODEX_STREAM", "message": "Codex returned no events."})
            return

        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            for event in chain((first,), stream):
                payload = (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
                self.wfile.write(payload)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            stream.close()


def create_server(
    bridge: CodexBridge,
    token: str,
    default_workspace: Path,
    *,
    port: int = 0,
) -> ConsoleHTTPServer:
    workspace = default_workspace.expanduser().resolve(strict=True)
    if not workspace.is_dir():
        raise ContractError("WORKSPACE_NOT_DIRECTORY", "The default workspace must be a directory.")
    if not token or len(token) < 24:
        raise ContractError("TOKEN_TOO_SHORT", "The local UI token must contain at least 24 characters.")
    return ConsoleHTTPServer(("127.0.0.1", port), bridge, token, workspace)


def _resolve_workspace(argument: Path | None) -> tuple[Path, str]:
    """Resolve an explicit workspace without binding to this launch directory."""
    if argument is not None:
        return argument, "cli"
    configured = os.environ.get("RESEARCH_GUARD_WORKSPACE", "").strip()
    if configured:
        return Path(configured), "environment"
    if sys.stdin.isatty() and sys.stdout.isatty():
        answer = input("Research workspace path (required): ").strip()
        if answer:
            return Path(answer), "prompt"
    raise ContractError(
        "WORKSPACE_REQUIRED",
        "Provide --workspace or RESEARCH_GUARD_WORKSPACE; the console never assumes the launch directory.",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch the optional Research Guard Research Console.")
    parser.add_argument("--workspace", type=Path, help="Initial research workspace (required unless RESEARCH_GUARD_WORKSPACE is set)")
    parser.add_argument("--port", type=int, default=0, help="Localhost port; 0 selects an available port")
    parser.add_argument("--token", help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if not 0 <= arguments.port <= 65535:
        parser.error("--port must be between 0 and 65535")

    bridge = CodexBridge.from_environment()
    token = arguments.token or secrets.token_urlsafe(32)
    workspace, workspace_source = _resolve_workspace(arguments.workspace)
    server = create_server(bridge, token, workspace, port=arguments.port)
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}/#token={token}"
    print(json.dumps({
        "status": "READY", "url": url, "bind": f"{host}:{port}",
        "workspace": str(workspace.expanduser().resolve()), "workspace_source": workspace_source,
        "privacy": "localhost-only; token is stored in the URL fragment and never sent as a referrer",
    }, ensure_ascii=False), flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
