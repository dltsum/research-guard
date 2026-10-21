from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resource_guard import (
    RUN_MIN_FREE_BYTES, ResourceGuardError, memory_snapshot,
    require_orchestrator_budget, require_start_headroom, run_managed,
)
from hydrate_release_payloads import PayloadHydrationError, validate_payload_directory


# Development mode inspects the source; release mode creates an ordinary ZIP.
# Neither mode computes source fingerprints or pins local editable files.


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BUILD_MODES = ("release", "development")
ROOT_FILES = {
    ".mcp.json", ".editorconfig", ".gitattributes", ".gitignore",
    "SKILL.md", "README.md", "README.zh-CN.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
    "CONTRIBUTING.md", "SECURITY.md", "GOVERNANCE.md", "SUPPORT.md",
    "CODE_OF_CONDUCT.md", "CITATION.cff", "CHANGELOG.md",
    "requirements-core.txt", "requirements-dev.txt", "REQUIREMENTS.md",
}
ROOT_DIRECTORIES = {".codex-plugin", ".github", "agents", "hooks", "skills", "scripts", "docs", "references", "tests", "assets"}
EXCLUDED_PARTS = {"__pycache__", ".git", ".research-guard", "development", "evals", "snapshots", "quarantine", "admitted"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
UNLICENSED_CACHED_SUFFIXES = {".pdf", ".html"}
PRIVATE_PATH = re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s\"'<>]+", re.I)


def _include(relative: Path) -> bool:
    if not relative.parts:
        return False
    if len(relative.parts) == 1:
        return relative.name in ROOT_FILES
    if relative.parts[0] not in ROOT_DIRECTORIES or any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if relative.suffix.casefold() in EXCLUDED_SUFFIXES:
        return False
    if relative.parts[:2] == ("assets", "venue-evidence"):
        if relative.suffix.casefold() in UNLICENSED_CACHED_SUFFIXES:
            return False
        if "templates" in relative.parts and relative.suffix.casefold() == ".zip":
            return False
    if relative.parts[0] == "scripts" and relative.name == "build_public_package.py":
        return False
    return True


def _check_text(path: Path, relative: Path) -> None:
    if path.suffix.casefold() not in {".py", ".md", ".json", ".yaml", ".yml", ".txt", ".ps1", ".cmd", ".sh"} and path.name not in {"LICENSE", ".mcp.json"}:
        return
    text = path.read_text(encoding="utf-8", errors="strict")
    if PRIVATE_PATH.search(text):
        raise RuntimeError(f"private absolute path found in release file: {relative.as_posix()}")


def _development_receipt(
    files: list[tuple[Path, Path]], platform_target: str,
) -> dict[str, object]:
    """Describe the source tree without copying it or pinning its contents.

    Development builds are intentionally not release artifacts.  In
    particular, no digest is calculated for source files: developers should
    edit the one checked-out tree and rerun the operation.  Release mode below
    remains the only path that emits a ZIP and a file-level manifest.
    """
    return {
        "status": "PASS",
        "mode": "development",
        "platform": platform_target,
        "source_tree": True,
        "archive_created": False,
        "third_party_assets_included": False,
        "files": len(files),
        "source_bytes": sum(path.stat().st_size for path, _ in files),
        "message": "Source tree was inspected in place; edit it directly and rerun.",
    }


