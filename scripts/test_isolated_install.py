from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from network_config_core import network_environment

try:
    import psutil
except ImportError:
    psutil = None


MAX_ARCHIVE_MEMBERS = 5_000
MAX_UNCOMPRESSED_BYTES = 1024 ** 3
MAX_MANIFEST_BYTES = 8 * 1024 ** 2
SUPPORTED_PLATFORMS = {"windows-x64", "linux-x64", "macos-x64", "macos-arm64"}
WINDOWS_RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


class IsolatedInstallError(RuntimeError):
    pass


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if not members or len(members) > MAX_ARCHIVE_MEMBERS:
        raise IsolatedInstallError(
            f"archive member count must be between 1 and {MAX_ARCHIVE_MEMBERS}: {len(members)}"
        )
    total = 0
    normalized_names: set[str] = set()
    manifest_count = 0
    for member in members:
        name = member.filename
        raw_parts = name.rstrip("/").split("/")
        if (
            not name or "\\" in name or "\x00" in name
            or any(not part or part == "." for part in raw_parts)
        ):
            raise IsolatedInstallError(f"archive member has an unsafe path separator: {name!r}")
        if ".." in raw_parts:
            raise IsolatedInstallError(f"archive member escapes the extraction root: {name!r}")
        for part in raw_parts:
            stem = part.split(".", 1)[0].casefold()
            if (
                ":" in part or part.rstrip(" .") != part or stem in WINDOWS_RESERVED_NAMES
                or any(ord(character) < 32 for character in part)
            ):
                raise IsolatedInstallError(f"archive member is not cross-platform safe: {name!r}")
        relative = PurePosixPath(name)
        windows = PureWindowsPath(name)
        if relative.is_absolute() or windows.is_absolute() or windows.drive or ".." in relative.parts:
            raise IsolatedInstallError(f"archive member escapes the extraction root: {name!r}")
        normalized = unicodedata.normalize("NFC", relative.as_posix().rstrip("/")).casefold()
        if not normalized or normalized in normalized_names:
            raise IsolatedInstallError(f"archive contains a duplicate or empty member path: {name!r}")
        normalized_names.add(normalized)
        unix_mode = (member.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(unix_mode):
            raise IsolatedInstallError(f"archive symlinks are not admitted: {name!r}")
        file_type = stat.S_IFMT(unix_mode)
        if file_type and not (stat.S_ISREG(unix_mode) or stat.S_ISDIR(unix_mode)):
            raise IsolatedInstallError(f"archive contains an unsupported filesystem entry: {name!r}")
        total += member.file_size
        if total > MAX_UNCOMPRESSED_BYTES:
            raise IsolatedInstallError(
                f"archive expands beyond {MAX_UNCOMPRESSED_BYTES} bytes"
            )
        if relative.as_posix() == "research-guard/RELEASE_MANIFEST.json":
            manifest_count += 1
            if member.file_size > MAX_MANIFEST_BYTES:
                raise IsolatedInstallError(f"release manifest exceeds {MAX_MANIFEST_BYTES} bytes")
    if manifest_count != 1:
        raise IsolatedInstallError("archive must contain exactly one research-guard/RELEASE_MANIFEST.json")
    return members


def extract_archive(archive_path: Path, destination: Path) -> dict[str, Any]:
    archive_path = archive_path.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not archive_path.is_file() or archive_path.suffix.casefold() != ".zip":
        raise IsolatedInstallError(f"archive is not a ZIP file: {archive_path}")
    if destination.exists():
        raise IsolatedInstallError(f"extraction destination already exists: {destination}")
    destination.mkdir(parents=True)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = _safe_members(archive)
            for member in members:
                target = destination.joinpath(*PurePosixPath(member.filename).parts).resolve()
                if destination != target and destination not in target.parents:
                    raise IsolatedInstallError(f"archive member escapes the extraction root: {member.filename!r}")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
        manifest_path = destination / "research-guard" / "RELEASE_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("package") != "research-guard" or manifest.get("platform") not in SUPPORTED_PLATFORMS:
            raise IsolatedInstallError("release manifest package or platform is invalid")
        return manifest
    except Exception:
        # Preserve a partially extracted tree as failure evidence. The caller owns cleanup.
        raise


def installed_python(user_root: Path) -> Path:
    runtime = user_root / ".research-guard" / "runtime" / "python"
    candidates = (runtime / "python.exe", runtime / "Scripts" / "python.exe", runtime / "bin" / "python")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise IsolatedInstallError(f"installed Python was not found under {runtime}")


def windows_powershell() -> str:
    for executable in ("pwsh", "powershell.exe"):
        resolved = shutil.which(executable)
        if resolved:
            return resolved
    raise IsolatedInstallError("neither pwsh nor powershell.exe is available")


def _stage_record(completed: Any) -> dict[str, Any]:
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    return {
        "returncode": completed.returncode,
        "stdout_tail": stdout[-4_000:],
        "stderr_tail": stderr[-4_000:],
        "resource_usage": completed.resource_usage,
    }


def _stage_working_set(process_id: int) -> int | None:
    """Observe the tree's RSS; shared pages can appear in several processes."""
    if psutil is None:
        return None
    try:
        parent = psutil.Process(process_id)
        processes = {item.pid: item for item in [parent, *parent.children(recursive=True)]}
    except psutil.Error:
        return 0
    total = 0
    for process in processes.values():
        try:
            total += process.memory_info().rss
        except psutil.Error:
            continue
    return total


def _terminate_stage(process: subprocess.Popen[bytes]) -> None:
    """Stop the installation's own tree on cancellation, never unrelated jobs."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True, timeout=20, check=False,
        )
        if process.poll() is None:
            process.kill()
    else:
        # Popen starts a new session, so this group belongs only to this stage.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=20)


def _run_stage(
    command: list[str], *, cwd: Path, env: dict[str, str], timeout: float,
    max_memory_bytes: int | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Run an actual install stage; only an explicit user budget limits RSS.

    The installation may contain pip and several Python processes at once.
    Their summed RSS is telemetry, not a reason to impose a fixed 448 MiB
    installation requirement. Container/OS limits and actual failures still
    apply, as does the requested per-stage timeout.
    """
    if not math.isfinite(timeout) or timeout <= 0:
        raise IsolatedInstallError("stage timeout must be finite and positive")
    if max_memory_bytes is not None:
        if isinstance(max_memory_bytes, bool) or not isinstance(max_memory_bytes, int) or max_memory_bytes <= 0:
            raise IsolatedInstallError("explicit stage memory budget must be a positive byte count")
        if psutil is None:
            raise IsolatedInstallError("the explicit stage memory budget requires psutil for process-tree observation")
    started = time.monotonic()
    peak_memory: int | None = None
    error: str | None = None
    with tempfile.TemporaryFile("w+b") as stdout_log, tempfile.TemporaryFile("w+b") as stderr_log:
        try:
            process = subprocess.Popen(
                command, cwd=cwd, env=env, stdout=stdout_log, stderr=stderr_log,
                start_new_session=os.name != "nt",
            )
        except OSError as exc:
            raise IsolatedInstallError(f"cannot start isolated stage: {exc}") from exc
        try:
            while process.poll() is None:
                observed = _stage_working_set(process.pid)
                if observed is not None:
                    peak_memory = max(peak_memory or 0, observed)
                if max_memory_bytes is not None and observed is not None and observed > max_memory_bytes:
                    error = (
                        "isolated stage exceeded the explicit user memory budget: "
                        f"observed={observed} bytes, requested={max_memory_bytes} bytes"
                    )
                    _terminate_stage(process)
                    break
                if time.monotonic() - started > timeout:
                    error = f"isolated stage timeout: process tree exceeded {timeout:g} seconds"
                    _terminate_stage(process)
                    break
                time.sleep(0.05)
            process.wait()
        finally:
            if process.poll() is None:
                _terminate_stage(process)
        stdout_log.seek(0)
        stderr_log.seek(0)
        completed = subprocess.CompletedProcess(
            command, process.returncode,
            stdout_log.read().decode("utf-8", errors="replace"),
            stderr_log.read().decode("utf-8", errors="replace"),
        )
    completed.resource_usage = {
        "memory_metric": "sum_process_rss",
        "memory_scope": "spawned_process_tree; shared pages may be counted more than once",
        "peak_worker_bytes": peak_memory,
        "memory_limit_bytes": max_memory_bytes,
        "memory_limit_source": "user" if max_memory_bytes is not None else "none",
        "memory_observation_available": psutil is not None,
        "duration_seconds": time.monotonic() - started,
        "timeout_seconds": timeout,
    }
    record = _stage_record(completed)
    if error or completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "stage failed")[-4_000:]
        failure = IsolatedInstallError(error or f"isolated stage failed with exit code {completed.returncode}: {detail}")
        failure.stage_record = record
        raise failure
    return completed, record


