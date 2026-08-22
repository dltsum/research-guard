from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import unicodedata
import zlib
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path("assets/documentation-parity.json")
TRANSLATION_SUFFIX = ".zh-CN.md"
EXCLUDED_PARTS = {
    ".git",
    ".research-guard",
    "__pycache__",
    "build",
    "dist",
    "evals",
    "snapshots",
}
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
PAIR_MARKER = re.compile(
    r"<!--\s*research-guard-doc-pair:\s*([a-z0-9][a-z0-9-]*)\s*\|\s*revision:\s*([^\s<>]+)\s*-->"
)
HEADING_TWO = re.compile(r"^##\s+(?!#)(.+?)\s*$", re.MULTILINE)
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+[\"'][^)]+[\"'])?\)")
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+[\"'][^)]+[\"'])?\)")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class DocumentationParityError(RuntimeError):
    pass


def _normalized_text(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise DocumentationParityError(f"cannot read strict UTF-8 document {path}: {exc}") from exc
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", value)


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pair_sha256(source_sha256: str, translation_sha256: str, revision: str) -> str:
    payload = f"{source_sha256}\n{translation_sha256}\n{revision}\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_relative(root: Path, value: Any, label: str) -> tuple[str, Path]:
    if not isinstance(value, str) or not value or "\\" in value:
        raise DocumentationParityError(f"{label} must be a non-empty POSIX relative path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise DocumentationParityError(f"{label} is not a safe relative path: {value!r}")
    resolved_root = root.resolve()
    resolved = root.joinpath(*pure.parts).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise DocumentationParityError(f"{label} escapes the repository: {value!r}") from exc
    return pure.as_posix(), resolved


def _load_manifest(root: Path, manifest_relative: Path) -> tuple[dict[str, Any], Path]:
    relative, path = _safe_relative(root, manifest_relative.as_posix(), "manifest path")
    if not path.is_file():
        raise DocumentationParityError(f"documentation manifest is missing: {relative}")
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DocumentationParityError(f"documentation manifest is invalid: {exc}") from exc
    if not isinstance(data, dict):
        raise DocumentationParityError("documentation manifest root must be an object")
    return data, path


def _one_marker(text: str, expected_id: str, expected_revision: str, relative: str) -> None:
    markers = PAIR_MARKER.findall(text)
    if markers != [(expected_id, expected_revision)]:
        raise DocumentationParityError(
            f"{relative} must contain exactly one marker for {expected_id}@{expected_revision}; found {markers}"
        )


def _headings(text: str) -> list[str]:
    return [match.strip().rstrip("#").strip() for match in HEADING_TWO.findall(text)]


def _target(value: str) -> str:
    return value.strip().removeprefix("<").removesuffix(">")


def _link_targets(text: str) -> Counter[str]:
    return Counter(_target(value) for value in LINK.findall(text))


def _images(text: str) -> list[tuple[str, str]]:
    return [(alt.strip(), _target(target)) for alt, target in IMAGE.findall(text)]


def _validate_internal_links(root: Path, document: Path, links: Counter[str], relative: str) -> None:
    for target in links:
        if target.startswith(("https://", "http://", "mailto:")) or target.startswith("#"):
            continue
        file_target = target.split("#", 1)[0].split("?", 1)[0]
        if not file_target:
            continue
        pure = PurePosixPath(file_target)
        if pure.is_absolute() or ".." in pure.parts and document.parent == root:
            candidate = document.parent.joinpath(*pure.parts).resolve()
        else:
            candidate = document.parent.joinpath(*pure.parts).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError as exc:
            raise DocumentationParityError(f"{relative} link escapes the repository: {target}") from exc
        if not candidate.exists():
            raise DocumentationParityError(f"{relative} has a missing local link target: {target}")


def _png_dimensions(path: Path) -> tuple[int, int]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise DocumentationParityError(f"cannot read image {path}: {exc}") from exc
    if len(data) < 45 or data[:8] != PNG_SIGNATURE:
        raise DocumentationParityError(f"image is not a valid PNG stream: {path}")
    offset = 8
    chunks: list[tuple[bytes, bytes]] = []
    while offset < len(data):
        if offset + 12 > len(data):
            raise DocumentationParityError(f"image has a truncated PNG chunk: {path}")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise DocumentationParityError(f"image has an invalid PNG chunk length: {path}")
        payload = data[offset + 8 : offset + 8 + length]
        recorded_crc = struct.unpack(">I", data[offset + 8 + length : end])[0]
        actual_crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        if recorded_crc != actual_crc:
            raise DocumentationParityError(f"image has a PNG CRC mismatch: {path}")
        chunks.append((kind, payload))
        offset = end
        if kind == b"IEND":
            break
    if offset != len(data) or not chunks or chunks[0][0] != b"IHDR" or len(chunks[0][1]) != 13:
        raise DocumentationParityError(f"image PNG structure is invalid: {path}")
    if not any(kind == b"IDAT" for kind, _ in chunks) or chunks[-1] != (b"IEND", b""):
        raise DocumentationParityError(f"image PNG lacks IDAT or final IEND: {path}")
    width, height = struct.unpack(">II", chunks[0][1][:8])
    if width <= 0 or height <= 0:
        raise DocumentationParityError(f"image has invalid dimensions: {path}")
    return width, height


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise DocumentationParityError(f"cannot hash file {path}: {exc}") from exc
    return digest.hexdigest()


def _validate_image_contract(
    root: Path,
    declared: dict[str, Any],
    source_images: list[tuple[str, str]],
    translation_images: list[tuple[str, str]],
) -> dict[str, Any]:
    relative, path = _safe_relative(root, declared.get("path"), "required image path")
    if not path.is_file():
        raise DocumentationParityError(f"required image is missing: {relative}")
    if declared.get("format") != "png" or path.suffix.casefold() != ".png":
        raise DocumentationParityError(f"only a declared PNG is admitted for README image audit: {relative}")
    if [target for _, target in source_images].count(relative) != 1:
        raise DocumentationParityError(f"source document must embed required image exactly once: {relative}")
    if [target for _, target in translation_images].count(relative) != 1:
        raise DocumentationParityError(f"translation document must embed required image exactly once: {relative}")
    source_alt = next(alt for alt, target in source_images if target == relative)
    translation_alt = next(alt for alt, target in translation_images if target == relative)
    if not source_alt or not translation_alt:
        raise DocumentationParityError(f"required image needs non-empty alt text in both languages: {relative}")

    width, height = _png_dimensions(path)
    aspect = width / height
    size = path.stat().st_size
    limits = {
        "minimum_width": int(declared.get("minimum_width", 1)),
        "minimum_height": int(declared.get("minimum_height", 1)),
        "minimum_aspect_ratio": float(declared.get("minimum_aspect_ratio", 0.0)),
        "maximum_aspect_ratio": float(declared.get("maximum_aspect_ratio", float("inf"))),
        "maximum_bytes": int(declared.get("maximum_bytes", 0)),
    }
    if width < limits["minimum_width"] or height < limits["minimum_height"]:
        raise DocumentationParityError(f"required image is below minimum dimensions: {relative}={width}x{height}")
    if not limits["minimum_aspect_ratio"] <= aspect <= limits["maximum_aspect_ratio"]:
        raise DocumentationParityError(f"required image aspect ratio is outside the contract: {relative}={aspect:.4f}")
    if limits["maximum_bytes"] <= 0 or size > limits["maximum_bytes"]:
        raise DocumentationParityError(f"required image exceeds its size contract: {relative}={size} bytes")

    provenance_relative, provenance_path = _safe_relative(
        root, declared.get("provenance_path"), "image provenance path"
    )
    if not provenance_path.is_file():
        raise DocumentationParityError(f"image provenance is missing: {provenance_relative}")
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DocumentationParityError(f"image provenance is invalid: {provenance_relative}: {exc}") from exc
    image_sha256 = _file_sha256(path)
    if provenance.get("asset") != relative or provenance.get("sha256") != image_sha256:
        raise DocumentationParityError(f"image provenance does not bind the current asset: {relative}")
    audit = provenance.get("visual_audit") or {}
    if audit.get("status") != "PASS" or audit.get("typographic_content") is None:
        raise DocumentationParityError(f"image provenance lacks a complete visual audit: {relative}")
    recorded = audit.get("dimensions") or {}
    if recorded.get("width") != width or recorded.get("height") != height:
        raise DocumentationParityError(f"image provenance dimensions drifted: {relative}")
    return {
        "path": relative,
        "bytes": size,
        "width": width,
        "height": height,
        "aspect_ratio": round(aspect, 6),
        "sha256": image_sha256,
        "provenance": provenance_relative,
    }


def _validate_pair(
    root: Path,
    pair: dict[str, Any],
    *,
    check_hashes: bool,
) -> dict[str, Any]:
    pair_id = pair.get("id")
    revision = pair.get("revision")
    if not isinstance(pair_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", pair_id):
        raise DocumentationParityError(f"invalid documentation pair id: {pair_id!r}")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z._-]*", revision):
        raise DocumentationParityError(f"invalid revision for documentation pair {pair_id}: {revision!r}")
    source_relative, source_path = _safe_relative(root, pair.get("source_path"), f"{pair_id}.source_path")
    translation_relative, translation_path = _safe_relative(
        root, pair.get("translation_path"), f"{pair_id}.translation_path"
    )
    if source_relative.endswith(TRANSLATION_SUFFIX):
        raise DocumentationParityError(f"source path uses the translation suffix: {source_relative}")
    if not translation_relative.endswith(TRANSLATION_SUFFIX):
        raise DocumentationParityError(f"translation path must end with {TRANSLATION_SUFFIX}: {translation_relative}")
    if not source_path.is_file() or not translation_path.is_file():
        raise DocumentationParityError(
            f"documentation pair {pair_id} is incomplete: {source_relative}, {translation_relative}"
        )
    source = _normalized_text(source_path)
    translation = _normalized_text(translation_path)
    _one_marker(source, pair_id, revision, source_relative)
    _one_marker(translation, pair_id, revision, translation_relative)

    section_records = pair.get("sections")
    if not isinstance(section_records, list) or not section_records:
        raise DocumentationParityError(f"documentation pair {pair_id} has no section contract")
    section_ids: set[str] = set()
    expected_source: list[str] = []
    expected_translation: list[str] = []
    for section in section_records:
        if not isinstance(section, dict):
            raise DocumentationParityError(f"documentation pair {pair_id} has a non-object section")
        section_id = section.get("id")
        if not isinstance(section_id, str) or not section_id or section_id in section_ids:
            raise DocumentationParityError(f"documentation pair {pair_id} has a duplicate/invalid section id")
        section_ids.add(section_id)
        for key, target in (("source_heading", expected_source), ("translation_heading", expected_translation)):
            value = section.get(key)
            if not isinstance(value, str) or not value.strip():
                raise DocumentationParityError(f"documentation pair {pair_id} has an invalid {key}")
            target.append(value.strip())
    if _headings(source) != expected_source:
        raise DocumentationParityError(
            f"source level-two section skeleton drifted for {pair_id}: {_headings(source)!r}"
        )
    if _headings(translation) != expected_translation:
        raise DocumentationParityError(
            f"translation level-two section skeleton drifted for {pair_id}: {_headings(translation)!r}"
        )

    for token in pair.get("common_tokens", []):
        if not isinstance(token, str) or token not in source or token not in translation:
            raise DocumentationParityError(f"documentation pair {pair_id} is missing common token: {token!r}")
    for token in pair.get("source_tokens", []):
        if not isinstance(token, str) or token not in source:
            raise DocumentationParityError(f"source document {source_relative} is missing token: {token!r}")
    for token in pair.get("translation_tokens", []):
        if not isinstance(token, str) or token not in translation:
            raise DocumentationParityError(f"translation document {translation_relative} is missing token: {token!r}")

    source_links = _link_targets(source)
    translation_links = _link_targets(translation)
    if source_links != translation_links:
        missing_in_translation = source_links - translation_links
        extra_in_translation = translation_links - source_links
        raise DocumentationParityError(
            f"link target parity drift for {pair_id}: missing={dict(missing_in_translation)}, "
            f"extra={dict(extra_in_translation)}"
        )
    _validate_internal_links(root, source_path, source_links, source_relative)
    _validate_internal_links(root, translation_path, translation_links, translation_relative)

    source_images = _images(source)
    translation_images = _images(translation)
    if Counter(target for _, target in source_images) != Counter(target for _, target in translation_images):
        raise DocumentationParityError(f"image target parity drift for {pair_id}")
    if any(not alt for alt, _ in source_images + translation_images):
        raise DocumentationParityError(f"documentation pair {pair_id} contains empty image alt text")
    declared_images = pair.get("required_images")
    if not isinstance(declared_images, list):
        raise DocumentationParityError(f"documentation pair {pair_id} required_images must be a list")
    declared_paths = [item.get("path") for item in declared_images if isinstance(item, dict)]
    actual_paths = sorted({target for _, target in source_images})
    if sorted(declared_paths) != actual_paths:
        raise DocumentationParityError(
            f"documentation pair {pair_id} image manifest drift: declared={declared_paths}, actual={actual_paths}"
        )
    image_reports = [
        _validate_image_contract(root, item, source_images, translation_images)
        for item in declared_images
    ]

    source_sha256 = _text_sha256(source)
    translation_sha256 = _text_sha256(translation)
    pair_sha256 = _pair_sha256(source_sha256, translation_sha256, revision)
    for key, value in (
        ("source_sha256", source_sha256),
        ("translation_sha256", translation_sha256),
        ("pair_sha256", pair_sha256),
    ):
        recorded = pair.get(key)
        if not isinstance(recorded, str) or not HEX_64.fullmatch(recorded):
            raise DocumentationParityError(f"documentation pair {pair_id} has invalid {key}")
        if check_hashes and recorded != value:
            raise DocumentationParityError(
                f"documentation pair {pair_id} {key} drifted; review both languages and run --refresh-hashes"
            )
    return {
        "id": pair_id,
        "revision": revision,
        "source_path": source_relative,
        "translation_path": translation_relative,
        "source_sha256": source_sha256,
        "translation_sha256": translation_sha256,
        "pair_sha256": pair_sha256,
        "sections": len(section_records),
        "links": sum(source_links.values()),
        "images": image_reports,
    }


def validate_documentation(
    root: Path = ROOT,
    manifest_relative: Path = DEFAULT_MANIFEST,
    *,
    check_hashes: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    manifest, _ = _load_manifest(root, manifest_relative)
    if manifest.get("schema_version") != 1:
        raise DocumentationParityError("documentation manifest schema_version must be 1")
    if manifest.get("translation_suffix") != TRANSLATION_SUFFIX:
        raise DocumentationParityError("documentation manifest translation suffix drifted")
    if manifest.get("all_translation_files_must_be_registered") is not True:
        raise DocumentationParityError("all translation files must be registered")
    pairs = manifest.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise DocumentationParityError("documentation manifest must contain at least one pair")
    ids: set[str] = set()
    paths: set[str] = set()
    registered_translations: set[str] = set()
    reports: list[dict[str, Any]] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            raise DocumentationParityError("documentation manifest contains a non-object pair")
        pair_id = pair.get("id")
        if pair_id in ids:
            raise DocumentationParityError(f"duplicate documentation pair id: {pair_id}")
        ids.add(pair_id)
        source_relative, _ = _safe_relative(root, pair.get("source_path"), f"{pair_id}.source_path")
        translation_relative, _ = _safe_relative(
            root, pair.get("translation_path"), f"{pair_id}.translation_path"
        )
        if source_relative in paths or translation_relative in paths or source_relative == translation_relative:
            raise DocumentationParityError(f"documentation path belongs to more than one pair: {pair_id}")
        paths.update({source_relative, translation_relative})
        registered_translations.add(translation_relative)
        reports.append(_validate_pair(root, pair, check_hashes=check_hashes))

    discovered_translations = {
        path.relative_to(root).as_posix()
        for path in root.rglob(f"*{TRANSLATION_SUFFIX}")
        if path.is_file() and not any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts)
    }
    if discovered_translations != registered_translations:
        unregistered = sorted(discovered_translations - registered_translations)
        missing = sorted(registered_translations - discovered_translations)
        raise DocumentationParityError(
            f"translation registry coverage drift: unregistered={unregistered}, missing={missing}"
        )
    return {
        "status": "PASS",
        "contract_id": manifest.get("contract_id"),
        "pair_count": len(reports),
        "translation_files": len(discovered_translations),
        "pairs": reports,
    }


def refresh_hashes(root: Path = ROOT, manifest_relative: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    root = root.resolve()
    manifest, manifest_path = _load_manifest(root, manifest_relative)
    preflight = validate_documentation(root, manifest_relative, check_hashes=False)
    report_by_id = {item["id"]: item for item in preflight["pairs"]}
    for pair in manifest["pairs"]:
        report = report_by_id[pair["id"]]
        pair["source_sha256"] = report["source_sha256"]
        pair["translation_sha256"] = report["translation_sha256"]
        pair["pair_sha256"] = report["pair_sha256"]
    temporary = manifest_path.with_name(f".{manifest_path.name}.tmp")
    rendered = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    temporary.write_text(rendered, encoding="utf-8", newline="\n")
    temporary.replace(manifest_path)
    result = validate_documentation(root, manifest_relative, check_hashes=True)
    result["hashes_refreshed"] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate every registered Research Guard bilingual document")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--refresh-hashes", action="store_true")
    arguments = parser.parse_args()
    try:
        report = (
            refresh_hashes(ROOT, arguments.manifest)
            if arguments.refresh_hashes
            else validate_documentation(ROOT, arguments.manifest)
        )
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
