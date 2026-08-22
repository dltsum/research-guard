from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from research_guard_core import GuardError, digest, project_root, utc_now


SCHEMA_VERSION = 1
STATE_NAME = "instruction-adherence.json"
POLICY_PATH = Path(__file__).resolve().parents[1] / "assets" / "instruction-adherence-policy.json"
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
OUTCOMES = {"satisfied", "blocked", "user_decision_required"}


class InstructionAdherenceError(GuardError):
    pass


def _state_path(root: str | os.PathLike[str]) -> Path:
    return project_root(root) / ".research-guard" / STATE_NAME


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _text(value: Any, field: str, *, minimum: int = 1) -> str:
    result = " ".join(str(value or "").split())
    if len(result) < minimum:
        raise InstructionAdherenceError(f"{field} must contain at least {minimum} characters")
    return result


def _load_policy() -> tuple[dict[str, Any], str]:
    try:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstructionAdherenceError(f"Unreadable instruction-adherence policy: {exc}") from exc
    required = {
        "schema_version": SCHEMA_VERSION,
        "activation": "main_agent_semantic_multistep_selection",
        "single_response_exempt": True,
        "required_selected_by": "main_agent",
        "completion_requires_all_mandatory_terminal_success": True,
        "blocked_handoff_is_not_completion": True,
    }
    for key, expected in required.items():
        if policy.get(key) != expected:
            raise InstructionAdherenceError(f"Instruction-adherence policy drift: {key}")
    if not isinstance(policy.get("maximum_contracts"), int) or policy["maximum_contracts"] <= 0:
        raise InstructionAdherenceError("Instruction-adherence maximum_contracts is invalid")
    if not isinstance(policy.get("maximum_requirements_per_contract"), int) or policy["maximum_requirements_per_contract"] <= 0:
        raise InstructionAdherenceError("Instruction-adherence requirement limit is invalid")
    return policy, digest(policy)


def _contract_stable(contract: dict[str, Any]) -> dict[str, Any]:
    return {key: contract.get(key) for key in (
        "contract_id", "version", "request_sha256", "scope", "selected_by",
        "selection_rationale", "requirements", "policy_sha256",
    )}


def _event_stable(event: dict[str, Any]) -> dict[str, Any]:
    return {key: event.get(key) for key in (
        "sequence", "requirement_id", "outcome", "note", "evidence",
        "blocker_code", "selected_by", "user_message_sha256",
        "previous_event_sha256", "created_at",
    )}


def _receipt_stable(receipt: dict[str, Any]) -> dict[str, Any]:
    return {key: receipt.get(key) for key in (
        "contract_id", "contract_sha256", "policy_sha256", "event_head_sha256",
        "requirement_states_sha256", "status", "verified_at",
    )}


def _load_state(root: Path, *, required: bool = True) -> dict[str, Any] | None:
    path = _state_path(root)
    if not path.is_file():
        if required:
            raise InstructionAdherenceError("No instruction contract; call instruction_action=register first")
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstructionAdherenceError(f"Unreadable instruction-adherence state: {exc}") from exc
    if state.get("schema_version") != SCHEMA_VERSION or not isinstance(state.get("contracts"), dict):
        raise InstructionAdherenceError("Unsupported instruction-adherence state schema")
    policy, policy_hash = _load_policy()
    if state.get("policy_sha256") != policy_hash:
        raise InstructionAdherenceError("INSTRUCTION_POLICY_CHANGED_REVIEW_REQUIRED")
    if len(state["contracts"]) > policy["maximum_contracts"]:
        raise InstructionAdherenceError("Instruction-adherence contract limit exceeded")
    for identifier, record in state["contracts"].items():
        contract = record.get("contract")
        if not isinstance(contract, dict) or contract.get("contract_id") != identifier:
            raise InstructionAdherenceError("Instruction-adherence contract record is invalid")
        if digest(_contract_stable(contract)) != record.get("contract_sha256"):
            raise InstructionAdherenceError("INSTRUCTION_CONTRACT_INTEGRITY_FAILURE")
        previous = None
        events = record.get("events")
        if not isinstance(events, list):
            raise InstructionAdherenceError("Instruction-adherence events must be an array")
        for sequence, event in enumerate(events, start=1):
            if event.get("sequence") != sequence or event.get("previous_event_sha256") != previous:
                raise InstructionAdherenceError("INSTRUCTION_EVENT_CHAIN_FAILURE")
            if digest(_event_stable(event)) != event.get("event_sha256"):
                raise InstructionAdherenceError("INSTRUCTION_EVENT_INTEGRITY_FAILURE")
            previous = event["event_sha256"]
        receipts = record.get("receipts")
        if not isinstance(receipts, list):
            raise InstructionAdherenceError("Instruction-adherence receipts must be an array")
        for receipt in receipts:
            if digest(_receipt_stable(receipt)) != receipt.get("receipt_sha256"):
                raise InstructionAdherenceError("INSTRUCTION_RECEIPT_INTEGRITY_FAILURE")
    return state


