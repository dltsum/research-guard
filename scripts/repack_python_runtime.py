from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resource_guard import GIB, ResourceGuardError, memory_snapshot, require_start_headroom


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _keep(name: str) -> bool:
    parts = [part.casefold() for part in Path(name).parts]
    if any(part in {"__pycache__", ".pytest_cache", "tests", "test"} for part in parts):
        return False
    return not name.casefold().endswith((".pyc", ".pyo"))


def repack(source: Path, output: Path) -> dict[str, object]:
    try:
        require_start_headroom()
    except ResourceGuardError as exc:
        raise RuntimeError(str(exc)) from exc
    source = source.resolve()
    output = output.resolve()
    if source == output:
        raise RuntimeError("source and output must differ")
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    kept = skipped = 0
    uncompressed_bytes = 0
    try:
        with zipfile.ZipFile(source) as incoming, zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True
        ) as outgoing:
            for item in incoming.infolist():
                if item.is_dir() or not _keep(item.filename):
                    skipped += 1
                    continue
                available = int(memory_snapshot()["available_physical_bytes"])
                if available < int(1.5 * GIB):
                    raise RuntimeError(
                        f"RESOURCE_LOW_WATER_ABORT: available RAM is {available / GIB:.2f} GiB during runtime repack"
                    )
                copied = zipfile.ZipInfo(item.filename, date_time=item.date_time)
                copied.external_attr = item.external_attr
                copied.create_system = item.create_system
                copied.compress_type = zipfile.ZIP_STORED if item.filename.casefold().endswith((".zip", ".pyd", ".dll", ".exe")) else zipfile.ZIP_DEFLATED
                with incoming.open(item) as reader, outgoing.open(copied, "w", force_zip64=True) as writer:
                    shutil.copyfileobj(reader, writer, length=1024 * 1024)
                kept += 1
                uncompressed_bytes += item.file_size
        if zipfile.ZipFile(temporary).testzip() is not None:
            raise RuntimeError("repacked Python runtime failed ZIP CRC validation")
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {
        "status": "PASS", "path": str(output), "entries": kept, "skipped": skipped,
        "bytes": output.stat().st_size, "uncompressed_bytes": uncompressed_bytes,
        "sha256": _sha256(output),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Stream-filter the bundled Python runtime")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(repack(arguments.source, arguments.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
