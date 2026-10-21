"""Optional documentation health check, without digest or exact-layout gates."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path("assets/documentation-parity.json")
TRANSLATION_SUFFIX = ".zh-CN.md"


class DocumentationParityError(RuntimeError):
    pass


def _document(root: Path, relative: Any) -> tuple[Path, str]:
    path = (root / str(relative)).resolve()
    if not path.is_relative_to(root):
        raise DocumentationParityError(f"document path escapes repository: {relative}")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise DocumentationParityError(f"cannot read document {relative}: {exc}") from exc
    if not text.strip():
        raise DocumentationParityError(f"empty document: {relative}")
    return path, text


def validate_documentation(root: Path = ROOT, manifest_relative: Path = DEFAULT_MANIFEST,
                           *, check_hashes: bool = False) -> dict[str, Any]:
    """Read listed translations. Digest fields in old manifests are ignored."""
    root = root.resolve()
    try:
        manifest = json.loads((root / manifest_relative).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise DocumentationParityError(f"cannot read documentation manifest: {exc}") from exc
    pairs = manifest.get("pairs")
    if not isinstance(pairs, list):
        raise DocumentationParityError("documentation manifest requires a pairs array")
    reports = []
    warnings = []
    for pair in pairs:
        if not isinstance(pair, dict):
            raise DocumentationParityError("documentation pair must be an object")
        for field in ("source_path", "translation_path"):
            path, text = _document(root, pair.get(field))
            for raw in re.findall(r"!?\[[^\]]*\]\(([^\s)]+)\)", text):
                target = urlsplit(raw)
                if target.scheme or target.netloc or not target.path:
                    continue
                if not (path.parent / unquote(target.path)).exists():
                    warnings.append(f"{pair[field]}: missing link {raw}")
        reports.append({"id": pair.get("id"), "source_path": pair["source_path"],
                        "translation_path": pair["translation_path"], "status": "PASS"})
    return {"status": "PASS", "pair_count": len(reports), "translation_files": len(reports),
            "pairs": reports, "warnings": warnings}


def refresh_hashes(root: Path = ROOT, manifest_relative: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    """Old command compatibility; no files are rewritten or sealed."""
    return validate_documentation(root, manifest_relative)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check readable documentation and report missing local links")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--refresh-hashes", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        report = validate_documentation(ROOT, args.manifest)
    except DocumentationParityError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
