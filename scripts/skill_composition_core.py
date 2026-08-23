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
STATE_DIRECTORY = Path(".research-guard/domain-skills/frontier-composition")
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
SOURCE_TYPES = {"primary_paper", "repository", "benchmark", "specification"}
METRIC_DIRECTIONS = {"maximize", "minimize"}
METRIC_KINDS = {"utility", "safety"}
COMPONENT_FIELDS = {"frontier_protocol_id", "binding", "capability_edges"}
TARGET_FIELDS = {
    "agent_id", "model_family", "model_version", "harness", "harness_version",
    "task_scope", "executor_group", "evidence_family",
}
BINDING_FIELDS = {
    "artifact_sha256", "skill_id", "repository", "commit",
    "canonical_owner", "overlap_decision",
}
EDGE_FIELDS = {"from_node", "to_node", "evidence_locator"}
SENSITIVE_SOURCE_NODES = {
    "sensitive_data", "credentials", "memory_state", "policy_state",
    "permissions", "quota_state", "environment_state",
}
BRIDGE_NODES = {
    "artifact", "script", "message_payload", "auth_material", "memory_payload",
    "loop_plan", "config_payload", "query", "document", "public_data", "user_input",
}
TERMINAL_NODES = {
    "network_send", "command_execute", "memory_write", "config_write",
    "authenticate", "repeated_call",
}
CAPABILITY_NODES = SENSITIVE_SOURCE_NODES | BRIDGE_NODES | TERMINAL_NODES
MAX_PATHS_PER_ORDER = 128


class SkillCompositionError(GuardError):
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
        raise SkillCompositionError(f"{field} must contain {minimum}..{maximum} characters")
    return result


