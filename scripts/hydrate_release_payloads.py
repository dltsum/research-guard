"""Fetch missing release payloads, or unpack a local release ZIP.

Old digest fields in release metadata are accepted but are not installation
requirements. ZIP reading, safe member names and ordinary download failures
provide the checks needed to use the actual files.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from network_config_core import NetworkConfigError, route_openers

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOOTSTRAP = PLUGIN_ROOT / "assets" / "payload-bootstrap.json"
DEFAULT_PAYLOAD_MANIFEST = PLUGIN_ROOT / "assets" / "payload-manifest.json"
DEFAULT_PAYLOAD_DIRECTORY = PLUGIN_ROOT / "assets" / "payloads"
MAX_MANIFEST_BYTES = 8 * 1024 ** 2
MAX_PAYLOAD_COUNT = 32
MAX_BOOTSTRAP_BYTES = 1024 ** 3


class PayloadHydrationError(RuntimeError):
    pass


def _load_json(path: Path, label: str) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise PayloadHydrationError(f"{label} is missing or too large: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PayloadHydrationError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise PayloadHydrationError(f"{label} must be a JSON object")
    return value


def _expected_payloads(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    payloads = manifest.get("payloads")
    if not isinstance(payloads, list) or not 1 <= len(payloads) <= MAX_PAYLOAD_COUNT:
        raise PayloadHydrationError(f"payload manifest must contain 1-{MAX_PAYLOAD_COUNT} payloads")
    normalized = []
    names: set[str] = set()
    for item in payloads:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name or name in {".", ".."} or Path(name).name != name or any(c in name for c in "/\\:"):
            raise PayloadHydrationError("payload name is not a safe file name")
        if name.casefold() in names:
            raise PayloadHydrationError(f"duplicate payload name: {name}")
        names.add(name.casefold())
        normalized.append({"name": name})
    return normalized


def validate_payload_directory(
    payload_manifest_path: Path = DEFAULT_PAYLOAD_MANIFEST,
    payload_directory: Path = DEFAULT_PAYLOAD_DIRECTORY,
) -> dict[str, Any]:
    """Explicit presence diagnostic; local edits and extra files are allowed."""
    expected = _expected_payloads(_load_json(payload_manifest_path, "payload manifest"))
    directory = payload_directory.expanduser().resolve()
    observed = []
    for item in expected:
        path = directory / item["name"]
        if not path.is_file():
            raise PayloadHydrationError(f"payload is missing: {path}")
        observed.append({"name": item["name"], "path": path.name, "bytes": path.stat().st_size})
    return {"status": "PASS", "payload_count": len(observed),
            "payload_bytes": sum(item["bytes"] for item in observed), "payloads": observed}


def validate_bootstrap_contract(bootstrap_path: Path, payload_manifest_path: Path) -> dict[str, Any]:
    bootstrap = _load_json(bootstrap_path, "payload bootstrap")
    _expected_payloads(_load_json(payload_manifest_path, "payload manifest"))
    url = urllib.parse.urlsplit(str(bootstrap.get("source", "")))
    if url.scheme != "https" or not url.netloc or url.username or url.password:
        raise PayloadHydrationError("payload bootstrap source must be credential-free HTTPS")
    name = bootstrap.get("asset_name")
    if not isinstance(name, str) or not name or Path(name).name != name or any(c in name for c in "/\\:"):
        raise PayloadHydrationError("payload bootstrap asset_name must be a safe file name")
    return bootstrap


def _download_archive(url: str, destination: Path, expected_bytes: int | None = None,
                      expected_sha256: str | None = None) -> str:
    # The old optional digest argument is intentionally ignored for callers
    # loading an older bootstrap. Content-Length detects truncated transfers.
    request = urllib.request.Request(url, headers={"User-Agent": "research-guard-payload-hydrator/2"})
    attempted = []
    last_transport = None
    try:
        routes = tuple(route_openers(url))
    except NetworkConfigError as exc:
        raise PayloadHydrationError(str(exc)) from exc
    for route_name, _proxy, opener in routes:
        attempted.append(route_name)
        received = 0
        try:
            with opener.open(request, timeout=120) as response, destination.open("xb") as output:
                header = response.headers.get("Content-Length")
                length = int(header) if header else None
                while block := response.read(1024 * 1024):
                    received += len(block)
                    if received > MAX_BOOTSTRAP_BYTES:
                        raise PayloadHydrationError("payload download exceeds the 1 GiB limit")
                    output.write(block)
                if length is not None and received != length:
                    raise PayloadHydrationError(f"payload download is truncated: {received}/{length} bytes")
        except urllib.error.HTTPError as exc:
            destination.unlink(missing_ok=True)
            raise PayloadHydrationError(f"payload download failed via {route_name}: HTTP {exc.code}") from exc
        except PayloadHydrationError:
            destination.unlink(missing_ok=True)
            raise
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            last_transport = exc
            destination.unlink(missing_ok=True)
            continue
        return route_name
    raise PayloadHydrationError(f"payload download failed after routes {attempted}: {last_transport}") from last_transport


def hydrate_from_archive(archive_path: Path, bootstrap_path: Path,
                         payload_manifest_path: Path, payload_directory: Path) -> dict[str, Any]:
    bootstrap = validate_bootstrap_contract(bootstrap_path, payload_manifest_path)
    expected = _expected_payloads(_load_json(payload_manifest_path, "payload manifest"))
    archive_path = archive_path.expanduser().resolve()
    payload_directory = payload_directory.expanduser().resolve()
    if not archive_path.is_file():
        raise PayloadHydrationError(f"payload archive is missing: {archive_path}")
    payload_directory.mkdir(parents=True, exist_ok=True)
    temporary_paths = []
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            for item in expected:
                archived = f"research-guard/assets/payloads/{item['name']}"
                matches = [member for member in members if member.filename == archived]
                if len(matches) != 1:
                    raise PayloadHydrationError(f"payload archive must contain exactly one {archived}")
                member = matches[0]
                mode = (member.external_attr >> 16) & 0xFFFF
                if member.is_dir() or stat.S_ISLNK(mode) or member.flag_bits & 1 or member.file_size > MAX_BOOTSTRAP_BYTES:
                    raise PayloadHydrationError(f"payload member is not a supported regular file: {archived}")
                temporary = payload_directory / f".{item['name']}.{os.getpid()}.tmp"
                final = payload_directory / item['name']
                temporary_paths.append((temporary, final))
                with archive.open(member) as source, temporary.open("xb") as output:
                    while block := source.read(1024 * 1024):
                        output.write(block)
        for temporary, final in temporary_paths:
            os.replace(temporary, final)
        return {"schema_version": 1, "source_release": bootstrap.get("release_tag"),
                "source_asset": bootstrap["asset_name"], "source_archive_bytes": archive_path.stat().st_size,
                **validate_payload_directory(payload_manifest_path, payload_directory)}
    except (zipfile.BadZipFile, RuntimeError) as exc:
        if isinstance(exc, PayloadHydrationError):
            raise
        raise PayloadHydrationError(f"payload ZIP cannot be read: {exc}") from exc
    finally:
        for temporary, _ in temporary_paths:
            temporary.unlink(missing_ok=True)


def hydrate(bootstrap_path: Path, payload_manifest_path: Path, payload_directory: Path,
            *, archive_path: Path | None = None, force: bool = False) -> dict[str, Any]:
    if not force and archive_path is None:
        try:
            return {**validate_payload_directory(payload_manifest_path, payload_directory), "reused_payloads": True}
        except PayloadHydrationError:
            pass
    bootstrap = validate_bootstrap_contract(bootstrap_path, payload_manifest_path)
    if archive_path is not None:
        return hydrate_from_archive(archive_path, bootstrap_path, payload_manifest_path, payload_directory)
    with tempfile.TemporaryDirectory(prefix="research-guard-payloads-") as temporary:
        downloaded = Path(temporary) / bootstrap["asset_name"]
        route = _download_archive(bootstrap["source"], downloaded)
        result = hydrate_from_archive(downloaded, bootstrap_path, payload_manifest_path, payload_directory)
        result["network_route"] = route
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch missing Windows payloads or unpack a local release ZIP")
    parser.add_argument("--bootstrap", type=Path, default=DEFAULT_BOOTSTRAP)
    parser.add_argument("--payload-manifest", type=Path, default=DEFAULT_PAYLOAD_MANIFEST)
    parser.add_argument("--payload-directory", type=Path, default=DEFAULT_PAYLOAD_DIRECTORY)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--report", type=Path)
    # Retain old invocation options; ordinary hydration needs no worker wrapper.
    parser.add_argument("--attempt-timeout-seconds", type=float, default=3600, help=argparse.SUPPRESS)
    parser.add_argument("--bounded-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        result = hydrate(args.bootstrap, args.payload_manifest, args.payload_directory,
                         archive_path=args.archive, force=args.force)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (PayloadHydrationError, OSError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
