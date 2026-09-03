from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


PACKAGE_ROOT = Path(__file__).resolve().parent
MANIFEST_NAME = "ADDON_MANIFEST.json"
ADDON_ID = "research-guard-ui-addon"
BASE_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[+.-]|$)")
SAFE_ADDON_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[+.-][0-9A-Za-z.-]+)?$")
_AMBIENT_NETWORK_VARIABLES = frozenset({
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_TRUSTED_HOST", "PIP_NO_INDEX",
    "PIP_FIND_LINKS", "PIP_CONFIG_FILE", "PIP_CERT", "PIP_CLIENT_CERT",
    "UV_INDEX_URL", "UV_EXTRA_INDEX_URL", "UV_FIND_LINKS",
})


class InstallError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_and_verify_manifest(root: Path = PACKAGE_ROOT) -> dict[str, Any]:
    path = root / MANIFEST_NAME
    if not path.is_file():
        raise InstallError("ADDON_MANIFEST.json is required; install from the checksum-verified UI add-on archive.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"The UI add-on manifest is unreadable: {exc}") from exc
    if value.get("schema_version") != 1 or value.get("addon_id") != ADDON_ID:
        raise InstallError("The UI add-on manifest identity is invalid.")
    if value.get("core_archive_embedded") is not False or value.get("package", {}).get("core_archive_embedded") is not False:
        raise InstallError("The optional UI manifest must not embed the Research Guard core archive.")
    if value.get("security", {}).get("server_transcript_persistence") is not False:
        raise InstallError("The optional UI manifest security boundary is invalid.")
    if value.get("security", {}).get("mcp_approval_scope") != (
        "automatic approval is limited to the locally installed Research Guard MCP server; "
        "all other configured MCP servers are disabled for the turn"
    ):
        raise InstallError("The optional UI manifest MCP approval boundary is invalid.")
    files = value.get("files")
    if not isinstance(files, list) or not files:
        raise InstallError("The UI add-on manifest has no files.")
    seen: set[str] = set()
    seen_casefolded: set[str] = set()
    for record in files:
        if not isinstance(record, dict):
            raise InstallError("The UI add-on manifest contains an invalid file record.")
        relative = str(record.get("path") or "")
        pure = PurePosixPath(relative)
        folded = relative.casefold()
        if (
            not relative or "\\" in relative or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in pure.parts)
            or relative in seen or folded in seen_casefolded
        ):
            raise InstallError(f"Unsafe or duplicate UI add-on path: {relative!r}")
        seen.add(relative)
        seen_casefolded.add(folded)
        source = root.joinpath(*pure.parts)
        if source.is_symlink() or not source.is_file() or source.stat().st_size != int(record.get("bytes", -1)):
            raise InstallError(f"UI add-on file size mismatch: {relative}")
        if _sha256(source) != record.get("sha256"):
            raise InstallError(f"UI add-on SHA-256 mismatch: {relative}")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    expected = {*seen, MANIFEST_NAME}
    if actual != expected:
        raise InstallError(
            f"UI add-on file set mismatch: extra={sorted(actual - expected)}, missing={sorted(expected - actual)}"
        )
    return value