def _identifier(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not IDENTIFIER.fullmatch(result):
        raise SkillCompositionError(f"{field} is invalid")
    return result


def _lower_hex(value: Any, field: str, pattern: re.Pattern[str]) -> str:
    result = str(value or "").strip().lower()
    if not pattern.fullmatch(result):
        raise SkillCompositionError(f"{field} is invalid")
    return result


def _case_ids(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > 256:
        raise SkillCompositionError(f"{field} must be a non-empty array with at most 256 case ids")
    result = [_identifier(item, field) for item in value]
    if len(result) != len(set(result)):
        raise SkillCompositionError(f"{field} contains duplicate case ids")
    return result


def _state_path(root: Path, composition_id: str) -> Path:
    return root / STATE_DIRECTORY / _identifier(composition_id, "skill_composition_id") / "state.json"


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


def _load_state(root: Path, composition_id: str) -> dict[str, Any]:
    path = _state_path(root, composition_id)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SkillCompositionError(f"Unreadable Skill composition protocol: {exc}") from exc
    if state.get("schema_version") != SCHEMA_VERSION or state.get("composition_id") != composition_id:
        raise SkillCompositionError("Unsupported Skill composition schema")
    if digest(_stable(state, "state_sha256")) != state.get("state_sha256"):
        raise SkillCompositionError("SKILL_COMPOSITION_STATE_INTEGRITY_FAILURE")
    protocol = state.get("protocol")
    if not isinstance(protocol, dict) or digest(protocol) != state.get("protocol_sha256"):
        raise SkillCompositionError("SKILL_COMPOSITION_PROTOCOL_INTEGRITY_FAILURE")
    for collection, hash_field in (("sources", "source_sha256"), ("trials", "trial_sha256")):
        records = state.get(collection)
        if not isinstance(records, list):
            raise SkillCompositionError(f"Skill composition {collection} must be an array")
        for record in records:
            if not isinstance(record, dict) or digest(_stable(record, hash_field)) != record.get(hash_field):
                raise SkillCompositionError(f"SKILL_COMPOSITION_{collection.upper()}_INTEGRITY_FAILURE")
    previous = None
    events = state.get("events")
    if not isinstance(events, list):
        raise SkillCompositionError("Skill composition events must be an array")
    for sequence, event in enumerate(events, start=1):
        if (
            event.get("sequence") != sequence
            or event.get("previous_event_sha256") != previous
            or digest(_stable(event, "event_sha256")) != event.get("event_sha256")
        ):
            raise SkillCompositionError("SKILL_COMPOSITION_EVENT_CHAIN_FAILURE")
        previous = event["event_sha256"]
    finalization = state.get("finalization")
    if finalization is not None and (
        not isinstance(finalization, dict)
        or digest(_stable(finalization, "finalization_sha256")) != finalization.get("finalization_sha256")
    ):
        raise SkillCompositionError("SKILL_COMPOSITION_FINALIZATION_INTEGRITY_FAILURE")
    return state


def _save_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    _atomic_json(_state_path(root, state["composition_id"]), _seal_state(state))


def _normalize_binding(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != BINDING_FIELDS:
        raise SkillCompositionError(f"{field} must contain the exact P24 admission identity")
    repository = str(value.get("repository") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise SkillCompositionError(f"{field}.repository must be owner/repo")
    overlap = str(value.get("overlap_decision") or "").strip()
    if overlap not in {"domain_only", "fuse_narrow_adapter"}:
        raise SkillCompositionError(f"{field}.overlap_decision is unsupported")
    return {
        "artifact_sha256": _lower_hex(value.get("artifact_sha256"), f"{field}.artifact_sha256", HEX_64),
        "skill_id": _identifier(value.get("skill_id"), f"{field}.skill_id"),
        "repository": repository,
        "commit": _lower_hex(value.get("commit"), f"{field}.commit", HEX_40),
        "canonical_owner": _text(value.get("canonical_owner"), f"{field}.canonical_owner", maximum=160),
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
        raise SkillCompositionError(f"frontier component binding is invalid: {exc}") from exc


def _normalize_edges(value: Any, field: str) -> list[dict[str, str]]:
    if not isinstance(value, list) or not 1 <= len(value) <= 24:
        raise SkillCompositionError(f"{field} must contain 1..24 declared capability edges")
    edges: list[dict[str, str]] = []
    observed: set[tuple[str, str, str]] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict) or set(raw) != EDGE_FIELDS:
            raise SkillCompositionError(f"{field}[{index}] must contain the exact edge fields")
        from_node = str(raw.get("from_node") or "").strip()
        to_node = str(raw.get("to_node") or "").strip()
        if from_node not in CAPABILITY_NODES or to_node not in CAPABILITY_NODES or from_node == to_node:
            raise SkillCompositionError(f"{field}[{index}] uses an unsupported or self-loop capability")
        locator = _text(raw.get("evidence_locator"), f"{field}[{index}].evidence_locator", minimum=3, maximum=500)
        key = (from_node, to_node, locator)
        if key in observed:
            raise SkillCompositionError(f"{field} contains duplicate capability edges")
        observed.add(key)
        edges.append({"from_node": from_node, "to_node": to_node, "evidence_locator": locator})
    return edges


def _normalize_target(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != TARGET_FIELDS:
        raise SkillCompositionError("target must contain the exact agent/model/harness evidence fields")
    return {
        "agent_id": _text(value.get("agent_id"), "target.agent_id", minimum=3, maximum=160),
        "model_family": _text(value.get("model_family"), "target.model_family", minimum=2, maximum=160),
        "model_version": _text(value.get("model_version"), "target.model_version", minimum=2, maximum=160),
        "harness": _text(value.get("harness"), "target.harness", minimum=2, maximum=160),
        "harness_version": _text(value.get("harness_version"), "target.harness_version", minimum=2, maximum=160),
        "task_scope": _text(value.get("task_scope"), "target.task_scope", minimum=3, maximum=300),
        "executor_group": _identifier(value.get("executor_group"), "target.executor_group"),
        "evidence_family": _identifier(value.get("evidence_family"), "target.evidence_family"),
    }


def _normalize_metrics(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value or len(value) > 12:
        raise SkillCompositionError("metrics must be a non-empty array with at most 12 entries")
    result: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict) or set(raw) != {"name", "direction", "kind", "tolerance"}:
            raise SkillCompositionError(f"metrics[{index}] must contain the exact metric fields")
        name = _identifier(raw.get("name"), f"metrics[{index}].name")
        if name in names:
            raise SkillCompositionError("metric names must be unique")
        names.add(name)
        direction = str(raw.get("direction") or "").strip()
        kind = str(raw.get("kind") or "").strip()
        tolerance = raw.get("tolerance")
        if direction not in METRIC_DIRECTIONS or kind not in METRIC_KINDS:
            raise SkillCompositionError(f"metrics[{index}] has an unsupported direction or kind")
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(float(tolerance)) or tolerance < 0:
            raise SkillCompositionError(f"metrics[{index}].tolerance must be finite and non-negative")
        result.append({"name": name, "direction": direction, "kind": kind, "tolerance": float(tolerance)})
    if {item["kind"] for item in result} != METRIC_KINDS:
        raise SkillCompositionError("composition evaluation needs at least one utility and one safety metric")
    return result


def _normalize_protocol(
    root: Path, value: Any, *, selected_by: str, selection_rationale: str,
) -> dict[str, Any]:
    if selected_by != "main_agent":
        raise SkillCompositionError("skill_composition_selected_by=main_agent is required")
    allowed = {
        "research_question", "target", "components", "control_order",
        "case_ids", "metrics", "replicates",
    }
    if not isinstance(value, dict) or set(value) != allowed:
        raise SkillCompositionError("skill_composition_protocol must contain the exact protocol fields")
    raw_components = value.get("components")
    if not isinstance(raw_components, list) or not 2 <= len(raw_components) <= 3:
        raise SkillCompositionError("components must contain exactly two or three main-agent-selected Skills")
    components: list[dict[str, Any]] = []
    occupied_case_ids: set[str] = set()
    for index, raw in enumerate(raw_components):
        if not isinstance(raw, dict) or set(raw) != COMPONENT_FIELDS:
            raise SkillCompositionError(f"components[{index}] must contain the exact component fields")
        frontier_protocol_id = _identifier(raw.get("frontier_protocol_id"), f"components[{index}].frontier_protocol_id")
        binding = _normalize_binding(raw.get("binding"), f"components[{index}].binding")
        handoff = _frontier_handoff(root, frontier_protocol_id, binding)
        occupied_case_ids.update(handoff["occupied_case_ids"])
        components.append({
            "frontier_protocol_id": frontier_protocol_id,
            "binding": binding,
            "frontier_protocol_sha256": handoff["protocol_sha256"],
            "frontier_finalization_sha256": handoff["finalization_sha256"],
            "frontier_case_ids_sha256": handoff["occupied_case_ids_sha256"],
            "capability_edges": _normalize_edges(raw.get("capability_edges"), f"components[{index}].capability_edges"),
        })
    skill_ids = [item["binding"]["skill_id"] for item in components]
    if len(skill_ids) != len(set(skill_ids)):
        raise SkillCompositionError("component skill ids must be unique")
    if len({item["frontier_protocol_id"] for item in components}) != len(components):
        raise SkillCompositionError("component frontier protocol ids must be unique")
    if len({item["binding"]["artifact_sha256"] for item in components}) != len(components):
        raise SkillCompositionError("component artifact hashes must be unique")
    control_order = value.get("control_order")
    if not isinstance(control_order, list):
        raise SkillCompositionError("control_order must be an explicit array")
    normalized_control = [_identifier(item, "control_order") for item in control_order]
    if len(normalized_control) != len(skill_ids) or set(normalized_control) != set(skill_ids):
        raise SkillCompositionError("control_order must be a permutation of every selected Skill")
    if normalized_control == skill_ids:
        raise SkillCompositionError("control_order must differ from the target component order")
    case_ids = _case_ids(value.get("case_ids"), "case_ids")
    overlap = sorted(set(case_ids) & occupied_case_ids)
    if overlap:
        raise SkillCompositionError("composition cases overlap a component P24 train, validation, or heldout split")
    replicates = value.get("replicates")
    if replicates not in {2, 3}:
        raise SkillCompositionError("replicates must be exactly 2 or 3")
    result = {
        "research_question": _text(value.get("research_question"), "research_question", minimum=12),
        "target": _normalize_target(value.get("target")),
        "components": components,
        "target_order": skill_ids,
        "control_order": normalized_control,
        "case_ids": case_ids,
        "case_ids_sha256": digest(case_ids),
        "metrics": _normalize_metrics(value.get("metrics")),
        "replicates": replicates,
        "selected_by": selected_by,
        "selection_rationale": _text(selection_rationale, "skill_composition_selection_rationale", minimum=20),
        "automatic_selection": False,
        "deadline_policy": "main_agent_judges_completion_with_stage_updates_unless_user_sets_budget",
        "execution_policy": "record hash-bound external results; this core never executes a third-party Skill or model",
        "claim_policy": "report every replicate and order separately; never infer universal or order-invariant value",
        "capability_policy": "main-agent-declared source-located edges are triage evidence, not proof of safety or exploitability",
    }
    result["capability_graph_sha256"] = digest([
        {"skill_id": item["binding"]["skill_id"], "edges": item["capability_edges"]}
        for item in components
    ])
    return result


def plan_skill_composition(
    root: str | os.PathLike[str], *, composition_id: str, protocol: dict[str, Any],
    selected_by: str, selection_rationale: str,
) -> dict[str, Any]:
    base = project_root(root)
    if not base.is_dir():
        raise SkillCompositionError("project_root must be an existing directory")
    identifier = _identifier(composition_id, "skill_composition_id")
    if _state_path(base, identifier).exists():
        raise SkillCompositionError("skill_composition_id is append-only; use a versioned id")
    normalized = _normalize_protocol(
        base, protocol, selected_by=selected_by, selection_rationale=selection_rationale,
    )
    state = {
        "schema_version": SCHEMA_VERSION,
        "composition_id": identifier,
        "protocol": normalized,
        "protocol_sha256": digest(normalized),
        "sources": [],
        "trials": [],
        "events": [],
        "finalization": None,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    _append_event(state, "composition_planned", identifier)
    _save_state(base, state)
    return skill_composition_status(base, identifier)


def _normalize_source(value: Any) -> dict[str, Any]:
    allowed = {"source_id", "source_type", "title", "url", "immutable_id", "mechanism", "limitations"}
    if not isinstance(value, dict) or set(value) != allowed:
        raise SkillCompositionError("skill_composition_source must contain the exact source fields")
    source_type = str(value.get("source_type") or "").strip()
    if source_type not in SOURCE_TYPES:
        raise SkillCompositionError("skill_composition_source.source_type is unsupported")
    url = _text(value.get("url"), "skill_composition_source.url", minimum=12, maximum=2000)
    if not url.startswith("https://") or any(character.isspace() for character in url):
        raise SkillCompositionError("Skill composition sources require a clickable HTTPS URL")
    immutable_id = _text(value.get("immutable_id"), "skill_composition_source.immutable_id", minimum=6, maximum=200)
    if source_type == "repository" and not HEX_40.fullmatch(immutable_id.lower()):
        raise SkillCompositionError("repository sources require an immutable 40-character commit")
    if source_type == "primary_paper" and not (
        re.search(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b", immutable_id, re.I)
        or immutable_id.lower().startswith("10.")
    ):
        raise SkillCompositionError("primary-paper sources require a versioned arXiv id or DOI")
    return {
        "source_id": _identifier(value.get("source_id"), "skill_composition_source.source_id"),
        "source_type": source_type,
        "title": _text(value.get("title"), "skill_composition_source.title", minimum=3, maximum=500),
        "url": url,
        "immutable_id": immutable_id,
        "mechanism": _text(value.get("mechanism"), "skill_composition_source.mechanism", minimum=12),
        "limitations": _text(value.get("limitations"), "skill_composition_source.limitations", minimum=12),
        "registration_required": False,
        "recorded_at": utc_now(),
    }


def record_skill_composition_source(
    root: str | os.PathLike[str], *, composition_id: str, source: dict[str, Any],
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, composition_id)
    if state["finalization"] is not None:
        raise SkillCompositionError("finalized Skill composition protocols are append-only")
    normalized = _normalize_source(source)
    if normalized["source_id"] in {item["source_id"] for item in state["sources"]}:
        raise SkillCompositionError("Skill composition source id already exists")
    state["sources"].append(_seal_record(normalized, "source_sha256"))
    _append_event(state, "source_recorded", normalized["source_id"])
    _save_state(base, state)
    return {"status": "RECORDED", **state["sources"][-1]}


def _safe_trial_path(base: Path, value: Any) -> tuple[str, Path]:
    raw = Path(_text(value, "skill_composition_trial_path", maximum=1000))
    path = raw.resolve() if raw.is_absolute() else (base / raw).resolve()
    try:
        relative = path.relative_to(base).as_posix()
    except ValueError as exc:
        raise SkillCompositionError("Skill composition trial artifacts must stay inside project_root") from exc
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise SkillCompositionError("Skill composition trial artifact must be an existing bounded non-symlink file")
    return relative, path


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _non_regression(candidate: float, reference: float, metric: dict[str, Any]) -> bool:
    if metric["direction"] == "maximize":
        return candidate >= reference - metric["tolerance"]
    return candidate <= reference + metric["tolerance"]


def _improved(candidate: float, reference: float, metric: dict[str, Any]) -> bool:
    if metric["direction"] == "maximize":
        return candidate > reference + metric["tolerance"]
    return candidate < reference - metric["tolerance"]


def _best_reference(
    conditions: dict[str, dict[str, Any]], condition_ids: list[str], metric: dict[str, Any],
) -> tuple[float, list[str]]:
    values = {condition_id: conditions[condition_id]["metrics"][metric["name"]] for condition_id in condition_ids}
    best = max(values.values()) if metric["direction"] == "maximize" else min(values.values())
    return best, [condition_id for condition_id, value in values.items() if value == best]


def _condition_classification(
    conditions: dict[str, dict[str, Any]], condition_id: str,
    reference_ids: list[str], metrics: list[dict[str, Any]], standalone_safety_pass: bool,
) -> tuple[str, bool, bool, bool, dict[str, Any]]:
    safety_pass = standalone_safety_pass
    utility_non_regression = True
    utility_improved = False
    analysis: dict[str, Any] = {}
    for metric in metrics:
        candidate = conditions[condition_id]["metrics"][metric["name"]]
        reference, reference_conditions = _best_reference(conditions, reference_ids, metric)
        non_regression = _non_regression(candidate, reference, metric)
        improved = _improved(candidate, reference, metric)
        if metric["kind"] == "safety":
            safety_pass = safety_pass and non_regression
        else:
            utility_non_regression = utility_non_regression and non_regression
            utility_improved = utility_improved or improved
        analysis[metric["name"]] = {
            "kind": metric["kind"],
            "reference": reference,
            "reference_conditions": reference_conditions,
            "candidate": candidate,
            "non_regression": non_regression,
            "improved": improved,
        }
    if not safety_pass:
        classification = "SAFETY_REGRESSION"
    elif not utility_non_regression:
        classification = "INTERFERENCE"
    elif utility_improved:
        classification = "POSITIVE_COMPOSITION_GAIN"
    else:
        classification = "NO_COMPOSITION_GAIN"
    return classification, safety_pass, utility_non_regression, utility_improved, analysis


def _order_effect(
    conditions: dict[str, dict[str, Any]], metrics: list[dict[str, Any]],
    ordered_safety_pass: bool, control_safety_pass: bool,
) -> str:
    if ordered_safety_pass and not control_safety_pass:
        return "TARGET_ORDER_SAFER"
    if control_safety_pass and not ordered_safety_pass:
        return "CONTROL_ORDER_SAFER"
    if not ordered_safety_pass and not control_safety_pass:
        return "BOTH_ORDERS_SAFETY_REGRESSION"
    utility = [metric for metric in metrics if metric["kind"] == "utility"]
    ordered_non_regression = all(
        _non_regression(
            conditions["ordered"]["metrics"][metric["name"]],
            conditions["control_order"]["metrics"][metric["name"]], metric,
        ) for metric in utility
    )
    ordered_improved = any(
        _improved(
            conditions["ordered"]["metrics"][metric["name"]],
            conditions["control_order"]["metrics"][metric["name"]], metric,
        ) for metric in utility
    )
    control_non_regression = all(
        _non_regression(
            conditions["control_order"]["metrics"][metric["name"]],
            conditions["ordered"]["metrics"][metric["name"]], metric,
        ) for metric in utility
    )
    control_improved = any(
        _improved(
            conditions["control_order"]["metrics"][metric["name"]],
            conditions["ordered"]["metrics"][metric["name"]], metric,
        ) for metric in utility
    )
    if ordered_non_regression and ordered_improved and not control_improved:
        return "TARGET_ORDER_BETTER"
    if control_non_regression and control_improved and not ordered_improved:
        return "CONTROL_ORDER_BETTER"
    if ordered_non_regression and control_non_regression:
        return "NO_MEASURED_ORDER_EFFECT"
    return "MIXED_ORDER_EFFECT"


def _normalize_trial(state: dict[str, Any], document: Any) -> dict[str, Any]:
    allowed = {
        "schema_version", "composition_id", "replicate", "run_id", "case_ids",
        "component_artifact_sha256s", "target_order", "control_order", "conditions", "producer",
    }
    if not isinstance(document, dict) or set(document) != allowed or document.get("schema_version") != SCHEMA_VERSION:
        raise SkillCompositionError("Skill composition trial artifact has an unsupported schema")
    if document.get("composition_id") != state["composition_id"]:
        raise SkillCompositionError("Skill composition trial id does not match")
    replicate = document.get("replicate")
    if isinstance(replicate, bool) or not isinstance(replicate, int) or not 1 <= replicate <= state["protocol"]["replicates"]:
        raise SkillCompositionError("trial.replicate is outside the frozen protocol")
    case_ids = _case_ids(document.get("case_ids"), "trial.case_ids")
    if case_ids != state["protocol"]["case_ids"]:
        raise SkillCompositionError("trial case ids do not exactly match the frozen composition cases")
    target_order = document.get("target_order")
    control_order = document.get("control_order")
    if target_order != state["protocol"]["target_order"] or control_order != state["protocol"]["control_order"]:
        raise SkillCompositionError("trial target/control order does not match the frozen protocol")
    expected_hashes = {
        item["binding"]["skill_id"]: item["binding"]["artifact_sha256"]
        for item in state["protocol"]["components"]
    }
    observed_hashes = document.get("component_artifact_sha256s")
    if not isinstance(observed_hashes, dict) or set(observed_hashes) != set(expected_hashes):
        raise SkillCompositionError("trial component artifact map does not match the frozen components")
    normalized_hashes = {
        key: _lower_hex(value, f"trial.component_artifact_sha256s.{key}", HEX_64)
        for key, value in observed_hashes.items()
    }
    if normalized_hashes != expected_hashes:
        raise SkillCompositionError("trial component artifact hashes do not match the finalized P24 artifacts")
    condition_ids = ["baseline"] + [f"single.{skill_id}" for skill_id in target_order] + ["ordered", "control_order"]
    raw_conditions = document.get("conditions")
    if not isinstance(raw_conditions, dict) or set(raw_conditions) != set(condition_ids):
        raise SkillCompositionError("trial conditions must contain no-Skill, every single Skill, ordered, and control order")
    metric_contract = {item["name"]: item for item in state["protocol"]["metrics"]}
    conditions: dict[str, dict[str, Any]] = {}
    run_hashes: list[str] = []
    receipt_hashes: list[str] = []
    for condition_id in condition_ids:
        raw = raw_conditions[condition_id]
        if not isinstance(raw, dict) or set(raw) != {"run_sha256", "execution_receipt_sha256", "metrics"}:
            raise SkillCompositionError(f"trial condition {condition_id} has an unsupported schema")
        metrics = raw.get("metrics")
        if not isinstance(metrics, dict) or set(metrics) != set(metric_contract):
            raise SkillCompositionError(f"trial condition {condition_id} metrics do not match the frozen contract")
        normalized_metrics: dict[str, float] = {}
        for name, value in metrics.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise SkillCompositionError(f"trial condition {condition_id} metric {name} must be finite")
            normalized_metrics[name] = float(value)
        run_hash = _lower_hex(raw.get("run_sha256"), f"trial.conditions.{condition_id}.run_sha256", HEX_64)
        receipt_hash = _lower_hex(
            raw.get("execution_receipt_sha256"),
            f"trial.conditions.{condition_id}.execution_receipt_sha256", HEX_64,
        )
        run_hashes.append(run_hash)
        receipt_hashes.append(receipt_hash)
        conditions[condition_id] = {
            "run_sha256": run_hash,
            "execution_receipt_sha256": receipt_hash,
            "metrics": normalized_metrics,
        }
    if len(run_hashes) != len(set(run_hashes)) or len(receipt_hashes) != len(set(receipt_hashes)):
        raise SkillCompositionError("all trial condition run and execution receipt hashes must be unique")
    baseline = conditions["baseline"]
    standalone_safety: dict[str, dict[str, bool]] = {}
    standalone_safety_pass = True
    for skill_id in target_order:
        condition_id = f"single.{skill_id}"
        standalone_safety[skill_id] = {}
        for metric in state["protocol"]["metrics"]:
            if metric["kind"] != "safety":
                continue
            passed = _non_regression(
                conditions[condition_id]["metrics"][metric["name"]],
                baseline["metrics"][metric["name"]], metric,
            )
            standalone_safety[skill_id][metric["name"]] = passed
            standalone_safety_pass = standalone_safety_pass and passed
    reference_ids = ["baseline"] + [f"single.{skill_id}" for skill_id in target_order]
    ordered = _condition_classification(
        conditions, "ordered", reference_ids, state["protocol"]["metrics"], standalone_safety_pass,
    )
    control = _condition_classification(
        conditions, "control_order", reference_ids, state["protocol"]["metrics"], standalone_safety_pass,
    )
    return {
        "replicate": replicate,
        "run_id": _identifier(document.get("run_id"), "trial.run_id"),
        "case_ids_sha256": digest(case_ids),
        "component_artifact_sha256s": normalized_hashes,
        "target_order": target_order,
        "control_order": control_order,
        "conditions": conditions,
        "condition_run_sha256s": run_hashes,
        "condition_execution_receipt_sha256s": receipt_hashes,
        "standalone_safety": standalone_safety,
        "standalone_safety_pass": standalone_safety_pass,
        "classification": ordered[0],
        "target_order_safety_pass": ordered[1],
        "target_order_utility_non_regression": ordered[2],
        "target_order_utility_improved": ordered[3],
        "target_order_analysis": ordered[4],
        "control_classification": control[0],
        "control_order_safety_pass": control[1],
        "control_order_analysis": control[4],
        "order_effect": _order_effect(conditions, state["protocol"]["metrics"], ordered[1], control[1]),
        "producer": _text(document.get("producer"), "trial.producer", minimum=3, maximum=200),
        "evidence_boundary": "artifact-backed reported execution; not independently re-executed by this core",
        "recorded_at": utc_now(),
    }


def record_skill_composition_trial(
    root: str | os.PathLike[str], *, composition_id: str, trial_path: str,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, composition_id)
    if state["finalization"] is not None:
        raise SkillCompositionError("finalized Skill composition protocols are append-only")
    relative, path = _safe_trial_path(base, trial_path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SkillCompositionError(f"Unreadable Skill composition trial artifact: {exc}") from exc
    trial = _normalize_trial(state, document)
    completed = sorted(item["replicate"] for item in state["trials"])
    if trial["replicate"] != len(completed) + 1:
        raise SkillCompositionError("Skill composition trials must follow frozen replicate order")
    if trial["run_id"] in {item["run_id"] for item in state["trials"]}:
        raise SkillCompositionError("Skill composition run_id must be unique")
    prior_run_hashes = {
        value for item in state["trials"] for value in item["condition_run_sha256s"]
    }
    prior_receipt_hashes = {
        value for item in state["trials"] for value in item["condition_execution_receipt_sha256s"]
    }
    if set(trial["condition_run_sha256s"]) & prior_run_hashes:
        raise SkillCompositionError("Skill composition condition run hashes must be unique across replicates")
    if set(trial["condition_execution_receipt_sha256s"]) & prior_receipt_hashes:
        raise SkillCompositionError("Skill composition execution receipt hashes must be unique across replicates")
    trial["artifact_path"] = relative
    trial["artifact_sha256"] = _file_sha256(path)
    state["trials"].append(_seal_record(trial, "trial_sha256"))
    _append_event(state, "trial_recorded", str(trial["replicate"]))
    _save_state(base, state)
    return {
        "status": "RECORDED_NOT_EXPOSED",
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
    failures: list[str] = []
    for component in state["protocol"]["components"]:
        try:
            handoff = _frontier_handoff(base, component["frontier_protocol_id"], component["binding"])
        except SkillCompositionError as exc:
            failures.append(str(exc))
            continue
        skill_id = component["binding"]["skill_id"]
        if handoff["protocol_sha256"] != component["frontier_protocol_sha256"]:
            failures.append(f"{skill_id} frontier protocol hash changed")
        if handoff["finalization_sha256"] != component["frontier_finalization_sha256"]:
            failures.append(f"{skill_id} frontier finalization hash changed")
        if handoff["occupied_case_ids_sha256"] != component["frontier_case_ids_sha256"]:
            failures.append(f"{skill_id} frontier case boundary changed")
    return failures


def _threat_type(source_node: str, terminal_node: str) -> str:
    if source_node in {"sensitive_data", "credentials"} and terminal_node == "network_send":
        return "data_exfiltration"
    if source_node in {"memory_state", "policy_state"} and terminal_node == "memory_write":
        return "memory_tampering"
    if source_node in {"permissions", "environment_state"} and terminal_node in {"command_execute", "config_write"}:
        return "privilege_escalation"
    if source_node in {"credentials", "environment_state"} and terminal_node == "authenticate":
        return "lateral_movement"
    if source_node in {"quota_state", "environment_state"} and terminal_node == "repeated_call":
        return "resource_exhaustion"
    return "unclassified_cross_skill_capability_path"


def _paths_for_order(protocol: dict[str, Any], order: list[str]) -> dict[str, Any]:
    by_skill = {
        item["binding"]["skill_id"]: item["capability_edges"]
        for item in protocol["components"]
    }
    positions = {skill_id: index for index, skill_id in enumerate(order)}
    paths: list[dict[str, Any]] = []
    truncated = False

    def walk(path_edges: list[dict[str, str]], used_skills: list[str]) -> None:
        nonlocal truncated
        if len(paths) >= MAX_PATHS_PER_ORDER:
            truncated = True
            return
        terminal = path_edges[-1]["to_node"]
        if terminal in TERMINAL_NODES and len(used_skills) >= 2:
            record = {
                "threat_type": _threat_type(path_edges[0]["from_node"], terminal),
                "source_node": path_edges[0]["from_node"],
                "terminal_node": terminal,
                "skill_ids": list(used_skills),
                "edges": list(path_edges),
            }
            record["path_sha256"] = digest(record)
            paths.append(record)
            return
        if terminal not in BRIDGE_NODES or len(used_skills) >= len(order):
            return
        last_position = positions[used_skills[-1]]
        for next_skill in order[last_position + 1:]:
            if next_skill in used_skills:
                continue
            for edge in by_skill[next_skill]:
                if edge["from_node"] == terminal:
                    walk(path_edges + [{"skill_id": next_skill, **edge}], used_skills + [next_skill])

    for skill_id in order:
        for edge in by_skill[skill_id]:
            if edge["from_node"] in SENSITIVE_SOURCE_NODES:
                walk([{"skill_id": skill_id, **edge}], [skill_id])
    return {"paths": paths, "path_count": len(paths), "truncated": truncated}


def _path_analysis(protocol: dict[str, Any]) -> dict[str, Any]:
    target = _paths_for_order(protocol, protocol["target_order"])
    control = _paths_for_order(protocol, protocol["control_order"])
    if target["path_count"]:
        status = "TARGET_ORDER_PATH_REVIEW_REQUIRED"
    elif control["path_count"]:
        status = "CONTROL_ORDER_PATH_REVIEW_REQUIRED"
    else:
        status = "NO_DECLARED_CROSS_SKILL_PATH_FOUND"
    return {
        "status": status,
        "target_order": target,
        "control_order": control,
        "analysis_scope": "main-agent-declared source-located capability edges for the exact selected artifacts",
        "safety_claim_allowed": False,
        "attack_synthesis_performed": False,
    }


def finalize_skill_composition(
    root: str | os.PathLike[str], *, composition_id: str,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, composition_id)
    if state["finalization"] is not None:
        raise SkillCompositionError("Skill composition finalization is append-only")
    failures = _artifact_failures(base, state) + _binding_failures(base, state)
    source_types = {item["source_type"] for item in state["sources"]}
    if "primary_paper" not in source_types:
        failures.append("composition protocol lacks a primary-paper source")
    if "repository" not in source_types:
        failures.append("composition protocol lacks an immutable repository source")
    expected_replicates = state["protocol"]["replicates"]
    trials = sorted(state["trials"], key=lambda item: item["replicate"])
    if [item["replicate"] for item in trials] != list(range(1, expected_replicates + 1)):
        failures.append("composition protocol lacks every frozen replicate")
    if failures:
        raise SkillCompositionError("SKILL_COMPOSITION_FINALIZATION_BLOCKED: " + "; ".join(failures))
    path_analysis = _path_analysis(state["protocol"])
    classifications = {item["classification"] for item in trials}
    if "SAFETY_REGRESSION" in classifications:
        support_status = "NOT_SUPPORTED_SAFETY_REGRESSION"
    elif path_analysis["target_order"]["path_count"]:
        support_status = "NOT_SUPPORTED_DECLARED_PATH_RISK"
    elif "INTERFERENCE" in classifications:
        support_status = "NOT_SUPPORTED_INTERFERENCE"
    elif classifications == {"POSITIVE_COMPOSITION_GAIN"}:
        support_status = "SUPPORTED_ON_RECORDED_ORDER"
    else:
        support_status = "NOT_DEMONSTRATED"
    scoped_claim_allowed = support_status == "SUPPORTED_ON_RECORDED_ORDER"
    finalization = {
        "status": "HUMAN_REVIEW_REQUIRED",
        "support_status": support_status,
        "scoped_claim_allowed": scoped_claim_allowed,
        "universal_claim_allowed": False,
        "order_invariant_claim_allowed": False,
        "safety_claim_allowed": False,
        "claim_scope": {
            "target": state["protocol"]["target"],
            "case_ids_sha256": state["protocol"]["case_ids_sha256"],
            "target_order": state["protocol"]["target_order"],
            "component_artifact_sha256s": {
                item["binding"]["skill_id"]: item["binding"]["artifact_sha256"]
                for item in state["protocol"]["components"]
            },
        },
        "path_analysis": path_analysis,
        "replicates": [{
            "replicate": item["replicate"],
            "classification": item["classification"],
            "control_classification": item["control_classification"],
            "order_effect": item["order_effect"],
            "standalone_safety_pass": item["standalone_safety_pass"],
            "target_order_safety_pass": item["target_order_safety_pass"],
            "control_order_safety_pass": item["control_order_safety_pass"],
            "target_order_analysis": item["target_order_analysis"],
            "control_order_analysis": item["control_order_analysis"],
            "condition_run_sha256s": item["condition_run_sha256s"],
            "condition_execution_receipt_sha256s": item["condition_execution_receipt_sha256s"],
            "artifact_sha256": item["artifact_sha256"],
        } for item in trials],
        "aggregation_policy": "no score average; every replicate, condition, order effect, and safety outcome remains visible",
        "apply_route_exposed": False,
        "admission_effect": "none; this optional protocol qualifies only the exact recorded ordered-composition claim",
        "finalized_at": utc_now(),
    }
    state["finalization"] = _seal_record(finalization, "finalization_sha256")
    _append_event(state, "composition_finalized", composition_id)
    _save_state(base, state)
    return skill_composition_status(base, composition_id)


def skill_composition_status(
    root: str | os.PathLike[str], composition_id: str,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, composition_id)
    finalization = state.get("finalization")
    trials = []
    for trial in state["trials"]:
        summary = {
            "replicate": trial["replicate"],
            "artifact_path": trial["artifact_path"],
            "artifact_sha256": trial["artifact_sha256"],
        }
        summary["status"] = trial["classification"] if finalization else "RECORDED_NOT_EXPOSED"
        if finalization:
            summary["order_effect"] = trial["order_effect"]
        trials.append(summary)
    return {
        "status": finalization["status"] if finalization else "ACTION_REQUIRED",
        "composition_id": composition_id,
        "protocol_sha256": state["protocol_sha256"],
        "state_sha256": state["state_sha256"],
        "target": state["protocol"]["target"],
        "target_order": state["protocol"]["target_order"],
        "control_order": state["protocol"]["control_order"],
        "component_bindings": [{
            "frontier_protocol_id": item["frontier_protocol_id"],
            **item["binding"],
        } for item in state["protocol"]["components"]],
        "capability_graph_sha256": state["protocol"]["capability_graph_sha256"],
        "case_count": len(state["protocol"]["case_ids"]),
        "case_ids_sha256": state["protocol"]["case_ids_sha256"],
        "replicates_required": state["protocol"]["replicates"],
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
        "automatic_selection": False,
        "apply_route_exposed": False,
        "resource_policy": {
            "gpu": "off",
            "execution": "serial",
            "aggregate_task_owned_working_set_limit_bytes": 536870912,
        },
        "next_action": (
            "Human-review the exact ordered claim and every path/order boundary; do not generalize it."
            if finalization else
            "Record current primary sources and every frozen replicate artifact, then finalize the exact order."
        ),
    }


def verify_skill_composition(
    root: str | os.PathLike[str], composition_id: str,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, composition_id)
    failures = _artifact_failures(base, state) + _binding_failures(base, state)
    finalization = state.get("finalization")
    return {
        "status": "FAIL" if failures else ("PASS" if finalization is not None else "ACTION_REQUIRED"),
        "integrity_status": "PASS" if not failures else "FAIL",
        "composition_id": composition_id,
        "state_sha256": state["state_sha256"],
        "finalized": finalization is not None,
        "support_status": finalization.get("support_status") if finalization else None,
        "scoped_claim_allowed": bool(finalization and finalization["scoped_claim_allowed"]),
        "universal_claim_allowed": False,
        "order_invariant_claim_allowed": False,
        "artifact_failures": failures,
        "third_party_execution_observed_by_core": False,
        "attack_synthesis_performed": False,
    }
