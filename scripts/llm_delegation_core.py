from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from research_guard_core import GuardError, digest, project_root, utc_now


SCHEMA_VERSION = 1
STATE_NAME = "llm-assistance-delegation.json"
POLICY_PATH = Path(__file__).resolve().parents[1] / "assets" / "llm-delegation-policy.json"
TASK_TYPES = {
    "literature_synthesis", "idea_critique", "draft_review", "translation_review",
    "metric_interpretation", "code_experiment_review", "ai_reviewer_evaluation", "other",
}
EXTERNAL_REQUIREMENTS = {"none", "user_requested_provider", "cross_provider_protocol"}
EXECUTION_MODES = {"native_subagent", "main_agent_local", "external_api_exception"}


class LLMDelegationError(GuardError):
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


def _text(value: Any, field: str) -> str:
    result = " ".join(str(value or "").split())
    if not result:
        raise LLMDelegationError(f"{field} is required")
    return result


def _load_policy() -> tuple[dict[str, Any], str]:
    try:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LLMDelegationError(f"Unreadable LLM delegation policy: {exc}") from exc
    if policy.get("schema_version") != SCHEMA_VERSION:
        raise LLMDelegationError("Unsupported LLM delegation policy schema")
    required = {
        "default_execution_mode": "native_subagent",
        "default_subagent_count": 1,
        "default_model_tier": "entry_or_lowest_capable",
        "default_reasoning_effort": "low",
        "maximum_reasoning_effort": "medium",
        "maximum_parallel_subagents": 1,
        "fallback_without_subagent": "main_agent_local",
        "external_api_default_allowed": False,
    }
    for key, expected in required.items():
        if policy.get(key) != expected:
            raise LLMDelegationError(f"LLM delegation policy drift: {key}")
    return policy, digest(policy)


def _plan_stable(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: plan.get(key) for key in (
        "task_id", "version", "task_type", "task_summary", "selected_by",
        "subagent_available", "external_requirement", "requested_provider",
        "external_selected_by", "external_rationale", "status", "execution_mode",
        "contract", "policy_sha256",
    )}


def _receipt_stable(receipt: dict[str, Any]) -> dict[str, Any]:
    return {key: receipt.get(key) for key in (
        "task_id", "plan_hash", "execution_mode", "executor_id", "model_tier",
        "reasoning_effort", "escalation_rationale", "provider_model_id",
        "artifact_path", "artifact_sha256", "independence_status",
    )}


def _load_state(root: Path, *, required: bool = True) -> dict[str, Any] | None:
    path = _state_path(root)
    if not path.exists():
        if required:
            raise LLMDelegationError("No LLM delegation state; call delegation_action=plan first")
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LLMDelegationError(f"Unreadable LLM delegation state: {exc}") from exc
    if state.get("schema_version") != SCHEMA_VERSION:
        raise LLMDelegationError("Unsupported LLM delegation state schema")
    tasks = state.get("tasks")
    if not isinstance(tasks, dict):
        raise LLMDelegationError("LLM delegation tasks must be an object")
    for task in tasks.values():
        for plan in task.get("plans", []):
            if digest(_plan_stable(plan)) != plan.get("plan_hash"):
                raise LLMDelegationError("LLM_DELEGATION_PLAN_INTEGRITY_FAILURE")
        for receipt in task.get("receipts", []):
            if digest(_receipt_stable(receipt)) != receipt.get("receipt_sha256"):
                raise LLMDelegationError("LLM_DELEGATION_RECEIPT_INTEGRITY_FAILURE")
    return state


def _save_state(root: Path, state: dict[str, Any]) -> None:
    _atomic_json(_state_path(root), state)


def _new_state(policy_hash: str) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "policy_sha256": policy_hash, "tasks": {}}


