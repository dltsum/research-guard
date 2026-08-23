from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from frontier_skill_research_core import (
    FrontierSkillResearchError,
    get_frontier_skill_portability_binding,
)
from research_guard_core import GuardError, digest, project_root, utc_now


SCHEMA_VERSION = 1
STATE_DIRECTORY = Path(".research-guard/domain-skills/frontier-portability")
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
SOURCE_TYPES = {"primary_paper", "repository", "benchmark", "specification"}
CELL_FIELDS = {
    "cell_id", "agent_id", "model_family", "model_version", "harness",
    "harness_version", "task_scope", "executor_group", "evidence_family", "case_ids",
}
VARIATION_FIELDS = ("model_family", "model_version", "harness", "harness_version", "task_scope")


class SkillPortabilityError(GuardError):
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
        raise SkillPortabilityError(f"{field} must contain {minimum}..{maximum} characters")
    return result


def _identifier(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not IDENTIFIER.fullmatch(result):
        raise SkillPortabilityError(f"{field} is invalid")
    return result


def _lower_hex(value: Any, field: str, pattern: re.Pattern[str]) -> str:
    result = str(value or "").strip().lower()
    if not pattern.fullmatch(result):
        raise SkillPortabilityError(f"{field} is invalid")
    return result


def _case_ids(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > 256:
        raise SkillPortabilityError(f"{field} must be a non-empty array with at most 256 case ids")
    result = [_identifier(item, field) for item in value]
    if len(result) != len(set(result)):
        raise SkillPortabilityError(f"{field} contains duplicate case ids")
    return result


def _state_path(root: Path, portability_id: str) -> Path:
    return root / STATE_DIRECTORY / _identifier(portability_id, "skill_portability_id") / "state.json"


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


def _load_state(root: Path, portability_id: str) -> dict[str, Any]:
    path = _state_path(root, portability_id)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SkillPortabilityError(f"Unreadable Skill portability protocol: {exc}") from exc
    if state.get("schema_version") != SCHEMA_VERSION or state.get("portability_id") != portability_id:
        raise SkillPortabilityError("Unsupported Skill portability schema")
    if digest(_stable(state, "state_sha256")) != state.get("state_sha256"):
        raise SkillPortabilityError("SKILL_PORTABILITY_STATE_INTEGRITY_FAILURE")
    protocol = state.get("protocol")
    if not isinstance(protocol, dict) or digest(protocol) != state.get("protocol_sha256"):
        raise SkillPortabilityError("SKILL_PORTABILITY_PROTOCOL_INTEGRITY_FAILURE")
    for collection, hash_field in (("sources", "source_sha256"), ("trials", "trial_sha256")):
        records = state.get(collection)
        if not isinstance(records, list):
            raise SkillPortabilityError(f"Skill portability {collection} must be an array")
        for record in records:
            if not isinstance(record, dict) or digest(_stable(record, hash_field)) != record.get(hash_field):
                raise SkillPortabilityError(f"SKILL_PORTABILITY_{collection.upper()}_INTEGRITY_FAILURE")
    previous = None
    events = state.get("events")
    if not isinstance(events, list):
        raise SkillPortabilityError("Skill portability events must be an array")
    for sequence, event in enumerate(events, start=1):
        if (
            event.get("sequence") != sequence
            or event.get("previous_event_sha256") != previous
            or digest(_stable(event, "event_sha256")) != event.get("event_sha256")
        ):
            raise SkillPortabilityError("SKILL_PORTABILITY_EVENT_CHAIN_FAILURE")
        previous = event["event_sha256"]
    finalization = state.get("finalization")
    if finalization is not None and (
        not isinstance(finalization, dict)
        or digest(_stable(finalization, "finalization_sha256")) != finalization.get("finalization_sha256")
    ):
        raise SkillPortabilityError("SKILL_PORTABILITY_FINALIZATION_INTEGRITY_FAILURE")
    return state


def _save_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    _atomic_json(_state_path(root, state["portability_id"]), _seal_state(state))


def _normalize_binding(value: Any) -> dict[str, str]:
    required = {
        "artifact_sha256", "skill_id", "repository", "commit",
        "canonical_owner", "overlap_decision",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise SkillPortabilityError("source_binding must contain the exact P24 admission identity")
    repository = str(value.get("repository") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise SkillPortabilityError("source_binding.repository must be owner/repo")
    overlap = str(value.get("overlap_decision") or "").strip()
    if overlap not in {"domain_only", "fuse_narrow_adapter"}:
        raise SkillPortabilityError("source_binding.overlap_decision is unsupported")
    return {
        "artifact_sha256": _lower_hex(value.get("artifact_sha256"), "source_binding.artifact_sha256", HEX_64),
        "skill_id": _identifier(value.get("skill_id"), "source_binding.skill_id"),
        "repository": repository,
        "commit": _lower_hex(value.get("commit"), "source_binding.commit", HEX_40),
        "canonical_owner": _text(value.get("canonical_owner"), "source_binding.canonical_owner", maximum=160),
        "overlap_decision": overlap,
    }


def _frontier_handoff(root: Path, frontier_protocol_id: str, binding: dict[str, str]) -> dict[str, Any]:
    try:
        return get_frontier_skill_portability_binding(
            root,
            protocol_id=frontier_protocol_id,
            artifact_sha256=binding["artifact_sha256"],
            skill_id=binding["skill_id"],
            repository=binding["repository"],
            commit=binding["commit"],
            canonical_owner=binding["canonical_owner"],
            overlap_decision=binding["overlap_decision"],
        )
    except (FrontierSkillResearchError, OSError, UnicodeError) as exc:
        raise SkillPortabilityError(f"frontier source binding is invalid: {exc}") from exc


def _normalize_cell(value: Any, index: int) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != CELL_FIELDS:
        raise SkillPortabilityError(f"cells[{index}] must contain the exact portability cell fields")
    cell = {
        "cell_id": _identifier(value.get("cell_id"), f"cells[{index}].cell_id"),
        "agent_id": _text(value.get("agent_id"), f"cells[{index}].agent_id", minimum=3, maximum=160),
        "model_family": _text(value.get("model_family"), f"cells[{index}].model_family", minimum=2, maximum=160),
        "model_version": _text(value.get("model_version"), f"cells[{index}].model_version", minimum=2, maximum=160),
        "harness": _text(value.get("harness"), f"cells[{index}].harness", minimum=2, maximum=160),
        "harness_version": _text(value.get("harness_version"), f"cells[{index}].harness_version", minimum=2, maximum=160),
        "task_scope": _text(value.get("task_scope"), f"cells[{index}].task_scope", minimum=3, maximum=300),
        "executor_group": _identifier(value.get("executor_group"), f"cells[{index}].executor_group"),
        "evidence_family": _identifier(value.get("evidence_family"), f"cells[{index}].evidence_family"),
        "case_ids": _case_ids(value.get("case_ids"), f"cells[{index}].case_ids"),
    }
    cell["case_ids_sha256"] = digest(cell["case_ids"])
    return cell


def _validate_evidence_families(cells: list[dict[str, Any]]) -> None:
    for index, left in enumerate(cells):
        for right in cells[index + 1:]:
            coupled = (
                left["model_family"].casefold() == right["model_family"].casefold()
                or left["executor_group"].casefold() == right["executor_group"].casefold()
            )
            if coupled and left["evidence_family"] != right["evidence_family"]:
                raise SkillPortabilityError(
                    "cells sharing a model family or executor group must share one evidence family"
                )


def _normalize_protocol(
    root: Path, value: Any, *, selected_by: str, selection_rationale: str,
) -> dict[str, Any]:
    if selected_by != "main_agent":
        raise SkillPortabilityError("skill_portability_selected_by=main_agent is required")
    allowed = {"research_question", "frontier_protocol_id", "source_binding", "replicates", "cells"}
    if not isinstance(value, dict) or set(value) != allowed:
        raise SkillPortabilityError("skill_portability_protocol must contain the exact protocol fields")
    frontier_protocol_id = _identifier(value.get("frontier_protocol_id"), "frontier_protocol_id")
    binding = _normalize_binding(value.get("source_binding"))
    handoff = _frontier_handoff(root, frontier_protocol_id, binding)
    replicates = value.get("replicates")
    if replicates not in {2, 3}:
        raise SkillPortabilityError("replicates must be exactly 2 or 3")
    raw_cells = value.get("cells")
    if not isinstance(raw_cells, list) or not 2 <= len(raw_cells) <= 12:
        raise SkillPortabilityError("cells must be an array with 2..12 entries")
    cells = [_normalize_cell(item, index) for index, item in enumerate(raw_cells)]
    cell_ids = [item["cell_id"] for item in cells]
    if len(cell_ids) != len(set(cell_ids)):
        raise SkillPortabilityError("portability cell ids must be unique")
    varying_dimensions = [
        field for field in VARIATION_FIELDS
        if len({str(item[field]).casefold() for item in cells}) > 1
    ]
    if not varying_dimensions:
        raise SkillPortabilityError("portability cells must vary by model, harness, or task scope")
    _validate_evidence_families(cells)
    occupied = set(handoff["occupied_case_ids"])
    overlap = sorted(occupied & {case_id for cell in cells for case_id in cell["case_ids"]})
    if overlap:
        raise SkillPortabilityError("portability cases overlap the source protocol train, validation, or heldout cases")
    return {
        "research_question": _text(value.get("research_question"), "research_question", minimum=12),
        "frontier_protocol_id": frontier_protocol_id,
        "source_binding": binding,
        "frontier_protocol_sha256": handoff["protocol_sha256"],
        "frontier_finalization_sha256": handoff["finalization_sha256"],
        "frontier_case_ids_sha256": handoff["occupied_case_ids_sha256"],
        "metrics": handoff["metrics"],
        "replicates": replicates,
        "cells": cells,
        "varying_dimensions": varying_dimensions,
        "selected_by": selected_by,
        "selection_rationale": _text(selection_rationale, "skill_portability_selection_rationale", minimum=20),
        "deadline_policy": "main_agent_judges_completion_with_stage_updates_unless_user_sets_budget",
        "execution_policy": "record hash-bound external results; this core never executes a third-party Skill or model",
        "claim_policy": "report each target cell; never infer universal portability or average away a failing cell",
    }


def plan_skill_portability(
    root: str | os.PathLike[str], *, portability_id: str, protocol: dict[str, Any],
    selected_by: str, selection_rationale: str,
) -> dict[str, Any]:
    base = project_root(root)
    if not base.is_dir():
        raise SkillPortabilityError("project_root must be an existing directory")
    identifier = _identifier(portability_id, "skill_portability_id")
    path = _state_path(base, identifier)
    if path.exists():
        raise SkillPortabilityError("skill_portability_id is append-only; use a versioned id")
    normalized = _normalize_protocol(
        base, protocol, selected_by=selected_by, selection_rationale=selection_rationale,
    )
    state = {
        "schema_version": SCHEMA_VERSION,
        "portability_id": identifier,
        "protocol": normalized,
        "protocol_sha256": digest(normalized),
        "sources": [],
        "trials": [],
        "events": [],
        "finalization": None,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    _append_event(state, "portability_planned", identifier)
    _save_state(base, state)
    return skill_portability_status(base, identifier)


def _normalize_source(value: Any) -> dict[str, Any]:
    allowed = {"source_id", "source_type", "title", "url", "immutable_id", "mechanism", "limitations"}
    if not isinstance(value, dict) or set(value) != allowed:
        raise SkillPortabilityError("skill_portability_source must contain the exact source fields")
    source_type = str(value.get("source_type") or "").strip()
    if source_type not in SOURCE_TYPES:
        raise SkillPortabilityError("skill_portability_source.source_type is unsupported")
    url = _text(value.get("url"), "skill_portability_source.url", minimum=12, maximum=2000)
    if not url.startswith("https://") or any(character.isspace() for character in url):
        raise SkillPortabilityError("Skill portability sources require a clickable HTTPS URL")
    immutable_id = _text(value.get("immutable_id"), "skill_portability_source.immutable_id", minimum=6, maximum=200)
    if source_type == "repository" and not HEX_40.fullmatch(immutable_id.lower()):
        raise SkillPortabilityError("repository sources require an immutable 40-character commit")
    if source_type == "primary_paper" and not (
        re.search(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b", immutable_id, re.I)
        or immutable_id.lower().startswith("10.")
    ):
        raise SkillPortabilityError("primary-paper sources require a versioned arXiv id or DOI")
    return {
        "source_id": _identifier(value.get("source_id"), "skill_portability_source.source_id"),
        "source_type": source_type,
        "title": _text(value.get("title"), "skill_portability_source.title", minimum=3, maximum=500),
        "url": url,
        "immutable_id": immutable_id,
        "mechanism": _text(value.get("mechanism"), "skill_portability_source.mechanism", minimum=12),
        "limitations": _text(value.get("limitations"), "skill_portability_source.limitations", minimum=12),
        "registration_required": False,
        "recorded_at": utc_now(),
    }


def record_skill_portability_source(
    root: str | os.PathLike[str], *, portability_id: str, source: dict[str, Any],
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, portability_id)
    if state["finalization"] is not None:
        raise SkillPortabilityError("finalized Skill portability protocols are append-only")
    normalized = _normalize_source(source)
    if normalized["source_id"] in {item["source_id"] for item in state["sources"]}:
        raise SkillPortabilityError("Skill portability source id already exists")
    state["sources"].append(_seal_record(normalized, "source_sha256"))
    _append_event(state, "source_recorded", normalized["source_id"])
    _save_state(base, state)
    return {"status": "RECORDED", **state["sources"][-1]}


def _safe_trial_path(base: Path, value: Any) -> tuple[str, Path]:
    raw = Path(_text(value, "skill_portability_trial_path", maximum=1000))
    path = raw.resolve() if raw.is_absolute() else (base / raw).resolve()
    try:
        relative = path.relative_to(base).as_posix()
    except ValueError as exc:
        raise SkillPortabilityError("Skill portability trial artifacts must stay inside project_root") from exc
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise SkillPortabilityError("Skill portability trial artifact must be an existing bounded non-symlink file")
    return relative, path


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _normalize_trial(state: dict[str, Any], document: Any) -> dict[str, Any]:
    allowed = {
        "schema_version", "portability_id", "cell_id", "replicate", "run_id", "case_ids",
        "frontier_protocol_id", "candidate_artifact_sha256", "baseline_run_sha256",
        "candidate_run_sha256", "execution_receipt_sha256", "metrics", "producer",
    }
    if not isinstance(document, dict) or set(document) != allowed or document.get("schema_version") != SCHEMA_VERSION:
        raise SkillPortabilityError("Skill portability trial artifact has an unsupported schema")
    if document.get("portability_id") != state["portability_id"]:
        raise SkillPortabilityError("Skill portability trial id does not match")
    cell_id = _identifier(document.get("cell_id"), "trial.cell_id")
    cell = next((item for item in state["protocol"]["cells"] if item["cell_id"] == cell_id), None)
    if cell is None:
        raise SkillPortabilityError("Skill portability trial cell is not frozen in the protocol")
    replicate = document.get("replicate")
    if isinstance(replicate, bool) or not isinstance(replicate, int) or not 1 <= replicate <= state["protocol"]["replicates"]:
        raise SkillPortabilityError("trial.replicate is outside the frozen protocol")
    case_ids = _case_ids(document.get("case_ids"), "trial.case_ids")
    if case_ids != cell["case_ids"]:
        raise SkillPortabilityError("trial case ids do not exactly match the frozen cell")
    if document.get("frontier_protocol_id") != state["protocol"]["frontier_protocol_id"]:
        raise SkillPortabilityError("trial frontier protocol id does not match")
    candidate_hash = _lower_hex(
        document.get("candidate_artifact_sha256"), "trial.candidate_artifact_sha256", HEX_64,
    )
    if candidate_hash != state["protocol"]["source_binding"]["artifact_sha256"]:
        raise SkillPortabilityError("trial candidate artifact does not match the finalized P24 artifact")
    baseline_run_hash = _lower_hex(document.get("baseline_run_sha256"), "trial.baseline_run_sha256", HEX_64)
    candidate_run_hash = _lower_hex(document.get("candidate_run_sha256"), "trial.candidate_run_sha256", HEX_64)
    receipt_hash = _lower_hex(document.get("execution_receipt_sha256"), "trial.execution_receipt_sha256", HEX_64)
    if baseline_run_hash == candidate_run_hash:
        raise SkillPortabilityError("paired baseline and candidate run hashes must differ")
    metric_contract = {item["name"]: item for item in state["protocol"]["metrics"]}
    metric_values = document.get("metrics")
    if not isinstance(metric_values, dict) or set(metric_values) != set(metric_contract):
        raise SkillPortabilityError("trial metrics must exactly match the P24 metric contract")
    normalized_metrics: dict[str, dict[str, float | bool]] = {}
    safety_pass = True
    utility_non_regression = True
    utility_improved = False
    for name, contract in metric_contract.items():
        values = metric_values[name]
        if not isinstance(values, dict) or set(values) != {"baseline", "candidate"}:
            raise SkillPortabilityError(f"trial metric {name} must contain baseline and candidate")
        baseline, candidate = values["baseline"], values["candidate"]
        if any(
            isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item))
            for item in (baseline, candidate)
        ):
            raise SkillPortabilityError(f"trial metric {name} values must be finite numbers")
        baseline, candidate = float(baseline), float(candidate)
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
    if not safety_pass:
        classification = "SAFETY_REGRESSION"
    elif not utility_non_regression:
        classification = "NEGATIVE_TRANSFER"
    elif utility_improved:
        classification = "POSITIVE_TRANSFER"
    else:
        classification = "NO_MEASURED_GAIN"
    return {
        "cell_id": cell_id,
        "replicate": replicate,
        "run_id": _identifier(document.get("run_id"), "trial.run_id"),
        "case_ids_sha256": digest(case_ids),
        "frontier_protocol_id": state["protocol"]["frontier_protocol_id"],
        "candidate_artifact_sha256": candidate_hash,
        "baseline_run_sha256": baseline_run_hash,
        "candidate_run_sha256": candidate_run_hash,
        "execution_receipt_sha256": receipt_hash,
        "metrics": normalized_metrics,
        "safety_pass": safety_pass,
        "utility_non_regression": utility_non_regression,
        "utility_improved": utility_improved,
        "classification": classification,
        "producer": _text(document.get("producer"), "trial.producer", minimum=3, maximum=200),
        "evidence_boundary": "artifact-backed reported execution; not independently re-executed by this core",
        "recorded_at": utc_now(),
    }


def record_skill_portability_trial(
    root: str | os.PathLike[str], *, portability_id: str, trial_path: str,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, portability_id)
    if state["finalization"] is not None:
        raise SkillPortabilityError("finalized Skill portability protocols are append-only")
    relative, path = _safe_trial_path(base, trial_path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SkillPortabilityError(f"Unreadable Skill portability trial artifact: {exc}") from exc
    trial = _normalize_trial(state, document)
    key = (trial["cell_id"], trial["replicate"])
    if key in {(item["cell_id"], item["replicate"]) for item in state["trials"]}:
        raise SkillPortabilityError("Skill portability cell/replicate is append-only")
    if trial["run_id"] in {item["run_id"] for item in state["trials"]}:
        raise SkillPortabilityError("Skill portability run_id must be unique")
    if trial["execution_receipt_sha256"] in {
        item["execution_receipt_sha256"] for item in state["trials"]
    }:
        raise SkillPortabilityError("Skill portability execution receipt hashes must be unique")
    observed_run_hashes = {
        value for item in state["trials"]
        for value in (item["baseline_run_sha256"], item["candidate_run_sha256"])
    }
    if {trial["baseline_run_sha256"], trial["candidate_run_sha256"]} & observed_run_hashes:
        raise SkillPortabilityError("Skill portability run hashes must be unique")
    completed = sorted(
        item["replicate"] for item in state["trials"] if item["cell_id"] == trial["cell_id"]
    )
    if trial["replicate"] != len(completed) + 1:
        raise SkillPortabilityError("Skill portability trials must follow frozen replicate order")
    trial["artifact_path"] = relative
    trial["artifact_sha256"] = _file_sha256(path)
    state["trials"].append(_seal_record(trial, "trial_sha256"))
    _append_event(state, "trial_recorded", f"{trial['cell_id']}:{trial['replicate']}")
    _save_state(base, state)
    return {
        "status": "RECORDED_NOT_EXPOSED",
        "cell_id": trial["cell_id"],
        "replicate": trial["replicate"],
        "run_id": trial["run_id"],
        "artifact_path": relative,
        "artifact_sha256": trial["artifact_sha256"],
    }


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


def _binding_failures(base: Path, state: dict[str, Any]) -> list[str]:
    protocol = state["protocol"]
    try:
        handoff = _frontier_handoff(
            base, protocol["frontier_protocol_id"], protocol["source_binding"],
        )
    except SkillPortabilityError as exc:
        return [str(exc)]
    failures = []
    if handoff["protocol_sha256"] != protocol["frontier_protocol_sha256"]:
        failures.append("frontier protocol hash changed")
    if handoff["finalization_sha256"] != protocol["frontier_finalization_sha256"]:
        failures.append("frontier finalization hash changed")
    if handoff["occupied_case_ids_sha256"] != protocol["frontier_case_ids_sha256"]:
        failures.append("frontier case boundary changed")
    if handoff["metrics"] != protocol["metrics"]:
        failures.append("frontier metric contract changed")
    return failures


def _cell_classification(trials: list[dict[str, Any]]) -> str:
    classifications = {item["classification"] for item in trials}
    if "SAFETY_REGRESSION" in classifications:
        return "SAFETY_REGRESSION"
    if "NEGATIVE_TRANSFER" in classifications:
        return "NEGATIVE_TRANSFER"
    if classifications == {"POSITIVE_TRANSFER"}:
        return "POSITIVE_TRANSFER"
    if classifications == {"NO_MEASURED_GAIN"}:
        return "NO_MEASURED_GAIN"
    return "MIXED_OR_UNCERTAIN"


def finalize_skill_portability(
    root: str | os.PathLike[str], *, portability_id: str,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, portability_id)
    if state["finalization"] is not None:
        raise SkillPortabilityError("Skill portability finalization is append-only")
    failures = _artifact_failures(base, state) + _binding_failures(base, state)
    source_types = {item["source_type"] for item in state["sources"]}
    if "primary_paper" not in source_types:
        failures.append("portability protocol lacks a primary-paper source")
    if "repository" not in source_types:
        failures.append("portability protocol lacks an immutable repository source")
    expected_replicates = state["protocol"]["replicates"]
    cells: list[dict[str, Any]] = []
    for cell in state["protocol"]["cells"]:
        trials = sorted(
            (item for item in state["trials"] if item["cell_id"] == cell["cell_id"]),
            key=lambda item: item["replicate"],
        )
        if [item["replicate"] for item in trials] != list(range(1, expected_replicates + 1)):
            failures.append(f"complete matrix is missing {cell['cell_id']} replicates")
            continue
        cells.append({
            "cell_id": cell["cell_id"],
            "agent_id": cell["agent_id"],
            "model_family": cell["model_family"],
            "model_version": cell["model_version"],
            "harness": cell["harness"],
            "harness_version": cell["harness_version"],
            "task_scope": cell["task_scope"],
            "executor_group": cell["executor_group"],
            "evidence_family": cell["evidence_family"],
            "case_count": len(cell["case_ids"]),
            "case_ids_sha256": cell["case_ids_sha256"],
            "classification": _cell_classification(trials),
            "replicates": [{
                "replicate": item["replicate"],
                "classification": item["classification"],
                "metrics": item["metrics"],
                "execution_receipt_sha256": item["execution_receipt_sha256"],
                "artifact_sha256": item["artifact_sha256"],
            } for item in trials],
        })
    if failures:
        raise SkillPortabilityError("SKILL_PORTABILITY_FINALIZATION_BLOCKED: " + "; ".join(failures))
    classifications = {item["classification"] for item in cells}
    if "SAFETY_REGRESSION" in classifications:
        support_status = "NOT_SUPPORTED_SAFETY_REGRESSION"
    elif "NEGATIVE_TRANSFER" in classifications:
        support_status = "PARTIAL_OR_NOT_SUPPORTED"
    elif classifications == {"POSITIVE_TRANSFER"}:
        support_status = "SUPPORTED_ON_RECORDED_CELLS"
    else:
        support_status = "NOT_DEMONSTRATED"
    scoped_claim_allowed = support_status == "SUPPORTED_ON_RECORDED_CELLS"
    evidence_family_count = len({item["evidence_family"] for item in cells})
    finalization = {
        "status": "HUMAN_REVIEW_REQUIRED",
        "support_status": support_status,
        "scoped_claim_allowed": scoped_claim_allowed,
        "universal_claim_allowed": False,
        "independent_corroboration": scoped_claim_allowed and evidence_family_count >= 2,
        "evidence_family_count": evidence_family_count,
        "claim_scope": {
            "cell_ids": [item["cell_id"] for item in cells],
            "varying_dimensions": state["protocol"]["varying_dimensions"],
            "candidate_artifact_sha256": state["protocol"]["source_binding"]["artifact_sha256"],
        },
        "cells": cells,
        "aggregation_policy": "no cross-cell score average; every cell classification remains visible",
        "apply_route_exposed": False,
        "admission_effect": "none; this optional protocol qualifies only a recorded portability claim",
        "finalized_at": utc_now(),
    }
    state["finalization"] = _seal_record(finalization, "finalization_sha256")
    _append_event(state, "portability_finalized", portability_id)
    _save_state(base, state)
    return skill_portability_status(base, portability_id)


def skill_portability_status(
    root: str | os.PathLike[str], portability_id: str,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, portability_id)
    finalization = state.get("finalization")
    trials = []
    for trial in state["trials"]:
        summary = {
            "cell_id": trial["cell_id"],
            "replicate": trial["replicate"],
            "artifact_path": trial["artifact_path"],
            "artifact_sha256": trial["artifact_sha256"],
        }
        if finalization is None:
            summary["status"] = "RECORDED_NOT_EXPOSED"
        else:
            summary["status"] = trial["classification"]
        trials.append(summary)
    return {
        "status": finalization["status"] if finalization else "ACTION_REQUIRED",
        "portability_id": portability_id,
        "protocol_sha256": state["protocol_sha256"],
        "state_sha256": state["state_sha256"],
        "frontier_protocol_id": state["protocol"]["frontier_protocol_id"],
        "source_binding": state["protocol"]["source_binding"],
        "replicates_required": state["protocol"]["replicates"],
        "varying_dimensions": state["protocol"]["varying_dimensions"],
        "cells": [{
            "cell_id": item["cell_id"],
            "agent_id": item["agent_id"],
            "model_family": item["model_family"],
            "model_version": item["model_version"],
            "harness": item["harness"],
            "harness_version": item["harness_version"],
            "task_scope": item["task_scope"],
            "executor_group": item["executor_group"],
            "evidence_family": item["evidence_family"],
            "case_count": len(item["case_ids"]),
            "case_ids_sha256": item["case_ids_sha256"],
        } for item in state["protocol"]["cells"]],
        "sources": [{
            "source_id": item["source_id"],
            "source_type": item["source_type"],
            "title": item["title"],
            "url": item["url"],
            "immutable_id": item["immutable_id"],
        } for item in state["sources"]],
        "trials": trials,
        "finalization": finalization,
        "execution_allowed_by_core": False,
        "apply_route_exposed": False,
        "next_action": (
            "Human-review the exact per-cell support boundary; do not generalize beyond recorded cells."
            if finalization else
            "Record primary sources and every frozen cell/replicate artifact, then finalize the matrix."
        ),
    }


def verify_skill_portability(
    root: str | os.PathLike[str], portability_id: str,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, portability_id)
    failures = _artifact_failures(base, state) + _binding_failures(base, state)
    finalization = state.get("finalization")
    return {
        "status": "FAIL" if failures else ("PASS" if finalization is not None else "ACTION_REQUIRED"),
        "integrity_status": "PASS" if not failures else "FAIL",
        "portability_id": portability_id,
        "state_sha256": state["state_sha256"],
        "finalized": finalization is not None,
        "support_status": finalization.get("support_status") if finalization else None,
        "scoped_claim_allowed": bool(finalization and finalization["scoped_claim_allowed"]),
        "universal_claim_allowed": False,
        "artifact_failures": failures,
        "third_party_execution_observed_by_core": False,
    }
