from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ADDON_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ADDON_ROOT.parents[1]
SOURCE_CONTRACT = ADDON_ROOT / "addon-source.json"
PRIVATE_PATH = re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s\"'<>]+", re.I)
TEXT_SUFFIXES = {".css", ".html", ".js", ".json", ".md", ".py", ".svg", ".txt"}
FIXED_ZIP_TIME = (2026, 8, 23, 0, 0, 0)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_files() -> list[tuple[Path, PurePosixPath]]:
    files: list[tuple[Path, PurePosixPath]] = []
    for name in ("addon-source.json", "install.py", "launch.py"):
        files.append((ADDON_ROOT / name, PurePosixPath(name)))
    for path in sorted((ADDON_ROOT / "research_console").rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix.casefold() not in {".pyc", ".pyo"}:
            relative = PurePosixPath(path.relative_to(ADDON_ROOT).as_posix())
            files.append((path, relative))
    files.extend([
        (REPOSITORY_ROOT / "docs" / "RESEARCH_CONSOLE_UI.md", PurePosixPath("README.md")),
        (REPOSITORY_ROOT / "docs" / "RESEARCH_CONSOLE_UI.zh-CN.md", PurePosixPath("README.zh-CN.md")),
        (REPOSITORY_ROOT / "LICENSE", PurePosixPath("LICENSE")),
    ])
    return files


def _read_checked(path: Path, relative: PurePosixPath) -> bytes:
    if not path.is_file():
        raise RuntimeError(f"required UI add-on source is missing: {path}")
    value = path.read_bytes()
    if path.suffix.casefold() in TEXT_SUFFIXES or path.name == "LICENSE":
        text = value.decode("utf-8", errors="strict")
        if PRIVATE_PATH.search(text):
            raise RuntimeError(f"private absolute path found in UI add-on file: {relative}")
    return value


def _write_member(archive: zipfile.ZipFile, name: str, value: bytes) -> None:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    archive.writestr(info, value, compress_type=zipfile.ZIP_STORED)


def build(output: Path, checksum_output: Path | None = None) -> dict[str, Any]:
    contract = json.loads(SOURCE_CONTRACT.read_text(encoding="utf-8"))
    if contract.get("schema_version") != 1 or contract.get("addon_id") != "research-guard-ui-addon":
        raise RuntimeError("UI add-on source contract is invalid")
    package = contract.get("package") or {}
    maximum = int(package.get("maximum_archive_bytes", 0))
    if maximum <= 0:
        raise RuntimeError("UI add-on archive size cap is invalid")

    records: list[dict[str, Any]] = []
    material: list[tuple[PurePosixPath, bytes]] = []
    seen: set[str] = set()
    for source, relative in _source_files():
        name = relative.as_posix()
        if name in seen:
            raise RuntimeError(f"duplicate UI add-on package path: {name}")
        seen.add(name)
        value = _read_checked(source, relative)
        records.append({"path": name, "bytes": len(value), "sha256": _sha256_bytes(value)})
        material.append((relative, value))
    file_set_hash = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest = {
        "schema_version": 1,
        "addon_id": contract["addon_id"],
        "display_name": contract["display_name"],
        "description": contract["description"],
        "version": contract["version"],
        "requires": contract["requires"],
        "runtime": contract["runtime"],
        "security": contract["security"],
        "package": contract["package"],
        "core_archive_embedded": False,
        "files_sha256": file_set_hash,
        "files": records,
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

    output = output.expanduser().resolve()
    if output.suffix.casefold() != ".zip":
        raise RuntimeError("UI add-on output must be a .zip file")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    prefix = "research-guard-ui-addon/"
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for relative, value in material:
                _write_member(archive, prefix + relative.as_posix(), value)
            _write_member(archive, prefix + "ADDON_MANIFEST.json", manifest_bytes)
        if temporary.stat().st_size > maximum:
            raise RuntimeError(f"UI add-on exceeds its {maximum}-byte archive cap")
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()

    archive_hash = _sha256(output)
    if checksum_output is not None:
        checksum_output = checksum_output.expanduser().resolve()
        checksum_output.parent.mkdir(parents=True, exist_ok=True)
        temporary_checksum = checksum_output.with_name(f".{checksum_output.name}.{os.getpid()}.tmp")
        temporary_checksum.write_text(f"{archive_hash}  {output.name}\n", encoding="ascii", newline="\n")
        os.replace(temporary_checksum, checksum_output)
    return {
        "status": "PASS",
        "addon_id": contract["addon_id"],
        "version": contract["version"],
        "path": str(output),
        "bytes": output.stat().st_size,
        "sha256": archive_hash,
        "files": len(records) + 1,
        "core_archive_embedded": False,
        "checksum_path": str(checksum_output) if checksum_output else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the optional cross-platform Research Guard UI add-on.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checksum-output", type=Path)
    arguments = parser.parse_args()
    try:
        receipt = build(arguments.output, arguments.checksum_output)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