def plan_llm_assistance(
    root: str | os.PathLike[str], *, task_id: str, task_type: str, task_summary: str,
    selected_by: str, subagent_available: bool, external_requirement: str = "none",
    requested_provider: str | None = None, external_selected_by: str | None = None,
    external_rationale: str | None = None,
) -> dict[str, Any]:
    base = project_root(root)
    task_id = _text(task_id, "delegation_task_id")
    task_type = _text(task_type, "delegation_task_type").lower()
    if task_type not in TASK_TYPES:
        raise LLMDelegationError(f"Unsupported delegation_task_type: {task_type}")
    if selected_by != "main_agent":
        raise LLMDelegationError("delegation_selected_by=main_agent is required")
    if not isinstance(subagent_available, bool):
        raise LLMDelegationError("subagent_available must be a boolean")
    external_requirement = str(external_requirement or "none").strip().lower()
    if external_requirement not in EXTERNAL_REQUIREMENTS:
        raise LLMDelegationError(f"Unsupported external_requirement: {external_requirement}")
    policy, policy_hash = _load_policy()
    state = _load_state(base, required=False) or _new_state(policy_hash)
    state["policy_sha256"] = policy_hash
    task = state["tasks"].setdefault(task_id, {"plans": [], "receipts": []})
    version = len(task["plans"]) + 1

    if external_requirement != "none":
        provider = _text(requested_provider, "requested_provider")
        rationale = _text(external_rationale, "external_rationale")
        if external_selected_by != "user":
            status = "EXTERNAL_API_USER_DECISION_REQUIRED"
            mode = None
        else:
            status = "EXTERNAL_API_AUTHORIZED"
            mode = "external_api_exception"
    else:
        if external_selected_by or requested_provider or external_rationale:
            raise LLMDelegationError("External API fields require an external_requirement")
        provider = None
        rationale = None
        if subagent_available:
            status = "SUBAGENT_REQUIRED"
            mode = policy["default_execution_mode"]
        else:
            status = "LOCAL_FALLBACK_REQUIRED"
            mode = policy["fallback_without_subagent"]

    contract = {
        "subagent_count": policy["default_subagent_count"],
        "model_tier": policy["default_model_tier"],
        "reasoning_effort": policy["default_reasoning_effort"],
        "maximum_reasoning_effort": policy["maximum_reasoning_effort"],
        "parallelism": policy["maximum_parallel_subagents"],
        "external_api_allowed": mode == "external_api_exception",
        "fallback_without_subagent": policy["fallback_without_subagent"],
        "independence_boundary": policy["independence_boundary"],
    }
    plan = {
        "task_id": task_id, "version": version, "task_type": task_type,
        "task_summary": _text(task_summary, "delegation_task_summary"), "selected_by": selected_by,
        "subagent_available": subagent_available, "external_requirement": external_requirement,
        "requested_provider": provider, "external_selected_by": external_selected_by,
        "external_rationale": rationale, "status": status, "execution_mode": mode,
        "contract": contract, "policy_sha256": policy_hash,
    }
    plan["plan_hash"] = digest(_plan_stable(plan))
    plan["created_at"] = utc_now()
    task["plans"].append(plan)
    _save_state(base, state)
    return plan


def _artifact(base: Path, value: str) -> tuple[str, str]:
    raw = Path(_text(value, "delegation_artifact_path"))
    unresolved = raw if raw.is_absolute() else base / raw
    resolved = unresolved.resolve()
    try:
        relative = resolved.relative_to(base)
    except ValueError as exc:
        raise LLMDelegationError("delegation_artifact_path must remain inside project_root") from exc
    if not resolved.is_file():
        raise LLMDelegationError("delegation_artifact_path must be an existing regular file")
    hasher = hashlib.sha256()
    with resolved.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return relative.as_posix(), hasher.hexdigest()


