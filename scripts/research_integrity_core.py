from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import platform
import re
import shlex
import shutil
import tempfile
import time
from collections import Counter
from pathlib import Path
from statistics import NormalDist
from typing import Any
from urllib.parse import quote, urlparse


SCHEMA_VERSION = 1
STATE_NAME = "research-integrity.json"
ALLOWED_RELATIONS = {"supports", "refutes", "insufficient"}
MATERIAL_UPDATE_TYPES = {
    "retraction", "withdrawal", "expression-of-concern", "correction", "update",
    "removal", "partial-retraction", "reinstatement",
}
DEFAULT_P12_CONFIG_PATH = Path(__file__).resolve().parents[1] / "assets" / "p12-skillopt-config.json"


def _p12_config_path() -> Path:
    override = os.environ.get("RESEARCH_GUARD_SKILLOPT_CONFIG")
    if not override:
        return DEFAULT_P12_CONFIG_PATH
    candidate = Path(override).resolve()
    evidence_root = DEFAULT_P12_CONFIG_PATH.parents[1] / "evals" / "p12-skillopt"
    expected = os.environ.get("RESEARCH_GUARD_SKILLOPT_CONFIG_SHA256", "")
    if not candidate.is_relative_to(evidence_root) or not expected:
        raise RuntimeError("SKILLOPT_CONFIG_OVERRIDE_INVALID: candidate path or hash is missing")
    actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError("SKILLOPT_CONFIG_OVERRIDE_INVALID: candidate hash mismatch")
    return candidate


def _active_review_tuning() -> tuple[float, float]:
    try:
        value = json.loads(_p12_config_path().read_text(encoding="utf-8"))
        tuning = value.get("active_review") or {}
        smoothing = float(tuning.get("smoothing", 1.0))
        prior_weight = float(tuning.get("prior_weight", 1.0))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return 1.0, 1.0
    if not 0.1 <= smoothing <= 10 or not 0 <= prior_weight <= 5:
        return 1.0, 1.0
    return smoothing, prior_weight


class IntegrityError(ValueError):
    pass


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _root(value: str | os.PathLike[str]) -> Path:
    root = Path(value).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _state_path(root: Path) -> Path:
    return root / ".research-guard" / STATE_NAME


def _atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _empty_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "method_version": None,
        "method_hash": None,
        "ingestions": {},
        "evidence_graphs": {},
        "preregistrations": {},
        "statistical_audits": {},
        "reproducibility": {},
        "reviews": {},
        "record_health": {},
        "invalidations": [],
    }


def _load(root: Path) -> dict[str, Any]:
    path = _state_path(root)
    if not path.is_file():
        return _empty_state()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"research-integrity state is invalid: {exc}") from exc
    if value.get("schema_version") != SCHEMA_VERSION:
        raise IntegrityError("unsupported research-integrity schema version")
    return value


def _save(root: Path, value: dict[str, Any]) -> None:
    _atomic(_state_path(root), value)


def _identifier(value: Any, label: str) -> str:
    identifier = re.sub(r"[^a-z0-9_-]+", "-", str(value or "").casefold()).strip("-")
    if not identifier or len(identifier) > 96:
        raise IntegrityError(f"{label} is invalid")
    return identifier


def _project_file(root: Path, value: str, label: str, *, required: bool = True) -> Path:
    path = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise IntegrityError(f"{label} must stay inside project_root") from exc
    if required and not path.is_file():
        raise IntegrityError(f"{label} does not exist: {value}")
    return path


def _https(value: Any, label: str) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise IntegrityError(f"{label} must be a credential-free clickable HTTPS URL")
    return text


def _doi(value: Any) -> str:
    normalized = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", str(value or "").strip(), flags=re.I).lower()
    if not re.match(r"^10\.\d{4,9}/\S+$", normalized):
        raise IntegrityError("a valid DOI is required")
    return normalized


def _method_binding(root: Path, *, required: bool = True) -> tuple[int | None, str | None]:
    path = root / ".research-guard" / "state.json"
    if not path.is_file():
        if required:
            raise IntegrityError("register the complete research method before this operation")
        return None, None
    try:
        method_state = json.loads(path.read_text(encoding="utf-8"))
        if required and method_state.get("pending_method_change"):
            raise IntegrityError(
                "a method adjustment is pending; register the complete adjusted method and rerun collision search first"
            )
        active = method_state["active_method"]
        return int(active["version"]), str(active["hash"])
    except IntegrityError:
        raise
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise IntegrityError(f"active research method is invalid: {exc}") from exc


def sync_method_binding(project_root: str | os.PathLike[str]) -> dict[str, Any]:
    root = _root(project_root)
    version, method_hash = _method_binding(root, required=False)
    state = _load(root)
    if state.get("method_hash") in (None, method_hash) and state.get("method_version") in (None, version):
        if state.get("method_hash") is None and method_hash is not None:
            state["method_hash"] = method_hash
            state["method_version"] = version
            _save(root, state)
        return {"changed": False, "method_version": version, "method_hash": method_hash}
    return invalidate_for_method_change(root, version, method_hash, reason="method binding changed")


def invalidate_for_method_change(
    project_root: str | os.PathLike[str], method_version: int | None, method_hash: str | None,
    *, reason: str = "research method changed",
) -> dict[str, Any]:
    root = _root(project_root)
    state = _load(root)
    prior = {"method_version": state.get("method_version"), "method_hash": state.get("method_hash")}
    affected: list[dict[str, str]] = []
    for bucket_name in (
        "ingestions", "evidence_graphs", "preregistrations", "statistical_audits",
        "reproducibility", "reviews", "record_health",
    ):
        for identifier, record in state.get(bucket_name, {}).items():
            if record.get("status") not in {"INVALIDATED", "HISTORICAL"}:
                record["prior_status"] = record.get("status")
                record["status"] = "INVALIDATED"
                record["invalidated_at"] = _now()
                record["invalidation_reason"] = reason
                affected.append({"component": bucket_name, "id": identifier})
    event = {
        "at": _now(), "reason": reason, "prior": prior,
        "new": {"method_version": method_version, "method_hash": method_hash},
        "affected": affected, "full_collision_rerun_required": True,
    }
    state["method_version"] = method_version
    state["method_hash"] = method_hash
    state.setdefault("invalidations", []).append(event)
    # Persist dependent invalidations before touching the separate paper-audit
    # file. A malformed audit file may block that audit's transition, but it
    # must never leave claim, preregistration, statistics, or run receipts PASS.
    _save(root, state)
    audit_state_path = root / ".research-guard" / "paper-audit-state.json"
    if audit_state_path.is_file():
        try:
            audit_state = json.loads(audit_state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IntegrityError(f"paper-audit state cannot be invalidated safely: {exc}") from exc
        if not isinstance(audit_state, dict):
            raise IntegrityError("paper-audit state cannot be invalidated safely")
        if audit_state.get("status") == "PASS" or audit_state.get("receipt") is not None:
            audit_state["status"] = "AUDIT_REQUIRED"
            audit_state["reason"] = f"research-integrity dependency invalidated: {reason}"
            audit_state["receipt"] = None
            _atomic(audit_state_path, audit_state)
            affected.append({"component": "paper_audit", "id": "paper-audit-state"})
            _save(root, state)
    return {"changed": prior != event["new"], **event}


def _read_text_document(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise IntegrityError("text-like document must be valid UTF-8") from exc
    lines = text.splitlines()
    raw_sections: list[dict[str, Any]] = []
    current: dict[str, Any] = {"heading": "Document", "level": 0, "start_line": 1, "text_lines": []}
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+?)\s*$") if path.suffix.casefold() in {".md", ".qmd"} else re.compile(r"^\\(section|subsection|subsubsection)\*?\{(.+?)\}\s*$")
    for number, line in enumerate(lines, 1):
        match = heading_pattern.match(line)
        if match:
            if current["text_lines"] or current["heading"] != "Document":
                raw_sections.append(current)
            if path.suffix.casefold() in {".md", ".qmd"}:
                level, heading = len(match.group(1)), match.group(2)
            else:
                level = {"section": 1, "subsection": 2, "subsubsection": 3}[match.group(1)]
                heading = match.group(2)
            current = {"heading": heading, "level": level, "start_line": number, "text_lines": []}
        else:
            current["text_lines"].append((number, line))
    raw_sections.append(current)
    sections: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    formulas: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    figures: list[dict[str, Any]] = []
    block_index = 0
    for section_index, raw_section in enumerate(raw_sections, 1):
        content_lines: list[tuple[int, str]] = raw_section.pop("text_lines")
        section_id = f"sec-{section_index:04d}"
        raw_text = "\n".join(value for _, value in content_lines)
        base_line = content_lines[0][0] if content_lines else int(raw_section["start_line"])
        section = {
            **raw_section, "section_id": section_id, "text": raw_text.strip(),
            "end_line": content_lines[-1][0] if content_lines else int(raw_section["start_line"]),
            "locator": {
                "start_line": int(raw_section["start_line"]),
                "end_line": content_lines[-1][0] if content_lines else int(raw_section["start_line"]),
            },
        }
        sections.append(section)

        paragraph_lines: list[tuple[int, str]] = []

        def flush_paragraph() -> None:
            nonlocal block_index
            if not paragraph_lines:
                return
            content = " ".join(value for _, value in paragraph_lines).strip()
            if content:
                block_index += 1
                blocks.append({
                    "block_id": f"blk-{block_index:06d}", "kind": "paragraph", "text": content,
                    "locator": {
                        "section_id": section_id,
                        "start_line": paragraph_lines[0][0], "end_line": paragraph_lines[-1][0],
                    },
                })
            paragraph_lines.clear()

        for line_number, line in content_lines:
            if line.strip():
                paragraph_lines.append((line_number, line))
            else:
                flush_paragraph()
        flush_paragraph()

        def span_locator(match: re.Match[str]) -> dict[str, Any]:
            return {
                "section_id": section_id,
                "start_line": base_line + raw_text[:match.start()].count("\n"),
                "end_line": base_line + raw_text[:match.end()].count("\n"),
            }

        for match in re.finditer(r"\\cite\w*\{([^}]+)\}|\[@([^\]]+)\]", raw_text):
            keys = (match.group(1) or match.group(2) or "").split(",")
            citations.extend({
                "key": key.strip().lstrip("@"), "section_id": section_id,
                "locator": span_locator(match),
            } for key in keys if key.strip())
        for match in re.finditer(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]|\\begin\{equation\*?\}(.+?)\\end\{equation\*?\}", raw_text, re.S):
            formulas.append({
                "formula_id": f"formula-{len(formulas)+1:04d}",
                "text": next(value for value in match.groups() if value), "section_id": section_id,
                "locator": span_locator(match),
            })
        for match in re.finditer(r"(?m)^(?:\s*\|.+\|\s*(?:\n|$))+", raw_text):
            tables.append({
                "table_id": f"table-{len(tables)+1:04d}", "section_id": section_id,
                "locator": span_locator(match),
            })
        for match in re.finditer(r"\\begin\{tabular.*?\\end\{tabular\}", raw_text, re.S):
            tables.append({
                "table_id": f"table-{len(tables)+1:04d}", "section_id": section_id,
                "locator": span_locator(match),
            })
        for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)|\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", raw_text):
            figures.append({
                "figure_id": f"figure-{len(figures)+1:04d}",
                "target": match.group(1) or match.group(2), "section_id": section_id,
                "locator": span_locator(match),
            })
    return {
        "parser": "research-guard-text-v1", "parser_version": "1",
        "sections": sections, "blocks": blocks, "tables": tables, "figures": figures,
        "formulas": formulas, "citations": citations,
        "limitations": ["line-grounded text parser; no visual layout or OCR authority"],
    }


