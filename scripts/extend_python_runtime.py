from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extend(source: Path, site_packages: Path, output: Path) -> dict[str, object]:
    source, site_packages, output = source.resolve(), site_packages.resolve(), output.resolve()
    if source == output or not source.is_file() or not site_packages.is_dir():
        raise ValueError("source/output must differ and site-packages must exist")
    additions = {
        "flexcache", "flexcache-0.3.dist-info", "flexparser", "flexparser-0.4.dist-info",
        "mpmath", "mpmath-1.3.0.dist-info", "pint", "pint-0.25.3.dist-info",
        "platformdirs", "platformdirs-4.11.2.dist-info", "sympy", "sympy-1.14.0.dist-info",
        "z3", "z3_solver-5.0.0.0.dist-info",
    }
    selected = [path for path in site_packages.rglob("*") if path.is_file() and path.relative_to(site_packages).parts[0] in additions]
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(source) as incoming, zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True,
        ) as outgoing:
            for item in incoming.infolist():
                if item.is_dir():
                    continue
                copied = zipfile.ZipInfo(item.filename, date_time=item.date_time)
                copied.external_attr, copied.create_system = item.external_attr, item.create_system
                copied.compress_type = zipfile.ZIP_STORED if item.filename.casefold().endswith((".pyd", ".dll", ".exe")) else zipfile.ZIP_DEFLATED
                with incoming.open(item) as reader, outgoing.open(copied, "w", force_zip64=True) as writer:
                    shutil.copyfileobj(reader, writer, length=1024 * 1024)
            for path in sorted(selected):
                relative = path.relative_to(site_packages).as_posix()
                arcname = f"Lib/site-packages/{relative}"
                info = zipfile.ZipInfo(arcname, date_time=(2026, 8, 14, 0, 0, 0))
                info.external_attr = 0o644 << 16
                info.compress_type = zipfile.ZIP_STORED if path.suffix.casefold() in {".pyd", ".dll", ".exe"} else zipfile.ZIP_DEFLATED
                with path.open("rb") as reader, outgoing.open(info, "w", force_zip64=True) as writer:
                    shutil.copyfileobj(reader, writer, length=1024 * 1024)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("extended runtime failed ZIP CRC validation")
            names = set(archive.namelist())
            for required in ("Lib/site-packages/sympy/__init__.py", "Lib/site-packages/pint/__init__.py", "Lib/site-packages/z3/__init__.py"):
                if required not in names:
                    raise RuntimeError(f"extended runtime is missing {required}")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {"status": "PASS", "path": str(output), "bytes": output.stat().st_size, "sha256": _sha256(output), "added_files": len(selected)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--site-packages", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(extend(arguments.source, arguments.site_packages, arguments.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