def _save_state(root: Path, state: dict[str, Any]) -> None:
    _atomic_json(_state_path(root), state)


def _new_state(policy_hash: str) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "policy_sha256": policy_hash, "contracts": {}}


def _string_list(value: Any, field: str, *, required: bool = False, limit: int = 16) -> list[str]:
    if value is None and not required:
        return []
    if not isinstance(value, list) or (required and not value) or len(value) > limit:
        qualifier = "a non-empty" if required else "an"
        raise InstructionAdherenceError(f"{field} must be {qualifier} array with at most {limit} items")
    normalized = [_text(item, field) for item in value]
    if len(normalized) != len(set(normalized)):
        raise InstructionAdherenceError(f"{field} contains duplicates")
    return normalized


def _normalize_requirements(value: Any, policy: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value or len(value) > policy["maximum_requirements_per_contract"]:
        raise InstructionAdherenceError("instruction_requirements must be a non-empty bounded array")
    allowed_fields = {
        "id", "text", "kind", "mandatory", "acceptance_criteria",
        "required_evidence_kinds", "forbidden_substitutions", "depends_on",
    }
    allowed_kinds = set(policy["allowed_requirement_kinds"])
    allowed_evidence = set(policy["allowed_evidence_kinds"])
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict) or not set(raw) <= allowed_fields:
            raise InstructionAdherenceError(f"instruction_requirements[{index}] has unknown or invalid fields")
        identifier = str(raw.get("id") or "").strip()
        if not IDENTIFIER.fullmatch(identifier) or identifier in seen:
            raise InstructionAdherenceError(f"instruction_requirements[{index}] has an illegal or duplicate id")
        seen.add(identifier)
        kind = str(raw.get("kind") or "").strip().lower()
        if kind not in allowed_kinds:
            raise InstructionAdherenceError(f"Unsupported instruction requirement kind: {kind}")
        mandatory = raw.get("mandatory")
        if not isinstance(mandatory, bool):
            raise InstructionAdherenceError(f"instruction requirement {identifier} needs mandatory=true/false")
        evidence_kinds = _string_list(
            raw.get("required_evidence_kinds"),
            f"instruction requirement {identifier} required_evidence_kinds",
            required=mandatory,
            limit=4,
        )
        unknown_evidence = sorted(set(evidence_kinds) - allowed_evidence)
        if unknown_evidence:
            raise InstructionAdherenceError(f"Unsupported evidence kinds: {', '.join(unknown_evidence)}")
        normalized.append({
            "id": identifier,
            "text": _text(raw.get("text"), f"instruction requirement {identifier} text", minimum=3),
            "kind": kind,
            "mandatory": mandatory,
            "acceptance_criteria": _string_list(
                raw.get("acceptance_criteria"),
                f"instruction requirement {identifier} acceptance_criteria",
                required=True,
                limit=12,
            ),
            "required_evidence_kinds": evidence_kinds,
            "forbidden_substitutions": _string_list(
                raw.get("forbidden_substitutions"),
                f"instruction requirement {identifier} forbidden_substitutions",
                limit=12,
            ),
            "depends_on": _string_list(
                raw.get("depends_on"), f"instruction requirement {identifier} depends_on", limit=16,
            ),
        })
    identifiers = {item["id"] for item in normalized}
    for item in normalized:
        unknown = sorted(set(item["depends_on"]) - identifiers)
        if unknown or item["id"] in item["depends_on"]:
            raise InstructionAdherenceError(f"instruction requirement {item['id']} has invalid dependencies")
    graph = {item["id"]: item["depends_on"] for item in normalized}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identifier: str) -> None:
        if identifier in visiting:
            raise InstructionAdherenceError("instruction requirement dependency cycle detected")
        if identifier in visited:
            return
        visiting.add(identifier)
        for dependency in graph[identifier]:
            visit(dependency)
        visiting.remove(identifier)
        visited.add(identifier)

    for identifier in graph:
        visit(identifier)
    return normalized


