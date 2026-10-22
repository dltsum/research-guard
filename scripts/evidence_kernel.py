from __future__ import annotations

import contextvars
import datetime as dt
import hashlib
import uuid
import json
import os
import tempfile
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


EVIDENCE_SCHEMA_VERSION = 1
_SECRET_QUERY_KEYS = {
    "api_key", "apikey", "key", "token", "access_token", "subscription-key",
    "email", "mailto",
}
_ACTIVE_EVIDENCE: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "research_guard_active_evidence", default=None
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def io_path(path: Path) -> Path:
    """Use Windows' extended namespace for local I/O, without changing stored paths."""
    if os.name != "nt":
        return path
    absolute = str(path.resolve())
    if absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


class EvidencePersistenceError(RuntimeError):
    """A local evidence write failed; it is not a remote transport failure."""


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path = io_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_json(path: Path, value: Any) -> None:
    _atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def sanitize_url(url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(str(url))
    query = []
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        query.append((key, "[REDACTED]" if key.lower() in _SECRET_QUERY_KEYS else value))
    sanitized = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), ""))
    endpoint = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return sanitized, endpoint


class EvidenceRecorder:
    def __init__(self, project_root: str | os.PathLike[str], run_id: str, *, resume: bool = False):
        self.project_root = Path(project_root).resolve()
        self.run_id = str(run_id)
        self.run_dir = self.project_root / ".research-guard" / "evidence" / "runs" / self.run_id
        self.attempts: list[dict[str, Any]] = []
        self._sequence = 0
        manifest_path = self.run_dir / "manifest.json"
        if resume and io_path(manifest_path).is_file():
            manifest_path.resolve().relative_to(self.project_root)
            manifest = json.loads(io_path(manifest_path).read_text(encoding="utf-8"))
            errors = verify_evidence_manifest(self.project_root, str(manifest_path.relative_to(self.project_root)), manifest=manifest)
            if errors:
                raise ValueError("Cannot resume invalid evidence manifest: " + "; ".join(errors))
            if manifest.get("run_id") != self.run_id:
                raise ValueError("Cannot resume evidence manifest with a different run id")
            self.attempts = list(manifest.get("attempts") or [])
            sequences = [
                int(str(item.get("attempt_id", "a0")).removeprefix("a"))
                for item in self.attempts
                if str(item.get("attempt_id", "")).removeprefix("a").isdigit()
            ]
            self._sequence = max(sequences, default=0)

    def _record(
        self,
        *,
        source: str,
        query_id: str,
        query: str,
        mode: str,
        outcome: str,
        started_at: str,
        ended_at: str,
        raw: bytes | None = None,
        url: str | None = None,
        status_code: int | None = None,
        media_type: str | None = None,
        error_type: str | None = None,
        message: str | None = None,
        route: str | None = None,
    ) -> dict[str, Any]:
        self._sequence += 1
        attempt_id = f"a{self._sequence:05d}"
        record: dict[str, Any] = {
            "attempt_id": attempt_id,
            "source": source,
            "query_id": query_id,
            "query": query,
            "mode": mode,
            "outcome": outcome,
            "started_at": started_at,
            "ended_at": ended_at,
        }
        if url:
            record["url"], record["endpoint"] = sanitize_url(url)
        if status_code is not None:
            record["status_code"] = int(status_code)
        if media_type:
            record["media_type"] = str(media_type)
        if error_type:
            record["error_type"] = str(error_type)
        if message:
            record["message"] = str(message)
        if route:
            record["route"] = str(route)
        if raw is not None:
            extension = ".json" if (media_type or "").lower().endswith("json") or mode == "fixture" else ".bin"
            relative = (
                Path(".research-guard") / "evidence" / "runs" / self.run_id / "raw"
                / source / query_id / f"{attempt_id}-{uuid.uuid4().hex[:12]}{extension}"
            )
            try:
                _atomic_bytes(self.project_root / relative, raw)
            except OSError as exc:
                raise EvidencePersistenceError(f"Cannot persist local evidence payload {relative}: {exc}") from exc
            record.update({
                "raw_path": str(relative).replace("\\", "/"),
                "raw_bytes": len(raw),
            })
        self.attempts.append(record)
        return record

    def record_fixture(self, *, source: str, query_id: str, query: str, payload: Any, outcome: str = "success", error_type: str | None = None, message: str | None = None, status_code: int | None = None) -> dict[str, Any]:
        now = utc_now()
        raw = canonical_json(payload).encode("utf-8")
        return self._record(
            source=source, query_id=query_id, query=query, mode="fixture", outcome=outcome,
            started_at=now, ended_at=now, raw=raw, media_type="application/json",
            error_type=error_type, message=message, status_code=status_code,
        )

    def record_manual(self, *, source: str, query_id: str, query: str, evidence: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        return self._record(
            source=source, query_id=query_id, query=query, mode="manual", outcome="success",
            started_at=now, ended_at=now, raw=canonical_json(evidence).encode("utf-8"),
            media_type="application/json",
        )

    def finalize(self, *, method_version: int, method_hash: str, query_plan_hash: str, query_runs: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
        body = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "created_at": utc_now(),
            "method_version": method_version,
            "method_hash": method_hash,
            "query_plan_hash": query_plan_hash,
            "query_runs_hash": digest(query_runs),
            "attempts": self.attempts,
        }
        body["manifest_hash"] = digest(body)
        path = self.run_dir / "manifest.json"
        _atomic_json(path, body)
        return str(path.relative_to(self.project_root)).replace("\\", "/"), body


@contextmanager
def evidence_scope(recorder: EvidenceRecorder, *, source: str, query_id: str, query: str) -> Iterator[None]:
    token = _ACTIVE_EVIDENCE.set({
        "recorder": recorder, "source": source, "query_id": query_id, "query": query,
    })
    try:
        yield
    finally:
        _ACTIVE_EVIDENCE.reset(token)


def record_http_response(*, url: str, started_at: str, ended_at: str, status_code: int, media_type: str | None, body: bytes, route: str | None = None) -> None:
    active = _ACTIVE_EVIDENCE.get()
    if not active:
        return
    active["recorder"]._record(
        source=active["source"], query_id=active["query_id"], query=active["query"],
        mode="http", outcome="success", started_at=started_at, ended_at=ended_at,
        raw=body, url=url, status_code=status_code, media_type=media_type, route=route,
    )


def record_http_error(*, url: str, started_at: str, ended_at: str, error_type: str, message: str, status_code: int | None = None, media_type: str | None = None, body: bytes | None = None, route: str | None = None) -> None:
    active = _ACTIVE_EVIDENCE.get()
    if not active:
        return
    active["recorder"]._record(
        source=active["source"], query_id=active["query_id"], query=active["query"],
        mode="http", outcome="error", started_at=started_at, ended_at=ended_at,
        raw=body, url=url, status_code=status_code, media_type=media_type,
        error_type=error_type, message=message, route=route,
    )


def verify_evidence_manifest(
    project_root: str | os.PathLike[str], relative_path: str, *, manifest: Any = None,
) -> list[str]:
    """Optional readability diagnostic for saved request/response records."""
    root = Path(project_root).resolve()
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
        if manifest is None:
            manifest = json.loads(io_path(path).read_text(encoding="utf-8"))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return [f"evidence manifest unreadable: {exc}"]
    if not isinstance(manifest, dict):
        return ["evidence manifest must be an object"]
    attempts = manifest.get("attempts", [])
    if not isinstance(attempts, list):
        return ["evidence manifest attempts must be an array"]
    errors = []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            errors.append("evidence attempt must be an object")
            continue
        if attempt.get("raw_path"):
            try:
                (root / attempt["raw_path"]).resolve().relative_to(root)
            except (ValueError, TypeError):
                errors.append("evidence raw path unreadable: outside project root")
    return errors
