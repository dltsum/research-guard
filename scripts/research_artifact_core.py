from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


STATE_NAME = "research-artifacts.json"
ARTIFACT_TYPES = {"paper_card", "systematic_review", "experiment_log", "reviewer_response"}
PAPER_CARD_SECTIONS = [f"{index:02d}" for index in range(1, 17)]


class ArtifactError(ValueError):
    pass


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _root(value: str | os.PathLike[str]) -> Path:
    root = Path(value).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _path(root: Path) -> Path:
    return root / ".research-guard" / STATE_NAME


def _atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _load(root: Path) -> dict[str, Any]:
    path = _path(root)
    if not path.is_file():
        return {"schema_version": 1, "artifacts": {}, "ledger_hash": _digest({})}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"research artifact state is invalid: {exc}") from exc
    if value.get("ledger_hash") != _digest(value.get("artifacts", {})):
        raise ArtifactError("research artifact ledger integrity check failed")
    return value


def _save(root: Path, value: dict[str, Any]) -> None:
    value["ledger_hash"] = _digest(value["artifacts"])
    _atomic(_path(root), value)


def _id(value: Any) -> str:
    identifier = re.sub(r"[^a-z0-9_-]+", "-", str(value or "").casefold()).strip("-")
    if not identifier or len(identifier) > 96:
        raise ArtifactError("artifact_id is invalid")
    return identifier


def _files(root: Path, values: list[str] | None) -> list[dict[str, Any]]:
    if not values:
        raise ArtifactError("at least one source file is required")
    records: list[dict[str, Any]] = []
    for value in values:
        path = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ArtifactError(f"source file must stay inside project_root: {value}") from exc
        if not path.is_file():
            raise ArtifactError(f"source file does not exist: {relative}")
        records.append({"path": relative, "sha256": _sha(path), "bytes": path.stat().st_size})
    return sorted(records, key=lambda item: item["path"])


def _https(value: Any, label: str) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    if parsed.scheme.casefold() != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ArtifactError(f"{label} must be a credential-free clickable HTTPS URL")
    return text


def _require_fields(value: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if value.get(field) in (None, "", [])]
    if missing:
        raise ArtifactError(f"{label} is missing: {', '.join(missing)}")


