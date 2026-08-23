from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from research_guard_core import GuardError, digest, project_root, utc_now


SCHEMA_VERSION = 1
STATE_DIRECTORY = Path(".research-guard/domain-skills/frontier")
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
SOURCE_TYPES = {"primary_paper", "repository", "benchmark", "specification"}
IMPLEMENTATION_SOURCE_TYPES = {"repository", "benchmark", "specification"}
OVERLAP_DECISIONS = {"domain_only", "fuse_narrow_adapter", "reject", "reference_only"}
METRIC_DIRECTIONS = {"maximize", "minimize"}
METRIC_KINDS = {"utility", "safety"}


class FrontierSkillResearchError(GuardError):
    pass


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _text(value: Any, field: str, *, minimum: int = 1, maximum: int = 4000) -> str:
    result = " ".join(str(value or "").split())
    if len(result) < minimum or len(result) > maximum:
        raise FrontierSkillResearchError(f"{field} must contain {minimum}..{maximum} characters")
    return result


def _identifier(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not IDENTIFIER.fullmatch(result):
        raise FrontierSkillResearchError(f"{field} is invalid")
    return result


def _state_path(root: Path, protocol_id: str) -> Path:
    return root / STATE_DIRECTORY / _identifier(protocol_id, "frontier_protocol_id") / "state.json"


def _stable(record: dict[str, Any], hash_field: str) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != hash_field}


def _seal_record(record: dict[str, Any], hash_field: str) -> dict[str, Any]:
    record[hash_field] = digest(_stable(record, hash_field))
    return record


def _seal_state(state: dict[str, Any]) -> dict[str, Any]:
    state["state_sha256"] = digest(_stable(state, "state_sha256"))
    return state


def _append_event(state: dict[str, Any], kind: str, subject: str) -> None:
    previous = state["events"][-1]["event_sha256"] if state["events"] else None
    event = {
        "sequence": len(state["events"]) + 1,
        "kind": kind,
        "subject": subject,
        "previous_event_sha256": previous,
        "created_at": utc_now(),
    }
    state["events"].append(_seal_record(event, "event_sha256"))


def _load_state(root: Path, protocol_id: str) -> dict[str, Any]:
    path = _state_path(root, protocol_id)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FrontierSkillResearchError(f"Unreadable frontier Skill protocol: {exc}") from exc
    if state.get("schema_version") != SCHEMA_VERSION or state.get("protocol_id") != protocol_id:
        raise FrontierSkillResearchError("Unsupported frontier Skill protocol schema")
    if digest(_stable(state, "state_sha256")) != state.get("state_sha256"):
        raise FrontierSkillResearchError("FRONTIER_SKILL_STATE_INTEGRITY_FAILURE")
    protocol = state.get("protocol")
    if not isinstance(protocol, dict) or digest(protocol) != state.get("protocol_sha256"):
        raise FrontierSkillResearchError("FRONTIER_SKILL_PROTOCOL_INTEGRITY_FAILURE")
    for collection, hash_field in (
        ("sources", "source_sha256"),
        ("hypotheses", "hypothesis_sha256"),
        ("trials", "trial_sha256"),
    ):
        records = state.get(collection)
        if not isinstance(records, list):
            raise FrontierSkillResearchError(f"Frontier Skill {collection} must be an array")
        for record in records:
            if not isinstance(record, dict) or digest(_stable(record, hash_field)) != record.get(hash_field):
                raise FrontierSkillResearchError(f"FRONTIER_SKILL_{collection.upper()}_INTEGRITY_FAILURE")
    previous = None
    for sequence, event in enumerate(state.get("events") or [], start=1):
        if (
            event.get("sequence") != sequence
            or event.get("previous_event_sha256") != previous
            or digest(_stable(event, "event_sha256")) != event.get("event_sha256")
        ):
            raise FrontierSkillResearchError("FRONTIER_SKILL_EVENT_CHAIN_FAILURE")
        previous = event["event_sha256"]
    finalization = state.get("finalization")
    if finalization is not None and (
        not isinstance(finalization, dict)
        or digest(_stable(finalization, "finalization_sha256")) != finalization.get("finalization_sha256")
    ):
        raise FrontierSkillResearchError("FRONTIER_SKILL_FINALIZATION_INTEGRITY_FAILURE")
    return state