def _run(command: Sequence[str], *, timeout: float = 30) -> subprocess.CompletedProcess[str]:
    environment = {key: value for key, value in os.environ.items() if key not in _AMBIENT_NETWORK_VARIABLES}
    try:
        return subprocess.run(
            list(command), text=True, capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False, cwd=PACKAGE_ROOT, env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError(f"Local preflight failed: {exc}") from exc


def _python_candidates() -> list[Path]:
    home = Path(os.environ.get("RESEARCH_GUARD_HOME", Path.home() / ".research-guard")).expanduser()
    configured = os.environ.get("RESEARCH_GUARD_PYTHON", "").strip()
    values = [
        Path(configured).expanduser() if configured else None,
        home / "runtime" / "python" / "python.exe",
        home / "runtime" / "python" / "Scripts" / "python.exe",
        home / "runtime" / "python" / "bin" / "python",
        Path(sys.executable),
    ]
    result: list[Path] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        key = os.path.normcase(str(value.resolve(strict=False)))
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _select_runtime(candidates: Sequence[Path] | None = None) -> Path:
    for candidate in candidates or _python_candidates():
        if not candidate.is_file():
            continue
        completed = _run([
            str(candidate), "-X", "utf8", "-c",
            "import json,psutil,sys; print(json.dumps({'version':list(sys.version_info[:3]),'psutil':psutil.__version__}))",
        ], timeout=20)
        if completed.returncode != 0:
            continue
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError:
            continue
        if tuple(value.get("version") or ()) >= (3, 11, 0):
            return candidate.resolve()
    raise InstallError(
        "No Python 3.11+ runtime with psutil was found. Install Research Guard core first or set RESEARCH_GUARD_PYTHON."
    )


def _probe_codex_plugin(command_prefix: Sequence[str] | None = None) -> dict[str, Any]:
    if command_prefix is None:
        executable = shutil.which("codex")
        if not executable:
            raise InstallError("Codex CLI is not on PATH; install Codex before the optional UI add-on.")
        command_prefix = (executable,)
    completed = _run([*command_prefix, "plugin", "list", "--json"], timeout=30)
    if completed.returncode != 0:
        raise InstallError("Codex could not list installed plugins.")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise InstallError("Codex returned invalid plugin metadata.") from exc
    records = [
        item for item in value.get("installed", [])
        if isinstance(item, dict) and item.get("name") == "research-guard"
        and item.get("installed") is True and item.get("enabled") is True
    ]
    if len(records) != 1:
        raise InstallError("Research Guard must be installed and enabled before this optional UI add-on.")
    matched = BASE_VERSION.match(str(records[0].get("version") or ""))
    if not matched or tuple(int(part) for part in matched.groups()) < (0, 7, 0):
        raise InstallError("Research Console requires Research Guard 0.7.0 or newer.")
    try:
        plugin_root = Path(str((records[0].get("source") or {}).get("path") or "")).expanduser().resolve(strict=True)
        declaration = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))
        servers = declaration["mcpServers"]
        server = servers["research-guard"]
        if set(servers) != {"research-guard"} or set(server) != {"command", "args"}:
            raise ValueError("unexpected MCP declaration shape")
        mcp_command = str(server["command"]).replace("${PLUGIN_ROOT}", str(plugin_root))
        mcp_args = [str(item).replace("${PLUGIN_ROOT}", str(plugin_root)) for item in server["args"]]
        if not mcp_command or not all(mcp_args) or "${" in mcp_command or any("${" in item for item in mcp_args):
            raise ValueError("unresolved MCP declaration")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InstallError("The installed Research Guard MCP declaration is invalid.") from exc
    mcp = _run([
        *command_prefix,
        "-c", "mcp_servers.research-guard.command=" + json.dumps(mcp_command),
        "-c", "mcp_servers.research-guard.args=" + json.dumps(mcp_args),
        "-c", "mcp_servers.research-guard.required=true",
        "-c", 'mcp_servers.research-guard.default_tools_approval_mode="approve"',
        "mcp", "list", "--json",
    ], timeout=30)
    if mcp.returncode != 0:
        raise InstallError("Codex does not support the required Research Guard per-server MCP controls.")
    try:
        mcp_inventory = json.loads(mcp.stdout)
    except json.JSONDecodeError as exc:
        raise InstallError("Codex returned invalid MCP metadata.") from exc
    active = [
        item for item in mcp_inventory
        if isinstance(item, dict) and item.get("name") == "research-guard" and item.get("enabled") is True
    ] if isinstance(mcp_inventory, list) else []
    if len(active) != 1:
        raise InstallError("The installed Research Guard MCP server is not enabled.")
    return {
        "plugin_id": records[0].get("pluginId"),
        "version": records[0].get("version"),
        "mcp": "required-local-server-controls-ready",
    }


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def install(
    *,
    package_root: Path = PACKAGE_ROOT,
    target_root: Path | None = None,
    command_prefix: Sequence[str] | None = None,
    runtime_candidates: Sequence[Path] | None = None,
    workspace: Path | None = None,
) -> dict[str, Any]:
    manifest = _load_and_verify_manifest(package_root)
    plugin = _probe_codex_plugin(command_prefix)
    runtime = _select_runtime(runtime_candidates)
    guard_home = Path(os.environ.get("RESEARCH_GUARD_HOME", Path.home() / ".research-guard")).expanduser().resolve()
    base = (target_root or guard_home / "addons" / "research-console").expanduser().resolve()
    version = str(manifest.get("version") or "")
    if not SAFE_ADDON_VERSION.fullmatch(version):
        raise InstallError("The UI add-on version is missing or unsafe.")
    target = base / version
    manifest_hash = _sha256(package_root / MANIFEST_NAME)

    if target.exists():
        existing = target / MANIFEST_NAME
        if not existing.is_file() or _sha256(existing) != manifest_hash:
            raise InstallError(f"An altered installation already exists at {target}; it was not overwritten.")
        _load_and_verify_manifest(target)
        status = "ALREADY_INSTALLED"
    else:
        base.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{version}-", dir=base))
        try:
            for record in manifest["files"]:
                pure = PurePosixPath(str(record["path"]))
                source = package_root.joinpath(*pure.parts)
                destination = staging.joinpath(*pure.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            shutil.copy2(package_root / MANIFEST_NAME, staging / MANIFEST_NAME)
            _load_and_verify_manifest(staging)
            os.replace(staging, target)
        finally:
            if staging.exists() and staging.parent == base:
                shutil.rmtree(staging, ignore_errors=True)
        status = "INSTALLED"

    pointer = {
        "schema_version": 1,
        "addon_id": ADDON_ID,
        "version": version,
        "relative_install": version,
        "manifest_sha256": manifest_hash,
        "python": str(runtime),
        "plugin": plugin,
    }
    _atomic_json(base / "current.json", pointer)
    command = [str(runtime), "-X", "utf8", str(target / "launch.py")]
    if workspace is not None:
        command.extend(("--workspace", str(workspace.expanduser().resolve())))
    return {
        "status": status,
        "addon_id": ADDON_ID,
        "version": version,
        "target": str(target),
        "manifest_sha256": manifest_hash,
        "runtime": str(runtime),
        "research_guard": plugin,
        "launch_command": command,
        "next_step": "Add --workspace <project> (or set RESEARCH_GUARD_WORKSPACE), run launch_command, and open the printed localhost URL manually; no optional dependency was downloaded.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the optional Research Guard visual UI add-on per user.")
    parser.add_argument("--target-root", type=Path, help="Override the per-user versioned add-on directory")
    parser.add_argument("--workspace", type=Path, help="Explicit initial research workspace for the generated launch command")
    arguments = parser.parse_args()
    try:
        receipt = install(target_root=arguments.target_root, workspace=arguments.workspace)
    except InstallError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
