from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resource_guard import ResourceGuardError, require_start_headroom, run_managed
from network_config_core import network_environment


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "assets" / "dependency-catalog.json"
PAYLOAD_MANIFEST_PATH = PLUGIN_ROOT / "assets" / "payload-manifest.json"
OPTIONAL_IDS = {"portable-git", "tex-basic", "lean-mathlib"}
INFORMATIONAL_IDS = {"structured-parser-adapters", "advanced-statistics", "active-review-ui"}
LEAN_TOOLCHAIN = "leanprover/lean4:v4.33.0"
MATHLIB_TAG = "v4.33.0"
MATHLIB_COMMIT = "db584cd6d46c92f209a44c0f1c829460d327499d"
TRANSACTION_DIRECTORY = "transactions"

# These directories are generated between user-visible research stages.  They
# are intentionally named rather than discovered by size so that ``clean``
# never guesses about a project's source or durable result files.
_CLEAN_DIRECTORY_NAMES = {
    "cache", "caches", "session", "sessions", "tmp", "temp",
    "install-staging", "__pycache__", ".pytest_cache",
}
_HARD_PROJECT_DIRECTORY_NAMES = {
    "runs", "raw", "tex-build", "formula-verification", "constructive-numerical",
}
_HARD_HOME_DIRECTORY_NAMES = {"receipts", "transactions", "install-staging"}
_CLEAN_FILE_SUFFIXES = {".tmp", ".part", ".partial", ".bak"}