def register_instruction_contract(
    root: str | os.PathLike[str], *, contract_id: str, request_text: str,
    scope: str, requirements: list[dict[str, Any]], selected_by: str,
    selection_rationale: str,
) -> dict[str, Any]:
    base = project_root(root)
    if not base.is_dir():
        raise InstructionAdherenceError("project_root must be an existing directory")
    identifier = str(contract_id or "").strip()
    if not IDENTIFIER.fullmatch(identifier):
        raise InstructionAdherenceError("instruction_contract_id is invalid")
    policy, policy_hash = _load_policy()
    if selected_by != policy["required_selected_by"]:
        raise InstructionAdherenceError("instruction_selected_by=main_agent is required")
    state = _load_state(base, required=False) or _new_state(policy_hash)
    if identifier in state["contracts"]:
        raise InstructionAdherenceError("instruction_contract_id already exists; additions require a new contract")
    if len(state["contracts"]) >= policy["maximum_contracts"]:
        raise InstructionAdherenceError("instruction-adherence contract limit reached")
    normalized = _normalize_requirements(requirements, policy)
    if not any(item["mandatory"] for item in normalized):
        raise InstructionAdherenceError("a multistep instruction contract needs at least one mandatory requirement")
    normalized_request = _text(request_text, "instruction_request_text", minimum=3)
    contract = {
        "contract_id": identifier,
        "version": 1,
        "request_sha256": hashlib.sha256(normalized_request.encode("utf-8")).hexdigest(),
        "scope": _text(scope, "instruction_scope", minimum=8),
        "selected_by": selected_by,
        "selection_rationale": _text(selection_rationale, "instruction_selection_rationale", minimum=20),
        "requirements": normalized,
        "policy_sha256": policy_hash,
    }
    record = {
        "contract": contract,
        "contract_sha256": digest(_contract_stable(contract)),
        "events": [],
        "receipts": [],
        "created_at": utc_now(),
    }
    state["contracts"][identifier] = record
    _save_state(base, state)
    return instruction_adherence_status(base, identifier)


def _safe_project_file(base: Path, value: Any) -> tuple[str, Path]:
    raw = Path(_text(value, "instruction evidence path"))
    candidate = raw.resolve() if raw.is_absolute() else (base / raw).resolve()
    try:
        relative = candidate.relative_to(base).as_posix()
    except ValueError as exc:
        raise InstructionAdherenceError("instruction evidence path must stay inside project_root") from exc
    if candidate.is_symlink() or not candidate.is_file():
        raise InstructionAdherenceError("instruction evidence path must be an existing non-symlink file")
    return relative, candidate


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _json_value(document: Any, path: str) -> Any:
    current = document
    for component in path.split("."):
        if not component or not isinstance(current, dict) or component not in current:
            raise InstructionAdherenceError(f"json_receipt status_path is missing: {path}")
        current = current[component]
    return current


