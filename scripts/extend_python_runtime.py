from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import zipfile
import importlib.metadata
import re
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


DEFAULT_ADDITIONS = ("flexcache", "flexparser", "mpmath", "pint", "platformdirs", "sympy", "z3-solver", "psutil", "PyYAML")


def distribution_files(site_packages: Path, packages: tuple[str, ...]) -> tuple[dict[str, Path], dict[str, str]]:
    """Select installed distribution files without hardcoding versioned directories."""
    normalize = lambda value: re.sub(r"[-_.]+", "-", value).lower()
    available = {normalize(d.metadata["Name"]): d for d in importlib.metadata.distributions(path=[str(site_packages)])}
    files: dict[str, Path] = {}
    versions = {}
    for package in packages:
        distribution = available.get(normalize(package))
        if distribution is None or distribution.files is None:
            raise ValueError(f"required local distribution is unavailable: {package}")
        versions[distribution.metadata["Name"]] = distribution.version
        for relative in distribution.files:
            if relative.is_absolute() or ".." in relative.parts or "__pycache__" in relative.parts or "tests" in relative.parts:
                continue
            path = site_packages / relative
            if path.is_file() and path.suffix not in {".pyc", ".pyo"}:
                files[relative.as_posix()] = path
    return files, versions


def extend(source: Path, site_packages: Path, output: Path, *, packages: tuple[str, ...] = DEFAULT_ADDITIONS) -> dict[str, object]:
    source, site_packages, output = source.resolve(), site_packages.resolve(), output.resolve()
    if source == output or not source.is_file() or not site_packages.is_dir():
        raise ValueError("source/output must differ and site-packages must exist")
    selected, versions = distribution_files(site_packages, packages)
    additions = {relative.split("/", 1)[0] for relative in selected}
    replaced_distributions = {re.sub(r"[-_.]+", "-", package).lower() for package in packages}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(source) as incoming, zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True,
        ) as outgoing:
            for item in incoming.infolist():
                if item.is_dir():
                    continue
                parts = item.filename.split("/")
                if len(parts) >= 3 and parts[:2] == ["Lib", "site-packages"]:
                    top = parts[2]
                    old_distribution = re.sub(r"[-_.]+", "-", re.split(r"-\d", top, maxsplit=1)[0]).lower()
                    if top in additions or (top.endswith(".dist-info") and old_distribution in replaced_distributions):
                        continue
                copied = zipfile.ZipInfo(item.filename, date_time=item.date_time)
                copied.external_attr, copied.create_system = item.external_attr, item.create_system
                copied.compress_type = zipfile.ZIP_STORED if item.filename.casefold().endswith((".pyd", ".dll", ".exe")) else zipfile.ZIP_DEFLATED
                with incoming.open(item) as reader, outgoing.open(copied, "w", force_zip64=True) as writer:
                    shutil.copyfileobj(reader, writer, length=1024 * 1024)
            for relative, path in sorted(selected.items()):
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
            for required in (f"Lib/site-packages/{relative}" for relative in selected):
                if required not in names:
                    raise RuntimeError(f"extended runtime is missing {required}")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {"status": "PASS", "path": str(output), "bytes": output.stat().st_size, "sha256": _sha256(output), "added_files": len(selected), "added_distributions": versions}


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
