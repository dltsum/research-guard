from __future__ import annotations

import argparse
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


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "assets" / "dependency-catalog.json"
PAYLOAD_MANIFEST_PATH = PLUGIN_ROOT / "assets" / "payload-manifest.json"
OPTIONAL_IDS = {"portable-git", "tex-basic", "lean-mathlib"}
INFORMATIONAL_IDS = {"structured-parser-adapters", "advanced-statistics", "active-review-ui"}
LEAN_TOOLCHAIN = "leanprover/lean4:v4.33.0"
MATHLIB_TAG = "v4.33.0"
MATHLIB_COMMIT = "db584cd6d46c92f209a44c0f1c829460d327499d"


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


def _run_version(executable: Path, *arguments: str, cwd: Path | None = None, timeout: int = 30) -> str | None:
    try:
        completed = subprocess.run(
            [str(executable), *arguments], cwd=cwd, text=True, capture_output=True,
            timeout=timeout, check=False,
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
        candidates.append(Path.home() / ".research-guard" / "lean-audit-runtime" / "v4.33.0")
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
            "FIRST_LOAD_SELECTION_REQUIRED" if decision is None else "DEPENDENCY_INSTALL_INCOMPLETE"
        ),
        "first_load_pending": not decision_ready,
        "state_root": str(dependency_root()),
        "core_features": catalog.get("core_features", []),
        "components": components,
        "required_component_ids": ["core-runtime"],
        "actionable_component_ids": sorted(OPTIONAL_IDS),
        "informational_component_ids": sorted(INFORMATIONAL_IDS),
        "commands": {
            "reuse_detected": "dependency_manager.py select --existing tex-basic --existing lean-mathlib",
            "install_bundled": "dependency_manager.py select --install portable-git --install tex-basic",
            "decline_all_optional": "dependency_manager.py acknowledge-none",
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
    python = runtime_root / "python.exe"
    if not python.is_file():
        raise DependencyError("DEPENDENCY_MISSING", f"bundled Python is missing: {python}")
    return _write_component("core-runtime", runtime_root, {"python": str(python.resolve())})


def _install_zip_component(component_id: str, payload_name: str, executable_relative: str) -> dict[str, Any]:
    payload = _verified_payload(payload_name)
    destination = dependency_root() / "installed" / component_id
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(payload) as archive:
            archive.extractall(destination)
    except (OSError, zipfile.BadZipFile) as exc:
        raise DependencyError("DEPENDENCY_INSTALL_FAILED", f"could not extract {payload_name}: {exc}") from exc
    executable = destination / Path(executable_relative)
    if not executable.is_file():
        raise DependencyError("DEPENDENCY_INSTALL_FAILED", f"expected executable is absent after install: {executable}")
    completed = subprocess.run([str(executable), "--version"], text=True, capture_output=True, timeout=30, check=False)
    if completed.returncode != 0:
        raise DependencyError("DEPENDENCY_INSTALL_FAILED", f"installed executable failed smoke test: {executable}")
    return _write_component(component_id, destination, {"git": str(executable.resolve())})


def _install_tex() -> dict[str, Any]:
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


def _install_lean() -> dict[str, Any]:
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
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
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


def install(component_id: str) -> dict[str, Any]:
    if component_id == "portable-git":
        return _install_zip_component(component_id, "mingit.zip", "cmd/git.exe")
    if component_id == "tex-basic":
        return _install_tex()
    if component_id == "lean-mathlib":
        return _install_lean()
    raise DependencyError("DEPENDENCY_UNKNOWN", f"unknown optional component: {component_id}")


def register_existing(component_id: str) -> dict[str, Any]:
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


def decide(install_ids: list[str], existing_ids: list[str]) -> dict[str, Any]:
    overlap = sorted(set(install_ids) & set(existing_ids))
    if overlap:
        raise DependencyError("DEPENDENCY_SELECTION_CONFLICT", f"choose existing or install, not both: {overlap}")
    selected = list(dict.fromkeys([*existing_ids, *install_ids]))
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
    }
    _atomic_json(dependency_root() / "selection.json", staged)
    installed = []
    try:
        for component_id in existing_ids:
            installed.append(register_existing(component_id))
        for component_id in install_ids:
            installed.append(install(component_id))
    except Exception:
        failed = dict(staged)
        failed["status"] = "INSTALL_FAILED"
        failed["failed_at"] = _now()
        _atomic_json(dependency_root() / "selection.json", failed)
        _receipt("selection-install-failed", failed)
        raise
    value = {
        "schema_version": 1,
        "status": "DECIDED",
        "decided_at": _now(),
        "selected": selected,
        "declined": sorted(OPTIONAL_IDS - set(selected)),
    }
    _atomic_json(dependency_root() / "selection.json", value)
    receipt = _receipt("selection", value)
    return {"status": "READY", "decision": value, "installed": installed, "receipt": str(receipt)}


def require(component_id: str) -> dict[str, Any]:
    decision = _decision()
    if decision is None:
        raise DependencyError("FIRST_LOAD_SELECTION_REQUIRED", "run dependency inventory and ask the user to select optional components")
    if decision.get("status") != "DECIDED":
        raise DependencyError("DEPENDENCY_INSTALL_INCOMPLETE", "the selected dependency installation did not complete")
    selected = set(decision.get("selected", []))
    if component_id not in selected and component_id != "core-runtime":
        raise DependencyError("DEPENDENCY_NOT_SELECTED", f"optional component was not selected: {component_id}")
    status = _component_status(component_id)
    if not status or status.get("status") != "INSTALLED":
        raise DependencyError("DEPENDENCY_MISSING", f"selected component is not installed: {component_id}")
    return status


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
        print("\nAsk the user which optional component IDs to install. Do not choose for them.")
        print("To reuse detected environments: dependency_manager.py select --existing ID [--existing ID]")
        print("To install choices: dependency_manager.py select --install ID [--install ID]")
        print("To decline all optional components: dependency_manager.py acknowledge-none")


def main() -> int:
    parser = argparse.ArgumentParser(description="Research Guard dependency selection and capability gate")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inventory_parser = subparsers.add_parser("inventory")
    inventory_parser.add_argument("--json", action="store_true")
    select_parser = subparsers.add_parser("select")
    select_parser.add_argument("--existing", action="append", default=[])
    select_parser.add_argument("--install", action="append", default=[])
    subparsers.add_parser("acknowledge-none")
    require_parser = subparsers.add_parser("require")
    require_parser.add_argument("component")
    core_parser = subparsers.add_parser("register-core")
    core_parser.add_argument("runtime_root", type=Path)
    arguments = parser.parse_args()
    try:
        if arguments.command == "inventory":
            value = inventory()
            if arguments.json:
                print(json.dumps(value, ensure_ascii=False, sort_keys=True))
            else:
                _print_human(value)
        elif arguments.command == "select":
            if not arguments.existing and not arguments.install:
                raise DependencyError("DEPENDENCY_SELECTION_EMPTY", "select requires --existing ID or --install ID")
            print(json.dumps(decide(arguments.install, arguments.existing), ensure_ascii=False, indent=2))
        elif arguments.command == "acknowledge-none":
            print(json.dumps(decide([], []), ensure_ascii=False, indent=2))
        elif arguments.command == "require":
            print(json.dumps(require(arguments.component), ensure_ascii=False, sort_keys=True))
        elif arguments.command == "register-core":
            print(json.dumps(register_core(arguments.runtime_root), ensure_ascii=False, sort_keys=True))
    except DependencyError as exc:
        print(json.dumps({"status": "ERROR", "error": exc.code, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 86
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