def _save_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    _atomic_json(_state_path(root, state["protocol_id"]), _seal_state(state))


def _case_ids(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > 256:
        raise FrontierSkillResearchError(f"{field} must be a non-empty array with at most 256 case ids")
    result = [_identifier(item, field) for item in value]
    if len(result) != len(set(result)):
        raise FrontierSkillResearchError(f"{field} contains duplicate case ids")
    return result


def _normalize_protocol(value: Any, *, selected_by: str, selection_rationale: str) -> dict[str, Any]:
    if selected_by != "main_agent":
        raise FrontierSkillResearchError("frontier_selected_by=main_agent is required")
    if not isinstance(value, dict):
        raise FrontierSkillResearchError("frontier_protocol must be an object")
    allowed = {
        "research_question", "target_agent", "target_harness", "baseline_artifact_sha256",
        "candidate_identity", "splits", "metrics", "validation_rounds",
    }
    if not set(value) <= allowed:
        raise FrontierSkillResearchError("frontier_protocol contains unknown fields")
    baseline_hash = str(value.get("baseline_artifact_sha256") or "").strip().lower()
    if not HEX_64.fullmatch(baseline_hash):
        raise FrontierSkillResearchError("baseline_artifact_sha256 must be a lowercase SHA-256 digest")
    candidate_identity = value.get("candidate_identity")
    if not isinstance(candidate_identity, dict) or set(candidate_identity) != {"skill_id", "repository", "commit"}:
        raise FrontierSkillResearchError("candidate_identity must contain exactly skill_id, repository, and commit")
    repository = str(candidate_identity.get("repository") or "").strip()
    commit = str(candidate_identity.get("commit") or "").strip().lower()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise FrontierSkillResearchError("candidate_identity.repository must be owner/repo")
    if not HEX_40.fullmatch(commit):
        raise FrontierSkillResearchError("candidate_identity.commit must be an immutable lowercase commit")
    splits = value.get("splits")
    if not isinstance(splits, dict) or set(splits) != {"train", "validation", "heldout"}:
        raise FrontierSkillResearchError("splits must contain exactly train, validation, and heldout")
    normalized_splits = {name: _case_ids(splits[name], f"splits.{name}") for name in splits}
    all_ids = [item for values in normalized_splits.values() for item in values]
    if len(all_ids) != len(set(all_ids)):
        raise FrontierSkillResearchError("train, validation, and heldout case ids must be disjoint")
    metrics = value.get("metrics")
    if not isinstance(metrics, list) or not metrics or len(metrics) > 12:
        raise FrontierSkillResearchError("metrics must be a non-empty array with at most 12 entries")
    normalized_metrics: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, raw in enumerate(metrics):
        if not isinstance(raw, dict) or not set(raw) <= {"name", "direction", "kind", "tolerance"}:
            raise FrontierSkillResearchError(f"metrics[{index}] is invalid")
        name = _identifier(raw.get("name"), f"metrics[{index}].name")
        if name in names:
            raise FrontierSkillResearchError("metric names must be unique")
        names.add(name)
        direction = str(raw.get("direction") or "").strip()
        kind = str(raw.get("kind") or "").strip()
        tolerance = raw.get("tolerance", 0.0)
        if direction not in METRIC_DIRECTIONS or kind not in METRIC_KINDS:
            raise FrontierSkillResearchError(f"metrics[{index}] has an unsupported direction or kind")
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(float(tolerance)) or tolerance < 0:
            raise FrontierSkillResearchError(f"metrics[{index}].tolerance must be finite and non-negative")
        normalized_metrics.append({"name": name, "direction": direction, "kind": kind, "tolerance": float(tolerance)})
    if {item["kind"] for item in normalized_metrics} != METRIC_KINDS:
        raise FrontierSkillResearchError("frontier evaluation needs at least one utility and one safety metric")
    validation_rounds = value.get("validation_rounds")
    if validation_rounds not in {2, 3}:
        raise FrontierSkillResearchError("validation_rounds must be exactly 2 or 3")
    return {
        "research_question": _text(value.get("research_question"), "research_question", minimum=12),
        "target_agent": _text(value.get("target_agent"), "target_agent", minimum=3, maximum=200),
        "target_harness": _text(value.get("target_harness"), "target_harness", minimum=3, maximum=500),
        "baseline_artifact_sha256": baseline_hash,
        "candidate_identity": {
            "skill_id": _identifier(candidate_identity.get("skill_id"), "candidate_identity.skill_id"),
            "repository": repository,
            "commit": commit,
        },
        "splits": normalized_splits,
        "split_sha256": {name: digest(items) for name, items in normalized_splits.items()},
        "metrics": normalized_metrics,
        "validation_rounds": validation_rounds,
        "selected_by": selected_by,
        "selection_rationale": _text(selection_rationale, "frontier_selection_rationale", minimum=20),
        "deadline_policy": "main_agent_judges_completion_with_stage_updates_unless_user_sets_budget",
        "execution_policy": "artifact-backed evaluation only; never execute third-party Skill code",
    }


def plan_frontier_skill_research(
    root: str | os.PathLike[str], *, protocol_id: str, protocol: dict[str, Any],
    selected_by: str, selection_rationale: str,
) -> dict[str, Any]:
    base = project_root(root)
    if not base.is_dir():
        raise FrontierSkillResearchError("project_root must be an existing directory")
    identifier = _identifier(protocol_id, "frontier_protocol_id")
    path = _state_path(base, identifier)
    if path.exists():
        raise FrontierSkillResearchError("frontier_protocol_id is append-only; use a versioned id")
    normalized = _normalize_protocol(protocol, selected_by=selected_by, selection_rationale=selection_rationale)
    state = {
        "schema_version": SCHEMA_VERSION,
        "protocol_id": identifier,
        "protocol": normalized,
        "protocol_sha256": digest(normalized),
        "sources": [],
        "hypotheses": [],
        "trials": [],
        "events": [],
        "finalization": None,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    _append_event(state, "protocol_planned", identifier)
    _save_state(base, state)
    return frontier_skill_research_status(base, identifier)


def _normalize_source(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FrontierSkillResearchError("frontier_source must be an object")
    allowed = {"source_id", "source_type", "title", "url", "immutable_id", "mechanism", "limitations"}
    if not set(value) <= allowed:
        raise FrontierSkillResearchError("frontier_source contains unknown fields")
    source_type = str(value.get("source_type") or "").strip()
    if source_type not in SOURCE_TYPES:
        raise FrontierSkillResearchError("frontier_source.source_type is unsupported")
    url = _text(value.get("url"), "frontier_source.url", minimum=12, maximum=2000)
    if not url.startswith("https://") or any(character.isspace() for character in url):
        raise FrontierSkillResearchError("frontier sources require a clickable HTTPS URL")
    immutable_id = _text(value.get("immutable_id"), "frontier_source.immutable_id", minimum=6, maximum=200)
    if source_type == "repository" and not HEX_40.fullmatch(immutable_id.lower()):
        raise FrontierSkillResearchError("repository sources require an immutable 40-character commit")
    if source_type == "primary_paper" and not (
        re.search(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b", immutable_id, re.I)
        or immutable_id.lower().startswith("10.")
    ):
        raise FrontierSkillResearchError("primary-paper immutable_id must be a versioned arXiv id or DOI")
    return {
        "source_id": _identifier(value.get("source_id"), "frontier_source.source_id"),
        "source_type": source_type,
        "title": _text(value.get("title"), "frontier_source.title", minimum=3, maximum=500),
        "url": url,
        "immutable_id": immutable_id,
        "mechanism": _text(value.get("mechanism"), "frontier_source.mechanism", minimum=12),
        "limitations": _text(value.get("limitations"), "frontier_source.limitations", minimum=12),
        "registration_required": False,
        "recorded_at": utc_now(),
    }


def record_frontier_skill_source(
    root: str | os.PathLike[str], *, protocol_id: str, source: dict[str, Any],
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, protocol_id)
    if state["finalization"] is not None:
        raise FrontierSkillResearchError("finalized frontier protocols are append-only")
    normalized = _normalize_source(source)
    if normalized["source_id"] in {item["source_id"] for item in state["sources"]}:
        raise FrontierSkillResearchError("frontier source id already exists")
    state["sources"].append(_seal_record(normalized, "source_sha256"))
    _append_event(state, "source_recorded", normalized["source_id"])
    _save_state(base, state)
    return {"status": "RECORDED", **state["sources"][-1]}


def _normalize_hypothesis(value: Any, source_ids: set[str], hypothesis_ids: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FrontierSkillResearchError("frontier_hypothesis must be an object")
    allowed = {
        "hypothesis_id", "statement", "mechanism", "expected_effect", "failure_condition",
        "canonical_owner", "overlap_decision", "source_ids", "parent_id", "rejection_reason",
    }
    if not set(value) <= allowed:
        raise FrontierSkillResearchError("frontier_hypothesis contains unknown fields")
    identifier = _identifier(value.get("hypothesis_id"), "frontier_hypothesis.hypothesis_id")
    parent = value.get("parent_id")
    if parent is not None:
        parent = _identifier(parent, "frontier_hypothesis.parent_id")
        if parent not in hypothesis_ids or parent == identifier:
            raise FrontierSkillResearchError("frontier hypothesis parent must already exist")
    references = value.get("source_ids")
    if not isinstance(references, list) or not references or len(references) > 16:
        raise FrontierSkillResearchError("frontier_hypothesis.source_ids must be a non-empty bounded array")
    references = [_identifier(item, "frontier_hypothesis.source_ids") for item in references]
    if len(references) != len(set(references)) or not set(references) <= source_ids:
        raise FrontierSkillResearchError("frontier hypothesis source ids must be unique registered sources")
    overlap = str(value.get("overlap_decision") or "").strip()
    if overlap not in OVERLAP_DECISIONS:
        raise FrontierSkillResearchError("frontier hypothesis overlap_decision is unsupported")
    rejection_reason = value.get("rejection_reason")
    if overlap == "reject":
        rejection_reason = _text(rejection_reason, "frontier_hypothesis.rejection_reason", minimum=20)
    elif rejection_reason not in {None, ""}:
        raise FrontierSkillResearchError("rejection_reason is only valid for rejected hypotheses")
    return {
        "hypothesis_id": identifier,
        "statement": _text(value.get("statement"), "frontier_hypothesis.statement", minimum=12),
        "mechanism": _text(value.get("mechanism"), "frontier_hypothesis.mechanism", minimum=12),
        "expected_effect": _text(value.get("expected_effect"), "frontier_hypothesis.expected_effect", minimum=8),
        "failure_condition": _text(value.get("failure_condition"), "frontier_hypothesis.failure_condition", minimum=8),
        "canonical_owner": _text(value.get("canonical_owner"), "frontier_hypothesis.canonical_owner", minimum=3, maximum=160),
        "overlap_decision": overlap,
        "source_ids": references,
        "parent_id": parent,
        "rejection_reason": rejection_reason,
        "registered_at": utc_now(),
    }


def register_frontier_skill_hypothesis(
    root: str | os.PathLike[str], *, protocol_id: str, hypothesis: dict[str, Any],
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, protocol_id)
    if state["finalization"] is not None:
        raise FrontierSkillResearchError("finalized frontier protocols are append-only")
    normalized = _normalize_hypothesis(
        hypothesis,
        {item["source_id"] for item in state["sources"]},
        {item["hypothesis_id"] for item in state["hypotheses"]},
    )
    if normalized["hypothesis_id"] in {item["hypothesis_id"] for item in state["hypotheses"]}:
        raise FrontierSkillResearchError("frontier hypothesis id already exists")
    state["hypotheses"].append(_seal_record(normalized, "hypothesis_sha256"))
    _append_event(state, "hypothesis_registered", normalized["hypothesis_id"])
    _save_state(base, state)
    return {"status": "REGISTERED", **state["hypotheses"][-1]}


def _safe_trial_path(base: Path, value: Any) -> tuple[str, Path]:
    raw = Path(_text(value, "frontier_trial_path", minimum=1, maximum=1000))
    path = raw.resolve() if raw.is_absolute() else (base / raw).resolve()
    try:
        relative = path.relative_to(base).as_posix()
    except ValueError as exc:
        raise FrontierSkillResearchError("frontier trial artifacts must stay inside project_root") from exc
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise FrontierSkillResearchError("frontier trial artifact must be an existing bounded non-symlink file")
    return relative, path


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _normalize_trial(state: dict[str, Any], document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise FrontierSkillResearchError("frontier trial artifact must contain a JSON object")
    allowed = {
        "schema_version", "protocol_id", "hypothesis_id", "split", "round", "run_id",
        "case_ids", "baseline_artifact_sha256", "candidate_artifact_sha256", "metrics", "producer",
    }
    if set(document) != allowed or document.get("schema_version") != SCHEMA_VERSION:
        raise FrontierSkillResearchError("frontier trial artifact has an unsupported schema")
    if document.get("protocol_id") != state["protocol_id"]:
        raise FrontierSkillResearchError("frontier trial protocol id does not match")
    hypothesis_id = _identifier(document.get("hypothesis_id"), "trial.hypothesis_id")
    hypothesis = next((item for item in state["hypotheses"] if item["hypothesis_id"] == hypothesis_id), None)
    if hypothesis is None or hypothesis["overlap_decision"] not in {"domain_only", "fuse_narrow_adapter"}:
        raise FrontierSkillResearchError("only retained hypotheses may record evaluation trials")
    split = str(document.get("split") or "").strip()
    if split not in {"validation", "heldout"}:
        raise FrontierSkillResearchError("frontier trials use validation or heldout splits only")
    round_number = document.get("round")
    expected_rounds = state["protocol"]["validation_rounds"]
    if not isinstance(round_number, int) or isinstance(round_number, bool):
        raise FrontierSkillResearchError("trial.round must be an integer")
    if split == "validation" and not 1 <= round_number <= expected_rounds:
        raise FrontierSkillResearchError("validation trial round is outside the frozen protocol")
    if split == "heldout" and round_number != 1:
        raise FrontierSkillResearchError("heldout evaluation is a single final round")
    case_ids = _case_ids(document.get("case_ids"), "trial.case_ids")
    if case_ids != state["protocol"]["splits"][split]:
        raise FrontierSkillResearchError("trial case ids do not exactly match the frozen split")
    baseline_hash = str(document.get("baseline_artifact_sha256") or "").strip().lower()
    candidate_hash = str(document.get("candidate_artifact_sha256") or "").strip().lower()
    if baseline_hash != state["protocol"]["baseline_artifact_sha256"] or not HEX_64.fullmatch(candidate_hash):
        raise FrontierSkillResearchError("trial artifact hashes are invalid or do not match the frozen baseline")
    if split == "heldout":
        validations = sorted(
            (item for item in state["trials"] if item["hypothesis_id"] == hypothesis_id and item["split"] == "validation"),
            key=lambda item: item["round"],
        )
        if len(validations) != expected_rounds or not all(item["accepted"] for item in validations):
            raise FrontierSkillResearchError("heldout evaluation is locked until all validation rounds pass")
        if candidate_hash != validations[-1]["candidate_artifact_sha256"]:
            raise FrontierSkillResearchError("heldout evaluation must use the last accepted validation artifact")
    metric_values = document.get("metrics")
    metric_contract = {item["name"]: item for item in state["protocol"]["metrics"]}
    if not isinstance(metric_values, dict) or set(metric_values) != set(metric_contract):
        raise FrontierSkillResearchError("trial metrics must exactly match the frozen metric contract")
    normalized_metrics: dict[str, dict[str, float | bool]] = {}
    safety_pass = True
    utility_non_regression = True
    utility_improved = False
    for name, contract in metric_contract.items():
        values = metric_values[name]
        if not isinstance(values, dict) or set(values) != {"baseline", "candidate"}:
            raise FrontierSkillResearchError(f"trial metric {name} must contain baseline and candidate")
        baseline = values["baseline"]
        candidate = values["candidate"]
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)) for item in (baseline, candidate)):
            raise FrontierSkillResearchError(f"trial metric {name} values must be finite numbers")
        baseline = float(baseline)
        candidate = float(candidate)
        tolerance = contract["tolerance"]
        if contract["direction"] == "maximize":
            non_regression = candidate >= baseline - tolerance
            improved = candidate > baseline + tolerance
        else:
            non_regression = candidate <= baseline + tolerance
            improved = candidate < baseline - tolerance
        if contract["kind"] == "safety":
            safety_pass = safety_pass and non_regression
        else:
            utility_non_regression = utility_non_regression and non_regression
            utility_improved = utility_improved or improved
        normalized_metrics[name] = {
            "baseline": baseline,
            "candidate": candidate,
            "non_regression": non_regression,
            "improved": improved,
        }
    return {
        "hypothesis_id": hypothesis_id,
        "split": split,
        "round": round_number,
        "run_id": _identifier(document.get("run_id"), "trial.run_id"),
        "case_ids_sha256": digest(case_ids),
        "baseline_artifact_sha256": baseline_hash,
        "candidate_artifact_sha256": candidate_hash,
        "metrics": normalized_metrics,
        "safety_pass": safety_pass,
        "utility_non_regression": utility_non_regression,
        "utility_improved": utility_improved,
        "accepted": safety_pass and utility_non_regression and utility_improved,
        "producer": _text(document.get("producer"), "trial.producer", minimum=3, maximum=200),
        "recorded_at": utc_now(),
    }


def record_frontier_skill_trial(
    root: str | os.PathLike[str], *, protocol_id: str, trial_path: str,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, protocol_id)
    if state["finalization"] is not None:
        raise FrontierSkillResearchError("finalized frontier protocols are append-only")
    relative, path = _safe_trial_path(base, trial_path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FrontierSkillResearchError(f"Unreadable frontier trial artifact: {exc}") from exc
    trial = _normalize_trial(state, document)
    key = (trial["hypothesis_id"], trial["split"], trial["round"])
    if key in {(item["hypothesis_id"], item["split"], item["round"]) for item in state["trials"]}:
        raise FrontierSkillResearchError("frontier trial split/round is append-only")
    if trial["run_id"] in {item["run_id"] for item in state["trials"]}:
        raise FrontierSkillResearchError("frontier trial run_id must be unique within the protocol")
    if trial["split"] == "validation":
        completed_rounds = sorted(
            item["round"] for item in state["trials"]
            if item["hypothesis_id"] == trial["hypothesis_id"] and item["split"] == "validation"
        )
        if trial["round"] != len(completed_rounds) + 1:
            raise FrontierSkillResearchError("validation trials must be appended in frozen round order")
    trial["artifact_path"] = relative
    trial["artifact_sha256"] = _file_sha256(path)
    state["trials"].append(_seal_record(trial, "trial_sha256"))
    _append_event(state, "trial_recorded", f"{trial['hypothesis_id']}:{trial['split']}:{trial['round']}")
    _save_state(base, state)
    response = {key: trial[key] for key in (
        "hypothesis_id", "split", "round", "run_id", "accepted", "safety_pass",
        "utility_non_regression", "utility_improved", "candidate_artifact_sha256",
        "artifact_path", "artifact_sha256",
    )}
    if trial["split"] == "heldout":
        for hidden in ("accepted", "safety_pass", "utility_non_regression", "utility_improved"):
            response.pop(hidden)
        response["status"] = "HELDOUT_RECORDED_NOT_EXPOSED"
    else:
        response["status"] = "PASS" if trial["accepted"] else "FAIL"
    return response


def _artifact_failures(base: Path, state: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for trial in state["trials"]:
        path = (base / trial["artifact_path"]).resolve()
        try:
            path.relative_to(base)
        except ValueError:
            failures.append(f"trial path escaped project: {trial['artifact_path']}")
            continue
        if path.is_symlink() or not path.is_file() or _file_sha256(path) != trial["artifact_sha256"]:
            failures.append(f"trial artifact drift: {trial['artifact_path']}")
    return failures


def finalize_frontier_skill_research(root: str | os.PathLike[str], *, protocol_id: str) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, protocol_id)
    if state["finalization"] is not None:
        raise FrontierSkillResearchError("frontier protocol finalization is append-only")
    if not state["hypotheses"]:
        raise FrontierSkillResearchError("frontier protocol needs at least one registered hypothesis")
    failures = _artifact_failures(base, state)
    source_map = {item["source_id"]: item for item in state["sources"]}
    candidate_identity = state["protocol"]["candidate_identity"]
    retained: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for hypothesis in state["hypotheses"]:
        source_types = {source_map[item]["source_type"] for item in hypothesis["source_ids"]}
        decision = hypothesis["overlap_decision"]
        if "primary_paper" not in source_types:
            failures.append(f"{hypothesis['hypothesis_id']} lacks a primary-paper source")
        if decision in {"domain_only", "fuse_narrow_adapter"}:
            if not source_types & IMPLEMENTATION_SOURCE_TYPES:
                failures.append(f"{hypothesis['hypothesis_id']} lacks an implementation/specification source")
            expected_repository_url = f"https://github.com/{candidate_identity['repository']}".casefold()
            candidate_sources = [source_map[item] for item in hypothesis["source_ids"]]
            if not any(
                source["source_type"] == "repository"
                and source["immutable_id"].casefold() == candidate_identity["commit"]
                and source["url"].rstrip("/").removesuffix(".git").casefold() == expected_repository_url
                for source in candidate_sources
            ):
                failures.append(f"{hypothesis['hypothesis_id']} lacks the exact candidate repository/commit source")
            validations = sorted(
                (item for item in state["trials"] if item["hypothesis_id"] == hypothesis["hypothesis_id"] and item["split"] == "validation"),
                key=lambda item: item["round"],
            )
            heldout = [
                item for item in state["trials"]
                if item["hypothesis_id"] == hypothesis["hypothesis_id"] and item["split"] == "heldout"
            ]
            expected = state["protocol"]["validation_rounds"]
            if [item["round"] for item in validations] != list(range(1, expected + 1)) or not all(item["accepted"] for item in validations):
                failures.append(f"{hypothesis['hypothesis_id']} lacks exactly {expected} accepted validation rounds")
            if len(heldout) != 1 or not heldout[0]["accepted"]:
                failures.append(f"{hypothesis['hypothesis_id']} lacks one accepted final heldout evaluation")
            if validations and heldout and heldout[0]["candidate_artifact_sha256"] != validations[-1]["candidate_artifact_sha256"]:
                failures.append(f"{hypothesis['hypothesis_id']} changed its artifact after validation")
            if validations and heldout:
                retained.append({
                    "hypothesis_id": hypothesis["hypothesis_id"],
                    "canonical_owner": hypothesis["canonical_owner"],
                    "overlap_decision": decision,
                    "candidate_artifact_sha256": heldout[0]["candidate_artifact_sha256"],
                    "validation_rounds": expected,
                    "heldout_status": "PASS" if heldout[0]["accepted"] else "FAIL",
                })
        else:
            rejected.append({
                "hypothesis_id": hypothesis["hypothesis_id"],
                "decision": decision,
                "reason": hypothesis.get("rejection_reason") or "retained as evidence-only reference",
            })
    if failures:
        raise FrontierSkillResearchError("FRONTIER_SKILL_FINALIZATION_BLOCKED: " + "; ".join(failures))
    finalization = {
        "status": "HUMAN_REVIEW_REQUIRED",
        "retained_proposals": retained,
        "rejected_or_reference_branches": rejected,
        "source_count": len(state["sources"]),
        "hypothesis_count": len(state["hypotheses"]),
        "apply_route_exposed": False,
        "admission_policy": "an explicit existing domain_skill_action=admit call may consume one matching retained proposal",
        "finalized_at": utc_now(),
    }
    state["finalization"] = _seal_record(finalization, "finalization_sha256")
    _append_event(state, "protocol_finalized", protocol_id)
    _save_state(base, state)
    return frontier_skill_research_status(base, protocol_id)


def verify_frontier_skill_admission(
    root: str | os.PathLike[str], *, protocol_id: str, artifact_sha256: str,
    skill_id: str, repository: str, commit: str,
    canonical_owner: str, overlap_decision: str,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, protocol_id)
    if _artifact_failures(base, state):
        raise FrontierSkillResearchError("frontier trial artifacts changed after recording")
    finalization = state.get("finalization")
    if not finalization:
        raise FrontierSkillResearchError("frontier protocol is not finalized")
    expected_identity = state["protocol"]["candidate_identity"]
    observed_identity = {
        "skill_id": str(skill_id or "").strip(),
        "repository": str(repository or "").strip(),
        "commit": str(commit or "").strip().lower(),
    }
    if observed_identity != expected_identity:
        raise FrontierSkillResearchError("frontier evidence does not bind this Skill id, repository, and commit")
    binding = next((
        item for item in finalization["retained_proposals"]
        if item["candidate_artifact_sha256"] == artifact_sha256
        and item["canonical_owner"] == canonical_owner
        and item["overlap_decision"] == overlap_decision
    ), None)
    if binding is None:
        raise FrontierSkillResearchError("frontier evidence does not bind this artifact, owner, and overlap decision")
    return {
        "status": "PASS",
        "protocol_id": protocol_id,
        "protocol_sha256": state["protocol_sha256"],
        "finalization_sha256": finalization["finalization_sha256"],
        "binding": binding,
    }


def get_frontier_skill_portability_binding(
    root: str | os.PathLike[str], *, protocol_id: str, artifact_sha256: str,
    skill_id: str, repository: str, commit: str,
    canonical_owner: str, overlap_decision: str,
) -> dict[str, Any]:
    """Return the exact finalized P24 handoff needed by a portability protocol."""
    verified = verify_frontier_skill_admission(
        root,
        protocol_id=protocol_id,
        artifact_sha256=artifact_sha256,
        skill_id=skill_id,
        repository=repository,
        commit=commit,
        canonical_owner=canonical_owner,
        overlap_decision=overlap_decision,
    )
    base = project_root(root)
    state = _load_state(base, protocol_id)
    occupied_case_ids = [
        case_id
        for split in ("train", "validation", "heldout")
        for case_id in state["protocol"]["splits"][split]
    ]
    return {
        **verified,
        "candidate_identity": state["protocol"]["candidate_identity"],
        "candidate_artifact_sha256": artifact_sha256,
        "canonical_owner": canonical_owner,
        "overlap_decision": overlap_decision,
        "metrics": state["protocol"]["metrics"],
        "occupied_case_ids": occupied_case_ids,
        "occupied_case_ids_sha256": digest(sorted(occupied_case_ids)),
    }


def frontier_skill_research_status(root: str | os.PathLike[str], protocol_id: str) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, protocol_id)
    finalization = state.get("finalization")
    trial_summaries = []
    for trial in state["trials"]:
        summary = {
            "hypothesis_id": trial["hypothesis_id"],
            "split": trial["split"],
            "round": trial["round"],
            "artifact_path": trial["artifact_path"],
            "artifact_sha256": trial["artifact_sha256"],
        }
        if trial["split"] == "heldout" and finalization is None:
            summary["status"] = "RECORDED_NOT_EXPOSED"
        else:
            summary["status"] = "PASS" if trial["accepted"] else "FAIL"
            summary["safety_pass"] = trial["safety_pass"]
            summary["utility_improved"] = trial["utility_improved"]
        trial_summaries.append(summary)
    return {
        "status": finalization["status"] if finalization else "ACTION_REQUIRED",
        "protocol_id": state["protocol_id"],
        "protocol_sha256": state["protocol_sha256"],
        "state_sha256": state["state_sha256"],
        "target_agent": state["protocol"]["target_agent"],
        "target_harness": state["protocol"]["target_harness"],
        "candidate_identity": state["protocol"]["candidate_identity"],
        "validation_rounds_required": state["protocol"]["validation_rounds"],
        "split_counts": {key: len(value) for key, value in state["protocol"]["splits"].items()},
        "split_sha256": state["protocol"]["split_sha256"],
        "sources": [{
            "source_id": item["source_id"], "source_type": item["source_type"],
            "title": item["title"], "url": item["url"], "immutable_id": item["immutable_id"],
        } for item in state["sources"]],
        "hypotheses": [{
            "hypothesis_id": item["hypothesis_id"], "parent_id": item["parent_id"],
            "canonical_owner": item["canonical_owner"], "overlap_decision": item["overlap_decision"],
        } for item in state["hypotheses"]],
        "trials": trial_summaries,
        "finalization": finalization,
        "execution_allowed": False,
        "apply_route_exposed": False,
        "next_action": (
            "Review a retained proposal, then explicitly call the existing admission gate."
            if finalization else
            "Record current primary sources, a bounded hypothesis tree, artifact-backed validation rounds, and one locked heldout run."
        ),
    }


def verify_frontier_skill_research(root: str | os.PathLike[str], protocol_id: str) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, protocol_id)
    failures = _artifact_failures(base, state)
    return {
        "status": "FAIL" if failures else ("PASS" if state["finalization"] is not None else "ACTION_REQUIRED"),
        "integrity_status": "PASS" if not failures else "FAIL",
        "protocol_id": protocol_id,
        "state_sha256": state["state_sha256"],
        "finalized": state["finalization"] is not None,
        "artifact_failures": failures,
        "third_party_execution_observed": False,
    }
