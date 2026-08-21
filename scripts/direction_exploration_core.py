from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from research_guard_core import (
    GuardError,
    digest,
    get_collision_report,
    load_state as load_novelty_state,
    method_files_fingerprint,
    normalize_method,
    project_root,
    register_method,
    utc_now,
    verify_receipt,
)
from research_integrity_core import IntegrityError, integrity_status
from resource_task_planner_core import ResourcePlanError, inventory_resources


SCHEMA_VERSION = 1
CONTRACT_PATH = Path(__file__).resolve().parents[1] / "assets" / "direction-exploration-contract.json"
STATE_DIRECTORY = "direction-explorations"
IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9_-]{0,95}")
FORBIDDEN_SELECTION_FIELDS = {
    "rank", "ranking", "score", "priority", "winner", "recommended",
    "recommendation", "prestige", "acceptance_probability",
}


class DirectionExplorationError(GuardError):
    pass


def _contract() -> tuple[dict[str, Any], str]:
    try:
        value = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DirectionExplorationError(f"Unreadable direction-exploration contract: {exc}") from exc
    expected = {
        "schema_version": SCHEMA_VERSION,
        "final_choice_count": 5,
        "managed_resource_profile": "managed_standard",
        "automatic_ranking_allowed": False,
        "automatic_winner_selection_allowed": False,
        "gpu_allowed": False,
    }
    for key, wanted in expected.items():
        if value.get(key) != wanted:
            raise DirectionExplorationError(f"Direction-exploration contract drift: {key}")
    return value, digest(value)


def _identifier(value: Any, field: str) -> str:
    text = str(value or "").strip().casefold()
    if not IDENTIFIER.fullmatch(text):
        raise DirectionExplorationError(f"{field} is invalid")
    return text


def _text(value: Any, field: str, *, maximum: int = 4000) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise DirectionExplorationError(f"{field} is required")
    if len(text) > maximum:
        raise DirectionExplorationError(f"{field} exceeds {maximum} characters")
    return text