def _read_pdf(path: Path) -> dict[str, Any]:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise IntegrityError("PDF ingestion requires the bundled pypdf component") from exc
    reader = PdfReader(str(path))
    sections: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        section_id = f"page-{page_number:04d}"
        sections.append({
            "section_id": section_id, "heading": f"Page {page_number}", "level": 0,
            "page_start": page_number, "page_end": page_number, "text": text,
            "locator": {"page_start": page_number, "page_end": page_number},
        })
        for paragraph in re.split(r"\n\s*\n", text):
            content = " ".join(paragraph.split())
            if content:
                blocks.append({
                    "block_id": f"blk-{len(blocks)+1:06d}", "kind": "paragraph", "text": content,
                    "locator": {"page": page_number, "section_id": section_id},
                })
    return {
        "parser": "pypdf", "parser_version": getattr(__import__("pypdf"), "__version__", "unknown"),
        "sections": sections, "blocks": blocks, "tables": [], "figures": [], "formulas": [], "citations": [],
        "limitations": [
            "native PDF text extraction only; reading order, tables, figures, formulas, and OCR require an optional structured parser",
        ],
    }


def _validate_locator(locator: Any, label: str) -> None:
    if not isinstance(locator, dict) or not locator:
        raise IntegrityError(f"{label} lacks locator provenance")
    supported = {"page", "page_start", "start_line", "xpath", "xml_id", "json_pointer"}
    if not any(key in locator for key in supported):
        raise IntegrityError(
            f"{label} locator needs page/page_start, start_line, xpath, xml_id, or json_pointer"
        )
    if "bbox" in locator:
        bbox = locator["bbox"]
        if not isinstance(bbox, list) or len(bbox) != 4 or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in bbox):
            raise IntegrityError(f"{label} bbox must contain four finite numbers")