def _normalize_evidence(base: Path, value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > 16:
        raise InstructionAdherenceError("instruction_evidence must be an array with at most 16 items")
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise InstructionAdherenceError(f"instruction_evidence[{index}] must be an object")
        kind = str(raw.get("kind") or "").strip().lower()
        if kind == "file":
            relative, path = _safe_project_file(base, raw.get("path"))
            normalized.append({"kind": kind, "path": relative, "sha256": _file_sha256(path)})
        elif kind == "json_receipt":
            relative, path = _safe_project_file(base, raw.get("path"))
            status_path = _text(raw.get("status_path"), "json_receipt.status_path")
            expected = raw.get("expected")
            if not isinstance(expected, (str, int, float, bool)) or expected == "":
                raise InstructionAdherenceError("json_receipt.expected must be a non-empty scalar")
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise InstructionAdherenceError(f"json_receipt is invalid: {exc}") from exc
            actual = _json_value(document, status_path)
            if actual != expected:
                raise InstructionAdherenceError(
                    f"json_receipt expected {status_path}={expected!r}, observed {actual!r}"
                )
            normalized.append({
                "kind": kind, "path": relative, "sha256": _file_sha256(path),
                "status_path": status_path, "expected": expected,
            })
        elif kind == "https_url":
            url = _text(raw.get("url"), "https_url.url")
            if not url.startswith("https://") or any(character.isspace() for character in url):
                raise InstructionAdherenceError("instruction URL evidence must be a clickable HTTPS URL")
            normalized.append({
                "kind": kind, "url": url,
                "claim": _text(raw.get("claim"), "https_url.claim", minimum=8),
            })
        elif kind == "manual_review":
            checklist = _string_list(raw.get("checklist"), "manual_review.checklist", required=True, limit=24)
            if raw.get("status") != "PASS":
                raise InstructionAdherenceError("manual_review.status must be PASS")
            normalized.append({
                "kind": kind,
                "reviewer": _text(raw.get("reviewer"), "manual_review.reviewer"),
                "status": "PASS", "checklist": checklist,
            })
        else:
            raise InstructionAdherenceError(f"Unsupported instruction evidence kind: {kind}")
    return normalized


def _requirement_map(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in record["contract"]["requirements"]}


def _latest_events(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for event in record["events"]:
        latest[event["requirement_id"]] = event
    return latest


def _verify_evidence(base: Path, evidence: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for item in evidence:
        kind = item.get("kind")
        if kind in {"file", "json_receipt"}:
            try:
                relative, path = _safe_project_file(base, item.get("path"))
            except InstructionAdherenceError as exc:
                failures.append(str(exc))
                continue
            if relative != item.get("path") or _file_sha256(path) != item.get("sha256"):
                failures.append(f"evidence changed: {item.get('path')}")
                continue
            if kind == "json_receipt":
                try:
                    document = json.loads(path.read_text(encoding="utf-8"))
                    actual = _json_value(document, str(item.get("status_path") or ""))
                except (OSError, UnicodeError, json.JSONDecodeError, InstructionAdherenceError) as exc:
                    failures.append(f"invalid JSON receipt {item.get('path')}: {exc}")
                    continue
                if actual != item.get("expected"):
                    failures.append(f"JSON receipt status changed: {item.get('path')}")
    return failures


def record_instruction_requirement(
    root: str | os.PathLike[str], *, contract_id: str, requirement_id: str,
    outcome: str, evidence: list[dict[str, Any]] | None, note: str,
    blocker_code: str | None, selected_by: str,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base)
    record = state["contracts"].get(str(contract_id))
    if not record:
        raise InstructionAdherenceError("Unknown instruction_contract_id")
    requirements = _requirement_map(record)
    identifier = str(requirement_id or "").strip()
    if identifier not in requirements:
        raise InstructionAdherenceError("Unknown instruction_requirement_id")
    if selected_by != "main_agent":
        raise InstructionAdherenceError("instruction_selected_by=main_agent is required")
    normalized_outcome = str(outcome or "").strip().lower()
    if normalized_outcome not in OUTCOMES:
        raise InstructionAdherenceError(f"Unsupported instruction outcome: {normalized_outcome}")
    latest = _latest_events(record)
    prior = latest.get(identifier) or {}
    prior_outcome = prior.get("outcome")
    prior_evidence_failures = (
        _verify_evidence(base, prior.get("evidence") or [])
        if prior_outcome == "satisfied" else []
    )
    if prior_outcome == "waived" or (prior_outcome == "satisfied" and not prior_evidence_failures):
        raise InstructionAdherenceError("A currently satisfied or user-waived requirement is terminal")
    normalized_evidence = _normalize_evidence(base, evidence or [])
    requirement = requirements[identifier]
    if normalized_outcome == "satisfied":
        dependency_states: dict[str, str] = {}
        for key in requirement["depends_on"]:
            dependency_event = latest.get(key) or {}
            dependency_outcome = str(dependency_event.get("outcome") or "pending")
            if dependency_outcome == "satisfied" and _verify_evidence(
                base, dependency_event.get("evidence") or [],
            ):
                dependency_outcome = "evidence_invalid"
            dependency_states[key] = dependency_outcome
        incomplete = sorted(key for key, value in dependency_states.items() if value not in {"satisfied", "waived"})
        if incomplete:
            raise InstructionAdherenceError(f"Requirement dependencies are incomplete: {', '.join(incomplete)}")
        observed_kinds = {item["kind"] for item in normalized_evidence}
        missing = sorted(set(requirement["required_evidence_kinds"]) - observed_kinds)
        if missing:
            raise InstructionAdherenceError(f"Required evidence kinds are missing: {', '.join(missing)}")
        blocker = None
        normalized_note = _text(note, "instruction_note", minimum=8)
    else:
        normalized_note = _text(note, "instruction_note", minimum=20)
        blocker = str(blocker_code or "").strip().upper() or None
        if normalized_outcome == "blocked" and (blocker is None or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", blocker)):
            raise InstructionAdherenceError("blocked outcome requires a stable instruction_blocker_code")
        if normalized_outcome == "user_decision_required" and blocker_code:
            raise InstructionAdherenceError("user_decision_required does not accept a blocker code")
    previous = record["events"][-1]["event_sha256"] if record["events"] else None
    event = {
        "sequence": len(record["events"]) + 1,
        "requirement_id": identifier,
        "outcome": normalized_outcome,
        "note": normalized_note,
        "evidence": normalized_evidence,
        "blocker_code": blocker,
        "selected_by": selected_by,
        "user_message_sha256": None,
        "previous_event_sha256": previous,
        "created_at": utc_now(),
    }
    event["event_sha256"] = digest(_event_stable(event))
    record["events"].append(event)
    record["receipts"] = []
    _save_state(base, state)
    return instruction_adherence_status(base, str(contract_id))


def waive_instruction_requirement(
    root: str | os.PathLike[str], *, contract_id: str, requirement_id: str,
    rationale: str, user_message_sha256: str, selected_by: str,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base)
    record = state["contracts"].get(str(contract_id))
    if not record or str(requirement_id) not in _requirement_map(record):
        raise InstructionAdherenceError("Unknown instruction contract or requirement")
    if selected_by != "user":
        raise InstructionAdherenceError("instruction waiver requires instruction_selected_by=user")
    message_hash = str(user_message_sha256 or "").strip().lower()
    if not HEX_64.fullmatch(message_hash):
        raise InstructionAdherenceError("instruction_user_message_sha256 must be a lowercase SHA-256")
    latest = _latest_events(record)
    prior = latest.get(str(requirement_id)) or {}
    prior_outcome = prior.get("outcome")
    prior_evidence_failures = (
        _verify_evidence(base, prior.get("evidence") or [])
        if prior_outcome == "satisfied" else []
    )
    if prior_outcome == "waived" or (prior_outcome == "satisfied" and not prior_evidence_failures):
        raise InstructionAdherenceError("A currently satisfied or user-waived requirement is terminal")
    previous = record["events"][-1]["event_sha256"] if record["events"] else None
    event = {
        "sequence": len(record["events"]) + 1,
        "requirement_id": str(requirement_id),
        "outcome": "waived",
        "note": _text(rationale, "instruction_waiver_rationale", minimum=20),
        "evidence": [],
        "blocker_code": None,
        "selected_by": selected_by,
        "user_message_sha256": message_hash,
        "previous_event_sha256": previous,
        "created_at": utc_now(),
    }
    event["event_sha256"] = digest(_event_stable(event))
    record["events"].append(event)
    record["receipts"] = []
    _save_state(base, state)
    return instruction_adherence_status(base, str(contract_id))


def _contract_status(base: Path, record: dict[str, Any]) -> dict[str, Any]:
    latest = _latest_events(record)
    requirements: list[dict[str, Any]] = []
    for requirement in record["contract"]["requirements"]:
        event = latest.get(requirement["id"])
        outcome = str((event or {}).get("outcome") or "pending")
        evidence_failures = _verify_evidence(base, (event or {}).get("evidence") or []) if outcome == "satisfied" else []
        effective = "evidence_invalid" if evidence_failures else outcome
        requirements.append({
            **requirement,
            "state": effective,
            "event_sha256": (event or {}).get("event_sha256"),
            "blocker_code": (event or {}).get("blocker_code"),
            "note": (event or {}).get("note"),
            "evidence": (event or {}).get("evidence") or [],
            "evidence_failures": evidence_failures,
        })
    mandatory = [item for item in requirements if item["mandatory"]]
    states = {item["state"] for item in mandatory}
    if states <= {"satisfied", "waived"}:
        status, stop_allowed = "PASS", True
    elif "user_decision_required" in states:
        status, stop_allowed = "USER_DECISION_REQUIRED", False
    elif "evidence_invalid" in states:
        status, stop_allowed = "ACTION_REQUIRED", False
    elif "pending" in states:
        status, stop_allowed = "ACTION_REQUIRED", False
    elif "blocked" in states:
        status, stop_allowed = "BLOCKED", True
    else:
        status, stop_allowed = "ACTION_REQUIRED", False
    return {
        "contract_id": record["contract"]["contract_id"],
        "contract_sha256": record["contract_sha256"],
        "status": status,
        "stop_allowed": stop_allowed,
        "completion_claim_allowed": status == "PASS",
        "blocked_handoff_only": status == "BLOCKED",
        "requirements": requirements,
        "event_head_sha256": record["events"][-1]["event_sha256"] if record["events"] else None,
    }


def instruction_adherence_status(
    root: str | os.PathLike[str], contract_id: str | None = None,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, required=False)
    if state is None:
        return {
            "status": "NOT_PLANNED", "stop_allowed": True,
            "completion_claim_allowed": False,
            "reason": "No multistep instruction contract is active; single-response work is exempt.",
            "contracts": [],
        }
    identifiers = [str(contract_id)] if contract_id else sorted(state["contracts"])
    missing = [identifier for identifier in identifiers if identifier not in state["contracts"]]
    if missing:
        raise InstructionAdherenceError(f"Unknown instruction contract: {', '.join(missing)}")
    contracts = [_contract_status(base, state["contracts"][identifier]) for identifier in identifiers]
    statuses = {item["status"] for item in contracts}
    if statuses <= {"PASS"}:
        status, stop_allowed = "PASS", True
    elif "USER_DECISION_REQUIRED" in statuses:
        status, stop_allowed = "USER_DECISION_REQUIRED", False
    elif "ACTION_REQUIRED" in statuses:
        status, stop_allowed = "ACTION_REQUIRED", False
    elif "BLOCKED" in statuses:
        status, stop_allowed = "BLOCKED", True
    else:
        status, stop_allowed = "ACTION_REQUIRED", False
    return {
        "status": status,
        "stop_allowed": stop_allowed,
        "completion_claim_allowed": status == "PASS",
        "blocked_handoff_only": status == "BLOCKED",
        "policy_sha256": state["policy_sha256"],
        "contracts": contracts,
    }


def verify_instruction_contract(
    root: str | os.PathLike[str], contract_id: str | None = None,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base)
    status = instruction_adherence_status(base, contract_id)
    if status["status"] != "PASS":
        return {**status, "receipt": None}
    receipts: list[dict[str, Any]] = []
    for contract_status in status["contracts"]:
        record = state["contracts"][contract_status["contract_id"]]
        stable_states = [{
            "id": item["id"], "state": item["state"],
            "event_sha256": item["event_sha256"],
        } for item in contract_status["requirements"]]
        receipt = {
            "contract_id": contract_status["contract_id"],
            "contract_sha256": contract_status["contract_sha256"],
            "policy_sha256": state["policy_sha256"],
            "event_head_sha256": contract_status["event_head_sha256"],
            "requirement_states_sha256": digest(stable_states),
            "status": "PASS",
            "verified_at": utc_now(),
        }
        current = next((
            item for item in record["receipts"]
            if item.get("contract_sha256") == receipt["contract_sha256"]
            and item.get("policy_sha256") == receipt["policy_sha256"]
            and item.get("event_head_sha256") == receipt["event_head_sha256"]
            and item.get("requirement_states_sha256") == receipt["requirement_states_sha256"]
            and item.get("status") == "PASS"
        ), None)
        if current is not None:
            receipt = current
        else:
            receipt["receipt_sha256"] = digest(_receipt_stable(receipt))
            record["receipts"].append(receipt)
        receipts.append(receipt)
    _save_state(base, state)
    return {**status, "receipts": receipts}