def _https(value: Any, field: str) -> str:
    text = _text(value, field, maximum=2000)
    parsed = urlparse(text)
    if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise DirectionExplorationError(f"{field} must be a credential-free clickable HTTPS URL")
    return text


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise DirectionExplorationError(f"{field} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DirectionExplorationError(f"{field} must be a finite number") from exc
    if not math.isfinite(number):
        raise DirectionExplorationError(f"{field} must be a finite number")
    return number


def _positive_integer(value: Any, field: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise DirectionExplorationError(f"{field} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise DirectionExplorationError(f"{field} must be a positive integer") from exc
    if number < 1 or (maximum is not None and number > maximum):
        suffix = f" no greater than {maximum}" if maximum is not None else ""
        raise DirectionExplorationError(f"{field} must be a positive integer{suffix}")
    return number


def _state_path(root: Path, exploration_id: str) -> Path:
    return root / ".research-guard" / STATE_DIRECTORY / f"{exploration_id}.json"


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
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


def _append_audit(root: Path, event: str, details: dict[str, Any]) -> None:
    path = root / ".research-guard" / "direction-exploration-audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"at": utc_now(), "event": event, **details}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _state_stable(state: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state.items() if key != "state_sha256"}


def _seal_state(state: dict[str, Any]) -> None:
    state["state_sha256"] = digest(_state_stable(state))


def _load_state(root: Path, exploration_id: str, *, required: bool = True) -> dict[str, Any] | None:
    path = _state_path(root, exploration_id)
    if not path.is_file():
        if required:
            raise DirectionExplorationError("Direction exploration is not planned")
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DirectionExplorationError(f"Direction-exploration state is unreadable: {exc}") from exc
    if state.get("schema_version") != SCHEMA_VERSION:
        raise DirectionExplorationError("Unsupported direction-exploration state schema")
    if digest(_state_stable(state)) != state.get("state_sha256"):
        raise DirectionExplorationError("DIRECTION_EXPLORATION_STATE_INTEGRITY_FAILURE")
    if state.get("contract_sha256") != _contract()[1]:
        raise DirectionExplorationError("DIRECTION_EXPLORATION_CONTRACT_CHANGED_REPLAN_REQUIRED")
    return state


def _save_state(root: Path, state: dict[str, Any]) -> None:
    _seal_state(state)
    _atomic_json(_state_path(root, state["exploration_id"]), state)


def _relative_file(root: Path, value: Any, field: str) -> tuple[Path, str]:
    raw = Path(_text(value, field, maximum=1000))
    resolved = (root / raw).resolve() if not raw.is_absolute() else raw.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise DirectionExplorationError(f"{field} must stay inside project_root") from exc
    if not resolved.is_file():
        raise DirectionExplorationError(f"{field} must be an existing regular file")
    return resolved, relative.as_posix()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _string_list(value: Any, field: str, *, minimum: int = 0, maximum: int = 20) -> list[str]:
    if not isinstance(value, list):
        raise DirectionExplorationError(f"{field} must be an array")
    output = [_text(item, f"{field}[{index}]", maximum=1000) for index, item in enumerate(value)]
    if not minimum <= len(output) <= maximum:
        raise DirectionExplorationError(f"{field} must contain between {minimum} and {maximum} items")
    if len(set(output)) != len(output):
        raise DirectionExplorationError(f"{field} must not contain duplicates")
    return output


def _reject_selection_fields(value: Any, path: str = "candidate") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in FORBIDDEN_SELECTION_FIELDS:
                raise DirectionExplorationError(
                    f"{path}.{key} is forbidden; direction exploration cannot rank or choose a winner"
                )
            _reject_selection_fields(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_selection_fields(item, f"{path}[{index}]")


def _normalize_checks(value: Any, field: str, *, maximum: int = 12) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value or len(value) > maximum:
        raise DirectionExplorationError(f"{field} must contain 1-{maximum} predeclared checks")
    output: list[dict[str, str]] = []
    identifiers: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict) or set(raw) != {"check_id", "description"}:
            raise DirectionExplorationError(f"{field}[{index}] requires only check_id and description")
        identifier = _identifier(raw.get("check_id"), f"{field}[{index}].check_id")
        if identifier in identifiers:
            raise DirectionExplorationError(f"{field} contains duplicate check_id {identifier}")
        identifiers.add(identifier)
        output.append({
            "check_id": identifier,
            "description": _text(raw.get("description"), f"{field}[{index}].description", maximum=800),
        })
    return output


def _normalize_protocol(value: Any, contract: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DirectionExplorationError("coarse_test_protocol must be an object")
    common = {
        "evidence_mode", "data_role", "iteration_limit", "resource_profile",
        "estimated_peak_memory_bytes", "protocol_checks", "scope_note",
    }
    mode = str(value.get("evidence_mode") or "").strip().casefold()
    if mode not in set(contract["allowed_evidence_modes"]):
        raise DirectionExplorationError("Unsupported coarse-test evidence_mode")
    role = str(value.get("data_role") or "").strip().casefold()
    if role not in set(contract["allowed_data_roles"]):
        raise DirectionExplorationError("data_role must be pilot, validation, or synthetic; final-test use is forbidden")
    limit = _positive_integer(
        value.get("iteration_limit"), "coarse_test_protocol.iteration_limit",
        maximum=int(contract["maximum_iterations_per_revision"]),
    )
    if value.get("resource_profile") != contract["managed_resource_profile"]:
        raise DirectionExplorationError("coarse tests require the managed_standard resource profile")
    memory = _positive_integer(
        value.get("estimated_peak_memory_bytes"),
        "coarse_test_protocol.estimated_peak_memory_bytes",
        maximum=384 * 1024 * 1024,
    )
    normalized: dict[str, Any] = {
        "evidence_mode": mode,
        "data_role": role,
        "iteration_limit": limit,
        "resource_profile": contract["managed_resource_profile"],
        "estimated_peak_memory_bytes": memory,
        "protocol_checks": _normalize_checks(value.get("protocol_checks"), "coarse_test_protocol.protocol_checks"),
        "scope_note": _text(value.get("scope_note"), "coarse_test_protocol.scope_note", maximum=1200),
    }
    if mode == "quantitative_delta":
        allowed = common | {
            "metric_id", "metric_label", "unit", "direction", "minimum_effect",
            "legal_range", "minimum_observations", "baseline_source",
        }
        unknown = set(value) - allowed
        if unknown:
            raise DirectionExplorationError(f"Unknown quantitative coarse-test fields: {', '.join(sorted(unknown))}")
        direction = str(value.get("direction") or "").strip().casefold()
        if direction not in {"maximize", "minimize"}:
            raise DirectionExplorationError("quantitative direction must be maximize or minimize")
        legal = value.get("legal_range")
        if not isinstance(legal, list) or len(legal) != 2:
            raise DirectionExplorationError("legal_range must be [minimum, maximum]")
        lower = _finite(legal[0], "coarse_test_protocol.legal_range[0]")
        upper = _finite(legal[1], "coarse_test_protocol.legal_range[1]")
        if lower >= upper:
            raise DirectionExplorationError("legal_range minimum must be below maximum")
        minimum_effect = _finite(value.get("minimum_effect"), "coarse_test_protocol.minimum_effect")
        if minimum_effect <= 0:
            raise DirectionExplorationError("minimum_effect must be greater than zero")
        normalized.update({
            "metric_id": _identifier(value.get("metric_id"), "coarse_test_protocol.metric_id"),
            "metric_label": _text(value.get("metric_label"), "coarse_test_protocol.metric_label", maximum=300),
            "unit": _text(value.get("unit"), "coarse_test_protocol.unit", maximum=120),
            "direction": direction,
            "minimum_effect": minimum_effect,
            "legal_range": [lower, upper],
            "minimum_observations": _positive_integer(
                value.get("minimum_observations"), "coarse_test_protocol.minimum_observations",
            ),
            "baseline_source": _text(value.get("baseline_source"), "coarse_test_protocol.baseline_source", maximum=800),
        })
    else:
        allowed = common | {"positive_checks"}
        unknown = set(value) - allowed
        if unknown:
            raise DirectionExplorationError(f"Unknown checklist coarse-test fields: {', '.join(sorted(unknown))}")
        normalized["positive_checks"] = _normalize_checks(
            value.get("positive_checks"), "coarse_test_protocol.positive_checks",
        )
    normalized["protocol_hash"] = digest(normalized)
    return normalized


def _normalize_prior_work(value: Any, maximum: int) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value or len(value) > maximum:
        raise DirectionExplorationError(f"prior_work must contain 1-{maximum} linked records")
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict) or set(raw) - {"title", "url", "relationship"}:
            raise DirectionExplorationError(f"prior_work[{index}] has unknown fields")
        url = _https(raw.get("url"), f"prior_work[{index}].url")
        if url in seen:
            continue
        seen.add(url)
        output.append({
            "title": _text(raw.get("title"), f"prior_work[{index}].title", maximum=500),
            "url": url,
            "relationship": _text(
                raw.get("relationship") or "prior-work anchor",
                f"prior_work[{index}].relationship", maximum=500,
            ),
        })
    if not output:
        raise DirectionExplorationError("prior_work must retain at least one linked record")
    return output


def _normalize_candidate(root: Path, value: Any, contract: dict[str, Any], revision: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DirectionExplorationError("Each direction candidate must be an object")
    _reject_selection_fields(value)
    allowed = {
        "candidate_id", "title", "problem", "mechanism", "falsifier",
        "minimum_viable_experiment", "differentiator", "feasibility", "method",
        "prior_work", "coarse_test_protocol",
    }
    unknown = set(value) - allowed
    if unknown:
        raise DirectionExplorationError(f"Unknown direction-candidate fields: {', '.join(sorted(unknown))}")
    candidate_id = _identifier(value.get("candidate_id"), "candidate_id")
    method = normalize_method(value.get("method") or {})
    title = _text(value.get("title"), "candidate.title", maximum=500)
    problem = _text(value.get("problem"), "candidate.problem", maximum=2000)
    mechanism = _text(value.get("mechanism"), "candidate.mechanism", maximum=3000)
    if title != method["title"] or problem != method["problem"] or mechanism != method["mechanism"]:
        raise DirectionExplorationError("Candidate title/problem/mechanism must exactly match the canonical method")
    files_hash = method_files_fingerprint(root, method.get("method_files", []))
    method_hash = digest({"method": method, "method_files_hash": files_hash})
    protocol = _normalize_protocol(value.get("coarse_test_protocol"), contract)
    record: dict[str, Any] = {
        "candidate_id": candidate_id,
        "revision": revision,
        "title": title,
        "problem": problem,
        "mechanism": mechanism,
        "falsifier": _text(value.get("falsifier"), "candidate.falsifier", maximum=1600),
        "minimum_viable_experiment": _text(
            value.get("minimum_viable_experiment"), "candidate.minimum_viable_experiment", maximum=2000,
        ),
        "differentiator": _text(value.get("differentiator"), "candidate.differentiator", maximum=1600),
        "feasibility": _text(value.get("feasibility"), "candidate.feasibility", maximum=1600),
        "method": method,
        "method_files_hash": files_hash,
        "method_hash": method_hash,
        "prior_work": _normalize_prior_work(value.get("prior_work"), int(contract["maximum_prior_work_links"])),
        "coarse_test_protocol": protocol,
        "activation_history": [],
        "iteration_history": [],
        "collision_history": [],
        "created_at": utc_now(),
    }
    stable = {key: value for key, value in record.items() if key not in {
        "activation_history", "iteration_history", "collision_history", "created_at", "revision_hash",
    }}
    record["revision_hash"] = digest(stable)
    return record


def _current_revision(state: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    candidate = state.get("candidates", {}).get(candidate_id)
    if not candidate or not candidate.get("revisions"):
        raise DirectionExplorationError("Direction candidate is not registered")
    return candidate["revisions"][-1]


def _active_method_hash(root: Path) -> str | None:
    try:
        state = load_novelty_state(root, required=False)
    except GuardError as exc:
        raise DirectionExplorationError(f"Cannot inspect active novelty method: {exc}") from exc
    return str(state.get("active_method", {}).get("hash")) if state else None


def plan_direction_exploration(
    root: str | os.PathLike[str], *, exploration_id: str, authorization_scope: str,
    problem: str, constraints: list[str] | None, authorized_by: str,
) -> dict[str, Any]:
    if authorized_by != "user":
        raise DirectionExplorationError("DIRECTION_EXPLORATION_USER_AUTHORIZATION_REQUIRED")
    base = project_root(root)
    identifier = _identifier(exploration_id, "exploration_id")
    if _load_state(base, identifier, required=False) is not None:
        raise DirectionExplorationError("Direction-exploration plans are append-only; use a versioned exploration_id")
    contract, contract_hash = _contract()
    try:
        snapshot = inventory_resources(base)
    except ResourcePlanError as exc:
        raise DirectionExplorationError(f"Resource inventory failed: {exc}") from exc
    if snapshot.get("accelerators", {}).get("policy_allowed") is not False:
        raise DirectionExplorationError("Direction exploration must keep GPU execution disabled")
    state: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "exploration_id": identifier,
        "authorization": {
            "authorized_by": authorized_by,
            "scope": _text(authorization_scope, "authorization_scope", maximum=3000),
            "authorized_at": utc_now(),
        },
        "problem": _text(problem, "direction_problem", maximum=4000),
        "constraints": _string_list(constraints or [], "direction_constraints", maximum=30),
        "contract_sha256": contract_hash,
        "resource_snapshot": snapshot,
        "resource_snapshot_sha256": snapshot["snapshot_sha256"],
        "candidate_order": [],
        "candidates": {},
        "choice_sets": [],
        "active_choice_set_sha256": None,
        "status": "CANDIDATES_REQUIRED",
        "created_at": utc_now(),
    }
    state["plan_hash"] = digest({
        "exploration_id": identifier,
        "authorization_scope": state["authorization"]["scope"],
        "problem": state["problem"],
        "constraints": state["constraints"],
        "contract_sha256": contract_hash,
        "resource_snapshot_sha256": snapshot["snapshot_sha256"],
    })
    _save_state(base, state)
    _append_audit(base, "direction_exploration_planned", {
        "exploration_id": identifier,
        "plan_hash": state["plan_hash"],
        "resource_snapshot_sha256": snapshot["snapshot_sha256"],
    })
    return {
        "status": state["status"],
        "exploration_id": identifier,
        "plan_hash": state["plan_hash"],
        "resource_snapshot": snapshot,
        "contract": contract,
        "next_action": "Register a main-agent-curated pool of 5-15 unranked candidates.",
    }


def register_direction_candidates(
    root: str | os.PathLike[str], *, exploration_id: str, candidates: list[dict[str, Any]],
    selected_by: str, selection_rationale: str,
) -> dict[str, Any]:
    if selected_by != "main_agent":
        raise DirectionExplorationError("direction candidates require selected_by=main_agent")
    base = project_root(root)
    identifier = _identifier(exploration_id, "exploration_id")
    state = _load_state(base, identifier)
    if state["candidate_order"]:
        raise DirectionExplorationError("Direction-candidate pools are append-only; revise candidates individually")
    contract, _ = _contract()
    if not isinstance(candidates, list):
        raise DirectionExplorationError("direction_candidates must be an array")
    if not int(contract["candidate_pool_minimum"]) <= len(candidates) <= int(contract["candidate_pool_maximum"]):
        raise DirectionExplorationError(
            f"direction_candidates must contain {contract['candidate_pool_minimum']}-{contract['candidate_pool_maximum']} items"
        )
    normalized = [_normalize_candidate(base, value, contract, 1) for value in candidates]
    ids = [item["candidate_id"] for item in normalized]
    if len(ids) != len(set(ids)):
        raise DirectionExplorationError("direction candidate IDs must be unique")
    state["candidate_order"] = ids
    state["candidates"] = {item["candidate_id"]: {"revisions": [item]} for item in normalized}
    state["pool_selection"] = {
        "selected_by": selected_by,
        "selection_rationale": _text(selection_rationale, "direction_selection_rationale", maximum=2500),
        "registered_at": utc_now(),
    }
    state["status"] = "EVIDENCE_REQUIRED"
    _save_state(base, state)
    _append_audit(base, "direction_candidates_registered", {
        "exploration_id": identifier,
        "candidate_ids": ids,
        "automatic_ranking": False,
    })
    return _summary_for_root(base, state)


def activate_direction_candidate(
    root: str | os.PathLike[str], *, exploration_id: str, candidate_id: str,
) -> dict[str, Any]:
    base = project_root(root)
    exploration_id = _identifier(exploration_id, "exploration_id")
    candidate_id = _identifier(candidate_id, "direction_candidate_id")
    state = _load_state(base, exploration_id)
    revision = _current_revision(state, candidate_id)
    current_files_hash = method_files_fingerprint(base, revision["method"].get("method_files", []))
    if current_files_hash != revision["method_files_hash"]:
        raise DirectionExplorationError(
            "CANDIDATE_METHOD_FILES_CHANGED: revise the candidate; old coarse-test and collision evidence cannot be reused"
        )
    result = register_method(base, revision["method"])
    novelty = result["state"]
    active = novelty["active_method"]
    if active["hash"] != revision["method_hash"]:
        raise DirectionExplorationError("Activated method hash does not match the direction revision")
    activation = {
        "method_version": active["version"],
        "method_hash": active["hash"],
        "activated_at": utc_now(),
    }
    if not revision["activation_history"] or revision["activation_history"][-1] != activation:
        revision["activation_history"].append(activation)
    _save_state(base, state)
    _append_audit(base, "direction_candidate_activated", {
        "exploration_id": exploration_id,
        "candidate_id": candidate_id,
        "revision": revision["revision"],
        "method_hash": revision["method_hash"],
    })
    return {
        "status": "DOMAIN_SELECTION_REQUIRED",
        "exploration_id": exploration_id,
        "candidate_id": candidate_id,
        "revision": revision["revision"],
        "candidate_revision_hash": revision["revision_hash"],
        "method_hash": revision["method_hash"],
        "coarse_test_protocol": revision["coarse_test_protocol"],
        "next_actions": [
            "Register the explicit domain route and complete the collision search for this exact method hash.",
            "Register and execute fresh user-selected reproducibility runs for the frozen coarse-test protocol.",
        ],
    }


def _boolean_results(value: Any, expected: list[dict[str, str]], field: str) -> dict[str, bool]:
    if not isinstance(value, dict):
        raise DirectionExplorationError(f"{field} must be an object")
    expected_ids = [item["check_id"] for item in expected]
    if set(value) != set(expected_ids) or any(not isinstance(value[item], bool) for item in expected_ids):
        raise DirectionExplorationError(f"{field} must contain exactly the frozen boolean check IDs")
    return {item: bool(value[item]) for item in expected_ids}


def _normalize_result_artifact(
    value: Any, revision: dict[str, Any], expected_iteration: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict):
        raise DirectionExplorationError("Direction coarse-test result must be a JSON object")
    common = {
        "schema_version", "candidate_id", "revision", "candidate_revision_hash",
        "method_hash", "protocol_hash", "iteration", "configuration_id", "data_role",
        "result_claim_scope", "protocol_checks", "evidence_urls", "notes",
    }
    protocol = revision["coarse_test_protocol"]
    if protocol["evidence_mode"] == "quantitative_delta":
        allowed = common | {
            "metric_id", "unit", "baseline_value", "candidate_value", "observation_count",
        }
    else:
        allowed = common | {"positive_checks"}
    unknown = set(value) - allowed
    if unknown:
        raise DirectionExplorationError(f"Unknown coarse-test result fields: {', '.join(sorted(unknown))}")
    bindings = {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": revision["candidate_id"],
        "revision": revision["revision"],
        "candidate_revision_hash": revision["revision_hash"],
        "method_hash": revision["method_hash"],
        "protocol_hash": protocol["protocol_hash"],
        "iteration": expected_iteration,
        "data_role": protocol["data_role"],
        "result_claim_scope": "local_coarse_signal_only",
    }
    for field, wanted in bindings.items():
        if value.get(field) != wanted:
            raise DirectionExplorationError(f"coarse-test result {field} does not match the frozen direction revision")
    protocol_checks = _boolean_results(
        value.get("protocol_checks"), protocol["protocol_checks"], "coarse-test result protocol_checks",
    )
    urls = value.get("evidence_urls") or []
    if not isinstance(urls, list) or len(urls) > 12:
        raise DirectionExplorationError("coarse-test evidence_urls must be an array of at most 12 URLs")
    normalized: dict[str, Any] = {
        **bindings,
        "configuration_id": _identifier(value.get("configuration_id"), "coarse-test configuration_id"),
        "protocol_checks": protocol_checks,
        "evidence_urls": [_https(item, f"coarse-test evidence_urls[{index}]") for index, item in enumerate(urls)],
        "notes": " ".join(str(value.get("notes") or "").split()) or None,
    }
    protocol_legal = all(protocol_checks.values())
    if protocol["evidence_mode"] == "quantitative_delta":
        if value.get("metric_id") != protocol["metric_id"] or value.get("unit") != protocol["unit"]:
            raise DirectionExplorationError("coarse-test metric identity or unit does not match the frozen protocol")
        baseline = _finite(value.get("baseline_value"), "coarse-test baseline_value")
        candidate = _finite(value.get("candidate_value"), "coarse-test candidate_value")
        observations = _positive_integer(value.get("observation_count"), "coarse-test observation_count")
        lower, upper = protocol["legal_range"]
        in_range = lower <= baseline <= upper and lower <= candidate <= upper
        enough = observations >= int(protocol["minimum_observations"])
        improvement = candidate - baseline if protocol["direction"] == "maximize" else baseline - candidate
        positive = protocol_legal and in_range and enough and improvement >= float(protocol["minimum_effect"])
        normalized.update({
            "metric_id": protocol["metric_id"],
            "unit": protocol["unit"],
            "baseline_value": baseline,
            "candidate_value": candidate,
            "observation_count": observations,
        })
        computed = {
            "outcome": "POSITIVE" if positive else "NON_POSITIVE",
            "protocol_legal": protocol_legal and in_range and enough,
            "improvement": improvement,
            "minimum_effect": protocol["minimum_effect"],
            "direction": protocol["direction"],
            "legal_range": protocol["legal_range"],
            "minimum_observations": protocol["minimum_observations"],
        }
    else:
        checks = _boolean_results(
            value.get("positive_checks"), protocol["positive_checks"], "coarse-test result positive_checks",
        )
        positive = protocol_legal and all(checks.values())
        normalized["positive_checks"] = checks
        computed = {
            "outcome": "POSITIVE" if positive else "NON_POSITIVE",
            "protocol_legal": protocol_legal,
            "passed_positive_checks": sum(1 for item in checks.values() if item),
            "required_positive_checks": len(checks),
        }
    return normalized, computed


def record_direction_iteration(
    root: str | os.PathLike[str], *, exploration_id: str, candidate_id: str,
    run_id: str, result_path: str,
) -> dict[str, Any]:
    base = project_root(root)
    exploration_id = _identifier(exploration_id, "exploration_id")
    candidate_id = _identifier(candidate_id, "direction_candidate_id")
    run_id = _identifier(run_id, "direction_run_id")
    state = _load_state(base, exploration_id)
    revision = _current_revision(state, candidate_id)
    if _active_method_hash(base) != revision["method_hash"]:
        raise DirectionExplorationError("Activate this exact direction revision before binding a coarse-test run")
    for other_id in state["candidate_order"]:
        for other_revision in state["candidates"][other_id]["revisions"]:
            for existing in other_revision["iteration_history"]:
                if existing["run_id"] == run_id:
                    if other_id == candidate_id and existing["candidate_revision_hash"] == revision["revision_hash"]:
                        return existing
                    raise DirectionExplorationError("A reproducibility run cannot be bound to two direction revisions")
    expected_iteration = len(revision["iteration_history"]) + 1
    if expected_iteration > int(revision["coarse_test_protocol"]["iteration_limit"]):
        raise DirectionExplorationError("COARSE_ITERATION_LIMIT_REACHED: revise or reject the candidate")
    try:
        reproduction = integrity_status(base, "reproducibility", run_id)
    except IntegrityError as exc:
        raise DirectionExplorationError(f"Cannot load reproducibility receipt: {exc}") from exc
    execution = reproduction.get("execution") or {}
    if reproduction.get("status") != "PASS" or execution.get("execution_mode") != "managed":
        raise DirectionExplorationError("Direction evidence requires a managed reproducibility PASS")
    if reproduction.get("method_hash") != revision["method_hash"]:
        raise DirectionExplorationError("Reproducibility method hash does not match the direction revision")
    resolved, relative = _relative_file(base, result_path, "direction_result_path")
    output = next((item for item in execution.get("outputs", []) if item.get("path") == relative), None)
    if not output:
        raise DirectionExplorationError("direction_result_path is not a declared reproducibility output")
    actual_hash = _sha256_file(resolved)
    if output.get("sha256") != actual_hash or output.get("bytes") != resolved.stat().st_size:
        raise DirectionExplorationError("Direction result does not match the managed reproducibility receipt")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DirectionExplorationError(f"Direction result must be UTF-8 JSON: {exc}") from exc
    normalized, computed = _normalize_result_artifact(payload, revision, expected_iteration)
    binding = {
        "candidate_id": candidate_id,
        "candidate_revision_hash": revision["revision_hash"],
        "iteration": expected_iteration,
        "run_id": run_id,
        "reproducibility_plan_hash": reproduction["plan_hash"],
        "execution_hash": execution["execution_hash"],
        "resource_usage": execution.get("resource_usage"),
        "duration_seconds": execution.get("duration_seconds"),
        "result_path": relative,
        "result_sha256": actual_hash,
        "result_bytes": resolved.stat().st_size,
        "normalized_result": normalized,
        "computed_evidence": computed,
        "bound_at": utc_now(),
    }
    binding["binding_sha256"] = digest({key: value for key, value in binding.items() if key != "binding_sha256"})
    revision["iteration_history"].append(binding)
    _save_state(base, state)
    _append_audit(base, "direction_iteration_bound", {
        "exploration_id": exploration_id,
        "candidate_id": candidate_id,
        "revision": revision["revision"],
        "iteration": expected_iteration,
        "outcome": computed["outcome"],
        "run_id": run_id,
    })
    return binding


def _literature_links(report: dict[str, Any], revision: dict[str, Any], maximum: int) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for work in report.get("works", []):
        url = str(work.get("citation_url") or "")
        if not url.startswith("https://") or url in seen:
            continue
        seen.add(url)
        output.append({
            "title": _text(work.get("title") or "Linked search record", "collision work title", maximum=500),
            "url": _https(url, "collision work citation_url"),
            "relationship": "nearest work under the recorded collision-search plan",
        })
        if len(output) >= maximum:
            break
    for item in revision["prior_work"]:
        if item["url"] in seen:
            continue
        output.append(dict(item))
        seen.add(item["url"])
        if len(output) >= maximum:
            break
    return output[:maximum]


def bind_direction_collision(
    root: str | os.PathLike[str], *, exploration_id: str, candidate_id: str,
) -> dict[str, Any]:
    base = project_root(root)
    exploration_id = _identifier(exploration_id, "exploration_id")
    candidate_id = _identifier(candidate_id, "direction_candidate_id")
    state = _load_state(base, exploration_id)
    revision = _current_revision(state, candidate_id)
    if _active_method_hash(base) != revision["method_hash"]:
        raise DirectionExplorationError("Activate this exact direction revision before binding collision evidence")
    verification = verify_receipt(base, strict=True)
    if not verification.get("valid") or verification.get("gate_status") != "PASS":
        raise DirectionExplorationError("A strict current collision-search PASS receipt is required")
    report = get_collision_report(base)
    if report.get("method_hash") != revision["method_hash"] or report.get("gate_status") != "PASS":
        raise DirectionExplorationError("Collision report does not match the direction revision")
    if report.get("missing_sources") or report.get("unresolved_collision_candidates"):
        raise DirectionExplorationError("Collision coverage or candidate resolution is incomplete")
    report_copy = dict(report)
    saved_report_hash = report_copy.pop("report_hash", None)
    if digest(report_copy) != saved_report_hash:
        raise DirectionExplorationError("Collision report hash is invalid")
    novelty_state = load_novelty_state(base)
    report_path, report_relative = _relative_file(base, novelty_state.get("latest_report"), "collision report")
    receipt_path, receipt_relative = _relative_file(base, novelty_state.get("current_receipt"), "collision receipt")
    links = _literature_links(
        report,
        revision,
        int(_contract()[0]["maximum_report_links_per_direction"]),
    )
    if not links:
        raise DirectionExplorationError("Collision evidence must retain at least one clickable literature link")
    binding = {
        "candidate_id": candidate_id,
        "candidate_revision_hash": revision["revision_hash"],
        "method_hash": revision["method_hash"],
        "report_path": report_relative,
        "report_file_sha256": _sha256_file(report_path),
        "report_hash": report["report_hash"],
        "receipt_path": receipt_relative,
        "receipt_file_sha256": _sha256_file(receipt_path),
        "coverage_hash": report.get("coverage_hash"),
        "evidence_manifest_hash": report.get("evidence_manifest_hash"),
        "gate_reason": report.get("gate_reason"),
        "literature_links": links,
        "claim_scope": "no unresolved collision under the recorded sources, queries, coverage, and date",
        "bound_at": utc_now(),
    }
    binding["binding_sha256"] = digest({key: value for key, value in binding.items() if key != "binding_sha256"})
    if revision["collision_history"] and revision["collision_history"][-1]["binding_sha256"] == binding["binding_sha256"]:
        return revision["collision_history"][-1]
    revision["collision_history"].append(binding)
    _save_state(base, state)
    _append_audit(base, "direction_collision_bound", {
        "exploration_id": exploration_id,
        "candidate_id": candidate_id,
        "revision": revision["revision"],
        "report_hash": report["report_hash"],
    })
    return binding


def revise_direction_candidate(
    root: str | os.PathLike[str], *, exploration_id: str, candidate_id: str,
    candidate: dict[str, Any], selected_by: str, change_summary: str,
) -> dict[str, Any]:
    if selected_by != "main_agent":
        raise DirectionExplorationError("direction revision requires selected_by=main_agent")
    base = project_root(root)
    exploration_id = _identifier(exploration_id, "exploration_id")
    candidate_id = _identifier(candidate_id, "direction_candidate_id")
    state = _load_state(base, exploration_id)
    previous = _current_revision(state, candidate_id)
    supplied = dict(candidate or {})
    if _identifier(supplied.get("candidate_id"), "candidate.candidate_id") != candidate_id:
        raise DirectionExplorationError("Revised candidate ID must match the existing candidate")
    current = _normalize_candidate(base, supplied, _contract()[0], int(previous["revision"]) + 1)
    if current["method_hash"] == previous["method_hash"]:
        raise DirectionExplorationError(
            "METHOD_UNCHANGED: use a new method revision only for a real canonical method or tracked-file change"
        )
    current["supersedes_revision_hash"] = previous["revision_hash"]
    current["change_summary"] = _text(change_summary, "direction_change_summary", maximum=2000)
    state["candidates"][candidate_id]["revisions"].append(current)
    if state.get("active_choice_set_sha256"):
        for choice_set in state["choice_sets"]:
            if choice_set["choice_set_sha256"] == state["active_choice_set_sha256"]:
                choice_set["invalidated_at"] = utc_now()
                choice_set["invalidation_reason"] = f"candidate {candidate_id} received method revision {current['revision']}"
        state["active_choice_set_sha256"] = None
    state["status"] = "EVIDENCE_REQUIRED"
    _save_state(base, state)
    _append_audit(base, "direction_candidate_revised", {
        "exploration_id": exploration_id,
        "candidate_id": candidate_id,
        "prior_revision_hash": previous["revision_hash"],
        "revision_hash": current["revision_hash"],
        "method_hash": current["method_hash"],
    })
    return {
        "status": "NOVELTY_AND_COARSE_TEST_REQUIRED",
        "candidate_id": candidate_id,
        "revision": current["revision"],
        "candidate_revision_hash": current["revision_hash"],
        "method_hash": current["method_hash"],
        "invalidated": _contract()[0]["method_revision_invalidates"],
        "history_preserved": True,
    }


def _verify_iteration(root: Path, revision: dict[str, Any], binding: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    stable = {key: value for key, value in binding.items() if key != "binding_sha256"}
    if digest(stable) != binding.get("binding_sha256"):
        errors.append("ITERATION_BINDING_HASH_MISMATCH")
    if binding.get("candidate_revision_hash") != revision["revision_hash"]:
        errors.append("ITERATION_REVISION_MISMATCH")
    try:
        path, relative = _relative_file(root, binding.get("result_path"), "direction result")
        if relative != binding.get("result_path") or _sha256_file(path) != binding.get("result_sha256"):
            errors.append("ITERATION_ARTIFACT_HASH_MISMATCH")
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
            normalized, computed = _normalize_result_artifact(payload, revision, int(binding["iteration"]))
            if normalized != binding.get("normalized_result") or computed != binding.get("computed_evidence"):
                errors.append("ITERATION_RESULT_RECOMPUTATION_MISMATCH")
    except (DirectionExplorationError, OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"ITERATION_ARTIFACT_INVALID:{exc}")
    return errors


def _verify_collision(root: Path, revision: dict[str, Any], binding: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    stable = {key: value for key, value in binding.items() if key != "binding_sha256"}
    if digest(stable) != binding.get("binding_sha256"):
        errors.append("COLLISION_BINDING_HASH_MISMATCH")
    if binding.get("candidate_revision_hash") != revision["revision_hash"]:
        errors.append("COLLISION_REVISION_MISMATCH")
    try:
        report_path, _ = _relative_file(root, binding.get("report_path"), "collision report")
        receipt_path, _ = _relative_file(root, binding.get("receipt_path"), "collision receipt")
        if _sha256_file(report_path) != binding.get("report_file_sha256"):
            errors.append("COLLISION_REPORT_FILE_HASH_MISMATCH")
        if _sha256_file(receipt_path) != binding.get("receipt_file_sha256"):
            errors.append("COLLISION_RECEIPT_FILE_HASH_MISMATCH")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report_copy = dict(report)
        report_hash = report_copy.pop("report_hash", None)
        if digest(report_copy) != report_hash or report_hash != binding.get("report_hash"):
            errors.append("COLLISION_REPORT_HASH_MISMATCH")
        if report.get("method_hash") != revision["method_hash"]:
            errors.append("COLLISION_METHOD_MISMATCH")
        if report.get("gate_status") != "PASS" or report.get("missing_sources") or report.get("unresolved_collision_candidates"):
            errors.append("COLLISION_GATE_NOT_PASS")
        if not binding.get("literature_links") or any(
            not str(item.get("url", "")).startswith("https://") for item in binding.get("literature_links", [])
        ):
            errors.append("COLLISION_LINK_MISSING")
    except (DirectionExplorationError, OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        errors.append(f"COLLISION_EVIDENCE_INVALID:{exc}")
    return errors


def _candidate_errors(root: Path, revision: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        current_files_hash = method_files_fingerprint(root, revision["method"].get("method_files", []))
        if current_files_hash != revision["method_files_hash"]:
            errors.append("METHOD_FILES_CHANGED_REVISION_REQUIRED")
    except GuardError as exc:
        errors.append(f"METHOD_FILE_CHECK_FAILED:{exc}")
    if not revision["iteration_history"]:
        errors.append("POSITIVE_COARSE_TEST_REQUIRED")
    else:
        for binding in revision["iteration_history"]:
            errors.extend(_verify_iteration(root, revision, binding))
        if not any(item.get("computed_evidence", {}).get("outcome") == "POSITIVE" for item in revision["iteration_history"]):
            errors.append("POSITIVE_COARSE_TEST_REQUIRED")
    if not revision["collision_history"]:
        errors.append("COLLISION_SEARCH_REQUIRED")
    else:
        errors.extend(_verify_collision(root, revision, revision["collision_history"][-1]))
    return sorted(set(errors))


def _candidate_summary(root: Path, revision: dict[str, Any]) -> dict[str, Any]:
    errors = _candidate_errors(root, revision)
    positives = [
        item for item in revision["iteration_history"]
        if item.get("computed_evidence", {}).get("outcome") == "POSITIVE"
    ]
    return {
        "candidate_id": revision["candidate_id"],
        "revision": revision["revision"],
        "candidate_revision_hash": revision["revision_hash"],
        "method_hash": revision["method_hash"],
        "title": revision["title"],
        "eligible": not errors,
        "errors": errors,
        "iteration_count": len(revision["iteration_history"]),
        "positive_iteration_count": len(positives),
        "collision_bound": bool(revision["collision_history"]),
    }


def _summary_for_root(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    summaries = [_candidate_summary(root, _current_revision(state, item)) for item in state["candidate_order"]]
    eligible = [item for item in summaries if item["eligible"]]
    status = (
        "USER_SELECTION_REQUIRED" if state.get("active_choice_set_sha256")
        else "FIVE_CHOICES_READY_TO_FINALIZE" if len(eligible) >= 5
        else state.get("status", "EVIDENCE_REQUIRED")
    )
    return {
        "status": status,
        "exploration_id": state["exploration_id"],
        "plan_hash": state["plan_hash"],
        "resource_snapshot_sha256": state["resource_snapshot_sha256"],
        "candidate_count": len(state["candidate_order"]),
        "eligible_candidate_count": len(eligible),
        "candidates": summaries,
        "active_choice_set_sha256": state.get("active_choice_set_sha256"),
        "automatic_ranking": False,
        "automatic_winner_selection": False,
    }


def finalize_direction_choices(
    root: str | os.PathLike[str], *, exploration_id: str, choice_ids: list[str],
    selected_by: str, selection_rationale: str,
) -> dict[str, Any]:
    if selected_by != "main_agent":
        raise DirectionExplorationError("five-choice curation requires selected_by=main_agent")
    base = project_root(root)
    exploration_id = _identifier(exploration_id, "exploration_id")
    state = _load_state(base, exploration_id)
    expected = int(_contract()[0]["final_choice_count"])
    if not isinstance(choice_ids, list) or len(choice_ids) != expected:
        raise DirectionExplorationError(f"Exactly {expected} direction_choice_ids are required")
    normalized_ids = [_identifier(item, "direction_choice_ids") for item in choice_ids]
    if len(set(normalized_ids)) != expected:
        raise DirectionExplorationError("direction_choice_ids must be distinct")
    if any(item not in state["candidates"] for item in normalized_ids):
        raise DirectionExplorationError("Every direction_choice_id must be a registered candidate")
    ordered_ids = [item for item in state["candidate_order"] if item in set(normalized_ids)]
    choices = []
    failures: dict[str, list[str]] = {}
    for candidate_id in ordered_ids:
        revision = _current_revision(state, candidate_id)
        errors = _candidate_errors(base, revision)
        if errors:
            failures[candidate_id] = errors
            continue
        positive = next(
            item for item in reversed(revision["iteration_history"])
            if item["computed_evidence"]["outcome"] == "POSITIVE"
        )
        collision = revision["collision_history"][-1]
        choices.append({
            "candidate_id": candidate_id,
            "revision": revision["revision"],
            "candidate_revision_hash": revision["revision_hash"],
            "title": revision["title"],
            "problem": revision["problem"],
            "mechanism": revision["mechanism"],
            "falsifier": revision["falsifier"],
            "minimum_viable_experiment": revision["minimum_viable_experiment"],
            "differentiator": revision["differentiator"],
            "feasibility": revision["feasibility"],
            "positive_coarse_signal": {
                "claim_scope": "local coarse signal only; not confirmatory evidence",
                "iteration": positive["iteration"],
                "configuration_id": positive["normalized_result"]["configuration_id"],
                "result_path": positive["result_path"],
                "result_sha256": positive["result_sha256"],
                "computed_evidence": positive["computed_evidence"],
                "all_attempts_retained": len(revision["iteration_history"]),
            },
            "collision_check": {
                "claim_scope": collision["claim_scope"],
                "report_hash": collision["report_hash"],
                "coverage_hash": collision["coverage_hash"],
                "checked_at": collision["bound_at"],
                "literature_links": collision["literature_links"],
            },
        })
    if failures:
        raise DirectionExplorationError(
            "Five-choice gate failed: " + json.dumps(failures, ensure_ascii=False, sort_keys=True)
        )
    choice_set = {
        "exploration_id": exploration_id,
        "choice_ids": ordered_ids,
        "candidate_revision_hashes": [item["candidate_revision_hash"] for item in choices],
        "selected_by": selected_by,
        "selection_rationale": _text(selection_rationale, "direction_selection_rationale", maximum=2500),
        "selection_policy": "main-agent-curated unranked set; final direction belongs to the user",
        "choices": choices,
        "status": "USER_SELECTION_REQUIRED",
        "created_at": utc_now(),
    }
    choice_set["choice_set_sha256"] = digest({
        key: value for key, value in choice_set.items() if key not in {"choice_set_sha256", "created_at"}
    })
    state["choice_sets"].append(choice_set)
    state["active_choice_set_sha256"] = choice_set["choice_set_sha256"]
    state["status"] = "USER_SELECTION_REQUIRED"
    _save_state(base, state)
    _append_audit(base, "direction_choices_finalized", {
        "exploration_id": exploration_id,
        "choice_set_sha256": choice_set["choice_set_sha256"],
        "choice_ids": ordered_ids,
    })
    return choice_set


def direction_exploration_status(
    root: str | os.PathLike[str], exploration_id: str | None = None,
) -> dict[str, Any]:
    base = project_root(root)
    if exploration_id:
        state = _load_state(base, _identifier(exploration_id, "exploration_id"))
        return _summary_for_root(base, state)
    directory = base / ".research-guard" / STATE_DIRECTORY
    if not directory.is_dir():
        return {"status": "NOT_PLANNED", "explorations": []}
    output = []
    for path in sorted(directory.glob("*.json")):
        if not IDENTIFIER.fullmatch(path.stem):
            continue
        state = _load_state(base, path.stem)
        summary = _summary_for_root(base, state)
        output.append({
            "exploration_id": summary["exploration_id"],
            "status": summary["status"],
            "candidate_count": summary["candidate_count"],
            "eligible_candidate_count": summary["eligible_candidate_count"],
        })
    return {"status": "PASS", "explorations": output}


def verify_direction_exploration(root: str | os.PathLike[str], exploration_id: str) -> dict[str, Any]:
    base = project_root(root)
    identifier = _identifier(exploration_id, "exploration_id")
    try:
        state = _load_state(base, identifier)
    except DirectionExplorationError as exc:
        return {"status": "FAIL", "exploration_id": identifier, "errors": [str(exc)]}
    errors: list[str] = []
    snapshot = dict(state.get("resource_snapshot") or {})
    saved_snapshot_hash = snapshot.pop("snapshot_sha256", None)
    if digest(snapshot) != saved_snapshot_hash or saved_snapshot_hash != state.get("resource_snapshot_sha256"):
        errors.append("RESOURCE_SNAPSHOT_HASH_MISMATCH")
    if state.get("authorization", {}).get("authorized_by") != "user":
        errors.append("USER_AUTHORIZATION_MISSING")
    candidate_reports = []
    for candidate_id in state["candidate_order"]:
        revision = _current_revision(state, candidate_id)
        candidate_errors = _candidate_errors(base, revision)
        for error in candidate_errors:
            if any(marker in error for marker in ("HASH_MISMATCH", "ARTIFACT_INVALID", "EVIDENCE_INVALID", "RECOMPUTATION_MISMATCH")):
                errors.append(f"{candidate_id}:{error}")
        candidate_reports.append({
            "candidate_id": candidate_id,
            "revision": revision["revision"],
            "errors": candidate_errors,
        })
    active_hash = state.get("active_choice_set_sha256")
    if active_hash:
        active = next((item for item in state["choice_sets"] if item.get("choice_set_sha256") == active_hash), None)
        if not active:
            errors.append("ACTIVE_CHOICE_SET_MISSING")
        else:
            stable = {key: value for key, value in active.items() if key not in {
                "choice_set_sha256", "created_at", "invalidated_at", "invalidation_reason",
            }}
            if digest(stable) != active_hash:
                errors.append("CHOICE_SET_HASH_MISMATCH")
            if len(active.get("choice_ids", [])) != 5 or len(set(active.get("choice_ids", []))) != 5:
                errors.append("CHOICE_SET_NOT_EXACTLY_FIVE")
            for candidate_id in active.get("choice_ids", []):
                revision = _current_revision(state, candidate_id)
                if _candidate_errors(base, revision):
                    errors.append(f"ACTIVE_CHOICE_INELIGIBLE:{candidate_id}")
    summary = _summary_for_root(base, state)
    return {
        "status": "PASS" if not errors else "FAIL",
        "exploration_id": identifier,
        "workflow_status": summary["status"],
        "errors": sorted(set(errors)),
        "candidate_reports": candidate_reports,
        "eligible_candidate_count": summary["eligible_candidate_count"],
        "active_choice_set_sha256": active_hash,
        "automatic_ranking": False,
        "automatic_winner_selection": False,
    }