def submit_llm_assistance(
    root: str | os.PathLike[str], *, task_id: str, execution_mode: str,
    artifact_path: str, executor_id: str, model_tier: str | None = None,
    reasoning_effort: str | None = None, escalation_rationale: str | None = None,
    provider_model_id: str | None = None,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base)
    task_id = _text(task_id, "delegation_task_id")
    task = state["tasks"].get(task_id)
    if not task or not task.get("plans"):
        raise LLMDelegationError("Unknown delegation task; call delegation_action=plan first")
    plan = task["plans"][-1]
    execution_mode = _text(execution_mode, "delegation_execution_mode").lower()
    if execution_mode not in EXECUTION_MODES or execution_mode != plan.get("execution_mode"):
        raise LLMDelegationError("Execution mode does not match the current delegation plan")
    if plan["status"] == "EXTERNAL_API_USER_DECISION_REQUIRED":
        raise LLMDelegationError("EXTERNAL_API_USER_DECISION_REQUIRED")
    executor_id = _text(executor_id, "delegation_executor_id")
    tier = str(model_tier or "").strip().lower() or None
    effort = str(reasoning_effort or "").strip().lower() or None
    provider = str(provider_model_id or "").strip() or None

    if execution_mode == "native_subagent":
        allowed_tiers = set(_load_policy()[0]["allowed_submission_model_tiers"])
        if tier not in allowed_tiers:
            raise LLMDelegationError("Native subagent model tier must be entry, economy, or lowest_capable")
        effort = effort or "low"
        if effort not in {"low", "medium"}:
            raise LLMDelegationError("Native subagent reasoning effort cannot exceed medium")
        if effort == "medium" and not str(escalation_rationale or "").strip():
            raise LLMDelegationError("Medium reasoning requires delegation_escalation_rationale")
        if provider:
            raise LLMDelegationError("Native subagent receipts must not claim an external provider model")
        independence = "NOT_CROSS_PROVIDER"
    elif execution_mode == "main_agent_local":
        if any((tier, effort, provider)):
            raise LLMDelegationError("Main-agent local fallback must not claim subagent/API model metadata")
        independence = "NOT_INDEPENDENT_REVIEW"
    else:
        if plan.get("external_selected_by") != "user":
            raise LLMDelegationError("External API execution requires explicit user selection")
        provider = _text(provider, "delegation_provider_model_id")
        independence = "DECLARED_EXTERNAL_PROVIDER"

    relative, artifact_hash = _artifact(base, artifact_path)
    receipt = {
        "task_id": task_id, "plan_hash": plan["plan_hash"], "execution_mode": execution_mode,
        "executor_id": executor_id, "model_tier": tier, "reasoning_effort": effort,
        "escalation_rationale": " ".join(str(escalation_rationale or "").split()) or None,
        "provider_model_id": provider, "artifact_path": relative,
        "artifact_sha256": artifact_hash, "independence_status": independence,
    }
    receipt["receipt_sha256"] = digest(_receipt_stable(receipt))
    receipt["created_at"] = utc_now()
    task["receipts"].append(receipt)
    _save_state(base, state)
    return receipt


def llm_assistance_status(root: str | os.PathLike[str], task_id: str | None = None) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, required=False)
    if state is None:
        return {"status": "NOT_PLANNED", "tasks": []}
    if task_id:
        task = state["tasks"].get(str(task_id))
        if not task:
            return {"status": "NOT_PLANNED", "task_id": str(task_id)}
        plan = task["plans"][-1]
        current_policy_hash = _load_policy()[1]
        if plan.get("policy_sha256") != current_policy_hash:
            return {"status": "POLICY_CHANGED_REPLAN_REQUIRED", "plan": plan, "receipts": []}
        current = [item for item in task.get("receipts", []) if item.get("plan_hash") == plan["plan_hash"]]
        return {"status": "COMPLETE" if current else plan["status"], "plan": plan, "receipts": current}
    return {"status": "PASS", "tasks": sorted(state["tasks"]), "policy_sha256": state["policy_sha256"]}


def verify_llm_assistance(root: str | os.PathLike[str], task_id: str | None = None) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base)
    task_ids = [str(task_id)] if task_id else sorted(state["tasks"])
    failures: list[dict[str, str]] = []
    verified = 0
    for identifier in task_ids:
        task = state["tasks"].get(identifier)
        if not task:
            failures.append({"task_id": identifier, "error": "NOT_PLANNED"})
            continue
        current_plan = task["plans"][-1]
        if current_plan.get("policy_sha256") != _load_policy()[1]:
            failures.append({"task_id": identifier, "error": "POLICY_CHANGED_REPLAN_REQUIRED"})
            continue
        current = [item for item in task.get("receipts", []) if item.get("plan_hash") == current_plan["plan_hash"]]
        if not current:
            failures.append({"task_id": identifier, "error": current_plan["status"]})
            continue
        for receipt in current:
            try:
                _, actual = _artifact(base, receipt["artifact_path"])
            except LLMDelegationError as exc:
                failures.append({"task_id": identifier, "error": str(exc)})
                continue
            if actual != receipt["artifact_sha256"]:
                failures.append({"task_id": identifier, "error": "DELEGATION_ARTIFACT_CHANGED"})
            else:
                verified += 1
    return {
        "status": "PASS" if not failures else "FAIL",
        "verified_receipts": verified, "failures": failures,
        "independence_boundary": _load_policy()[0]["independence_boundary"],
    }