def build(
    output: Path | None, platform_target: str, *, mode: str = "release",
) -> dict[str, object]:
    if mode not in BUILD_MODES:
        raise RuntimeError(f"unsupported build mode: {mode!r}")
    try:
        headroom = require_start_headroom()
    except ResourceGuardError as exc:
        raise RuntimeError(str(exc)) from exc
    if mode == "release":
        if output is None:
            raise RuntimeError("output is required for release mode")
        output = output.resolve()
        if output.suffix.casefold() != ".zip":
            raise RuntimeError("output must be a .zip file")
    if mode == "release" and platform_target == "windows-x64":
        try:
            validate_payload_directory(
                PLUGIN_ROOT / "assets" / "payload-manifest.json",
                PLUGIN_ROOT / "assets" / "payloads",
            )
        except PayloadHydrationError as exc:
            raise RuntimeError(
                "WINDOWS_PAYLOAD_PREFLIGHT_FAILED: run scripts/hydrate_release_payloads.py; " + str(exc)
            ) from exc
    files: list[tuple[Path, Path]] = []
    for path in sorted(item for item in PLUGIN_ROOT.rglob("*") if item.is_file()):
        relative = path.relative_to(PLUGIN_ROOT)
        if _include(relative):
            # Exploratory builds never copy third-party payloads.  The release
            # Windows path includes them only after its explicit preflight.
            if (
                (mode == "development" or platform_target != "windows-x64")
                and relative.parts[:2] == ("assets", "payloads")
            ):
                continue
            if mode == "release":
                _check_text(path, relative)
            files.append((path, relative))
    if mode == "development":
        receipt = _development_receipt(files, platform_target)
        receipt["start_memory"] = headroom
        return receipt
    found = {relative for _, relative in files}
    required = {Path(name) for name in (
        "SKILL.md", "LICENSE", ".mcp.json", "scripts/mcp_server.py",
        "scripts/component_install.py", "assets/feature-components.json",
    )}
    missing = sorted(str(path) for path in required - found)
    if missing:
        raise RuntimeError(f"release is missing required files: {missing}")
    manifest_files = [
        {"path": relative.as_posix(), "bytes": source.stat().st_size}
        for source, relative in files
    ]
    manifest = {
        "schema_version": 1,
        "package": "research-guard",
        "variant": "windows-x64-modular" if platform_target == "windows-x64" else f"{platform_target}-venv",
        "platform": platform_target,
        "runtime_delivery": "bundled-python" if platform_target == "windows-x64" else "system-python-venv",
        "optional_downloads_require_user_selection": True,
        "optional_addons_included": [],
        "files": manifest_files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for source, relative in files:
                available = int(memory_snapshot()["available_physical_bytes"])
                if available < RUN_MIN_FREE_BYTES:
                    raise RuntimeError(
                        f"RESOURCE_LOW_WATER_ABORT: available RAM is {available / 1024 ** 2:.0f} MiB during packaging"
                    )
                already_compressed = source.suffix.casefold() in {".zip", ".exe", ".png", ".jpg", ".jpeg", ".pdf"}
                archive.write(
                    source, Path("research-guard") / relative,
                    compress_type=zipfile.ZIP_STORED if already_compressed else zipfile.ZIP_DEFLATED,
                    compresslevel=None if already_compressed else 6,
                )
            archive.writestr(
                "research-guard/RELEASE_MANIFEST.json",
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )
        if temporary.stat().st_size > 1024 ** 3:
            raise RuntimeError(f"modular archive exceeds the 1 GiB cap: {temporary.stat().st_size} bytes")
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {
        "status": "PASS", "path": str(output), "platform": platform_target,
        "runtime_delivery": manifest["runtime_delivery"], "files": len(files) + 1,
        "bytes": output.stat().st_size, "start_memory": headroom,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or inspect the Research Guard modular migration Skill")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--platform", dest="platform_target", required=True,
        choices=("windows-x64", "linux-x64", "macos-x64", "macos-arm64"),
    )
    parser.add_argument(
        "--mode", choices=BUILD_MODES, default="release",
        help="release creates a ZIP; development inspects the current source tree in place",
    )
    parser.add_argument("--bounded-worker", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.mode == "release" and arguments.output is None:
        parser.error("--output is required in release mode")
    if arguments.bounded_worker or os.environ.get("RESEARCH_GUARD_MANAGED_WORKER") == "1":
        print(json.dumps(
            build(arguments.output, arguments.platform_target, mode=arguments.mode),
            ensure_ascii=False, indent=2,
        ))
        return 0
    require_orchestrator_budget()
    command = [
        sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
        "--platform", arguments.platform_target, "--mode", arguments.mode, "--bounded-worker",
    ]
    if arguments.output is not None:
        command.extend(("--output", str(arguments.output)))
    completed = run_managed(
        command, cwd=PLUGIN_ROOT,
        timeout=300 if arguments.mode == "development" else 1800,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.returncode != 0:
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