def _json_pointer_value(document: Any, pointer: str, label: str) -> Any:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise IntegrityError(f"{label} json_pointer must start with /")
    current = document
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                raise IntegrityError(f"{label} json_pointer does not resolve")
            current = current[token]
        elif isinstance(current, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", token):
                raise IntegrityError(f"{label} json_pointer array index is invalid")
            index = int(token)
            if index >= len(current):
                raise IntegrityError(f"{label} json_pointer does not resolve")
            current = current[index]
        else:
            raise IntegrityError(f"{label} json_pointer traverses a scalar")
    return current


def _located_utf8_excerpt(source_text: str, locator: dict[str, Any], label: str) -> str:
    if "json_pointer" in locator:
        try:
            document = json.loads(source_text)
        except json.JSONDecodeError as exc:
            raise IntegrityError(f"{label} json_pointer requires a JSON source") from exc
        value = _json_pointer_value(document, locator["json_pointer"], label)
        return value if isinstance(value, str) else _canonical(value)
    if "start_line" in locator:
        start = locator["start_line"]
        end = locator.get("end_line", start)
        if (
            not isinstance(start, int) or isinstance(start, bool) or start < 1
            or not isinstance(end, int) or isinstance(end, bool) or end < start
        ):
            raise IntegrityError(f"{label} line locator requires positive ordered integers")
        lines = source_text.splitlines()
        if end > len(lines):
            raise IntegrityError(f"{label} line locator exceeds the source")
        return "\n".join(lines[start - 1:end])
    raise IntegrityError(f"{label} requires a verifiable json_pointer or line locator")


def _normalize_external_document(payload: Any, backend: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise IntegrityError("external parser output must be a JSON object")
    sections = payload.get("sections")
    blocks = payload.get("blocks")
    if not isinstance(sections, list) or not isinstance(blocks, list):
        raise IntegrityError("external parser output requires sections and blocks arrays")
    normalized_sections: list[dict[str, Any]] = []
    section_ids: set[str] = set()
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise IntegrityError(f"external parser section {index} is invalid")
        _validate_locator(section.get("locator"), f"external parser section {index}")
        section_id = _identifier(section.get("section_id") or f"section-{index + 1:04d}", "section_id")
        if section_id in section_ids:
            raise IntegrityError(f"external parser section {index} duplicates section_id")
        section_ids.add(section_id)
        normalized_sections.append({**section, "section_id": section_id})
    normalized_blocks: list[dict[str, Any]] = []
    block_ids: set[str] = set()
    for index, block in enumerate(blocks):
        if not isinstance(block, dict) or not str(block.get("text") or "").strip():
            raise IntegrityError(f"external parser block {index} lacks text")
        _validate_locator(block.get("locator"), f"external parser block {index}")
        block_id = _identifier(block.get("block_id") or f"blk-{index + 1:06d}", "block_id")
        if block_id in block_ids:
            raise IntegrityError(f"external parser block {index} duplicates block_id")
        block_ids.add(block_id)
        normalized_blocks.append({**block, "block_id": block_id})
    for collection in ("tables", "figures", "formulas", "citations"):
        values = payload.get(collection) or []
        if not isinstance(values, list):
            raise IntegrityError(f"external parser {collection} must be an array")
        for index, value in enumerate(values):
            if not isinstance(value, dict):
                raise IntegrityError(f"external parser {collection} item {index} is invalid")
            _validate_locator(value.get("locator"), f"external parser {collection} item {index}")
    return {
        "parser": backend, "parser_version": str(payload.get("parser_version") or "external"),
        "sections": normalized_sections, "blocks": normalized_blocks,
        "tables": payload.get("tables") if isinstance(payload.get("tables"), list) else [],
        "figures": payload.get("figures") if isinstance(payload.get("figures"), list) else [],
        "formulas": payload.get("formulas") if isinstance(payload.get("formulas"), list) else [],
        "citations": payload.get("citations") if isinstance(payload.get("citations"), list) else [],
        "limitations": payload.get("limitations") if isinstance(payload.get("limitations"), list) else [],
    }


def ingest_document(
    project_root: str, document_path: str, document_id: str, *, parser_backend: str = "auto",
    parser_output_path: str | None = None, source_url: str | None = None,
) -> dict[str, Any]:
    root = _root(project_root)
    sync_method_binding(root)
    version, method_hash = _method_binding(root)
    source = _project_file(root, document_path, "document")
    identifier = _identifier(document_id, "document_id")
    backend = str(parser_backend or "auto").casefold()
    if backend in {"docling", "grobid", "mineru", "marker"}:
        if not parser_output_path:
            raise IntegrityError(f"{backend} adapter requires a project-local normalized parser_output_path")
        output = _project_file(root, parser_output_path, "parser output")
        try:
            parsed = _normalize_external_document(json.loads(output.read_text(encoding="utf-8")), backend)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IntegrityError(f"external parser output is invalid: {exc}") from exc
        parser_output = {"path": output.relative_to(root).as_posix(), "sha256": _sha(output)}
    elif source.suffix.casefold() == ".pdf":
        parsed = _read_pdf(source)
        parser_output = None
    elif source.suffix.casefold() in {".md", ".qmd", ".tex", ".txt"}:
        parsed = _read_text_document(source)
        parser_output = None
    else:
        raise IntegrityError("supported core inputs are PDF, Markdown, LaTeX, and UTF-8 text; use a normalized external adapter for other formats")
    if source_url:
        source_url = _https(source_url, "source_url")
    stable_record = {
        "schema_version": SCHEMA_VERSION, "document_id": identifier, "status": "PASS",
        "method_version": version, "method_hash": method_hash,
        "source": {"path": source.relative_to(root).as_posix(), "sha256": _sha(source), "bytes": source.stat().st_size, "url": source_url},
        "parser_output": parser_output, "parsed": parsed,
    }
    record = {**stable_record, "document_hash": _digest(stable_record), "ingested_at": _now()}
    state = _load(root)
    existing = state["ingestions"].get(identifier)
    if existing:
        if existing.get("document_hash") == record["document_hash"]:
            return existing
        raise IntegrityError("ingestions are append-only; use a versioned document_id for a changed source")
    state["ingestions"][identifier] = record
    _save(root, state)
    return record


def document_status(project_root: str, document_id: str) -> dict[str, Any]:
    root = _root(project_root)
    state = _load(root)
    record = state["ingestions"].get(_identifier(document_id, "document_id"))
    if not record:
        raise IntegrityError("document ingestion is not registered")
    if record.get("status") == "INVALIDATED":
        return record
    reason = None
    try:
        source = _project_file(root, record["source"]["path"], "ingested document")
        if _sha(source) != record["source"]["sha256"]:
            reason = "ingested source changed"
        if not reason and record.get("parser_output"):
            output = _project_file(root, record["parser_output"]["path"], "parser output")
            if _sha(output) != record["parser_output"]["sha256"]:
                reason = "parser output changed"
    except IntegrityError as exc:
        reason = str(exc)
    if reason:
        record["prior_status"] = record.get("status")
        record["status"] = "INVALIDATED"
        record["invalidated_at"] = _now()
        record["invalidation_reason"] = reason
        _save(root, state)
    return record


def register_claim_evidence(
    project_root: str, graph_id: str, claims: list[dict[str, Any]], evidence: list[dict[str, Any]],
    edges: list[dict[str, Any]], *, selected_by: str,
) -> dict[str, Any]:
    if selected_by != "user":
        raise IntegrityError("claim-evidence submission must be selected_by=user")
    root = _root(project_root)
    sync_method_binding(root)
    version, method_hash = _method_binding(root)
    identifier = _identifier(graph_id, "graph_id")
    if not claims or not evidence or not edges:
        raise IntegrityError("claims, evidence, and edges must all be non-empty")
    claim_map: dict[str, dict[str, Any]] = {}
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise IntegrityError(f"claim {index} is invalid")
        claim_id = _identifier(claim.get("claim_id"), "claim_id")
        if claim_id in claim_map or not str(claim.get("text") or "").strip():
            raise IntegrityError(f"claim {index} is missing text or duplicates an ID")
        claim_map[claim_id] = {**claim, "claim_id": claim_id}
    evidence_map: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            raise IntegrityError(f"evidence {index} is invalid")
        evidence_id = _identifier(item.get("evidence_id"), "evidence_id")
        if evidence_id in evidence_map:
            raise IntegrityError(f"duplicate evidence ID: {evidence_id}")
        kind = str(item.get("kind") or "").casefold()
        locator = item.get("locator")
        excerpt = " ".join(str(item.get("excerpt") or "").split())
        if kind not in {"literature", "raw_data", "code", "experiment", "registry"}:
            raise IntegrityError(f"evidence {evidence_id} has an invalid kind")
        if not isinstance(locator, dict) or not locator or not excerpt:
            raise IntegrityError(f"evidence {evidence_id} requires an exact locator and excerpt")
        source_hash = str(item.get("source_sha256") or "").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", source_hash):
            raise IntegrityError(f"evidence {evidence_id} requires source_sha256")
        if kind == "literature":
            primary_url = _https(item.get("primary_record_url"), f"evidence {evidence_id} primary_record_url")
            document_id = _identifier(item.get("document_id"), f"evidence {evidence_id} document_id")
            document = document_status(root, document_id)
            if document.get("status") != "PASS" or document["source"]["sha256"] != source_hash:
                raise IntegrityError(f"evidence {evidence_id} does not match a valid ingested document")
            block_id = str(locator.get("block_id") or "").strip()
            block = next(
                (value for value in document["parsed"]["blocks"] if value.get("block_id") == block_id), None,
            )
            submitted_locator = {key: value for key, value in locator.items() if key != "block_id"}
            if not block or _canonical(submitted_locator) != _canonical(block.get("locator", {})):
                raise IntegrityError(f"evidence {evidence_id} locator does not identify an ingested block")
            if " ".join(excerpt.split()).casefold() not in " ".join(str(block.get("text") or "").split()).casefold():
                raise IntegrityError(f"evidence {evidence_id} excerpt is absent from the located block")
        else:
            primary_url = (
                _https(item.get("primary_record_url"), f"evidence {evidence_id} primary_record_url")
                if kind == "registry" or item.get("primary_record_url") else None
            )
            source_path = _project_file(root, str(item.get("source_path") or ""), f"evidence {evidence_id} source_path")
            if _sha(source_path) != source_hash:
                raise IntegrityError(f"evidence {evidence_id} source hash does not match")
            if source_path.stat().st_size > 16 * 1024 ** 2:
                raise IntegrityError(
                    f"evidence {evidence_id} is too large for exact excerpt binding; register a project-local normalized extract"
                )
            try:
                source_text = source_path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise IntegrityError(
                    f"evidence {evidence_id} must use a UTF-8 normalized extract for exact excerpt binding"
                ) from exc
            located_text = _located_utf8_excerpt(source_text, locator, f"evidence {evidence_id}")
            if excerpt.casefold() not in " ".join(located_text.split()).casefold():
                raise IntegrityError(f"evidence {evidence_id} excerpt is absent from the located source extract")
        evidence_map[evidence_id] = {**item, "evidence_id": evidence_id, "kind": kind, "excerpt": excerpt, "primary_record_url": primary_url}
    edge_ids: set[str] = set()
    normalized_edges: list[dict[str, Any]] = []
    covered: dict[str, set[str]] = {claim_id: set() for claim_id in claim_map}
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise IntegrityError(f"edge {index} is invalid")
        claim_id = _identifier(edge.get("claim_id"), "claim_id")
        evidence_id = _identifier(edge.get("evidence_id"), "evidence_id")
        relation = str(edge.get("relation") or "").casefold()
        if claim_id not in claim_map or evidence_id not in evidence_map or relation not in ALLOWED_RELATIONS:
            raise IntegrityError(f"edge {index} references an unknown node or relation")
        rationale = " ".join(str(edge.get("rationale") or "").split())
        if len(rationale) < 20:
            raise IntegrityError(f"edge {index} needs a substantive rationale")
        edge_id = _digest({"claim_id": claim_id, "evidence_id": evidence_id, "relation": relation})[:20]
        if edge_id in edge_ids:
            raise IntegrityError(f"duplicate claim-evidence edge: {edge_id}")
        edge_ids.add(edge_id)
        covered[claim_id].add(relation)
        normalized_edges.append({**edge, "edge_id": edge_id, "claim_id": claim_id, "evidence_id": evidence_id, "relation": relation, "rationale": rationale})
    missing = [claim_id for claim_id, relations in covered.items() if not relations]
    if missing:
        raise IntegrityError(f"claims lack evidence edges: {', '.join(missing)}")
    ambiguous = [claim_id for claim_id, relations in covered.items() if "supports" in relations and "refutes" in relations]
    refuted = [claim_id for claim_id, relations in covered.items() if "refutes" in relations and "supports" not in relations]
    insufficient = [claim_id for claim_id, relations in covered.items() if relations == {"insufficient"}]
    if ambiguous:
        graph_status = "CONFLICT_REVIEW_REQUIRED"
    elif refuted:
        graph_status = "CLAIMS_REFUTED"
    elif insufficient:
        graph_status = "EVIDENCE_INSUFFICIENT"
    else:
        graph_status = "PASS"
    record = {
        "schema_version": SCHEMA_VERSION, "graph_id": identifier, "method_version": version,
        "method_hash": method_hash, "claims": list(claim_map.values()), "evidence": list(evidence_map.values()),
        "edges": normalized_edges, "status": graph_status,
        "ambiguous_claim_ids": ambiguous, "refuted_claim_ids": refuted,
        "insufficient_claim_ids": insufficient,
        "selected_by": selected_by, "registered_at": _now(),
    }
    record["graph_hash"] = _digest({key: value for key, value in record.items() if key != "registered_at"})
    state = _load(root)
    existing = state["evidence_graphs"].get(identifier)
    if existing:
        if existing.get("graph_hash") == record["graph_hash"]:
            return existing
        raise IntegrityError("claim-evidence graphs are append-only; use a versioned graph_id")
    state["evidence_graphs"][identifier] = record
    _save(root, state)
    return record


def register_preregistration(project_root: str, prereg_id: str, protocol: dict[str, Any], *, selected_by: str) -> dict[str, Any]:
    if selected_by != "user":
        raise IntegrityError("preregistration must be selected_by=user")
    required = (
        "research_questions", "hypotheses", "outcomes", "exclusions", "sample_size_basis", "analysis_plan",
        "missing_data", "multiplicity", "stopping_rule", "random_seed_policy",
    )
    missing = [field for field in required if protocol.get(field) in (None, "", [])]
    if missing:
        raise IntegrityError(f"preregistration protocol is missing: {', '.join(missing)}")
    for field in ("research_questions", "hypotheses", "outcomes", "exclusions"):
        value = protocol[field]
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            raise IntegrityError(f"preregistration {field} must be a non-empty array of non-empty strings")
    for field in ("sample_size_basis", "analysis_plan", "missing_data", "multiplicity", "stopping_rule", "random_seed_policy"):
        if not isinstance(protocol[field], str) or not protocol[field].strip():
            raise IntegrityError(f"preregistration {field} must be a non-empty string")
    root = _root(project_root)
    sync_method_binding(root)
    version, method_hash = _method_binding(root)
    identifier = _identifier(prereg_id, "prereg_id")
    state = _load(root)
    if identifier in state["preregistrations"]:
        raise IntegrityError("preregistrations are immutable; use a versioned prereg_id and preserve deviations")
    body = {
        "schema_version": SCHEMA_VERSION, "prereg_id": identifier, "method_version": version,
        "method_hash": method_hash, "protocol": protocol, "protocol_hash": _digest(protocol),
        "selected_by": selected_by, "frozen_at": _now(), "deviations": [], "status": "FROZEN",
    }
    body["receipt_hash"] = _digest(body)
    state["preregistrations"][identifier] = body
    _save(root, state)
    return body


def record_preregistration_deviation(
    project_root: str, prereg_id: str, deviation: dict[str, Any], *, selected_by: str,
) -> dict[str, Any]:
    if selected_by != "user":
        raise IntegrityError("a deviation decision must be selected_by=user")
    required = ("changed_field", "original", "replacement", "reason", "timing", "impact")
    missing = [field for field in required if deviation.get(field) in (None, "", [])]
    if missing:
        raise IntegrityError(f"deviation is missing: {', '.join(missing)}")
    root = _root(project_root)
    state = _load(root)
    record = state["preregistrations"].get(_identifier(prereg_id, "prereg_id"))
    if not record:
        raise IntegrityError("preregistration is not registered")
    if record.get("status") == "INVALIDATED":
        raise IntegrityError("invalidated preregistration cannot accept deviations; create a versioned preregistration")
    changed_field = str(deviation.get("changed_field") or "").strip()
    if changed_field not in record["protocol"]:
        raise IntegrityError("deviation changed_field is not present in the frozen protocol")
    entry = {**deviation, "changed_field": changed_field, "selected_by": selected_by, "recorded_at": _now()}
    entry["deviation_hash"] = _digest({key: value for key, value in entry.items() if key != "recorded_at"})
    if any(item.get("deviation_hash") == entry["deviation_hash"] for item in record["deviations"]):
        return record
    current_value = record["protocol"][changed_field]
    for prior in record["deviations"]:
        if prior.get("changed_field") == changed_field:
            current_value = prior.get("replacement")
    if _canonical(deviation["original"]) != _canonical(current_value):
        raise IntegrityError("deviation original does not match the frozen value or latest declared replacement")
    if _canonical(deviation["replacement"]) == _canonical(current_value):
        raise IntegrityError("deviation replacement must differ from the current declared value")
    record["deviations"].append(entry)
    record["status"] = "DEVIATIONS_DECLARED"
    record["receipt_hash"] = _digest({key: value for key, value in record.items() if key != "receipt_hash"})
    _save(root, state)
    return record


_STAT_PATTERN = re.compile(
    r"(?P<test>t|z|r|f|chi2|χ2|χ²|q)\s*\(\s*(?P<df1>\d+(?:\.\d+)?)"
    r"(?:\s*,\s*(?P<df2>\d+(?:\.\d+)?))?\s*\)\s*=\s*(?P<stat>-?\d+(?:\.\d+)?)"
    r"\s*,?\s*p\s*(?P<op><=|>=|<|>|=)\s*(?P<p>\.?\d+(?:\.\d+)?)",
    re.I,
)


def _regularized_gamma_q(a: float, x: float) -> float:
    if a <= 0 or x < 0:
        raise IntegrityError("invalid chi-square parameters")
    if x == 0:
        return 1.0
    eps = 3e-14
    gln = math.lgamma(a)
    if x < a + 1:
        term = 1.0 / a
        total = term
        ap = a
        for _ in range(200):
            ap += 1
            term *= x / ap
            total += term
            if abs(term) < abs(total) * eps:
                break
        return max(0.0, min(1.0, 1.0 - total * math.exp(-x + a * math.log(x) - gln)))
    b = x + 1 - a
    c = 1 / 1e-300
    d = 1 / b
    h = d
    for i in range(1, 201):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < 1e-300:
            d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < eps:
            break
    return max(0.0, min(1.0, math.exp(-x + a * math.log(x) - gln) * h))


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1, a - 1
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, 201):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 3e-14:
            break
    return h


def _regularized_beta(x: float, a: float, b: float) -> float:
    if not 0 <= x <= 1 or a <= 0 or b <= 0:
        raise IntegrityError("invalid beta-distribution parameters")
    if x in (0, 1):
        return x
    factor = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return factor * _beta_continued_fraction(a, b, x) / a
    return 1 - factor * _beta_continued_fraction(b, a, 1 - x) / b


def _p_value(test: str, statistic: float, df1: float, df2: float | None) -> float:
    kind = test.casefold().replace("χ", "chi").replace("²", "2")
    if kind == "z":
        return 2 * (1 - NormalDist().cdf(abs(statistic)))
    if kind == "t":
        x = df1 / (df1 + statistic * statistic)
        return _regularized_beta(x, df1 / 2, 0.5)
    if kind in {"chi2", "q"}:
        return _regularized_gamma_q(df1 / 2, statistic / 2)
    if kind == "f":
        if df2 is None:
            raise IntegrityError("F test requires two degrees of freedom")
        x = df2 / (df2 + df1 * statistic)
        return _regularized_beta(x, df2 / 2, df1 / 2)
    if kind == "r":
        if abs(statistic) >= 1 or df1 <= 0:
            raise IntegrityError("correlation requires |r| < 1 and positive df")
        t_value = statistic * math.sqrt(df1 / (1 - statistic * statistic))
        x = df1 / (df1 + t_value * t_value)
        return _regularized_beta(x, df1 / 2, 0.5)
    raise IntegrityError(f"unsupported statistical test: {test}")


def _reported_consistent(operator: str, reported: float, computed: float, decimals: int) -> bool:
    tolerance = 0.5 * (10 ** -decimals)
    if operator == "=":
        return abs(reported - computed) <= tolerance
    if operator == "<":
        return computed < reported + tolerance
    if operator == "<=":
        return computed <= reported + tolerance
    if operator == ">":
        return computed > reported - tolerance
    return computed >= reported - tolerance


def audit_statistics(
    project_root: str, audit_id: str, *, text: str | None = None, source_path: str | None = None,
    alpha: float = 0.05, robustness_cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not 0 < float(alpha) < 1:
        raise IntegrityError("alpha must be between zero and one")
    root = _root(project_root)
    sync_method_binding(root)
    version, method_hash = _method_binding(root)
    identifier = _identifier(audit_id, "audit_id")
    if source_path:
        source = _project_file(root, source_path, "statistical source")
        try:
            content = source.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise IntegrityError("statistical source must be UTF-8 text") from exc
        source_record = {"path": source.relative_to(root).as_posix(), "sha256": _sha(source)}
    else:
        content = str(text or "")
        source_record = {"inline_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}
    if not content.strip() and not robustness_cases:
        raise IntegrityError("statistical audit requires report text, a source path, or robustness cases")
    checks: list[dict[str, Any]] = []
    for match in _STAT_PATTERN.finditer(content):
        test = match.group("test")
        df1 = float(match.group("df1"))
        df2 = float(match.group("df2")) if match.group("df2") else None
        statistic = float(match.group("stat"))
        reported = float(match.group("p"))
        operator = match.group("op")
        decimals = len(match.group("p").split(".", 1)[1]) if "." in match.group("p") else 0
        try:
            computed = _p_value(test, statistic, df1, df2)
            consistent = _reported_consistent(operator, reported, computed, decimals)
            if operator == "=":
                reported_sig: bool | None = reported < alpha
            elif operator in {"<", "<="}:
                reported_sig = True if reported <= alpha else None
            else:
                reported_sig = False if reported >= alpha else None
            computed_sig = computed < alpha
            checks.append({
                "text": match.group(0), "test": test.casefold(), "df1": df1, "df2": df2,
                "statistic": statistic, "reported_operator": operator, "reported_p": reported,
                "computed_p": computed, "consistent": consistent,
                "reported_significance": reported_sig,
                "decision_error": reported_sig is not None and reported_sig != computed_sig,
                "span": [match.start(), match.end()],
            })
        except IntegrityError as exc:
            checks.append({"text": match.group(0), "status": "NOT_RECOMPUTED", "reason": str(exc), "span": [match.start(), match.end()]})
    inconsistent = [item for item in checks if item.get("consistent") is False]
    decision_errors = [item for item in checks if item.get("decision_error")]
    not_recomputed = [item for item in checks if item.get("status") == "NOT_RECOMPUTED"]
    robustness: list[dict[str, Any]] = []
    for index, case in enumerate(robustness_cases or []):
        if not isinstance(case, dict):
            raise IntegrityError(f"robustness case {index} is invalid")
        case_id = _identifier(case.get("case_id"), "robustness case_id")
        try:
            baseline = float(case["baseline_estimate"])
            alternative = float(case["alternative_estimate"])
        except (KeyError, TypeError, ValueError) as exc:
            raise IntegrityError(f"robustness case {case_id} requires numeric estimates") from exc
        if not math.isfinite(baseline) or not math.isfinite(alternative):
            raise IntegrityError(f"robustness case {case_id} estimates must be finite")
        absolute_change = abs(alternative - baseline)
        relative_change = absolute_change / abs(baseline) if baseline != 0 else None
        tolerance_abs = float(case["tolerance_abs"]) if case.get("tolerance_abs") is not None else None
        tolerance_relative = float(case["tolerance_relative"]) if case.get("tolerance_relative") is not None else None
        if tolerance_abs is None and tolerance_relative is None:
            raise IntegrityError(f"robustness case {case_id} requires an absolute or relative tolerance")
        if (
            tolerance_abs is not None and (not math.isfinite(tolerance_abs) or tolerance_abs < 0)
        ) or (
            tolerance_relative is not None and (not math.isfinite(tolerance_relative) or tolerance_relative < 0)
        ):
            raise IntegrityError(f"robustness case {case_id} tolerance must be non-negative")
        sign_flip = baseline * alternative < 0
        intervals = {}
        interval_crossing_change = False
        for label in ("baseline_interval", "alternative_interval"):
            raw = case.get(label)
            if raw is not None:
                if not isinstance(raw, list) or len(raw) != 2:
                    raise IntegrityError(f"robustness case {case_id} {label} must be [lower, upper]")
                bounds = [float(raw[0]), float(raw[1])]
                if not all(math.isfinite(value) for value in bounds) or bounds[0] > bounds[1]:
                    raise IntegrityError(f"robustness case {case_id} {label} must contain finite ordered bounds")
                intervals[label] = bounds
        if len(intervals) == 2:
            interval_crossing_change = (
                intervals["baseline_interval"][0] <= 0 <= intervals["baseline_interval"][1]
            ) != (
                intervals["alternative_interval"][0] <= 0 <= intervals["alternative_interval"][1]
            )
        within_abs = tolerance_abs is None or absolute_change <= tolerance_abs
        within_relative = tolerance_relative is None or (relative_change is not None and relative_change <= tolerance_relative)
        passed = within_abs and within_relative and not sign_flip and not interval_crossing_change
        robustness.append({
            "case_id": case_id, "baseline_estimate": baseline, "alternative_estimate": alternative,
            "absolute_change": absolute_change, "relative_change": relative_change,
            "tolerance_abs": tolerance_abs, "tolerance_relative": tolerance_relative,
            "sign_flip": sign_flip, "interval_crossing_change": interval_crossing_change,
            "intervals": intervals, "passed": passed,
        })
    robustness_issues = [item for item in robustness if not item["passed"]]
    has_checks = bool(checks or robustness)
    status = (
        "PASS" if has_checks and not inconsistent and not decision_errors and not not_recomputed and not robustness_issues
        else ("NO_CHECKABLE_STATISTICS" if not has_checks else "ISSUES_FOUND")
    )
    record = {
        "schema_version": SCHEMA_VERSION, "audit_id": identifier, "method_version": version,
        "method_hash": method_hash, "source": source_record, "alpha": float(alpha), "checks": checks,
        "robustness_cases": robustness, "robustness_issue_count": len(robustness_issues),
        "status": status, "inconsistency_count": len(inconsistent), "decision_error_count": len(decision_errors),
        "not_recomputed_count": len(not_recomputed),
        "limitations": ["APA-like t, z, r, F, chi-square, and Q reports plus declared estimate-sensitivity cases only; recomputation is not a design-validity judgment"],
        "audited_at": _now(),
    }
    record["audit_hash"] = _digest({key: value for key, value in record.items() if key != "audited_at"})
    state = _load(root)
    existing = state["statistical_audits"].get(identifier)
    if existing:
        if existing.get("audit_hash") == record["audit_hash"]:
            return existing
        raise IntegrityError("statistical audits are append-only; use a versioned audit_id")
    state["statistical_audits"][identifier] = record
    _save(root, state)
    return record


def _reproducibility_plan_payload(record: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "schema_version", "run_id", "method_version", "method_hash", "command",
        "working_directory", "inputs", "outputs", "parameters", "seeds", "environment",
        "runtime_fingerprint", "executable", "expected_checks", "selected_by", "planned_at",
    )
    payload = {key: record.get(key) for key in keys}
    payload["status"] = "EXECUTION_REQUIRED"
    payload["execution"] = None
    return payload


def _verify_reproducibility_hashes(record: dict[str, Any]) -> None:
    if _digest(_reproducibility_plan_payload(record)) != record.get("plan_hash"):
        raise IntegrityError("reproducibility plan hash does not match its frozen contract")
    execution = record.get("execution")
    if execution is not None:
        if not isinstance(execution, dict):
            raise IntegrityError("reproducibility execution receipt is invalid")
        stable = {key: value for key, value in execution.items() if key != "execution_hash"}
        if _digest(stable) != execution.get("execution_hash"):
            raise IntegrityError("reproducibility execution hash does not match its receipt")


def register_reproducibility_plan(project_root: str, run_id: str, plan: dict[str, Any], *, selected_by: str) -> dict[str, Any]:
    if selected_by != "user":
        raise IntegrityError("reproducibility execution plans must be selected_by=user")
    required = ("command", "working_directory", "inputs", "outputs", "parameters", "seeds", "environment", "expected_checks")
    missing = [field for field in required if plan.get(field) in (None, "", [])]
    if missing:
        raise IntegrityError(f"reproducibility plan is missing: {', '.join(missing)}")
    root = _root(project_root)
    sync_method_binding(root)
    version, method_hash = _method_binding(root)
    identifier = _identifier(run_id, "run_id")
    working = _project_file(root, str(plan["working_directory"]), "working_directory", required=False)
    if not working.is_dir():
        raise IntegrityError("working_directory must be an existing project directory")
    command = plan["command"]
    if isinstance(command, str):
        command = shlex.split(command, posix=False)
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        raise IntegrityError("command must be a non-empty argv array or string")
    if any(re.search(r"[;&|><`\r\n]", item) for item in command):
        raise IntegrityError("command tokens must not contain shell control operators")
    executable = _executable_receipt(command[0], working)
    inputs = []
    for item in plan["inputs"]:
        path = _project_file(root, str(item), "reproducibility input")
        inputs.append({"path": path.relative_to(root).as_posix(), "sha256": _sha(path), "bytes": path.stat().st_size})
    outputs = []
    if not isinstance(plan["outputs"], list) or not all(isinstance(item, str) and item.strip() for item in plan["outputs"]):
        raise IntegrityError("outputs must be a non-empty array of project-relative paths")
    for item in plan["outputs"]:
        path = _project_file(root, str(item), "reproducibility output", required=False)
        outputs.append(path.relative_to(root).as_posix())
    if len(set(outputs)) != len(outputs):
        raise IntegrityError("reproducibility outputs must be unique")
    if not isinstance(plan["parameters"], dict) or not isinstance(plan["environment"], dict):
        raise IntegrityError("parameters and environment must be objects")
    if not isinstance(plan["seeds"], list) or not plan["seeds"] or not all(isinstance(value, int) and not isinstance(value, bool) for value in plan["seeds"]):
        raise IntegrityError("seeds must be a non-empty array of integers")
    if len(set(plan["seeds"])) != len(plan["seeds"]):
        raise IntegrityError("seeds must be unique")
    try:
        _canonical(plan["parameters"])
        _canonical(plan["environment"])
    except (TypeError, ValueError) as exc:
        raise IntegrityError("parameters and environment must contain canonical JSON values") from exc
    expected_checks = _validate_expected_checks(root, outputs, plan["expected_checks"])
    body = {
        "schema_version": SCHEMA_VERSION, "run_id": identifier, "method_version": version,
        "method_hash": method_hash, "command": command, "working_directory": working.relative_to(root).as_posix(),
        "inputs": inputs, "outputs": outputs, "parameters": plan["parameters"], "seeds": plan["seeds"],
        "environment": plan["environment"], "runtime_fingerprint": _runtime_fingerprint(),
        "executable": executable, "expected_checks": expected_checks,
        "selected_by": selected_by, "status": "EXECUTION_REQUIRED", "planned_at": _now(), "execution": None,
    }
    body["plan_hash"] = _digest(_reproducibility_plan_payload(body))
    state = _load(root)
    if identifier in state["reproducibility"]:
        raise IntegrityError("reproducibility plans are append-only; use a versioned run_id")
    state["reproducibility"][identifier] = body
    _save(root, state)
    return body


def _runtime_fingerprint() -> dict[str, str]:
    return {
        "system": platform.system(), "release": platform.release(), "machine": platform.machine(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
    }


def _executable_receipt(token: str, working: Path) -> dict[str, Any]:
    candidate = Path(token)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    elif any(separator in token for separator in ("/", "\\")):
        resolved = (working / candidate).resolve()
    else:
        found = shutil.which(token)
        if not found:
            raise IntegrityError(f"reproducibility command executable is not resolvable: {token}")
        resolved = Path(found).resolve()
    if not resolved.is_file():
        raise IntegrityError(f"reproducibility command executable is not a file: {token}")
    return {"path": str(resolved), "sha256": _sha(resolved), "bytes": resolved.stat().st_size}


def _validate_expected_checks(root: Path, outputs: list[str], checks: Any) -> list[dict[str, Any]]:
    if not isinstance(checks, list) or not checks:
        raise IntegrityError("expected_checks must be a non-empty array")
    supported = {"exit_code", "output_exists", "output_sha256"}
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(checks):
        if not isinstance(raw, dict) or raw.get("kind") not in supported:
            raise IntegrityError(f"expected check {index} must use one of: {', '.join(sorted(supported))}")
        kind = raw["kind"]
        if kind == "exit_code":
            try:
                value = int(raw.get("value", 0))
            except (TypeError, ValueError) as exc:
                raise IntegrityError(f"expected check {index} exit code must be an integer") from exc
            normalized.append({"kind": kind, "value": value})
            continue
        path = _project_file(root, str(raw.get("path") or ""), f"expected check {index} path", required=False)
        relative = path.relative_to(root).as_posix()
        if relative not in outputs:
            raise IntegrityError(f"expected check {index} must reference a declared output")
        item = {"kind": kind, "path": relative}
        if kind == "output_sha256":
            expected_hash = str(raw.get("sha256") or "").lower()
            if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
                raise IntegrityError(f"expected check {index} requires a SHA-256 value")
            item["sha256"] = expected_hash
        normalized.append(item)
    return normalized


def _evaluate_expected_checks(root: Path, expected: list[dict[str, Any]], exit_code: int) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for check in expected:
        kind = check["kind"]
        if kind == "exit_code":
            observed: Any = exit_code
            passed = exit_code == int(check["value"])
        else:
            output = _project_file(root, check["path"], "expected output", required=False)
            if kind == "output_exists":
                observed = output.is_file()
                passed = bool(observed)
            else:
                observed = _sha(output) if output.is_file() else None
                passed = observed == check["sha256"]
        checks.append({**check, "passed": passed, "observed": observed})
    return checks


def _finalize_reproducibility_result(
    project_root: str, run_id: str, result: dict[str, Any], *, managed_execution: bool,
) -> dict[str, Any]:
    root = _root(project_root)
    state = _load(root)
    record = state["reproducibility"].get(_identifier(run_id, "run_id"))
    if not record:
        raise IntegrityError("reproducibility plan is not registered")
    if record.get("status") == "INVALIDATED":
        raise IntegrityError("invalidated reproducibility plan cannot accept results; create a versioned plan")
    if record.get("execution"):
        raise IntegrityError("reproducibility results are append-only")
    _verify_reproducibility_hashes(record)
    required = (
        "exit_code", "started_at", "ended_at", "stdout_sha256", "stderr_sha256",
        "stdout_receipt", "stderr_receipt", "checks",
    )
    missing = [field for field in required if result.get(field) in (None, "", [])]
    if missing:
        raise IntegrityError(f"reproducibility result is missing: {', '.join(missing)}")
    if not re.fullmatch(r"[0-9a-f]{64}", str(result["stdout_sha256"]).lower()) or not re.fullmatch(r"[0-9a-f]{64}", str(result["stderr_sha256"]).lower()):
        raise IntegrityError("stdout/stderr receipts require SHA-256 values")
    if managed_execution:
        try:
            duration_seconds = float(result.get("duration_seconds"))
        except (TypeError, ValueError) as exc:
            raise IntegrityError("managed reproducibility requires measured duration_seconds") from exc
        if not math.isfinite(duration_seconds) or duration_seconds < 0:
            raise IntegrityError("managed reproducibility duration_seconds must be finite and non-negative")
        usage = result.get("resource_usage")
        required_usage = {
            "memory_metric", "peak_worker_bytes", "peak_orchestrator_bytes", "peak_owned_bytes",
            "worker_limit_bytes", "orchestrator_limit_bytes", "owned_limit_bytes",
        }
        if not isinstance(usage, dict) or not required_usage.issubset(usage):
            raise IntegrityError("managed reproducibility requires resource-guard memory telemetry")
        if usage.get("memory_metric") != "aggregate_working_set":
            raise IntegrityError("managed reproducibility memory telemetry uses an unsupported metric")
        numeric_usage = required_usage - {"memory_metric"}
        if any(
            not isinstance(usage.get(field), int) or isinstance(usage.get(field), bool) or usage[field] < 0
            for field in numeric_usage
        ):
            raise IntegrityError("managed reproducibility memory telemetry is invalid")
        from resource_guard import (
            ORCHESTRATOR_RESERVE_BYTES, OWNED_TASK_BUDGET_BYTES, WORKER_JOB_LIMIT_BYTES,
        )
        if (
            usage["worker_limit_bytes"] != WORKER_JOB_LIMIT_BYTES
            or usage["orchestrator_limit_bytes"] != ORCHESTRATOR_RESERVE_BYTES
            or usage["owned_limit_bytes"] != OWNED_TASK_BUDGET_BYTES
        ):
            raise IntegrityError("managed reproducibility resource profile does not match managed_standard")
        if (
            usage["peak_worker_bytes"] > usage["worker_limit_bytes"]
            or usage["peak_orchestrator_bytes"] > usage["orchestrator_limit_bytes"]
            or usage["peak_owned_bytes"] > usage["owned_limit_bytes"]
        ):
            raise IntegrityError("managed reproducibility resource telemetry exceeds the frozen profile")
    submitted_checks = result["checks"]
    if not isinstance(submitted_checks, list) or not submitted_checks:
        raise IntegrityError("reproducibility result requires explicit expected checks")
    expected = record["expected_checks"]
    submitted_definitions = [
        {key: value for key, value in item.items() if key not in {"passed", "observed"}}
        if isinstance(item, dict) else item
        for item in submitted_checks
    ]
    if submitted_definitions != expected:
        raise IntegrityError("submitted checks do not match the frozen expected_checks")
    stdout_receipt = _project_file(root, str(result["stdout_receipt"]), "stdout receipt")
    stderr_receipt = _project_file(root, str(result["stderr_receipt"]), "stderr receipt")
    if _sha(stdout_receipt) != str(result["stdout_sha256"]).lower():
        raise IntegrityError("stdout receipt hash does not match")
    if _sha(stderr_receipt) != str(result["stderr_sha256"]).lower():
        raise IntegrityError("stderr receipt hash does not match")
    exit_code = int(result["exit_code"])
    checks = _evaluate_expected_checks(root, expected, exit_code)
    output_records = []
    missing_outputs = []
    for relative in record["outputs"]:
        path = _project_file(root, relative, "reproducibility output", required=False)
        if path.is_file():
            output_records.append({"path": relative, "sha256": _sha(path), "bytes": path.stat().st_size})
        else:
            missing_outputs.append(relative)
    passed = exit_code == 0 and not missing_outputs and all(bool(item["passed"]) for item in checks)
    execution = {
        **result, "checks": checks, "outputs": output_records, "missing_outputs": missing_outputs,
        "execution_mode": "managed" if managed_execution else "external_submission", "submitted_at": _now(),
    }
    execution["execution_hash"] = _digest(execution)
    record["execution"] = execution
    record["status"] = "PASS" if passed and managed_execution else "REVIEW_REQUIRED" if passed else "FAILED"
    _save(root, state)
    return record


def submit_reproducibility_result(project_root: str, run_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Register externally produced receipts without claiming a managed rerun PASS."""
    return _finalize_reproducibility_result(project_root, run_id, result, managed_execution=False)


def execute_reproducibility(project_root: str, run_id: str, *, timeout: float = 1800.0) -> dict[str, Any]:
    """Execute a frozen argv plan through the shared RAM/job-object guard."""
    root = _root(project_root)
    sync_method_binding(root)
    state = _load(root)
    identifier = _identifier(run_id, "run_id")
    record = state["reproducibility"].get(identifier)
    if not record:
        raise IntegrityError("reproducibility plan is not registered")
    if record.get("status") == "INVALIDATED":
        raise IntegrityError("invalidated reproducibility plan cannot be executed; create a versioned plan")
    if record.get("execution"):
        raise IntegrityError("reproducibility results are append-only")
    _verify_reproducibility_hashes(record)
    current_inputs = []
    for item in record["inputs"]:
        path = _project_file(root, item["path"], "reproducibility input")
        current = {"path": item["path"], "sha256": _sha(path), "bytes": path.stat().st_size}
        current_inputs.append(current)
        if current != item:
            raise IntegrityError(f"reproducibility input changed after plan freeze: {item['path']}")
    expected = _validate_expected_checks(root, record["outputs"], record.get("expected_checks"))
    working = _project_file(root, record["working_directory"], "working_directory", required=False)
    current_runtime = _runtime_fingerprint()
    if current_runtime != record.get("runtime_fingerprint"):
        raise IntegrityError("runtime fingerprint changed after reproducibility plan freeze")
    current_executable = _executable_receipt(record["command"][0], working)
    if current_executable != record.get("executable"):
        raise IntegrityError("command executable changed after reproducibility plan freeze")
    occupied_outputs = []
    for relative in record["outputs"]:
        path = _project_file(root, relative, "reproducibility output", required=False)
        if path.is_file():
            occupied_outputs.append(relative)
    if occupied_outputs:
        raise IntegrityError(
            "managed reproducibility requires fresh versioned output paths; existing outputs: "
            + ", ".join(occupied_outputs)
        )
    from resource_guard import ResourceGuardError, run_managed
    started_at = _now()
    started_monotonic = time.monotonic()
    try:
        completed = run_managed(record["command"], cwd=working, timeout=float(timeout))
    except ResourceGuardError:
        raise
    ended_at = _now()
    duration_seconds = max(0.0, time.monotonic() - started_monotonic)
    receipt_dir = root / ".research-guard" / "reproducibility" / identifier
    receipt_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = receipt_dir / "stdout-tail.txt"
    stderr_path = receipt_dir / "stderr-tail.txt"
    stdout_path.write_text(completed.stdout or "", encoding="utf-8", newline="\n")
    stderr_path.write_text(completed.stderr or "", encoding="utf-8", newline="\n")
    checks = _evaluate_expected_checks(root, expected, completed.returncode)
    return _finalize_reproducibility_result(root, identifier, {
        "exit_code": completed.returncode,
        "started_at": started_at,
        "ended_at": ended_at,
        "stdout_sha256": _sha(stdout_path),
        "stderr_sha256": _sha(stderr_path),
        "stdout_receipt": stdout_path.relative_to(root).as_posix(),
        "stderr_receipt": stderr_path.relative_to(root).as_posix(),
        "capture_scope": "last_200000_bytes_per_stream",
        "checks": checks,
        "inputs_reverified": current_inputs,
        "duration_seconds": duration_seconds,
        "resource_usage": completed.resource_usage,
    }, managed_execution=True)


def _review_tokens(text: str) -> list[str]:
    return [value for value in re.findall(r"[a-z][a-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}", text.casefold()) if value]


def _score_review_candidates(
    records: list[dict[str, Any]], *, smoothing: float, prior_weight: float,
) -> list[dict[str, Any]]:
    """Score undecided records using the exact runtime model shared with SkillOpt."""
    if not 0.1 <= float(smoothing) <= 10:
        raise IntegrityError("active-review smoothing must be between 0.1 and 10")
    if not 0 <= float(prior_weight) <= 5:
        raise IntegrityError("active-review prior_weight must be between 0 and 5")
    include_counts: Counter[str] = Counter()
    exclude_counts: Counter[str] = Counter()
    for record in records:
        target = include_counts if record.get("decision") == "include" else exclude_counts if record.get("decision") == "exclude" else None
        if target is not None:
            target.update(set(_review_tokens(f"{record.get('title', '')} {record.get('abstract', '')}")))
    if not include_counts or not exclude_counts:
        raise IntegrityError("active-review ranking requires at least one user-labelled include and exclude example")
    vocabulary = set(include_counts) | set(exclude_counts)
    labelled = sum(1 for item in records if item.get("decision") in {"include", "exclude"})
    prior_include = (sum(1 for item in records if item.get("decision") == "include") + 1) / (labelled + 2)
    ranked = []
    for record in records:
        if record.get("decision") is not None:
            continue
        tokens = set(_review_tokens(f"{record.get('title', '')} {record.get('abstract', '')}"))
        score = prior_weight * math.log(prior_include / (1 - prior_include))
        for token in tokens & vocabulary:
            score += math.log((include_counts[token] + smoothing) / (exclude_counts[token] + smoothing))
        probability = 1 / (1 + math.exp(-max(-50.0, min(50.0, score))))
        ranked.append({
            "record_id": record["record_id"], "priority_score": score,
            "priority_probability": probability,
            "primary_record_url": record.get("primary_record_url"),
        })
    ranked.sort(key=lambda item: (-item["priority_score"], item["record_id"]))
    return ranked


def rank_systematic_review(project_root: str, review_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    root = _root(project_root)
    sync_method_binding(root)
    version, method_hash = _method_binding(root)
    identifier = _identifier(review_id, "review_id")
    if not records:
        raise IntegrityError("systematic-review ranking requires records")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise IntegrityError(f"review record {index} is invalid")
        record_id = _identifier(record.get("record_id"), "record_id")
        if record_id in seen:
            raise IntegrityError(f"duplicate review record: {record_id}")
        seen.add(record_id)
        title = " ".join(str(record.get("title") or "").split())
        abstract = " ".join(str(record.get("abstract") or "").split())
        if not title and not abstract:
            raise IntegrityError(f"review record {record_id} requires a title or abstract")
        primary_url = _https(record.get("primary_record_url"), f"record {record_id} primary_record_url")
        decision = record.get("decision")
        selected_by = record.get("selected_by")
        if decision not in (None, "include", "exclude", "maybe"):
            raise IntegrityError(f"record {record_id} has an invalid decision")
        if decision is not None and selected_by != "user":
            raise IntegrityError("only selected_by=user screening decisions are admissible")
        normalized.append({**record, "record_id": record_id, "title": title, "abstract": abstract, "primary_record_url": primary_url})
    smoothing, prior_weight = _active_review_tuning()
    ranked = _score_review_candidates(normalized, smoothing=smoothing, prior_weight=prior_weight)
    flow = {decision: sum(1 for item in normalized if item.get("decision") == decision) for decision in ("include", "exclude", "maybe")}
    body = {
        "schema_version": SCHEMA_VERSION, "review_id": identifier, "method_version": version,
        "method_hash": method_hash, "records": normalized, "ranking": ranked,
        "flow_counts": flow, "decision_owner": "user", "status": "PASS",
        "algorithm": "smoothed-token-log-odds-v1",
        "algorithm_parameters": {"smoothing": smoothing, "prior_weight": prior_weight},
        "ranked_at": _now(),
    }
    body["review_hash"] = _digest({key: value for key, value in body.items() if key != "ranked_at"})
    state = _load(root)
    existing = state["reviews"].get(identifier)
    if existing and existing.get("review_hash") != body["review_hash"]:
        raise IntegrityError("review rankings are append-only; use a versioned review_id")
    state["reviews"][identifier] = body
    _save(root, state)
    return body


def monitor_record_health(
    project_root: str, watch_id: str, doi: str, *, timeout: float = 20.0,
    fixture_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _root(project_root)
    sync_method_binding(root)
    version, method_hash = _method_binding(root)
    identifier = _identifier(watch_id, "watch_id")
    normalized_doi = _doi(doi)
    if fixture_record is None:
        from research_guard_core import _json_request  # local canonical network/evidence boundary
        payload = _json_request(f"https://api.crossref.org/works/{quote(normalized_doi, safe='')}", timeout=float(timeout))
        record = payload.get("message") if isinstance(payload, dict) else None
    else:
        record = fixture_record
    if not isinstance(record, dict):
        raise IntegrityError("Crossref record-health response is invalid")
    returned_doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", str(record.get("DOI") or normalized_doi), flags=re.I).lower()
    if returned_doi != normalized_doi:
        raise IntegrityError("Crossref record-health DOI does not match the requested DOI")
    updates = []
    for field in ("update-to", "updated-by"):
        raw = record.get(field) or []
        if not isinstance(raw, list):
            raise IntegrityError(f"Crossref {field} must be an array")
        for item in raw:
            if isinstance(item, dict):
                update_type = str(item.get("type") or item.get("label") or "update").casefold().replace("_", "-").replace(" ", "-")
                update_doi = str(item.get("DOI") or "").strip().lower()
                update_url = f"https://doi.org/{update_doi}" if re.match(r"^10\.\d{4,9}/\S+$", update_doi) else f"https://api.crossref.org/works/{quote(normalized_doi, safe='')}"
                updates.append({
                    "direction": field, "type": update_type, "label": item.get("label"),
                    "source": item.get("source"), "doi": update_doi or None,
                    "primary_record_url": update_url, "updated": item.get("updated"),
                })
    material = [item for item in updates if item["type"] in MATERIAL_UPDATE_TYPES or any(term in item["type"] for term in ("retract", "withdraw", "concern", "correct", "remov", "reinstate"))]
    snapshot = {
        "doi": normalized_doi, "doi_url": f"https://doi.org/{normalized_doi}",
        "crossref_record_url": f"https://api.crossref.org/works/{quote(normalized_doi, safe='')}",
        "title": (record.get("title") or [None])[0] if isinstance(record.get("title"), list) else record.get("title"),
        "updates": updates, "material_updates": material,
        "metadata_hash": _digest({key: record.get(key) for key in (
            "DOI", "title", "type", "subtype", "author", "publisher", "container-title",
            "issued", "published", "relation", "license", "link", "update-to", "updated-by",
        )}),
        "checked_at": _now(),
    }
    state = _load(root)
    previous = state["record_health"].get(identifier)
    if previous and previous.get("status") == "INVALIDATED":
        raise IntegrityError("invalidated record-health watch requires a versioned watch_id")
    changed = bool(previous and previous.get("current", {}).get("metadata_hash") != snapshot["metadata_hash"])
    status = "ACTION_REQUIRED" if material else "REVIEW_REQUIRED" if changed else "PASS"
    history = list(previous.get("history", [])) if previous else []
    if previous and changed:
        history.append(previous["current"])
    body = {
        "schema_version": SCHEMA_VERSION, "watch_id": identifier, "method_version": version,
        "method_hash": method_hash, "status": status, "changed": changed,
        "current": snapshot, "history": history,
        "dependent_receipts_invalidated": bool(changed or material),
    }
    body["watch_hash"] = _digest(body)
    state["record_health"][identifier] = body
    _save(root, state)
    if body["dependent_receipts_invalidated"]:
        audit_state_path = root / ".research-guard" / "paper-audit-state.json"
        if audit_state_path.is_file():
            try:
                audit_state = json.loads(audit_state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise IntegrityError(f"paper-audit state cannot be invalidated safely: {exc}") from exc
            if not isinstance(audit_state, dict):
                raise IntegrityError("paper-audit state cannot be invalidated safely")
            audit_state["status"] = "AUDIT_REQUIRED"
            audit_state["reason"] = f"scholarly record health changed for https://doi.org/{normalized_doi}"
            audit_state["receipt"] = None
            _atomic(audit_state_path, audit_state)
    return body


def _sync_integrity_inputs(root: Path, state: dict[str, Any]) -> bool:
    """Persistently invalidate PASS-like records whose hash-bound inputs drifted."""
    changed = False
    for document in state.get("ingestions", {}).values():
        if document.get("status") == "INVALIDATED":
            continue
        reason = None
        try:
            source = _project_file(root, document.get("source", {}).get("path"), "ingested document")
            if _sha(source) != document.get("source", {}).get("sha256"):
                reason = "ingested source hash changed"
            parser_output = document.get("parser_output")
            if not reason and parser_output:
                output = _project_file(root, parser_output.get("path"), "parser output")
                if _sha(output) != parser_output.get("sha256"):
                    reason = "parser output hash changed"
        except IntegrityError as exc:
            reason = str(exc)
        if reason:
            document["prior_status"] = document.get("status")
            document["status"] = "INVALIDATED"
            document["invalidated_at"] = _now()
            document["invalidation_reason"] = reason
            changed = True
    for graph in state.get("evidence_graphs", {}).values():
        if graph.get("status") in {"INVALIDATED", "HISTORICAL"}:
            continue
        for evidence in graph.get("evidence", []):
            reason = None
            if evidence.get("kind") == "literature":
                document = state.get("ingestions", {}).get(evidence.get("document_id"))
                if not document or document.get("status") == "INVALIDATED":
                    reason = "bound literature ingestion is missing or invalidated"
                elif document.get("source", {}).get("sha256") != evidence.get("source_sha256"):
                    reason = "bound literature source hash changed"
            else:
                try:
                    path = _project_file(root, evidence.get("source_path"), "evidence source")
                    if _sha(path) != evidence.get("source_sha256"):
                        reason = "bound evidence source hash changed"
                except IntegrityError as exc:
                    reason = str(exc)
            if reason:
                graph["prior_status"] = graph.get("status")
                graph["status"] = "INVALIDATED"
                graph["invalidated_at"] = _now()
                graph["invalidation_reason"] = reason
                changed = True
                break
    for record in state.get("statistical_audits", {}).values():
        source = record.get("source") or {}
        if record.get("status") in {"INVALIDATED", "HISTORICAL"} or not source.get("path"):
            continue
        reason = None
        try:
            path = _project_file(root, source["path"], "statistical source")
            if _sha(path) != source.get("sha256"):
                reason = "statistical source hash changed"
        except IntegrityError as exc:
            reason = str(exc)
        if reason:
            record["prior_status"] = record.get("status")
            record["status"] = "INVALIDATED"
            record["invalidated_at"] = _now()
            record["invalidation_reason"] = reason
            changed = True
    for record in state.get("reproducibility", {}).values():
        if record.get("status") in {"INVALIDATED", "HISTORICAL"}:
            continue
        reason = None
        try:
            _verify_reproducibility_hashes(record)
        except IntegrityError as exc:
            reason = str(exc)
        if not reason and record.get("status") == "EXECUTION_REQUIRED":
            continue
        outputs_to_check = record.get("execution", {}).get("outputs", []) if not reason else []
        for output in outputs_to_check:
            try:
                path = _project_file(root, output["path"], "reproducibility output")
                if _sha(path) != output.get("sha256"):
                    reason = "reproducibility output hash changed"
                    break
            except IntegrityError as exc:
                reason = str(exc)
                break
        if reason:
            record["prior_status"] = record.get("status")
            record["status"] = "INVALIDATED"
            record["invalidated_at"] = _now()
            record["invalidation_reason"] = reason
            changed = True
    if changed:
        _save(root, state)
    return changed


def integrity_status(project_root: str, component: str | None = None, identifier: str | None = None) -> dict[str, Any]:
    root = _root(project_root)
    sync_method_binding(root)
    state = _load(root)
    _sync_integrity_inputs(root, state)
    if component:
        bucket = str(component).casefold()
        if bucket not in state or not isinstance(state[bucket], dict):
            raise IntegrityError("unknown research-integrity component")
        if identifier:
            record = state[bucket].get(_identifier(identifier, "identifier"))
            if not record:
                raise IntegrityError("research-integrity record is not registered")
            return record
        return {"component": bucket, "records": state[bucket]}
    return state