def run_isolated_install(
    archive_path: Path, test_root: Path, *, pip_index_url: str | None = None, timeout: float = 1800,
    max_memory_bytes: int | None = None,
) -> dict[str, Any]:
    archive_path = archive_path.expanduser().resolve()
    test_root = test_root.expanduser().resolve()
    if test_root.exists():
        raise IsolatedInstallError(f"test root must not already exist: {test_root}")
    extraction_root = test_root / "extract"
    user_root = test_root / "user"
    manifest = extract_archive(archive_path, extraction_root)
    package_root = extraction_root / "research-guard"
    user_root.mkdir()
    environment = network_environment(base=dict(os.environ), proxy=None)
    for variable in (
        "RESEARCH_GUARD_FOREIGN_PROXY", "RESEARCH_GUARD_DISABLE_FOREIGN_DIRECT_FALLBACK",
        "RESEARCH_GUARD_PYTHON", "RESEARCH_GUARD_WORKSPACE",
    ):
        environment.pop(variable, None)
    environment.update({
        "RESEARCH_GUARD_INSTALL_USER_ROOT": str(user_root),
        "RESEARCH_GUARD_HOME": str(user_root / ".research-guard"),
        "RESEARCH_GUARD_CODEX_ROOT": str(user_root / ".codex"),
        "CODEX_HOME": str(user_root / ".codex"),
        "PYTHONUTF8": "1",
        "MPLBACKEND": "Agg",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
    })
    if os.name == "nt":
        install_command = [
            windows_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(package_root / "scripts" / "install.ps1"), "-SkipCodexRegistration",
        ]
    else:
        environment["HOME"] = str(user_root)
        environment["PYTHON_BIN"] = sys.executable
        install_command = [
            "sh", str(package_root / "scripts" / "install.sh"),
            "--user-root", str(user_root), "--skip-codex-registration",
        ]
        if pip_index_url:
            install_command.extend(["--pip-index-url", pip_index_url])
    _, install_record = _run_stage(
        install_command, cwd=package_root, env=environment, timeout=timeout,
        max_memory_bytes=max_memory_bytes,
    )
    python = installed_python(user_root)
    verified, verify_record = _run_stage(
        [str(python), "-I", "-X", "utf8", str(package_root / "scripts" / "verify_isolated_install.py"),
         "--user-root", str(user_root)],
        cwd=package_root, env=environment, timeout=timeout, max_memory_bytes=max_memory_bytes,
    )
    try:
        verification = json.loads(verified.stdout)
    except json.JSONDecodeError as exc:
        raise IsolatedInstallError("isolated verifier did not return JSON") from exc
    if verification.get("status") != "PASS":
        raise IsolatedInstallError("isolated verifier did not return PASS")
    return {
        "schema_version": 1,
        "status": "PASS",
        "archive": str(archive_path),
        "manifest_platform": manifest["platform"],
        "test_root": str(test_root),
        "installed_python_layout": python.relative_to(user_root).as_posix(),
        "installation": install_record,
        "verification_stage": verify_record,
        "verification": verification,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean-install and verify one Research Guard migration archive")
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--test-root", required=True, type=Path)
    parser.add_argument("--pip-index-url")
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--max-memory-mib", type=float, help="Optional explicit limit for a stage's summed process RSS; no fixed memory limit by default")
    arguments = parser.parse_args()
    try:
        max_memory_bytes = None
        if arguments.max_memory_mib is not None:
            if not math.isfinite(arguments.max_memory_mib) or arguments.max_memory_mib <= 0:
                raise IsolatedInstallError("--max-memory-mib must be finite and positive")
            max_memory_bytes = int(arguments.max_memory_mib * 1024 ** 2)
        result = run_isolated_install(
            arguments.archive, arguments.test_root,
            pip_index_url=arguments.pip_index_url, timeout=arguments.timeout,
            max_memory_bytes=max_memory_bytes,
        )
    except Exception as exc:
        print(json.dumps({
            "schema_version": 1, "status": "FAIL", "error": type(exc).__name__, "message": str(exc),
            **({"stage_record": exc.stage_record} if hasattr(exc, "stage_record") else {}),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
