from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from research_guard_core import GuardError, digest, project_root, utc_now


SCHEMA_VERSION = 1
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")


class ConstructiveNumericalError(GuardError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _record_stable(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record.get(key) for key in (
        "schema_version", "audit_id", "manifest", "manifest_sha256", "result",
        "resource_usage", "created_at",
    )}


def _record_path(root: Path, audit_id: str) -> Path:
    return root / ".research-guard" / "constructive-numerical" / f"{audit_id}.json"


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load_record(root: Path, audit_id: str) -> dict[str, Any]:
    path = _record_path(root, audit_id)
    if not path.is_file():
        raise ConstructiveNumericalError("Constructive numerical audit is not registered")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConstructiveNumericalError(f"Constructive numerical record is invalid: {exc}") from exc
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ConstructiveNumericalError("Unsupported constructive numerical schema")
    manifest = record.get("manifest")
    if not isinstance(manifest, dict) or hashlib.sha256(_canonical(manifest)).hexdigest() != record.get("manifest_sha256"):
        raise ConstructiveNumericalError("CONSTRUCTIVE_NUMERICAL_MANIFEST_INTEGRITY_FAILURE")
    if digest(_record_stable(record)) != record.get("receipt_sha256"):
        raise ConstructiveNumericalError("CONSTRUCTIVE_NUMERICAL_RECEIPT_INTEGRITY_FAILURE")
    result = record.get("result")
    if not isinstance(result, dict) or result.get("manifest_sha256") != record["manifest_sha256"]:
        raise ConstructiveNumericalError("CONSTRUCTIVE_NUMERICAL_RESULT_BINDING_FAILURE")
    return record


def _public(record: dict[str, Any]) -> dict[str, Any]:
    result = dict(record["result"])
    result["receipt_sha256"] = record["receipt_sha256"]
    result["resource_usage"] = record["resource_usage"]
    result["recorded_at"] = record["created_at"]
    return result


def run_constructive_numerical_audit(
    root: str | os.PathLike[str], manifest: dict[str, Any], *, timeout: float = 180,
) -> dict[str, Any]:
    from dependency_manager import DependencyError, require
    from resource_guard import ResourceGuardError, run_managed

    base = project_root(root)
    if not base.is_dir():
        raise ConstructiveNumericalError("project_root must be an existing directory")
    if not isinstance(manifest, dict):
        raise ConstructiveNumericalError("numeric_constraint_manifest must be an object")
    audit_id = str(manifest.get("audit_id") or "").strip()
    if not IDENTIFIER.fullmatch(audit_id):
        raise ConstructiveNumericalError("numeric_constraint_manifest.audit_id is invalid")
    manifest_sha256 = hashlib.sha256(_canonical(manifest)).hexdigest()
    path = _record_path(base, audit_id)
    if path.is_file():
        existing = _load_record(base, audit_id)
        if existing.get("manifest_sha256") != manifest_sha256:
            raise ConstructiveNumericalError("audit_id already binds a different manifest; use a new versioned audit_id")
        return _public(existing)
    try:
        core = require("core-runtime")
    except DependencyError as exc:
        raise ConstructiveNumericalError(f"{exc.code}: {exc}") from exc
    python = Path(str((core.get("executables") or {}).get("python") or "")).resolve()
    if not python.is_file():
        raise ConstructiveNumericalError("DEPENDENCY_MISSING: registered core Python is unavailable")
    worker = Path(__file__).with_name("constructive_numerical_worker.py")
    if not worker.is_file():
        raise ConstructiveNumericalError("constructive numerical worker is missing")
    work_root = base / ".research-guard" / "constructive-numerical"
    work_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="research-guard-constructive-", dir=work_root) as temporary:
        input_path = Path(temporary) / "input.json"
        output_path = Path(temporary) / "output.json"
        _atomic_json(input_path, {"project_root": str(base), "manifest": manifest})
        isolated = (python.parent / "Lib" / "site-packages" / "pint").is_dir()
        interpreter_flags = ["-I"] if isolated else []
        try:
            completed = run_managed(
                [str(python), *interpreter_flags, "-X", "utf8", str(worker), str(input_path), str(output_path)],
                cwd=base, timeout=float(timeout),
            )
        except ResourceGuardError as exc:
            raise ConstructiveNumericalError(f"RESOURCE_GUARD_BLOCKED: {exc}") from exc
        if completed.returncode != 0 or not output_path.is_file():
            detail = (completed.stderr or completed.stdout or "constructive worker produced no result")[-3000:]
            if output_path.is_file():
                detail = output_path.read_text(encoding="utf-8")[-3000:]
            raise ConstructiveNumericalError(f"constructive numerical worker failed: {detail.strip()}")
        try:
            result = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConstructiveNumericalError(f"constructive numerical output is invalid: {exc}") from exc
    if result.get("manifest_sha256") != manifest_sha256 or result.get("audit_id") != audit_id:
        raise ConstructiveNumericalError("constructive numerical output is not bound to the submitted manifest")
    if result.get("status") not in {"PASS", "BLOCKED", "NOT_CERTIFIED"}:
        raise ConstructiveNumericalError("constructive numerical worker returned an unsupported status")
    record = {
        "schema_version": SCHEMA_VERSION,
        "audit_id": audit_id,
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "result": result,
        "resource_usage": getattr(completed, "resource_usage", {}),
        "created_at": utc_now(),
    }
    record["receipt_sha256"] = digest(_record_stable(record))
    _atomic_json(path, record)
    return _public(record)


def get_constructive_numerical_audit(
    root: str | os.PathLike[str], audit_id: str,
) -> dict[str, Any]:
    base = project_root(root)
    identifier = str(audit_id or "").strip()
    if not IDENTIFIER.fullmatch(identifier):
        raise ConstructiveNumericalError("numeric_audit_id is invalid")
    return _public(_load_record(base, identifier))


def verify_constructive_numerical_audit(
    root: str | os.PathLike[str], audit_id: str,
) -> dict[str, Any]:
    result = get_constructive_numerical_audit(root, audit_id)
    return {
        **result,
        "verification": "PASS" if result.get("status") == "PASS" else "FAIL",
    }