class DependencyError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _home() -> Path:
    configured = os.environ.get("RESEARCH_GUARD_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / ".research-guard"


def dependency_root() -> Path:
    return _home() / "dependencies"


def _safe_name(value: str) -> str:
    """Return a stable filename fragment for a component/transaction key."""
    return "".join(character if character.isalnum() or character in "-_" else "_" for character in str(value))


def _transaction_path(component_id: str) -> Path:
    return dependency_root() / TRANSACTION_DIRECTORY / f"{_safe_name(component_id)}.json"


def _read_transaction(component_id: str) -> dict[str, Any] | None:
    path = _transaction_path(component_id)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_transaction(component_id: str, value: dict[str, Any]) -> dict[str, Any]:
    body = {"schema_version": 1, "component": component_id, **value}
    _atomic_json(_transaction_path(component_id), body)
    return body


def _begin_transaction(component_id: str, action: str, target: Path) -> dict[str, Any]:
    """Start/resume one component transaction without a repository-wide lock."""
    previous = _read_transaction(component_id) or {}
    attempts = int(previous.get("attempts", 0)) + 1
    return _write_transaction(component_id, {
        "status": "IN_PROGRESS",
        "action": action,
        "target": str(target.resolve()),
        "started_at": _now(),
        "attempts": attempts,
        "resumed": previous.get("status") in {"IN_PROGRESS", "INTERRUPTED", "CANCELLED", "FAILED"},
    })


def _finish_transaction(component_id: str, status: str, **details: Any) -> dict[str, Any]:
    previous = _read_transaction(component_id) or {}
    return _write_transaction(component_id, {
        **previous,
        "status": status,
        "finished_at": _now(),
        **details,
    })


def _component_ready(component_id: str, value: dict[str, Any] | None = None) -> bool:
    """Check only the installed receipt and its local paths (no compiler run)."""
    receipt = value if value is not None else _component_status(component_id)
    if not receipt or receipt.get("status") != "INSTALLED":
        return False
    root_value = receipt.get("root")
    if root_value and not Path(str(root_value)).expanduser().exists():
        return False
    executables = receipt.get("executables")
    if not isinstance(executables, dict):
        return False
    for executable in executables.values():
        if executable and not Path(str(executable)).expanduser().exists():
            return False
    return True


@contextlib.contextmanager
def _component_transaction(component_id: str, action: str, target: Path):
    """Record a short, independently resumable component operation.

    A cancelled/interrupted component is left explicitly resumable.  Other
    components may already be committed; callers can invoke ``resume`` to
    continue only the incomplete units.
    """
    _begin_transaction(component_id, action, target)
    try:
        yield
    except KeyboardInterrupt as exc:
        _finish_transaction(component_id, "CANCELLED", error=type(exc).__name__)
        _remove_incomplete_target(target, component_id)
        raise DependencyError(
            "DEPENDENCY_INSTALL_CANCELLED",
            f"{component_id} installation was cancelled; run install/resume to continue",
        ) from exc
    except Exception as exc:
        _finish_transaction(component_id, "FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    else:
        _finish_transaction(component_id, "COMMITTED")


def _remove_incomplete_target(target: Path, component_id: str) -> None:
    """Remove a target only when its receipt is not a valid committed unit."""
    if _component_ready(component_id):
        return
    try:
        allowed_root = (dependency_root() / "installed").resolve()
        target_resolved = target.resolve()
        target_resolved.relative_to(allowed_root)
    except (OSError, ValueError):
        # Existing host tools and the core runtime are user-owned paths.  A
        # cancelled registration must never remove those paths.
        return
    try:
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists() and not target.is_symlink():
            target.unlink()
    except OSError:
        # The transaction remains CANCELLED/FAILED and the next ``install``
        # reports the remaining path; a cleanup failure is not hidden.
        pass


def _idempotent_component(component_id: str, receipt: dict[str, Any]) -> dict[str, Any]:
    transaction = _finish_transaction(
        component_id, "COMMITTED", action="install", idempotent=True,
        target=receipt.get("root"), reason="already installed",
    )
    return {**receipt, "idempotent": True, "transaction": transaction}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DependencyError("DEPENDENCY_METADATA_MISSING", f"missing metadata: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise DependencyError("DEPENDENCY_METADATA_INVALID", f"invalid metadata {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DependencyError("DEPENDENCY_METADATA_INVALID", f"metadata is not an object: {path}")
    return value


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _receipt(kind: str, value: dict[str, Any]) -> Path:
    root = dependency_root() / "receipts"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = root / f"{stamp}-{kind}-{uuid.uuid4().hex[:8]}.json"
    _atomic_json(path, {"schema_version": 1, "kind": kind, "recorded_at": _now(), **value})
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _payload_records() -> dict[str, dict[str, Any]]:
    if not PAYLOAD_MANIFEST_PATH.is_file():
        return {}
    manifest = _load_json(PAYLOAD_MANIFEST_PATH)
    records = manifest.get("payloads")
    if not isinstance(records, list):
        raise DependencyError("DEPENDENCY_METADATA_INVALID", "payload manifest has no payloads array")
    return {str(item.get("name")): item for item in records if isinstance(item, dict)}


def _verified_payload(name: str) -> Path:
    record = _payload_records().get(name)
    if not record:
        raise DependencyError("DEPENDENCY_PAYLOAD_MISSING", f"unregistered payload: {name}")
    path = PLUGIN_ROOT / "assets" / "payloads" / name
    if not path.is_file():
        raise DependencyError("DEPENDENCY_PAYLOAD_MISSING", f"missing bundled payload: {path}")
    actual_size = path.stat().st_size
    actual_hash = _sha256(path)
    if actual_size != int(record.get("bytes", -1)) or actual_hash.casefold() != str(record.get("sha256", "")).casefold():
        raise DependencyError("DEPENDENCY_PAYLOAD_HASH_MISMATCH", f"payload integrity check failed: {name}")
    return path


def _component_receipt(component_id: str) -> Path:
    return dependency_root() / "components" / f"{component_id}.json"


def _component_status(component_id: str) -> dict[str, Any] | None:
    path = _component_receipt(component_id)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _internal_tool_environment() -> dict[str, str]:
    """Keep dependency probes independent of ambient host routing/config."""
    environment = network_environment(proxy=None)
    environment.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    })
    return environment


def _run_version(executable: Path, *arguments: str, cwd: Path | None = None, timeout: int = 30) -> str | None:
    try:
        completed = subprocess.run(
            [str(executable), *arguments], cwd=cwd, text=True, capture_output=True,
            timeout=timeout, check=False, env=_internal_tool_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return (completed.stdout or completed.stderr or "").strip().splitlines()[0] if (completed.stdout or completed.stderr) else "PASS"


def _validate_lean_runtime(runtime: Path) -> bool:
    toolchain = runtime / "lean-toolchain"
    manifest_path = runtime / "lake-manifest.json"
    if not toolchain.is_file() or toolchain.read_text(encoding="utf-8-sig").strip() != LEAN_TOOLCHAIN:
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return False
    mathlib = next((item for item in manifest.get("packages", []) if item.get("name") == "mathlib"), None)
    return bool(mathlib and mathlib.get("inputRev") == MATHLIB_TAG and mathlib.get("rev") == MATHLIB_COMMIT)


def detect_existing(component_id: str) -> dict[str, Any]:
    if component_id == "portable-git":
        executable = shutil.which("git")
        path = Path(executable).resolve() if executable else None
        return {"available": bool(path), "executables": {"git": str(path)} if path else {}, "version": "detected; verify on selection"}
    if component_id == "tex-basic":
        detected: dict[str, str] = {}
        for name in ("pdflatex", "xelatex", "lualatex", "latexmk"):
            executable = shutil.which(name)
            if executable:
                detected[name] = str(Path(executable).resolve())
        return {"available": "pdflatex" in detected, "executables": detected, "version": "detected; verify on selection"}
    if component_id == "lean-mathlib":
        candidates = []
        configured = os.environ.get("RESEARCH_GUARD_LEAN_RUNTIME")
        if configured:
            candidates.append(Path(configured).expanduser().resolve())
        # Resolve the fallback through the same explicit Research Guard home
        # used by receipts/installers.  Never make the current host user's home
        # win over a user-selected RESEARCH_GUARD_HOME.
        candidates.append(_home() / "lean-audit-runtime" / "v4.33.0")
        runtime = next((path for path in candidates if _validate_lean_runtime(path)), None)
        executable = shutil.which("lake")
        lake = Path(executable).resolve() if executable else None
        return {
            "available": bool(runtime and lake),
            "executables": {"lake": str(lake), "runtime_root": str(runtime)} if runtime and lake else {},
            "version": "Lean 4.33.0 plus pinned Mathlib manifest; verify on selection" if runtime and lake else None,
            "toolchain": LEAN_TOOLCHAIN if runtime else None,
            "mathlib_tag": MATHLIB_TAG if runtime else None,
            "mathlib_commit": MATHLIB_COMMIT if runtime else None,
        }
    return {"available": False, "executables": {}, "version": None}


def _decision() -> dict[str, Any] | None:
    path = dependency_root() / "selection.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _component_definition(component_id: str) -> dict[str, Any]:
    catalog = _load_json(CATALOG_PATH)
    for component in catalog.get("components", []):
        if isinstance(component, dict) and str(component.get("id")) == component_id:
            return dict(component)
    raise DependencyError("DEPENDENCY_UNKNOWN", f"unknown component: {component_id}")


def component_need(component_id: str) -> dict[str, Any]:
    """Return a read-only, machine-actionable decision for one capability dependency."""
    component = _component_definition(component_id)
    decision = _decision() or {}
    selected = set(decision.get("selected", []))
    declined = set(decision.get("declined", []))
    receipt = _component_status(component_id)
    installed = bool(receipt and receipt.get("status") == "INSTALLED")
    if component.get("required"):
        status = "AVAILABLE" if installed else "MISSING_REQUIRED"
    elif installed and component_id in selected:
        status = "AVAILABLE"
    elif component_id in selected:
        status = "INSTALL_INCOMPLETE"
    elif component_id in declined:
        status = "DEGRADED"
    else:
        status = "USER_DECISION_REQUIRED"
    detected = detect_existing(component_id) if component_id in OPTIONAL_IDS else {
        "available": False, "executables": {}, "version": None,
    }
    download_min = int(component.get("download_bytes_min", component.get("download_bytes", 0)))
    download_max = int(component.get("download_bytes_max", component.get("download_bytes", 0)))
    install_min = int(component.get("installed_bytes_min", 0))
    install_max = int(component.get("installed_bytes_max", 0))
    choices: list[dict[str, Any]] = []
    if component_id in OPTIONAL_IDS and status != "AVAILABLE":
        if detected.get("available"):
            choices.append({
                "id": "reuse_existing", "download_bytes": 0,
                "command": f"dependency_manager.py select --existing {component_id} --confirmed-by-user",
            })
        if os.name == "nt":
            choices.append({
                "id": "install", "download_bytes_min": download_min,
                "download_bytes_max": download_max,
                "command": f"dependency_manager.py select --install {component_id} --confirmed-by-user",
            })
        else:
            choices.append({
                "id": "install_system_then_reuse", "download_bytes_min": download_min,
                "download_bytes_max": download_max,
                "command": f"Install {component_id} with the host package manager, then run dependency_manager.py select --existing {component_id} --confirmed-by-user",
                "automatic_install": False,
            })
        choices.append({
            "id": "not_now", "download_bytes": 0,
            "command": f"dependency_manager.py not-now {component_id} --confirmed-by-user",
        })
    prerequisite = None
    if component_id == "lean-mathlib" and not (
        (_component_status("portable-git") or {}).get("status") == "INSTALLED"
    ):
        prerequisite = {
            "component": "portable-git",
            "reason": "the fixed Lean/Mathlib installer requires a registered Git client",
            "next_action": "resolve portable-git first, then request lean-mathlib again",
        }
    return {
        "schema_version": 1,
        "component": component_id,
        "label": component.get("label"),
        "status": status,
        "features": component.get("features", []),
        "detected_existing": detected,
        "download_bytes_min": download_min,
        "download_bytes_max": download_max,
        "installed_bytes_min": install_min,
        "installed_bytes_max": install_max,
        "network_route": component.get("network_route", "none"),
        "choices": choices,
        "prerequisite": prerequisite,
        "degradation": component.get("degradation"),
        "installed_receipt": receipt,
        "prompt_user": status == "USER_DECISION_REQUIRED",
        "may_continue_degraded": status == "DEGRADED",
    }


def inventory() -> dict[str, Any]:
    catalog = _load_json(CATALOG_PATH)
    decision = _decision()
    decision_ready = bool(decision and decision.get("status") == "DECIDED")
    selected = set(decision.get("selected", [])) if decision else set()
    declined = set(decision.get("declined", [])) if decision else set()
    payloads = _payload_records()
    components = []
    for component in catalog.get("components", []):
        if not isinstance(component, dict):
            continue
        item = dict(component)
        item_id = str(item.get("id"))
        bundled_bytes = 0
        missing_payloads = []
        for payload_name in item.get("payloads", []):
            record = payloads.get(str(payload_name))
            if record:
                bundled_bytes += int(record.get("bytes", 0))
            else:
                missing_payloads.append(str(payload_name))
        status = _component_status(item_id)
        detected = detect_existing(item_id) if not item.get("required") else {"available": False, "executables": {}, "version": None}
        item.update({
            "bundled_bytes": bundled_bytes,
            "missing_payloads": missing_payloads,
            "selected": bool(item.get("required")) or item_id in selected,
            "declined": item_id in declined,
            "installed": bool(status and status.get("status") == "INSTALLED"),
            "installed_receipt": status,
            "detected_existing": detected,
        })
        components.append(item)
    return {
        "schema_version": 1,
        "status": "READY" if decision_ready else (
            "CORE_READY_OPTIONALS_ON_DEMAND" if decision is None else "DEPENDENCY_INSTALL_INCOMPLETE"
        ),
        "first_load_pending": not decision_ready,
        "core_work_blocked": False,
        "optional_selection_mode": "on-demand",
        "state_root": str(dependency_root()),
        "core_features": catalog.get("core_features", []),
        "components": components,
        "required_component_ids": ["core-runtime"],
        "actionable_component_ids": sorted(OPTIONAL_IDS),
        "informational_component_ids": sorted(INFORMATIONAL_IDS),
        "commands": {
            "inspect_one": "dependency_manager.py need COMPONENT_ID",
            "reuse_detected": "dependency_manager.py select --existing tex-basic --existing lean-mathlib --confirmed-by-user",
            "install_bundled": "dependency_manager.py select --install portable-git --install tex-basic --confirmed-by-user",
            "install_or_update": "dependency_manager.py install --install COMPONENT_ID --confirmed-by-user (update is an alias)",
            "resume": "dependency_manager.py resume",
            "cancel": "dependency_manager.py cancel",
            "clean": "dependency_manager.py clean [--project-root PATH]",
            "hard_clean": "dependency_manager.py hard-clean [--project-root PATH]",
            "decline_one": "dependency_manager.py not-now COMPONENT_ID --confirmed-by-user",
            "decline_all_optional": "dependency_manager.py acknowledge-none --confirmed-by-user",
            "show_again": "dependency_manager.py inventory",
        },
    }


def _write_component(
    component_id: str, root: Path, executables: dict[str, str], *, source_mode: str = "installed",
    detected_version: str | None = None,
) -> dict[str, Any]:
    value = {
        "schema_version": 1,
        "component": component_id,
        "status": "INSTALLED",
        "installed_at": _now(),
        "root": str(root.resolve()),
        "executables": executables,
        "source_mode": source_mode,
    }
    if detected_version:
        value["detected_version"] = detected_version
    _atomic_json(_component_receipt(component_id), value)
    _receipt(f"component-{source_mode}-registered", value)
    return value


def register_core(runtime_root: Path) -> dict[str, Any]:
    candidates = [
        runtime_root / "python.exe",
        runtime_root / "Scripts" / "python.exe",
        runtime_root / "bin" / "python",
    ]
    python = next((candidate for candidate in candidates if candidate.is_file()), None)
    if python is None:
        raise DependencyError("DEPENDENCY_MISSING", f"Python runtime is missing below: {runtime_root}")
    previous = _component_status("core-runtime")
    if _component_ready("core-runtime", previous) and Path(str(previous.get("root"))).resolve() == runtime_root.resolve():
        return _idempotent_component("core-runtime", previous)
    with _component_transaction("core-runtime", "register", runtime_root):
        return _write_component("core-runtime", runtime_root, {"python": str(python.resolve())})


def _install_zip_component_impl(component_id: str, payload_name: str, executable_relative: str) -> dict[str, Any]:
    payload = _verified_payload(payload_name)
    destination = dependency_root() / "installed" / component_id
    staging_parent = dependency_root() / "install-staging"
    staging_parent.mkdir(parents=True, exist_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f"{_safe_name(component_id)}-", dir=staging_parent))
    try:
        with zipfile.ZipFile(payload) as archive:
            archive.extractall(staging)
    except (OSError, zipfile.BadZipFile) as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise DependencyError("DEPENDENCY_INSTALL_FAILED", f"could not extract {payload_name}: {exc}") from exc
    executable = staging / Path(executable_relative)
    if not executable.is_file():
        shutil.rmtree(staging, ignore_errors=True)
        raise DependencyError("DEPENDENCY_INSTALL_FAILED", f"expected executable is absent after install: {executable}")
    completed = subprocess.run(
        [str(executable), "--version"], text=True, capture_output=True,
        timeout=30, check=False, env=_internal_tool_environment(),
    )
    if completed.returncode != 0:
        shutil.rmtree(staging, ignore_errors=True)
        raise DependencyError("DEPENDENCY_INSTALL_FAILED", f"installed executable failed smoke test: {executable}")
    backup = staging_parent / f"{_safe_name(component_id)}-backup-{uuid.uuid4().hex[:8]}"
    committed = False
    try:
        if destination.exists():
            os.replace(destination, backup)
        os.replace(staging, destination)
        executable = destination / Path(executable_relative)
        result = _write_component(component_id, destination, {"git": str(executable.resolve())})
        committed = True
        return result
    except Exception as exc:
        # If receipt persistence failed after the staged tree was swapped in,
        # remove that incomplete tree before restoring the previous one.  This
        # keeps the component receipt and its target path consistent for the
        # next short/resumable transaction.
        if not committed and destination.exists():
            try:
                if destination.is_dir() and not destination.is_symlink():
                    shutil.rmtree(destination, ignore_errors=True)
                elif not destination.is_symlink():
                    destination.unlink()
            except OSError:
                pass
        if backup.exists() and not destination.exists():
            try:
                os.replace(backup, destination)
            except OSError:
                pass
        if isinstance(exc, DependencyError):
            raise
        raise DependencyError("DEPENDENCY_INSTALL_FAILED", f"could not commit {component_id}: {exc}") from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if committed or not destination.exists():
            shutil.rmtree(backup, ignore_errors=True)


def _install_zip_component(component_id: str, payload_name: str, executable_relative: str) -> dict[str, Any]:
    previous = _component_status(component_id)
    if _component_ready(component_id, previous):
        return _idempotent_component(component_id, previous)
    destination = dependency_root() / "installed" / component_id
    with _component_transaction(component_id, "install", destination):
        return _install_zip_component_impl(component_id, payload_name, executable_relative)


def _install_tex_impl() -> dict[str, Any]:
    installer = _verified_payload("miktex-portable.exe")
    destination = dependency_root() / "installed" / "tex-basic"
    staging_parent = dependency_root() / "install-staging"
    staging_parent.mkdir(parents=True, exist_ok=True)
    staging = staging_parent / f"tex-basic-{uuid.uuid4().hex[:8]}"
    staging.mkdir(parents=True, exist_ok=False)
    local_installer = staging / "miktex-portable.exe"
    shutil.copy2(installer, local_installer)
    command = [
        str(local_installer), "--unattended", "--portable", "--no-registry",
        "--auto-install=no", "--paper-size=A4",
    ]
    try:
        completed = run_managed(command, cwd=staging, timeout=1800)
    except ResourceGuardError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise DependencyError("RESOURCE_GUARD_BLOCKED", str(exc)) from exc
    candidates = list(staging.rglob("pdflatex.exe"))
    if completed.returncode != 0 or not candidates:
        detail = (completed.stderr or completed.stdout or "pdflatex.exe was not created").strip()[-2000:]
        shutil.rmtree(staging, ignore_errors=True)
        raise DependencyError("DEPENDENCY_INSTALL_FAILED", f"MiKTeX portable installation failed: {detail}")
    relative_pdflatex = candidates[0].relative_to(staging)
    local_installer.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="research-guard-tex-install-smoke-") as temporary:
        smoke_root = Path(temporary)
        smoke_tex = smoke_root / "smoke.tex"
        smoke_tex.write_text("\\documentclass{article}\\begin{document}Research Guard\\end{document}\n", encoding="ascii")
        try:
            smoke = run_managed(
                [str(staging / relative_pdflatex), "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", smoke_tex.name],
                cwd=smoke_root, timeout=180,
            )
        except ResourceGuardError as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise DependencyError("RESOURCE_GUARD_BLOCKED", str(exc)) from exc
        if smoke.returncode != 0 or not (smoke_root / "smoke.pdf").is_file():
            detail = (smoke.stderr or smoke.stdout or "smoke.pdf was not created").strip()[-2000:]
            shutil.rmtree(staging, ignore_errors=True)
            raise DependencyError("DEPENDENCY_INSTALL_FAILED", f"installed MiKTeX failed a real PDF compile: {detail}")
    backup = staging_parent / f"tex-basic-backup-{uuid.uuid4().hex[:8]}"
    try:
        if destination.exists():
            os.replace(destination, backup)
        os.replace(staging, destination)
    except OSError as exc:
        if backup.exists() and not destination.exists():
            os.replace(backup, destination)
        shutil.rmtree(staging, ignore_errors=True)
        raise DependencyError("DEPENDENCY_INSTALL_FAILED", f"could not commit portable MiKTeX: {exc}") from exc
    finally:
        shutil.rmtree(backup, ignore_errors=True)
    pdflatex = destination / relative_pdflatex
    return _write_component("tex-basic", destination, {"pdflatex": str(pdflatex.resolve())})


def _install_tex() -> dict[str, Any]:
    previous = _component_status("tex-basic")
    if _component_ready("tex-basic", previous):
        return _idempotent_component("tex-basic", previous)
    destination = dependency_root() / "installed" / "tex-basic"
    with _component_transaction("tex-basic", "install", destination):
        return _install_tex_impl()


def _install_lean_impl() -> dict[str, Any]:
    git_status = _component_status("portable-git")
    if not git_status or git_status.get("status") != "INSTALLED":
        raise DependencyError(
            "DEPENDENCY_PREREQUISITE_MISSING",
            "lean-mathlib installation requires the selected portable-git component to finish first",
        )
    script = PLUGIN_ROOT / "scripts" / "install_lean_mathlib.ps1"
    if not script.is_file():
        raise DependencyError("DEPENDENCY_INSTALL_FAILED", f"Lean installer is absent: {script}")
    destination = dependency_root() / "installed" / "lean-mathlib"
    # Resolve the host tool from PATH first.  Do not embed a Windows system
    # directory: a copied installation must follow the invoking host's PATH or
    # its explicit SystemRoot setting.
    powershell_value = shutil.which("pwsh") or shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell_value:
        system_root = os.environ.get("SystemRoot", "").strip()
        if system_root:
            candidate = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            if candidate.is_file():
                powershell_value = str(candidate)
    if not powershell_value:
        raise DependencyError("DEPENDENCY_INSTALL_FAILED", "Lean/Mathlib installation requires pwsh or powershell.exe on PATH (or an explicit SystemRoot).")
    powershell = Path(powershell_value)
    try:
        completed = run_managed(
            [str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
             "-Destination", str(destination), "-GitExe", str(git_status["executables"]["git"])],
            timeout=7200,
        )
    except ResourceGuardError as exc:
        raise DependencyError("RESOURCE_GUARD_BLOCKED", str(exc)) from exc
    receipt_path = destination / "research-guard-lean-runtime.json"
    if completed.returncode != 0 or not receipt_path.is_file():
        detail = (completed.stderr or completed.stdout or "runtime receipt was not created").strip()[-3000:]
        raise DependencyError("DEPENDENCY_INSTALL_FAILED", f"Lean/Mathlib installation failed: {detail}")
    receipt = _load_json(receipt_path)
    lake = Path(str(receipt.get("lake", "")))
    runtime = Path(str(receipt.get("runtime_root", "")))
    if not lake.is_file() or not runtime.is_dir():
        raise DependencyError("DEPENDENCY_INSTALL_FAILED", "Lean installer receipt points to missing paths")
    return _write_component("lean-mathlib", destination, {"lake": str(lake.resolve()), "runtime_root": str(runtime.resolve())})


def _install_lean() -> dict[str, Any]:
    previous = _component_status("lean-mathlib")
    if _component_ready("lean-mathlib", previous):
        return _idempotent_component("lean-mathlib", previous)
    destination = dependency_root() / "installed" / "lean-mathlib"
    with _component_transaction("lean-mathlib", "install", destination):
        return _install_lean_impl()


def install(component_id: str) -> dict[str, Any]:
    if os.name != "nt":
        raise DependencyError(
            "DEPENDENCY_PLATFORM_INSTALL_UNAVAILABLE",
            "Automatic optional-component installation currently uses audited Windows payloads only. "
            "Install the dependency with the host package manager, then explicitly select reuse_existing; "
            "or choose not_now for the documented degradation.",
        )
    if component_id == "portable-git":
        return _install_zip_component(component_id, "mingit.zip", "cmd/git.exe")
    if component_id == "tex-basic":
        return _install_tex()
    if component_id == "lean-mathlib":
        return _install_lean()
    raise DependencyError("DEPENDENCY_UNKNOWN", f"unknown optional component: {component_id}")


def _register_existing_impl(component_id: str) -> dict[str, Any]:
    detected = detect_existing(component_id)
    if not detected.get("available"):
        raise DependencyError("DEPENDENCY_EXISTING_INVALID", f"no compatible existing environment was detected for {component_id}")
    executables = dict(detected["executables"])
    if component_id == "tex-basic":
        try:
            require_start_headroom()
        except ResourceGuardError as exc:
            raise DependencyError("RESOURCE_GUARD_BLOCKED", str(exc)) from exc
        with tempfile.TemporaryDirectory(prefix="research-guard-tex-smoke-") as temporary:
            root = Path(temporary)
            tex = root / "smoke.tex"
            tex.write_text("\\documentclass{article}\\begin{document}Research Guard\\end{document}\n", encoding="ascii")
            try:
                completed = run_managed(
                    [executables["pdflatex"], "-interaction=nonstopmode", "-halt-on-error", tex.name],
                    cwd=root, timeout=120,
                )
            except ResourceGuardError as exc:
                raise DependencyError("RESOURCE_GUARD_BLOCKED", str(exc)) from exc
            if completed.returncode != 0 or not (root / "smoke.pdf").is_file():
                raise DependencyError("DEPENDENCY_EXISTING_INVALID", "detected TeX failed a real PDF compile smoke")
        root = Path(executables["pdflatex"]).parent
    elif component_id == "lean-mathlib":
        try:
            require_start_headroom()
        except ResourceGuardError as exc:
            raise DependencyError("RESOURCE_GUARD_BLOCKED", str(exc)) from exc
        root = Path(executables["runtime_root"])
        with tempfile.TemporaryDirectory(prefix="research-guard-lean-smoke-") as temporary:
            lean_file = Path(temporary) / "Smoke.lean"
            lean_file.write_text(
                "import Mathlib\nset_option autoImplicit false\nexample (x : Nat) : x = x := by rfl\n",
                encoding="utf-8",
            )
            try:
                from resource_guard import run_managed_lean
                completed = run_managed_lean(
                    [executables["lake"], "env", "lean", str(lean_file)], cwd=root, timeout=360,
                )
            except ResourceGuardError as exc:
                raise DependencyError("RESOURCE_GUARD_BLOCKED", str(exc)) from exc
            if completed.returncode != 0:
                raise DependencyError("DEPENDENCY_EXISTING_INVALID", "detected Lean/Mathlib failed a real import Mathlib compile smoke")
    else:
        root = Path(next(iter(executables.values()))).parent
    return _write_component(
        component_id, root, executables, source_mode="existing",
        detected_version=str(detected.get("version") or "verified on selection"),
    )


def register_existing(component_id: str) -> dict[str, Any]:
    previous = _component_status(component_id)
    if _component_ready(component_id, previous):
        return _idempotent_component(component_id, previous)
    target = Path(str((previous or {}).get("root") or dependency_root() / "installed" / component_id))
    with _component_transaction(component_id, "register-existing", target):
        return _register_existing_impl(component_id)


def decide(install_ids: list[str], existing_ids: list[str]) -> dict[str, Any]:
    overlap = sorted(set(install_ids) & set(existing_ids))
    if overlap:
        raise DependencyError("DEPENDENCY_SELECTION_CONFLICT", f"choose existing or install, not both: {overlap}")
    prior = _decision() or {}
    prior_selected = list(prior.get("selected", [])) if prior.get("status") in {
        "DECIDED", "INSTALLING", "INSTALL_FAILED", "INTERRUPTED", "CANCELLED",
    } else []
    selected = list(dict.fromkeys([*prior_selected, *existing_ids, *install_ids]))
    selected_modes = dict(prior.get("selected_modes", {})) if isinstance(prior.get("selected_modes"), dict) else {}
    selected_modes.update({component_id: "existing" for component_id in existing_ids})
    selected_modes.update({component_id: "install" for component_id in install_ids})
    informational = sorted(set(selected) & INFORMATIONAL_IDS)
    if informational:
        raise DependencyError(
            "DEPENDENCY_EXTERNAL_SELECTION",
            f"external adapters are inventory-only and cannot be installed by this manager: {informational}",
        )
    unknown = sorted(set(selected) - OPTIONAL_IDS)
    if unknown:
        raise DependencyError("DEPENDENCY_UNKNOWN", f"unknown component ids: {unknown}")
    if "lean-mathlib" in install_ids and "portable-git" not in selected:
        raise DependencyError(
            "DEPENDENCY_PREREQUISITE_NOT_SELECTED",
            "installing lean-mathlib requires portable-git in the same explicit selection",
        )
    install_ids = sorted(install_ids, key=lambda item: (item != "portable-git", item))
    staged = {
        "schema_version": 1,
        "status": "INSTALLING",
        "decided_at": _now(),
        "selected": selected,
        "declined": sorted(OPTIONAL_IDS - set(selected)),
        "selected_modes": selected_modes,
    }
    _atomic_json(dependency_root() / "selection.json", staged)
    installed = []
    try:
        for component_id in existing_ids:
            installed.append(register_existing(component_id))
        for component_id in install_ids:
            installed.append(install(component_id))
    except KeyboardInterrupt as exc:
        interrupted = dict(staged)
        interrupted["status"] = "INTERRUPTED"
        interrupted["interrupted_at"] = _now()
        interrupted["error"] = type(exc).__name__
        _atomic_json(dependency_root() / "selection.json", interrupted)
        _receipt("selection-install-interrupted", interrupted)
        raise DependencyError(
            "DEPENDENCY_INSTALL_CANCELLED",
            "dependency installation was interrupted; run install --resume to continue",
        ) from exc
    except DependencyError as exc:
        failed = dict(staged)
        failed["status"] = "CANCELLED" if exc.code == "DEPENDENCY_INSTALL_CANCELLED" else "INSTALL_FAILED"
        failed["failed_at"] = _now()
        failed["error"] = exc.code
        _atomic_json(dependency_root() / "selection.json", failed)
        _receipt("selection-install-cancelled" if exc.code == "DEPENDENCY_INSTALL_CANCELLED" else "selection-install-failed", failed)
        raise
    except Exception as exc:
        failed = dict(staged)
        failed["status"] = "INSTALL_FAILED"
        failed["failed_at"] = _now()
        failed["error"] = f"{type(exc).__name__}: {exc}"
        _atomic_json(dependency_root() / "selection.json", failed)
        _receipt("selection-install-failed", failed)
        raise
    value = {
        "schema_version": 1,
        "status": "DECIDED",
        "decided_at": _now(),
        "selected": selected,
        "declined": sorted(OPTIONAL_IDS - set(selected)),
        "selected_modes": selected_modes,
    }
    _atomic_json(dependency_root() / "selection.json", value)
    receipt = _receipt("selection", value)
    return {"status": "READY", "decision": value, "installed": installed, "receipt": str(receipt)}


def resume_install() -> dict[str, Any]:
    """Resume only incomplete component units from the last selection."""
    prior = _decision()
    if not prior:
        return {"status": "NOTHING_TO_RESUME", "reason": "no saved dependency selection"}
    if prior.get("status") == "DECIDED":
        return {"status": "READY", "decision": prior, "installed": [], "resumed": False}
    selected = [str(item) for item in prior.get("selected", [])]
    modes = prior.get("selected_modes") if isinstance(prior.get("selected_modes"), dict) else {}
    existing = [item for item in selected if modes.get(item) == "existing"]
    install_ids = [item for item in selected if modes.get(item, "install") == "install"]
    if not selected:
        return decline_all()
    result = decide(install_ids, existing)
    result["resumed"] = True
    return result


def cancel_install() -> dict[str, Any]:
    """Cancel active component units and preserve a resumable selection."""
    root = dependency_root()
    cancelled: list[str] = []
    transaction_root = root / TRANSACTION_DIRECTORY
    if transaction_root.is_dir():
        for path in transaction_root.glob("*.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict) and value.get("status") == "IN_PROGRESS":
                component_id = str(value.get("component") or path.stem)
                _finish_transaction(component_id, "CANCELLED", reason="user requested cancellation")
                target_value = value.get("target")
                if target_value:
                    _remove_incomplete_target(Path(str(target_value)), component_id)
                cancelled.append(component_id)
    staging = root / "install-staging"
    removed_bytes = 0
    if staging.is_dir():
        removed_bytes = _path_size(staging)
        shutil.rmtree(staging, ignore_errors=True)
    prior = _decision() or {}
    if prior.get("status") in {"INSTALLING", "INSTALL_FAILED", "INTERRUPTED"}:
        value = {
            **prior,
            "status": "CANCELLED",
            "cancelled_at": _now(),
        }
        _atomic_json(root / "selection.json", value)
    return {
        "status": "CANCELLED",
        "cancelled_components": sorted(cancelled),
        "removed_staging_bytes": removed_bytes,
        "selection": _decision(),
    }


def decline(component_id: str) -> dict[str, Any]:
    if component_id not in OPTIONAL_IDS:
        raise DependencyError("DEPENDENCY_UNKNOWN", f"unknown optional component: {component_id}")
    prior = _decision() or {}
    selected = set(prior.get("selected", []))
    selected.discard(component_id)
    declined = set(prior.get("declined", []))
    declined.add(component_id)
    value = {
        "schema_version": 1,
        "status": "DECIDED",
        "decided_at": _now(),
        "selected": sorted(selected),
        "declined": sorted(declined),
    }
    _atomic_json(dependency_root() / "selection.json", value)
    receipt = _receipt("component-not-now", {"component": component_id, "decision": value})
    guidance = component_need(component_id)
    return {**guidance, "decision_receipt": str(receipt)}


def decline_all() -> dict[str, Any]:
    value = {
        "schema_version": 1,
        "status": "DECIDED",
        "decided_at": _now(),
        "selected": [],
        "declined": sorted(OPTIONAL_IDS),
    }
    _atomic_json(dependency_root() / "selection.json", value)
    receipt = _receipt("all-optional-not-now", {"decision": value})
    return {"status": "READY", "decision": value, "installed": [], "receipt": str(receipt)}


def require(component_id: str) -> dict[str, Any]:
    guidance = component_need(component_id)
    decision = _decision()
    if guidance["status"] == "USER_DECISION_REQUIRED":
        raise DependencyError(
            "DEPENDENCY_USER_DECISION_REQUIRED",
            json.dumps(guidance, ensure_ascii=False, sort_keys=True),
        )
    if guidance["status"] == "DEGRADED":
        raise DependencyError(
            "DEPENDENCY_DECLINED",
            json.dumps(guidance, ensure_ascii=False, sort_keys=True),
        )
    if guidance["status"] == "MISSING_REQUIRED":
        raise DependencyError("DEPENDENCY_MISSING", f"required component is not installed: {component_id}")
    if guidance["status"] == "INSTALL_INCOMPLETE":
        raise DependencyError("DEPENDENCY_INSTALL_INCOMPLETE", json.dumps(guidance, ensure_ascii=False, sort_keys=True))
    if component_id == "core-runtime":
        status = _component_status(component_id)
        if not status or status.get("status") != "INSTALLED":
            raise DependencyError("DEPENDENCY_MISSING", f"required component is not installed: {component_id}")
        return status
    if decision is None and component_id != "core-runtime":
        raise DependencyError("DEPENDENCY_USER_DECISION_REQUIRED", json.dumps(guidance, ensure_ascii=False, sort_keys=True))
    if decision.get("status") != "DECIDED":
        raise DependencyError("DEPENDENCY_INSTALL_INCOMPLETE", "the selected dependency installation did not complete")
    selected = set(decision.get("selected", []))
    if component_id not in selected and component_id != "core-runtime":
        raise DependencyError("DEPENDENCY_NOT_SELECTED", f"optional component was not selected: {component_id}")
    status = _component_status(component_id)
    if not status or status.get("status") != "INSTALLED":
        raise DependencyError("DEPENDENCY_MISSING", f"selected component is not installed: {component_id}")
    return status


def _path_size(path: Path) -> int:
    """Best-effort byte count that does not follow symlinks/reparse points."""
    try:
        if path.is_symlink():
            return 0
        if path.is_file():
            return int(path.stat().st_size)
        if not path.is_dir():
            return 0
    except OSError:
        return 0
    total = 0
    try:
        for child in path.iterdir():
            total += _path_size(child)
    except OSError:
        pass
    return total


def _clean_candidates(base: Path, *, hard: bool, home_scope: bool) -> list[Path]:
    """Collect explicitly generated paths below one state root.

    The collector never treats arbitrary user files as cache.  Durable state
    JSON, receipts outside the dependency transaction area, and installed
    dependency components are retained.
    """
    if not base.is_dir():
        return []
    candidates: list[Path] = []

    def walk(directory: Path) -> None:
        try:
            children = list(directory.iterdir())
        except OSError:
            return
        for child in children:
            try:
                if child.is_symlink():
                    continue
                name = child.name.casefold()
                if child.is_dir():
                    names = set(_CLEAN_DIRECTORY_NAMES)
                    if hard:
                        names.update(_HARD_HOME_DIRECTORY_NAMES if home_scope else _HARD_PROJECT_DIRECTORY_NAMES)
                    # The user home contains the bundled Python/Lean trees.
                    # They are durable installation payloads and can be very
                    # large, so do not recursively inspect arbitrary siblings.
                    if home_scope and directory == base and name not in {
                        "dependencies", *names,
                    }:
                        continue
                    if home_scope and directory == base / "dependencies" and name not in names:
                        continue
                    # dependencies/installed contains user-selected tools and
                    # is always durable.  Only its generated subtrees are walked.
                    if home_scope and directory == base and name == "dependencies":
                        walk(child)
                        continue
                    if home_scope and directory == base / "dependencies" and name == "installed":
                        continue
                    if name in names or (hard and home_scope and name in _HARD_HOME_DIRECTORY_NAMES):
                        candidates.append(child)
                        continue
                    walk(child)
                elif child.is_file() and (
                    name.endswith(tuple(_CLEAN_FILE_SUFFIXES))
                    or name.startswith(".research-guard-install-")
                ):
                    candidates.append(child)
            except OSError:
                continue

    walk(base)
    # Ensure parent directories are removed only once; this also makes an
    # interrupted run safe to resume without touching already removed children.
    unique = {path.resolve(): path for path in candidates}
    return sorted(unique.values(), key=lambda item: (len(item.parts), str(item).casefold()))


def _project_build_candidates(project_root: Path) -> list[Path]:
    """Return only known disposable build-check artifacts below a project.

    Release archives and arbitrary project files are durable by default.  The
    development builders use the ``_devcheck-`` prefix for their temporary
    smoke archives, so a normal clean can reclaim those without guessing from
    file size or recursively deleting a user's ``dist`` directory.
    """
    candidates: list[Path] = []
    for directory_name in ("dist", "build"):
        directory = project_root / directory_name
        if not directory.is_dir():
            continue
        try:
            children = list(directory.iterdir())
        except OSError:
            continue
        for child in children:
            try:
                if child.is_symlink():
                    continue
                name = child.name.casefold()
                if name.startswith(("_devcheck-", ".research-guard-")) or name.endswith(tuple(_CLEAN_FILE_SUFFIXES)):
                    candidates.append(child)
            except OSError:
                continue
    return candidates


def clean_state(
    project_root: str | os.PathLike[str] | None = None,
    *,
    home: str | os.PathLike[str] | None = None,
    hard: bool = False,
    dry_run: bool = False,
    cancel: bool = False,
) -> dict[str, Any]:
    """Remove reproducible session/cache paths and report every action.

    ``clean`` keeps project state and installed dependencies.  ``hard`` adds
    generated evidence runs/builds and dependency receipts/transaction logs,
    while still retaining ``components/installed`` and selection metadata.
    Each candidate is one short deletion unit; a partial run can be repeated
    safely and reports failures instead of hiding them.
    """
    home_path = Path(home).expanduser().resolve() if home else _home().resolve()
    project_path = Path(project_root).expanduser().resolve() if project_root else None
    roots: list[tuple[Path, bool]] = [(home_path, True)]
    if project_path:
        roots.append((project_path / ".research-guard", False))
    candidates: list[Path] = []
    for root, home_scope in roots:
        candidates.extend(_clean_candidates(root, hard=hard, home_scope=home_scope))
    if project_path:
        candidates.extend(_project_build_candidates(project_path))
    # A redirected install may leave its short-lived staging sibling in the
    # selected user root.  It is safe to remove only the known prefix.
    user_root = home_path.parent
    if user_root.is_dir():
        for item in user_root.glob(".research-guard-install-*"):
            if item.is_dir() or item.is_file():
                candidates.append(item)
    unique = {path.resolve(): path for path in candidates}
    candidates = sorted(unique.values(), key=lambda item: (len(item.parts), str(item).casefold()))
    state_path = home_path / "cleanup-state.json"
    state: dict[str, Any] = {
        "schema_version": 1,
        "mode": "hard" if hard else "clean",
        "project_root": str(project_path) if project_path else None,
        "started_at": _now(),
        "completed": [],
    }
    if state_path.is_file():
        try:
            previous = json.loads(state_path.read_text(encoding="utf-8"))
            if (
                isinstance(previous, dict)
                and previous.get("mode") == state["mode"]
                and previous.get("project_root") == state["project_root"]
            ):
                state.update(previous)
        except (OSError, json.JSONDecodeError):
            pass
    completed = set(str(item) for item in state.get("completed", []))
    actions: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    released = 0
    interrupted = False
    for path in candidates:
        resolved = str(path.resolve())
        if resolved in completed:
            continue
        size = _path_size(path)
        action = {"path": resolved, "bytes": size, "status": "PENDING"}
        if cancel:
            action["status"] = "CANCELLED"
            actions.append(action)
            break
        if dry_run:
            action["status"] = "WOULD_REMOVE"
            actions.append(action)
            continue
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            elif path.exists() and not path.is_symlink():
                path.unlink()
            action["status"] = "REMOVED"
            released += size
            completed.add(resolved)
            state["completed"] = sorted(completed)
            state["updated_at"] = _now()
            _atomic_json(state_path, state)
        except KeyboardInterrupt:
            action["status"] = "CANCELLED"
            interrupted = True
            actions.append(action)
            break
        except OSError as exc:
            action["status"] = "FAILED"
            action["error"] = f"{type(exc).__name__}: {exc}"
            failures.append(action)
        actions.append(action)
    if cancel or interrupted:
        status = "CANCELLED"
    elif failures:
        status = "PARTIAL"
    elif dry_run:
        status = "DRY_RUN"
    else:
        status = "CLEANED"
    state.update({"status": status, "finished_at": _now(), "completed": sorted(completed)})
    if not dry_run:
        _atomic_json(state_path, state)
    return {
        "status": status,
        "mode": "hard" if hard else "clean",
        "project_root": str(project_path) if project_path else None,
        "candidates": len(candidates),
        "actions": actions,
        "removed": [item for item in actions if item["status"] == "REMOVED"],
        "failed": failures,
        "bytes_released": released,
        "resumable": bool(failures or status == "CANCELLED"),
        "state": str(state_path),
    }


def clean(
    project_root: str | os.PathLike[str] | None = None,
    *,
    home: str | os.PathLike[str] | None = None,
    dry_run: bool = False,
    cancel: bool = False,
) -> dict[str, Any]:
    """Named convenience entry point for the normal maintenance pass."""
    return clean_state(project_root, home=home, hard=False, dry_run=dry_run, cancel=cancel)


def hard_clean(
    project_root: str | os.PathLike[str] | None = None,
    *,
    home: str | os.PathLike[str] | None = None,
    dry_run: bool = False,
    cancel: bool = False,
) -> dict[str, Any]:
    """Named convenience entry point for removing all generated session data."""
    return clean_state(project_root, home=home, hard=True, dry_run=dry_run, cancel=cancel)


def _print_human(value: dict[str, Any]) -> None:
    print(f"Research Guard dependency status: {value['status']}")
    print("\nCore feature list:")
    for feature in value["core_features"]:
        print(f"  - {feature}")
    print("\nComponents:")
    for item in value["components"]:
        download_min = item.get("download_bytes_min", item.get("download_bytes", 0))
        download_max = item.get("download_bytes_max", item.get("download_bytes", 0))
        install_min = item.get("installed_bytes_min", 0)
        install_max = item.get("installed_bytes_max", 0)
        print(
            f"  {item['id']}: bundled={item['bundled_bytes'] / 1048576:.1f} MiB; "
            f"download={download_min / 1048576:.1f}-{download_max / 1048576:.1f} MiB; "
            f"installed={install_min / 1073741824:.2f}-{install_max / 1073741824:.2f} GiB; "
            f"selected={item['selected']}; installed={item['installed']}"
        )
        print(f"    features: {', '.join(item.get('features', []))}")
        print(f"    network: {item.get('network_route', 'none')}")
    if value["first_load_pending"]:
        print("\nCore work is ready. Optional components are resolved only when a requested feature needs one.")
        print("Ask then; do not choose or download for the user.")
        print("To inspect one feature dependency: dependency_manager.py need ID")
        print("To reuse detected environments after user choice: dependency_manager.py select --existing ID [--existing ID] --confirmed-by-user")
        print("To install choices after user choice: dependency_manager.py select --install ID [--install ID] --confirmed-by-user")
        print("To continue with the bounded degradation: dependency_manager.py not-now ID --confirmed-by-user")
        print("To decline all optional components: dependency_manager.py acknowledge-none --confirmed-by-user")


def main() -> int:
    parser = argparse.ArgumentParser(description="Research Guard dependency selection and capability gate")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inventory_parser = subparsers.add_parser("inventory")
    inventory_parser.add_argument("--json", action="store_true")
    select_parser = subparsers.add_parser("select")
    install_parser = subparsers.add_parser("install", aliases=["update"])
    for selection_parser in (select_parser, install_parser):
        selection_parser.add_argument("--existing", action="append", default=[])
        selection_parser.add_argument("--install", action="append", default=[])
        selection_parser.add_argument("--confirmed-by-user", action="store_true")
        selection_parser.add_argument("--resume", action="store_true", help="resume saved incomplete component units")
        selection_parser.add_argument("--cancel", action="store_true", help="cancel active units and retain a resumable selection")
    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--confirmed-by-user", action="store_true", help="retained for command symmetry")
    cancel_parser = subparsers.add_parser("cancel")
    cancel_parser.add_argument("--confirmed-by-user", action="store_true", help="retained for command symmetry")
    none_parser = subparsers.add_parser("acknowledge-none")
    none_parser.add_argument("--confirmed-by-user", action="store_true")
    need_parser = subparsers.add_parser("need")
    need_parser.add_argument("component")
    not_now_parser = subparsers.add_parser("not-now")
    not_now_parser.add_argument("component")
    not_now_parser.add_argument("--confirmed-by-user", action="store_true")
    require_parser = subparsers.add_parser("require")
    require_parser.add_argument("component")
    core_parser = subparsers.add_parser("register-core")
    core_parser.add_argument("runtime_root", type=Path)
    for name, hard in (("clean", False), ("hard-clean", True)):
        clean_parser = subparsers.add_parser(name)
        clean_parser.add_argument("--project-root")
        clean_parser.add_argument("--home")
        clean_parser.add_argument("--dry-run", action="store_true")
        clean_parser.add_argument("--cancel", action="store_true")
    arguments = parser.parse_args()
    try:
        if arguments.command == "inventory":
            value = inventory()
            if arguments.json:
                print(json.dumps(value, ensure_ascii=False, sort_keys=True))
            else:
                _print_human(value)
        elif arguments.command in {"select", "install", "update"}:
            if arguments.cancel:
                print(json.dumps(cancel_install(), ensure_ascii=False, indent=2))
                return 0
            if arguments.resume:
                print(json.dumps(resume_install(), ensure_ascii=False, indent=2))
                return 0
            if not arguments.confirmed_by_user:
                raise DependencyError("DEPENDENCY_USER_SELECTION_REQUIRED", "select requires --confirmed-by-user after the user chooses")
            if not arguments.existing and not arguments.install:
                raise DependencyError("DEPENDENCY_SELECTION_EMPTY", "select requires --existing ID or --install ID")
            value = decide(arguments.install, arguments.existing)
            value["operation"] = "install"
            value["requested_command"] = arguments.command
            print(json.dumps(value, ensure_ascii=False, indent=2))
        elif arguments.command == "resume":
            print(json.dumps(resume_install(), ensure_ascii=False, indent=2))
        elif arguments.command == "cancel":
            print(json.dumps(cancel_install(), ensure_ascii=False, indent=2))
        elif arguments.command == "acknowledge-none":
            if not arguments.confirmed_by_user:
                raise DependencyError("DEPENDENCY_USER_SELECTION_REQUIRED", "acknowledge-none requires --confirmed-by-user")
            print(json.dumps(decline_all(), ensure_ascii=False, indent=2))
        elif arguments.command == "need":
            print(json.dumps(component_need(arguments.component), ensure_ascii=False, indent=2))
        elif arguments.command == "not-now":
            if not arguments.confirmed_by_user:
                raise DependencyError("DEPENDENCY_USER_SELECTION_REQUIRED", "not-now requires --confirmed-by-user after the user chooses")
            print(json.dumps(decline(arguments.component), ensure_ascii=False, indent=2))
        elif arguments.command == "require":
            print(json.dumps(require(arguments.component), ensure_ascii=False, sort_keys=True))
        elif arguments.command == "register-core":
            print(json.dumps(register_core(arguments.runtime_root), ensure_ascii=False, sort_keys=True))
        elif arguments.command in {"clean", "hard-clean"}:
            print(json.dumps(clean_state(
                arguments.project_root, home=arguments.home, hard=arguments.command == "hard-clean",
                dry_run=arguments.dry_run, cancel=arguments.cancel,
            ), ensure_ascii=False, indent=2))
    except DependencyError as exc:
        print(json.dumps({"status": "ERROR", "error": exc.code, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 86
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