def plan_research_artifact(
    project_root: str, artifact_type: str, artifact_id: str,
    source_files: list[str] | None, protocol: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _root(project_root)
    kind = str(artifact_type or "").casefold()
    if kind not in ARTIFACT_TYPES:
        raise ArtifactError(f"artifact_type must be one of {', '.join(sorted(ARTIFACT_TYPES))}")
    identifier = _id(artifact_id)
    sources = _files(root, source_files)
    protocol = dict(protocol or {})
    if kind == "systematic_review":
        _require_fields(protocol, (
            "research_question", "databases", "search_strings", "date_range", "inclusion_criteria",
            "exclusion_criteria", "deduplication_keys", "screening_stages", "reviewer_policy", "conflict_resolution",
        ), "systematic-review protocol")
    if kind == "experiment_log":
        _require_fields(protocol, ("experiment_id", "objective", "started_at", "operator"), "experiment-log protocol")
    if kind == "reviewer_response":
        _require_fields(protocol, ("venue", "decision_type", "response_mode", "length_limit"), "reviewer-response protocol")
    contracts = {
        "paper_card": {
            "required_sections": PAPER_CARD_SECTIONS,
            "locator_modes": ["page-grounded", "structure-grounded", "source-limited"],
            "boundary": "author claims, agent analysis, limitations, and ideas remain distinct",
        },
        "systematic_review": {
            "required_fields": ["records", "flow_counts"],
            "decision_owner": "user",
            "boundary": "search ranking cannot make inclusion or exclusion decisions",
        },
        "experiment_log": {
            "required_fields": ["materials", "parameters", "measurements", "observations", "anomalies"],
            "boundary": "raw observations are immutable and separate from interpretations",
        },
        "reviewer_response": {
            "required_fields": ["issues"],
            "boundary": "every concern is covered; changes and commitments require evidence",
        },
    }
    record = {
        "artifact_id": identifier, "artifact_type": kind, "status": "SUBMISSION_REQUIRED",
        "source_files": sources, "source_bundle_hash": _digest(sources), "protocol": protocol,
        "contract": contracts[kind], "planned_at": _now(), "submission": None,
    }
    record["plan_hash"] = _digest({key: record[key] for key in ("artifact_id", "artifact_type", "source_files", "protocol", "contract")})
    state = _load(root)
    previous = state["artifacts"].get(identifier)
    if previous and previous.get("plan_hash") == record["plan_hash"]:
        return previous
    state["artifacts"][identifier] = record
    _save(root, state)
    return record


def _validate_links(values: Any, label: str) -> None:
    if isinstance(values, dict):
        for key, value in values.items():
            if key in {"source_url", "evidence_url", "doi_url", "primary_record_url"}:
                _https(value, f"{label}.{key}")
            else:
                _validate_links(value, f"{label}.{key}")
    elif isinstance(values, list):
        for index, value in enumerate(values):
            _validate_links(value, f"{label}[{index}]")


def _validate_paper_card(value: dict[str, Any]) -> dict[str, Any]:
    source_record = value.get("source_record")
    if not isinstance(source_record, dict):
        raise ArtifactError("paper card requires a verified source_record")
    _require_fields(source_record, ("title", "primary_record_url", "verified_metadata"), "paper-card source_record")
    _https(source_record["primary_record_url"], "paper-card primary_record_url")
    sections = value.get("sections")
    if not isinstance(sections, list):
        raise ArtifactError("paper card sections must be a list")
    ids = [str(item.get("section_id") or "") for item in sections if isinstance(item, dict)]
    if ids != PAPER_CARD_SECTIONS:
        raise ArtifactError("paper card requires Sections 01-16 exactly once and in order")
    for item in sections:
        _require_fields(item, ("heading", "content", "locators"), f"paper-card section {item.get('section_id')}")
    mode = str(value.get("locator_mode") or "")
    if mode not in {"page-grounded", "structure-grounded", "source-limited"}:
        raise ArtifactError("paper card locator_mode is invalid")
    return {"section_count": 16, "locator_mode": mode, "primary_record_link": source_record["primary_record_url"]}


def _validate_systematic_review(value: dict[str, Any]) -> dict[str, Any]:
    records = value.get("records")
    if not isinstance(records, list) or not records:
        raise ArtifactError("systematic-review records must be a non-empty list")
    seen: set[str] = set()
    counts = {"include": 0, "exclude": 0, "maybe": 0}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ArtifactError(f"systematic-review record {index} is invalid")
        _require_fields(record, ("record_id", "title", "primary_record_url", "decision", "selected_by", "reason"), f"record {index}")
        record_id = str(record["record_id"])
        if record_id in seen:
            raise ArtifactError(f"duplicate systematic-review record: {record_id}")
        seen.add(record_id)
        _https(record["primary_record_url"], f"record {record_id} primary_record_url")
        decision = str(record["decision"]).casefold()
        if decision not in counts or record["selected_by"] != "user":
            raise ArtifactError("screening decisions must be include/exclude/maybe and selected_by=user")
        counts[decision] += 1
    flow = value.get("flow_counts")
    if not isinstance(flow, dict) or any(int(flow.get(key, -1)) != count for key, count in counts.items()):
        raise ArtifactError("flow_counts must exactly match recomputed screening decisions")
    return {"records": len(records), "recomputed_flow_counts": counts}


def _validate_experiment_log(value: dict[str, Any]) -> dict[str, Any]:
    _require_fields(value, ("materials", "parameters", "measurements", "observations"), "experiment log")
    if "anomalies" not in value or not isinstance(value["anomalies"], list):
        raise ArtifactError("experiment log requires an anomalies list, which may be empty")
    measurements = value["measurements"]
    if not isinstance(measurements, list) or not measurements:
        raise ArtifactError("experiment log needs at least one raw measurement")
    for index, measurement in enumerate(measurements):
        if not isinstance(measurement, dict):
            raise ArtifactError(f"measurement {index} is invalid")
        _require_fields(measurement, ("name", "value", "unit", "recorded_at", "source_file"), f"measurement {index}")
    if "interpretations" in value and not isinstance(value["interpretations"], list):
        raise ArtifactError("interpretations must be a separate list")
    return {"measurements": len(measurements), "raw_interpretation_separated": True}


def _validate_reviewer_response(value: dict[str, Any]) -> dict[str, Any]:
    issues = value.get("issues")
    if not isinstance(issues, list) or not issues:
        raise ArtifactError("reviewer response requires an issue board")
    seen: set[str] = set()
    for index, issue in enumerate(issues):
        if not isinstance(issue, dict):
            raise ArtifactError(f"review issue {index} is invalid")
        _require_fields(issue, ("issue_id", "reviewer", "raw_anchor", "status", "response"), f"issue {index}")
        if "evidence" not in issue or not isinstance(issue["evidence"], list):
            raise ArtifactError(f"reviewer issue {index} requires an evidence list, which may be empty while awaiting user input")
        issue_id = str(issue["issue_id"])
        if issue_id in seen:
            raise ArtifactError(f"duplicate reviewer issue: {issue_id}")
        seen.add(issue_id)
        if issue["status"] not in {"answered", "deferred_intentionally", "needs_user_input"}:
            raise ArtifactError(f"reviewer issue {issue_id} has an invalid status")
        if issue["status"] == "answered" and not issue["evidence"]:
            raise ArtifactError(f"answered reviewer issue {issue_id} needs evidence")
    ready = all(issue["status"] != "needs_user_input" for issue in issues)
    return {"issues": len(issues), "coverage_complete": True, "delivery_ready": ready}


def submit_research_artifact(project_root: str, artifact_id: str, plan_hash: str, artifact: dict[str, Any]) -> dict[str, Any]:
    root = _root(project_root)
    state = _load(root)
    identifier = _id(artifact_id)
    record = state["artifacts"].get(identifier)
    if not record or record.get("plan_hash") != str(plan_hash):
        raise ArtifactError("artifact plan is missing or stale")
    current_files = _files(root, [item["path"] for item in record["source_files"]])
    if current_files != record["source_files"]:
        raise ArtifactError("source files changed after artifact planning")
    if not isinstance(artifact, dict):
        raise ArtifactError("artifact must be an object")
    artifact_hash = _digest(artifact)
    previous_submission = record.get("submission")
    if previous_submission:
        if previous_submission.get("artifact_hash") == artifact_hash:
            return {"status": record["status"], "artifact_id": identifier, "artifact_type": record["artifact_type"], **previous_submission}
        raise ArtifactError("submitted research artifacts are append-only; plan a versioned artifact_id for revisions")
    validators = {
        "paper_card": _validate_paper_card,
        "systematic_review": _validate_systematic_review,
        "experiment_log": _validate_experiment_log,
        "reviewer_response": _validate_reviewer_response,
    }
    checks = validators[record["artifact_type"]](artifact)
    _validate_links(artifact, "artifact")
    record["submission"] = {"artifact": artifact, "checks": checks, "artifact_hash": artifact_hash, "submitted_at": _now()}
    record["status"] = "PASS" if checks.get("delivery_ready", True) else "USER_INPUT_REQUIRED"
    _save(root, state)
    return {"status": record["status"], "artifact_id": identifier, "artifact_type": record["artifact_type"], **record["submission"]}


def research_artifact_status(project_root: str, artifact_id: str, verify: bool = False) -> dict[str, Any]:
    root = _root(project_root)
    state = _load(root)
    identifier = _id(artifact_id)
    record = state["artifacts"].get(identifier)
    if not record:
        raise ArtifactError("research artifact is not registered")
    current = _files(root, [item["path"] for item in record["source_files"]])
    if current != record["source_files"]:
        return {"status": "INVALIDATED", "artifact_id": identifier, "reason": "source files changed"}
    if verify and record["status"] != "PASS":
        return {"status": record["status"], "artifact_id": identifier, "reason": "artifact has not passed its contract"}
    return record
