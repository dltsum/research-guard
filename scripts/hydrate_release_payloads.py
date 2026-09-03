from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from network_config_core import NetworkConfigError, route_openers
from resource_guard import (
    INSTALL_ORCHESTRATOR_RESERVE_BYTES,
    RUN_MIN_FREE_BYTES,
    ResourceGuardError,
    memory_snapshot,
    require_orchestrator_budget,
    require_start_headroom,
    run_managed_install,
)


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOOTSTRAP = PLUGIN_ROOT / "assets" / "payload-bootstrap.json"
DEFAULT_PAYLOAD_MANIFEST = PLUGIN_ROOT / "assets" / "payload-manifest.json"
DEFAULT_PAYLOAD_DIRECTORY = PLUGIN_ROOT / "assets" / "payloads"
MAX_MANIFEST_BYTES = 8 * 1024 ** 2
MAX_PAYLOAD_COUNT = 32
MAX_BOOTSTRAP_BYTES = 1024 ** 3
SHA256 = re.compile(r"[0-9a-f]{64}")


class PayloadHydrationError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise PayloadHydrationError(f"{label} is missing or exceeds {MAX_MANIFEST_BYTES} bytes: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PayloadHydrationError(f"{label} is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise PayloadHydrationError(f"{label} must be a JSON object")
    return value


def _expected_payloads(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != 1 or manifest.get("platform") != "windows-x64":
        raise PayloadHydrationError("payload manifest schema or platform is invalid")
    payloads = manifest.get("payloads")
    if not isinstance(payloads, list) or not 1 <= len(payloads) <= MAX_PAYLOAD_COUNT:
        raise PayloadHydrationError(f"payload manifest must contain 1-{MAX_PAYLOAD_COUNT} payloads")
    normalized: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, raw in enumerate(payloads):
        if not isinstance(raw, dict):
            raise PayloadHydrationError(f"payloads[{index}] must be an object")
        name = str(raw.get("name") or "")
        if not name or Path(name).name != name or "/" in name or "\\" in name:
            raise PayloadHydrationError(f"payloads[{index}].name is not a safe file name")
        folded = name.casefold()
        if folded in names:
            raise PayloadHydrationError(f"duplicate payload name: {name}")
        names.add(folded)
        size = raw.get("bytes")
        digest = str(raw.get("sha256") or "").lower()
        if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_BOOTSTRAP_BYTES:
            raise PayloadHydrationError(f"payload {name} has an invalid byte count")
        if not SHA256.fullmatch(digest):
            raise PayloadHydrationError(f"payload {name} has an invalid SHA-256")
        normalized.append({"name": name, "bytes": size, "sha256": digest})
    if sum(item["bytes"] for item in normalized) > MAX_BOOTSTRAP_BYTES:
        raise PayloadHydrationError("payload manifest exceeds the 1 GiB expanded payload cap")
    return normalized


def validate_payload_directory(
    payload_manifest_path: Path = DEFAULT_PAYLOAD_MANIFEST,
    payload_directory: Path = DEFAULT_PAYLOAD_DIRECTORY,
) -> dict[str, Any]:
    manifest = _load_json(payload_manifest_path, "payload manifest")
    expected = _expected_payloads(manifest)
    directory = payload_directory.expanduser().resolve()
    if not directory.is_dir():
        raise PayloadHydrationError(f"payload directory is missing: {directory}")
    entries = list(directory.iterdir())
    observed_names = {entry.name.casefold() for entry in entries if entry.is_file()}
    expected_names = {item["name"].casefold() for item in expected}
    unsupported = sorted(entry.name for entry in entries if not entry.is_file())
    extra = sorted(entry.name for entry in entries if entry.is_file() and entry.name.casefold() not in expected_names)
    missing = sorted(item["name"] for item in expected if item["name"].casefold() not in observed_names)
    if unsupported or extra or missing:
        raise PayloadHydrationError(
            f"payload directory must exactly match the manifest; missing={missing}, extra={extra}, unsupported={unsupported}"
        )
    verified: list[dict[str, Any]] = []
    for item in expected:
        path = directory / item["name"]
        size = path.stat().st_size
        digest = _sha256(path)
        if size != item["bytes"] or digest != item["sha256"]:
            raise PayloadHydrationError(
                f"payload integrity mismatch for {item['name']}: bytes={size}, sha256={digest}"
            )
        verified.append({**item, "path": path.name})
    return {
        "status": "PASS",
        "payload_count": len(verified),
        "payload_bytes": sum(item["bytes"] for item in verified),
        "payloads": verified,
    }


def validate_bootstrap_contract(bootstrap_path: Path, payload_manifest_path: Path) -> dict[str, Any]:
    bootstrap = _load_json(bootstrap_path, "payload bootstrap")
    required = {
        "schema_version": 1,
        "repository": "dltsum/research-guard",
        "release_tag": "v0.7.0",
        "asset_name": "research-guard-windows-x64-modular.zip",
    }
    for field, expected in required.items():
        if bootstrap.get(field) != expected:
            raise PayloadHydrationError(f"payload bootstrap {field} must be {expected!r}")
    expected_url = (
        f"https://github.com/{bootstrap['repository']}/releases/download/"
        f"{bootstrap['release_tag']}/{bootstrap['asset_name']}"
    )
    if bootstrap.get("source") != expected_url:
        raise PayloadHydrationError("payload bootstrap source is not the pinned GitHub release URL")
    size = bootstrap.get("asset_bytes")
    archive_sha = str(bootstrap.get("asset_sha256") or "").lower()
    manifest_sha = str(bootstrap.get("payload_manifest_sha256") or "").lower()
    if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_BOOTSTRAP_BYTES:
        raise PayloadHydrationError("payload bootstrap asset_bytes is invalid")
    if not SHA256.fullmatch(archive_sha) or not SHA256.fullmatch(manifest_sha):
        raise PayloadHydrationError("payload bootstrap SHA-256 fields are invalid")
    actual_manifest_sha = _sha256(payload_manifest_path.expanduser().resolve())
    if actual_manifest_sha != manifest_sha:
        raise PayloadHydrationError(
            f"payload manifest changed without a new bootstrap contract: {actual_manifest_sha}"
        )
    return bootstrap


def _download_archive(url: str, destination: Path, expected_bytes: int, expected_sha256: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "research-guard-payload-hydrator/1"})
    attempted: list[str] = []
    last_transport: Exception | None = None
    try:
        routes = tuple(route_openers(url))
    except NetworkConfigError as exc:
        raise PayloadHydrationError(str(exc)) from exc
    for route_name, _proxy, opener in routes:
        attempted.append(route_name)
        digest = hashlib.sha256()
        received = 0
        try:
            with opener.open(request, timeout=120) as response, destination.open("xb") as output:
                while True:
                    if int(memory_snapshot()["available_physical_bytes"]) < RUN_MIN_FREE_BYTES:
                        raise PayloadHydrationError("RESOURCE_LOW_WATER_ABORT during payload download")
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    received += len(block)
                    if received > expected_bytes:
                        raise PayloadHydrationError("payload bootstrap download exceeds the pinned byte count")
                    digest.update(block)
                    output.write(block)
        except urllib.error.HTTPError as exc:
            destination.unlink(missing_ok=True)
            raise PayloadHydrationError(f"payload bootstrap download failed via {route_name}: HTTP {exc.code}") from exc
        except PayloadHydrationError:
            destination.unlink(missing_ok=True)
            raise
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            last_transport = exc
            destination.unlink(missing_ok=True)
            continue
        if received != expected_bytes or digest.hexdigest() != expected_sha256:
            destination.unlink(missing_ok=True)
            raise PayloadHydrationError(
                f"payload bootstrap integrity mismatch via {route_name}: bytes={received}, sha256={digest.hexdigest()}"
            )
        return route_name
    detail = type(last_transport).__name__ if last_transport is not None else "no route completed"
    raise PayloadHydrationError(
        f"payload bootstrap download failed after routes {attempted}: {detail}"
    ) from last_transport


def hydrate_from_archive(
    archive_path: Path,
    bootstrap_path: Path,
    payload_manifest_path: Path,
    payload_directory: Path,
) -> dict[str, Any]:
    archive_path = archive_path.expanduser().resolve()
    payload_manifest_path = payload_manifest_path.expanduser().resolve()
    payload_directory = payload_directory.expanduser().resolve()
    bootstrap = validate_bootstrap_contract(bootstrap_path, payload_manifest_path)
    if not archive_path.is_file():
        raise PayloadHydrationError(f"payload bootstrap archive is missing: {archive_path}")
    archive_size = archive_path.stat().st_size
    archive_sha = _sha256(archive_path)
    if archive_size != bootstrap["asset_bytes"] or archive_sha != bootstrap["asset_sha256"]:
        raise PayloadHydrationError(
            f"payload bootstrap archive mismatch: bytes={archive_size}, sha256={archive_sha}"
        )
    payload_manifest = _load_json(payload_manifest_path, "payload manifest")
    expected = _expected_payloads(payload_manifest)
    payload_directory.mkdir(parents=True, exist_ok=True)
    temporary_paths: list[tuple[Path, Path]] = []
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if not members or len(members) > 5000:
                raise PayloadHydrationError("payload bootstrap archive has an invalid member count")
            release_names = [item for item in members if item.filename == "research-guard/RELEASE_MANIFEST.json"]
            if len(release_names) != 1 or release_names[0].file_size > MAX_MANIFEST_BYTES:
                raise PayloadHydrationError("payload bootstrap archive must have one bounded release manifest")
            try:
                release_manifest = json.loads(archive.read(release_names[0]).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PayloadHydrationError("payload bootstrap release manifest is invalid") from exc
            if release_manifest.get("package") != "research-guard" or release_manifest.get("platform") != "windows-x64":
                raise PayloadHydrationError("payload bootstrap release manifest package or platform is invalid")
            release_files = release_manifest.get("files")
            if not isinstance(release_files, list):
                raise PayloadHydrationError("payload bootstrap release manifest files are invalid")
            release_map: dict[str, dict[str, Any]] = {}
            for record in release_files:
                if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                    raise PayloadHydrationError("payload bootstrap release file record is invalid")
                if record["path"] in release_map:
                    raise PayloadHydrationError(f"duplicate release manifest path: {record['path']}")
                release_map[record["path"]] = record
            for item in expected:
                relative = f"assets/payloads/{item['name']}"
                archived = f"research-guard/{relative}"
                matches = [member for member in members if member.filename == archived]
                if len(matches) != 1:
                    raise PayloadHydrationError(f"payload bootstrap must contain exactly one {archived}")
                member = matches[0]
                unix_mode = (member.external_attr >> 16) & 0xFFFF
                if member.is_dir() or stat.S_ISLNK(unix_mode) or member.flag_bits & 0x1:
                    raise PayloadHydrationError(f"payload bootstrap member is not an admitted regular file: {archived}")
                release_record = release_map.get(relative)
                if (
                    member.file_size != item["bytes"]
                    or not isinstance(release_record, dict)
                    or release_record.get("bytes") != item["bytes"]
                    or str(release_record.get("sha256") or "").lower() != item["sha256"]
                ):
                    raise PayloadHydrationError(f"payload bootstrap metadata mismatch for {item['name']}")
                temporary = payload_directory / f".{item['name']}.{os.getpid()}.tmp"
                final = payload_directory / item["name"]
                temporary_paths.append((temporary, final))
                digest = hashlib.sha256()
                written = 0
                with archive.open(member) as source, temporary.open("xb") as output:
                    while True:
                        block = source.read(1024 * 1024)
                        if not block:
                            break
                        written += len(block)
                        if written > item["bytes"]:
                            raise PayloadHydrationError(f"payload expands beyond its bound: {item['name']}")
                        digest.update(block)
                        output.write(block)
                if written != item["bytes"] or digest.hexdigest() != item["sha256"]:
                    raise PayloadHydrationError(f"payload content integrity mismatch: {item['name']}")
        for temporary, final in temporary_paths:
            os.replace(temporary, final)
        verified = validate_payload_directory(payload_manifest_path, payload_directory)
        return {
            "schema_version": 1,
            "status": "PASS",
            "source_release": bootstrap["release_tag"],
            "source_asset": bootstrap["asset_name"],
            "source_archive_bytes": archive_size,
            "source_archive_sha256": archive_sha,
            **verified,
        }
    finally:
        for temporary, _ in temporary_paths:
            temporary.unlink(missing_ok=True)


def hydrate(
    bootstrap_path: Path,
    payload_manifest_path: Path,
    payload_directory: Path,
    *,
    archive_path: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    bootstrap_path = bootstrap_path.expanduser().resolve()
    payload_manifest_path = payload_manifest_path.expanduser().resolve()
    payload_directory = payload_directory.expanduser().resolve()
    bootstrap = validate_bootstrap_contract(bootstrap_path, payload_manifest_path)
    if not force:
        try:
            verified = validate_payload_directory(payload_manifest_path, payload_directory)
        except PayloadHydrationError:
            pass
        else:
            return {
                "schema_version": 1,
                "status": "PASS",
                "source_release": bootstrap["release_tag"],
                "source_asset": bootstrap["asset_name"],
                "source_archive_bytes": None,
                "source_archive_sha256": None,
                "reused_verified_payloads": True,
                **verified,
            }
    if archive_path is not None:
        return hydrate_from_archive(archive_path, bootstrap_path, payload_manifest_path, payload_directory)
    with tempfile.TemporaryDirectory(prefix="research-guard-payload-bootstrap-") as temporary:
        downloaded = Path(temporary) / bootstrap["asset_name"]
        network_route = _download_archive(
            bootstrap["source"], downloaded, bootstrap["asset_bytes"], bootstrap["asset_sha256"],
        )
        result = hydrate_from_archive(downloaded, bootstrap_path, payload_manifest_path, payload_directory)
        result["network_route"] = network_route
        return result


def _write_report(path: Path, report: dict[str, Any]) -> None:
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    os.replace(temporary, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description="Hydrate SHA-pinned Windows payloads omitted from Git source")
    parser.add_argument("--bootstrap", type=Path, default=DEFAULT_BOOTSTRAP)
    parser.add_argument("--payload-manifest", type=Path, default=DEFAULT_PAYLOAD_MANIFEST)
    parser.add_argument("--payload-directory", type=Path, default=DEFAULT_PAYLOAD_DIRECTORY)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--attempt-timeout-seconds", type=float, default=3600)
    parser.add_argument("--bounded-worker", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.bounded_worker or os.environ.get("RESEARCH_GUARD_MANAGED_WORKER") == "1":
        try:
            result = hydrate(
                arguments.bootstrap, arguments.payload_manifest, arguments.payload_directory,
                archive_path=arguments.archive, force=arguments.force,
            )
        except Exception as exc:
            print(json.dumps({
                "schema_version": 1, "status": "FAIL", "error": type(exc).__name__, "message": str(exc),
            }, ensure_ascii=False, indent=2), file=sys.stderr)
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    try:
        require_start_headroom()
        require_orchestrator_budget(INSTALL_ORCHESTRATOR_RESERVE_BYTES)
        command = [
            sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
            "--bootstrap", str(arguments.bootstrap),
            "--payload-manifest", str(arguments.payload_manifest),
            "--payload-directory", str(arguments.payload_directory),
            "--attempt-timeout-seconds", str(arguments.attempt_timeout_seconds),
            "--bounded-worker",
        ]
        if arguments.archive is not None:
            command.extend(["--archive", str(arguments.archive)])
        if arguments.force:
            command.append("--force")
        completed = run_managed_install(
            command, cwd=PLUGIN_ROOT, timeout=arguments.attempt_timeout_seconds,
        )
        if completed.returncode != 0:
            if completed.stderr:
                print(completed.stderr, file=sys.stderr, end="")
            return completed.returncode
        result = json.loads(completed.stdout)
        result["resource_usage"] = completed.resource_usage
        if arguments.report:
            _write_report(arguments.report, result)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (PayloadHydrationError, ResourceGuardError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "schema_version": 1, "status": "FAIL", "error": type(exc).__name__, "message": str(exc),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
