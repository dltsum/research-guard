from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from dependency_manager import DependencyError, component_need
from llm_delegation_core import LLMDelegationError, llm_assistance_status
from research_guard_core import GuardError, digest, project_root, utc_now
from resource_guard import (
    INSTALL_ORCHESTRATOR_RESERVE_BYTES,
    INSTALL_WORKER_LIMIT_BYTES,
    LEAN_ORCHESTRATOR_RESERVE_BYTES,
    LEAN_WORKER_LIMIT_BYTES,
    ORCHESTRATOR_RESERVE_BYTES,
    OWNED_TASK_BUDGET_BYTES,
    RESOURCE_POLICY,
    RUN_MIN_FREE_BYTES,
    START_MIN_FREE_BYTES,
    WORKER_JOB_LIMIT_BYTES,
    memory_snapshot,
)


SCHEMA_VERSION = 1
PROFILE_PATH = Path(__file__).resolve().parents[1] / "assets" / "task-resource-profiles.json"
PLAN_DIRECTORY = "resource-task-plans"
AUDIT_NAME = "resource-task-plan-audit.jsonl"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
RESOURCE_CLASSES = {
    "inline_light", "managed_standard", "managed_install", "managed_lean",
    "llm_assistance", "external_wait",
}
COMPLETION_SEMANTICS = {"read_only", "idempotent", "stateful"}
RECORD_STATUSES = {"running", "completed", "failed", "blocked", "unknown"}
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "BLOCKED"}
MAX_TASKS = 64
MAX_REVISIONS = 32
MAX_TRANSITIONS = 128
_MANAGED_TRANSITION_TOKEN = object()


class ResourcePlanError(GuardError):
    pass


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResourcePlanError(f"{label} is unreadable: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise ResourcePlanError(f"{label} has an unsupported schema")
    return value


def _profiles() -> tuple[dict[str, dict[str, Any]], str]:
    value = _load_json(PROFILE_PATH, "task resource profiles")
    profiles = value.get("profiles")
    if not isinstance(profiles, dict) or set(profiles) != RESOURCE_CLASSES:
        raise ResourcePlanError("task resource profile set is invalid")
    if value.get("global_contract", {}).get("maximum_parallel_tasks") != 1:
        raise ResourcePlanError("task resource profiles must preserve serial execution")
    if value.get("global_contract", {}).get("gpu_allowed") is not False:
        raise ResourcePlanError("task resource profiles must keep GPU execution disabled")
    expected = {
        "managed_standard": (WORKER_JOB_LIMIT_BYTES, ORCHESTRATOR_RESERVE_BYTES),
        "managed_install": (INSTALL_WORKER_LIMIT_BYTES, INSTALL_ORCHESTRATOR_RESERVE_BYTES),
        "managed_lean": (LEAN_WORKER_LIMIT_BYTES, LEAN_ORCHESTRATOR_RESERVE_BYTES),
    }
    for name, limits in expected.items():
        profile = profiles.get(name, {})
        if (profile.get("worker_limit_bytes"), profile.get("orchestrator_limit_bytes")) != limits:
            raise ResourcePlanError(f"task resource profile drift: {name}")
    return profiles, digest(value)


def _policy_hash() -> str:
    return digest(RESOURCE_POLICY)


def _text(value: Any, field: str, *, maximum: int = 1000) -> str:
    result = " ".join(str(value or "").split())
    if not result:
        raise ResourcePlanError(f"{field} is required")
    if len(result) > maximum:
        raise ResourcePlanError(f"{field} exceeds {maximum} characters")
    return result


def _identifier(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not IDENTIFIER.fullmatch(result):
        raise ResourcePlanError(f"{field} must match {IDENTIFIER.pattern}")
    return result


def _integrity_identifier(value: Any, field: str) -> str:
    result = re.sub(r"[^a-z0-9_-]+", "-", str(value or "").casefold()).strip("-")
    if not result or len(result) > 96:
        raise ResourcePlanError(f"{field} is invalid")
    return result


def _boolean(value: Any, field: str, *, optional: bool = False) -> bool | None:
    if optional and value is None:
        return None
    if not isinstance(value, bool):
        raise ResourcePlanError(f"{field} must be a boolean")
    return value


def _nonnegative_int(value: Any, field: str, *, optional: bool = True) -> int | None:
    if optional and value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ResourcePlanError(f"{field} must be a non-negative integer")
    return value


def _positive_number(value: Any, field: str, *, optional: bool = True) -> float | None:
    if optional and value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ResourcePlanError(f"{field} must be a positive number")
    try:
        numeric = float(value)
    except OverflowError as exc:
        raise ResourcePlanError(f"{field} must be a positive number") from exc
    if not math.isfinite(numeric) or numeric <= 0:
        raise ResourcePlanError(f"{field} must be a positive number")
    return numeric


def _nonnegative_number(value: Any, field: str, *, optional: bool = True) -> float | None:
    if optional and value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ResourcePlanError(f"{field} must be a non-negative number")
    try:
        numeric = float(value)
    except OverflowError as exc:
        raise ResourcePlanError(f"{field} must be a non-negative number") from exc
    if not math.isfinite(numeric) or numeric < 0:
        raise ResourcePlanError(f"{field} must be a non-negative number")
    return numeric


def _relative_artifact(value: Any, field: str) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    candidate = Path(raw)
    if not raw or candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ResourcePlanError(f"{field} must be a project-relative path without dot segments")
    return candidate.as_posix()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


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


def _plan_path(root: Path, plan_id: str) -> Path:
    return root / ".research-guard" / PLAN_DIRECTORY / f"{plan_id}.json"


def _append_audit(root: Path, event: str, details: dict[str, Any]) -> None:
    path = root / ".research-guard" / AUDIT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"at": utc_now(), "event": event, "details": details}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def _cpu_inventory() -> dict[str, Any]:
    host_logical = os.cpu_count()
    process_count = None
    process_source = None
    process_cpu_count = getattr(os, "process_cpu_count", None)
    if callable(process_cpu_count):
        try:
            process_count = process_cpu_count()
            process_source = "os.process_cpu_count"
        except OSError:
            process_count = None
    affinity_count = None
    if hasattr(os, "sched_getaffinity"):
        try:
            affinity_count = len(os.sched_getaffinity(0))
            process_source = "os.sched_getaffinity"
        except OSError:
            affinity_count = None
    if affinity_count is None:
        try:
            import psutil  # type: ignore

            affinity = psutil.Process().cpu_affinity()
            affinity_count = len(affinity) if affinity else None
            if affinity_count:
                process_source = "psutil.Process.cpu_affinity"
        except (ImportError, AttributeError, OSError):
            affinity_count = None
        except Exception as exc:  # psutil uses platform-specific exception classes.
            if exc.__class__.__module__.startswith("psutil"):
                affinity_count = None
            else:
                raise
    candidates = [value for value in (host_logical, process_count, affinity_count) if isinstance(value, int) and value > 0]
    effective = min(candidates) if candidates else None
    return {
        "host_logical": host_logical,
        "process_available_logical": process_count,
        "affinity_logical": affinity_count,
        "effective_capacity_logical": effective,
        "process_constraint_source": process_source,
        "admitted_parallel_tasks": 1,
        "numerical_threads_per_task": 1,
        "note": "Host and affinity counts are inventory; the registered serial policy is the execution entitlement.",
    }


def _disk_inventory(root: Path) -> dict[str, Any]:
    usage = shutil.disk_usage(root)
    user_available = int(usage.free)
    if hasattr(os, "statvfs"):
        try:
            stat = os.statvfs(root)
            user_available = int(stat.f_bavail * stat.f_frsize)
        except OSError:
            pass
    return {
        "capacity_bytes": int(usage.total),
        "free_bytes": int(usage.free),
        "user_available_bytes": user_available,
        "writable_non_mutating_check": bool(os.access(root, os.W_OK)),
        "scope": "project_filesystem_path_redacted",
        "quota_status": "unknown",
    }


def inventory_resources(root: str | os.PathLike[str]) -> dict[str, Any]:
    base = project_root(root)
    if not base.is_dir():
        raise ResourcePlanError("project_root must be an existing directory")
    profiles, profiles_hash = _profiles()
    memory = memory_snapshot()
    snapshot: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_kind": "research_guard_effective_resource_snapshot",
        "observed_at": utc_now(),
        "platform": {
            "system": platform.system(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "hostname_included": False,
        },
        "cpu": _cpu_inventory(),
        "memory": {
            "host_total_bytes": int(memory["total_physical_bytes"]),
            "host_available_bytes": int(memory["available_physical_bytes"]),
            "host_memory_load_percent": memory["memory_load_percent"],
            "owned_task_budget_bytes": OWNED_TASK_BUDGET_BYTES,
            "start_min_free_bytes": START_MIN_FREE_BYTES,
            "run_min_free_bytes": RUN_MIN_FREE_BYTES,
            "point_in_time_not_reservation": True,
        },
        "disk": _disk_inventory(base),
        "network": {
            "connectivity": "not_tested",
            "admission": "must_be_declared_in_resource_constraints",
        },
        "accelerators": {
            "management_visibility": "not_queried",
            "runtime_usable_devices": None,
            "policy_allowed": False,
            "status": "NOT_ADMITTED",
        },
        "scheduler_or_container_enforcement": "unknown_beyond_registered_process_guard",
        "task_profiles": profiles,
        "policy_sha256": _policy_hash(),
        "profiles_sha256": profiles_hash,
        "privacy": {
            "hostname_redacted": True,
            "absolute_project_path_redacted": True,
            "environment_values_redacted": True,
            "device_identifiers_redacted": True,
        },
    }
    snapshot["snapshot_sha256"] = digest({key: value for key, value in snapshot.items() if key != "snapshot_sha256"})
    return snapshot


def _normalize_constraints(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = value or {}
    if not isinstance(raw, dict):
        raise ResourcePlanError("resource_constraints must be an object")
    allowed = {
        "network_allowed", "max_download_bytes", "max_disk_write_bytes",
        "minimum_remaining_disk_bytes", "wall_clock_budget_seconds",
        "max_external_cost", "cost_currency", "budget_selected_by",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ResourcePlanError(f"unknown resource constraint fields: {', '.join(unknown)}")
    constraints = {
        "network_allowed": _boolean(raw.get("network_allowed"), "resource_constraints.network_allowed", optional=True),
        "max_download_bytes": _nonnegative_int(raw.get("max_download_bytes"), "resource_constraints.max_download_bytes"),
        "max_disk_write_bytes": _nonnegative_int(raw.get("max_disk_write_bytes"), "resource_constraints.max_disk_write_bytes"),
        "minimum_remaining_disk_bytes": _nonnegative_int(
            raw.get("minimum_remaining_disk_bytes"), "resource_constraints.minimum_remaining_disk_bytes",
        ),
        "wall_clock_budget_seconds": _positive_number(
            raw.get("wall_clock_budget_seconds"), "resource_constraints.wall_clock_budget_seconds",
        ),
        "max_external_cost": _nonnegative_number(raw.get("max_external_cost"), "resource_constraints.max_external_cost"),
        "cost_currency": str(raw.get("cost_currency") or "").strip() or None,
        "budget_selected_by": str(raw.get("budget_selected_by") or "").strip() or None,
    }
    budget_fields = (
        "max_download_bytes", "max_disk_write_bytes", "minimum_remaining_disk_bytes",
        "wall_clock_budget_seconds", "max_external_cost",
    )
    if any(constraints[field] is not None for field in budget_fields) and constraints["budget_selected_by"] != "user":
        raise ResourcePlanError("explicit resource budgets require budget_selected_by=user")
    if (constraints["max_external_cost"] is None) != (constraints["cost_currency"] is None):
        raise ResourcePlanError("max_external_cost and cost_currency must be supplied together")
    if constraints["cost_currency"] and len(constraints["cost_currency"]) > 12:
        raise ResourcePlanError("cost_currency is too long")
    return constraints


def _normalize_string_list(value: Any, field: str, *, limit: int) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit:
        raise ResourcePlanError(f"{field} must be an array with at most {limit} entries")
    result = [_identifier(item, f"{field}[]") for item in value]
    if len(result) != len(set(result)):
        raise ResourcePlanError(f"{field} contains duplicates")
    return result


def _normalize_task(value: Any, profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ResourcePlanError("each resource task must be an object")
    allowed = {
        "task_id", "summary", "resource_class", "depends_on", "expected_artifacts",
        "completion_semantics", "network_required", "gpu_required", "optional_components",
        "delegation_task_id", "reproducibility_run_id", "cpu_threads", "estimated_peak_memory_bytes",
        "estimated_download_bytes", "estimated_disk_write_bytes", "estimated_duration_seconds",
        "estimated_external_cost",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ResourcePlanError(f"unknown resource task fields: {', '.join(unknown)}")
    resource_class = str(value.get("resource_class") or "").strip()
    if resource_class not in profiles:
        raise ResourcePlanError(f"unsupported resource_class: {resource_class}")
    semantics = str(value.get("completion_semantics") or "").strip()
    if semantics not in COMPLETION_SEMANTICS:
        raise ResourcePlanError(f"unsupported completion_semantics: {semantics}")
    artifacts_raw = value.get("expected_artifacts") or []
    if not isinstance(artifacts_raw, list) or len(artifacts_raw) > 16:
        raise ResourcePlanError("expected_artifacts must contain at most 16 paths")
    artifacts = [_relative_artifact(item, "expected_artifacts[]") for item in artifacts_raw]
    if len(artifacts) != len(set(artifacts)):
        raise ResourcePlanError("expected_artifacts contains duplicates")
    if (semantics != "read_only" or resource_class in {"llm_assistance", "external_wait"}) and not artifacts:
        raise ResourcePlanError("stateful, idempotent, LLM, and external-wait tasks require expected_artifacts")
    delegation_task_id = str(value.get("delegation_task_id") or "").strip() or None
    if resource_class == "llm_assistance":
        delegation_task_id = _identifier(delegation_task_id, "delegation_task_id")
    elif delegation_task_id:
        raise ResourcePlanError("delegation_task_id is valid only for resource_class=llm_assistance")
    reproducibility_run_id = str(value.get("reproducibility_run_id") or "").strip() or None
    if reproducibility_run_id:
        reproducibility_run_id = _integrity_identifier(reproducibility_run_id, "reproducibility_run_id")
        if resource_class != "managed_standard":
            raise ResourcePlanError(
                "reproducibility_run_id is valid only for resource_class=managed_standard"
            )
    optional_components = _normalize_string_list(value.get("optional_components"), "optional_components", limit=8)
    task = {
        "task_id": _identifier(value.get("task_id"), "task_id"),
        "summary": _text(value.get("summary"), "task.summary", maximum=500),
        "resource_class": resource_class,
        "depends_on": _normalize_string_list(value.get("depends_on"), "depends_on", limit=MAX_TASKS),
        "expected_artifacts": artifacts,
        "completion_semantics": semantics,
        "network_required": _boolean(value.get("network_required", False), "task.network_required"),
        "gpu_required": _boolean(value.get("gpu_required", False), "task.gpu_required"),
        "optional_components": optional_components,
        "delegation_task_id": delegation_task_id,
        "reproducibility_run_id": reproducibility_run_id,
        "reproducibility_plan_hash": None,
        "cpu_threads": _nonnegative_int(value.get("cpu_threads", 1), "task.cpu_threads", optional=False),
        "estimated_peak_memory_bytes": _nonnegative_int(
            value.get("estimated_peak_memory_bytes"), "task.estimated_peak_memory_bytes",
        ),
        "estimated_download_bytes": _nonnegative_int(
            value.get("estimated_download_bytes"), "task.estimated_download_bytes",
        ),
        "estimated_disk_write_bytes": _nonnegative_int(
            value.get("estimated_disk_write_bytes"), "task.estimated_disk_write_bytes",
        ),
        "estimated_duration_seconds": _positive_number(
            value.get("estimated_duration_seconds"), "task.estimated_duration_seconds",
        ),
        "estimated_external_cost": _nonnegative_number(
            value.get("estimated_external_cost"), "task.estimated_external_cost",
        ),
    }
    if task["cpu_threads"] < 1:
        raise ResourcePlanError("task.cpu_threads must be at least one")
    if not task["network_required"] and (task["estimated_download_bytes"] or 0) > 0:
        raise ResourcePlanError("estimated_download_bytes requires network_required=true")
    if task["resource_class"] not in {"llm_assistance", "external_wait"} and task["estimated_external_cost"] not in {None, 0.0}:
        raise ResourcePlanError("estimated_external_cost is valid only for LLM or external-wait tasks")
    return task


def _topological(tasks: list[dict[str, Any]]) -> tuple[list[str], list[list[str]]]:
    ids = {task["task_id"] for task in tasks}
    if len(ids) != len(tasks):
        raise ResourcePlanError("resource_tasks contains duplicate task_id values")
    for task in tasks:
        unknown = sorted(set(task["depends_on"]) - ids)
        if unknown:
            raise ResourcePlanError(f"task {task['task_id']} has unknown dependencies: {', '.join(unknown)}")
        if task["task_id"] in task["depends_on"]:
            raise ResourcePlanError(f"task {task['task_id']} depends on itself")
    order: list[str] = []
    waves: list[list[str]] = []
    remaining = {task["task_id"]: set(task["depends_on"]) for task in tasks}
    completed: set[str] = set()
    position = {task["task_id"]: index for index, task in enumerate(tasks)}
    while remaining:
        wave = sorted((identifier for identifier, deps in remaining.items() if deps <= completed), key=position.get)
        if not wave:
            raise ResourcePlanError("resource_tasks dependency graph contains a cycle")
        waves.append(wave)
        order.extend(wave)
        completed.update(wave)
        for identifier in wave:
            remaining.pop(identifier)
    return order, waves


def _issue(code: str, task_id: str, message: str, action: str) -> dict[str, str]:
    return {"code": code, "task_id": task_id, "message": message, "action": action}


def _task_issues(
    root: Path, task: dict[str, Any], constraints: dict[str, Any], snapshot: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    identifier = task["task_id"]
    profile = profiles[task["resource_class"]]
    if task["gpu_required"]:
        issues.append(_issue("GPU_NOT_ADMITTED", identifier, "The registered plugin policy disables GPU execution.", "Replan for CPU or obtain a separately registered resource-policy change."))
    if task["cpu_threads"] > 1:
        issues.append(_issue("CPU_PROFILE_NOT_ADMITTED", identifier, "Research Guard admits one numerical thread and one task at a time.", "Replan this stage for one thread or use an externally admitted environment."))
    memory_estimate = task["estimated_peak_memory_bytes"]
    memory_limit = profile.get("worker_limit_bytes")
    if task["resource_class"] == "inline_light":
        memory_limit = profile.get("orchestrator_limit_bytes")
    if memory_estimate is not None and isinstance(memory_limit, int) and memory_estimate > memory_limit:
        issues.append(_issue("MEMORY_PROFILE_EXCEEDED", identifier, f"Estimated peak memory {memory_estimate} exceeds profile limit {memory_limit} bytes.", "Split the task, stream its inputs, or choose an admitted profile that fits."))
    if task["resource_class"] == "llm_assistance":
        try:
            delegation = llm_assistance_status(root, task["delegation_task_id"])
        except LLMDelegationError as exc:
            delegation = {"status": "INVALID", "error": str(exc)}
        if delegation.get("status") in {"NOT_PLANNED", "POLICY_CHANGED_REPLAN_REQUIRED", "INVALID", "EXTERNAL_API_USER_DECISION_REQUIRED"}:
            issues.append(_issue("LLM_DELEGATION_PLAN_REQUIRED", identifier, "The LLM-assistance route is not currently admitted.", "Call research_design delegation_action=plan, resolve any explicit API decision, then replan resources."))
        warnings.append(_issue("HOST_RESOURCE_ACCOUNTING_NOT_PROVEN", identifier, "Host-native subagent memory is not measured by the plugin's local process guard.", "Keep execution serial and preserve the delegation receipt."))
    if task["reproducibility_run_id"]:
        try:
            from research_integrity_core import IntegrityError, integrity_status
            reproducibility = integrity_status(
                root, "reproducibility", task["reproducibility_run_id"],
            )
        except (IntegrityError, OSError, ValueError) as exc:
            reproducibility = None
            task["reproducibility_plan_hash"] = None
            issues.append(_issue(
                "REPRODUCIBILITY_PLAN_REQUIRED", identifier,
                f"The linked reproducibility plan is unavailable: {exc}",
                "Register a user-selected frozen reproducibility plan, then replan resources.",
            ))
        if reproducibility is not None:
            task["reproducibility_plan_hash"] = reproducibility.get("plan_hash")
            if reproducibility.get("status") != "EXECUTION_REQUIRED" or reproducibility.get("execution") is not None:
                issues.append(_issue(
                    "REPRODUCIBILITY_PLAN_NOT_EXECUTABLE", identifier,
                    f"The linked reproducibility plan status is {reproducibility.get('status')}.",
                    "Create a fresh versioned reproducibility plan, then replan this task.",
                ))
            if reproducibility.get("selected_by") != "user":
                issues.append(_issue(
                    "REPRODUCIBILITY_USER_SELECTION_REQUIRED", identifier,
                    "The linked command plan was not selected by the user.",
                    "Register the exact user-selected command, inputs, outputs, parameters, seeds, and checks.",
                ))
            if list(reproducibility.get("outputs") or []) != task["expected_artifacts"]:
                issues.append(_issue(
                    "REPRODUCIBILITY_OUTPUT_MISMATCH", identifier,
                    "The linked reproducibility outputs do not exactly match expected_artifacts.",
                    "Use the same ordered versioned output paths in both contracts, then replan.",
                ))
        if task["network_required"]:
            issues.append(_issue(
                "MANAGED_NETWORK_ISOLATION_UNAVAILABLE", identifier,
                "The canonical local reproducibility executor does not prove process-level network isolation.",
                "Use an admitted external sandbox with a receipt, or replan this managed execution as offline.",
            ))
        if constraints["max_disk_write_bytes"] is not None:
            issues.append(_issue(
                "MANAGED_DISK_TELEMETRY_UNAVAILABLE", identifier,
                "The canonical local reproducibility executor does not measure full process-tree disk writes.",
                "Remove this execution binding or use an admitted executor that produces disk-I/O telemetry; do not infer writes from output size.",
            ))
    if task["network_required"]:
        if constraints["network_allowed"] is None:
            issues.append(_issue("NETWORK_DECISION_REQUIRED", identifier, "Network access was not declared.", "Set resource_constraints.network_allowed from the current task authority and replan."))
        elif constraints["network_allowed"] is False:
            issues.append(_issue("NETWORK_NOT_ADMITTED", identifier, "This task needs network access but the plan forbids it.", "Use an offline route or replan after network authority changes."))
        if constraints["max_download_bytes"] is not None and task["estimated_download_bytes"] is None:
            issues.append(_issue("DOWNLOAD_ESTIMATE_REQUIRED", identifier, "A download budget exists but this network task has no download estimate.", "Supply an evidence-based estimate or an explicit zero and replan."))
    component_ids = list(task["optional_components"])
    if task["resource_class"] == "managed_lean" and "lean-mathlib" not in component_ids:
        component_ids.append("lean-mathlib")
    for component_id in component_ids:
        try:
            dependency = component_need(component_id)
        except DependencyError as exc:
            raise ResourcePlanError(f"dependency {component_id} is invalid: {exc.code}") from exc
        if dependency.get("status") != "AVAILABLE":
            issues.append(_issue("DEPENDENCY_DECISION_REQUIRED", identifier, f"Optional component {component_id} is {dependency.get('status')}.", f"Call dependency_action=need for {component_id}; apply only the user's reuse/install/not_now choice, then replan."))
    available_disk = snapshot["disk"]["user_available_bytes"]
    disk_estimate = task["estimated_disk_write_bytes"]
    disk_budget = constraints["max_disk_write_bytes"]
    reserve = constraints["minimum_remaining_disk_bytes"]
    if disk_budget is not None and disk_estimate is None:
        issues.append(_issue("DISK_ESTIMATE_REQUIRED", identifier, "A disk-write budget exists but this task has no disk estimate.", "Supply an evidence-based estimate or explicit zero and replan."))
    if disk_estimate is not None and disk_estimate > available_disk:
        issues.append(_issue("DISK_CAPACITY_EXCEEDED", identifier, "Estimated writes exceed current user-available filesystem space.", "Reduce outputs, free space, or choose another admitted filesystem."))
    if disk_estimate is not None and reserve is not None and disk_estimate + reserve > available_disk:
        issues.append(_issue("DISK_RESERVE_EXCEEDED", identifier, "Estimated writes would cross the user-selected remaining-disk reserve.", "Reduce outputs or revise the explicit reserve."))
    if constraints["wall_clock_budget_seconds"] is not None and task["estimated_duration_seconds"] is None:
        issues.append(_issue("DURATION_ESTIMATE_REQUIRED", identifier, "A user wall-clock budget exists but this stage has no duration estimate.", "Supply an evidence-based stage estimate; do not invent one."))
    if constraints["max_external_cost"] is not None and task["estimated_external_cost"] is None and task["resource_class"] in {"llm_assistance", "external_wait"}:
        issues.append(_issue("COST_ESTIMATE_REQUIRED", identifier, "A user cost budget exists but this external stage has no cost estimate.", "Supply a provider-backed estimate or explicit zero and replan."))
    if reserve is None:
        warnings.append(_issue("DISK_RESERVE_UNSPECIFIED", identifier, "No user-selected remaining-disk reserve was supplied.", "Recheck free space before execution and preserve incremental artifacts."))
    return issues, warnings


def _budget_issues(tasks: list[dict[str, Any]], constraints: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    mappings = (
        ("max_download_bytes", "estimated_download_bytes", "DOWNLOAD_BUDGET_EXCEEDED", lambda task: task["network_required"]),
        ("max_disk_write_bytes", "estimated_disk_write_bytes", "DISK_WRITE_BUDGET_EXCEEDED", lambda task: True),
        ("wall_clock_budget_seconds", "estimated_duration_seconds", "WALL_CLOCK_BUDGET_EXCEEDED", lambda task: True),
        ("max_external_cost", "estimated_external_cost", "EXTERNAL_COST_BUDGET_EXCEEDED", lambda task: task["resource_class"] in {"llm_assistance", "external_wait"}),
    )
    for budget_key, estimate_key, code, applies in mappings:
        budget = constraints[budget_key]
        relevant = [task for task in tasks if applies(task)]
        if budget is None or not relevant or any(task[estimate_key] is None for task in relevant):
            continue
        total = sum(task[estimate_key] for task in relevant)
        if total > budget:
            issues.append(_issue(code, "__plan__", f"Declared total {estimate_key}={total} exceeds {budget_key}={budget}.", "Reduce or split stages, or ask the user to revise the explicit budget."))
    return issues


def _state_stable(revision: dict[str, Any]) -> dict[str, Any]:
    return {
        "plan_hash": revision.get("plan_hash"),
        "task_states": revision.get("task_states"),
        "updated_at": revision.get("updated_at"),
        "superseded_at": revision.get("superseded_at"),
    }


def _plan_stable(revision: dict[str, Any]) -> dict[str, Any]:
    return {key: revision.get(key) for key in (
        "resource_plan_id", "revision", "task_goal", "selected_by", "constraints",
        "resource_snapshot", "policy_sha256", "profiles_sha256", "tasks",
        "dependency_waves", "serial_execution_order", "static_issues", "warnings",
        "plan_budget_issue_codes",
    )}


def _seal_revision(revision: dict[str, Any]) -> None:
    revision["plan_hash"] = digest(_plan_stable(revision))
    revision["state_sha256"] = digest(_state_stable(revision))


def _verify_revision(revision: dict[str, Any]) -> None:
    if digest(_plan_stable(revision)) != revision.get("plan_hash"):
        raise ResourcePlanError("RESOURCE_PLAN_INTEGRITY_FAILURE")
    if digest(_state_stable(revision)) != revision.get("state_sha256"):
        raise ResourcePlanError("RESOURCE_PLAN_STATE_INTEGRITY_FAILURE")


def _load_state(root: Path, plan_id: str, *, required: bool = True) -> dict[str, Any] | None:
    path = _plan_path(root, plan_id)
    if not path.exists():
        if required:
            raise ResourcePlanError("No resource task plan; call resource_plan_action=plan first")
        return None
    value = _load_json(path, "resource task plan")
    if value.get("resource_plan_id") != plan_id or not isinstance(value.get("revisions"), list):
        raise ResourcePlanError("resource task plan identity is invalid")
    if not value["revisions"] or value.get("active_revision") != value["revisions"][-1].get("revision"):
        raise ResourcePlanError("resource task plan active revision is invalid")
    for revision in value["revisions"]:
        _verify_revision(revision)
    return value


def _task_map(revision: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {task["task_id"]: task for task in revision["tasks"]}


def _refresh_states(revision: dict[str, Any]) -> None:
    tasks = _task_map(revision)
    states = revision["task_states"]
    static_by_task: dict[str, list[str]] = {}
    for issue in revision["static_issues"]:
        static_by_task.setdefault(issue["task_id"], []).append(issue["code"])
    for identifier in revision["serial_execution_order"]:
        state = states[identifier]
        if state["status"] in TERMINAL_STATUSES | {"RUNNING", "UNKNOWN"}:
            continue
        if static_by_task.get(identifier) or revision.get("plan_budget_issue_codes"):
            state["status"] = "BLOCKED"
            state["reason"] = "static resource admission issue"
            continue
        dependencies = [states[item]["status"] for item in tasks[identifier]["depends_on"]]
        if any(status in {"FAILED", "BLOCKED"} for status in dependencies):
            state["status"] = "BLOCKED"
            state["reason"] = "upstream task failed or is blocked"
        elif any(status == "UNKNOWN" for status in dependencies):
            state["status"] = "PENDING"
            state["reason"] = "upstream completion is unknown; inspect its receipt before replay"
        elif all(status == "COMPLETED" for status in dependencies):
            state["status"] = "READY"
            state["reason"] = "dependencies and static resource admission are satisfied"
        else:
            state["status"] = "PENDING"
            state["reason"] = "waiting for dependencies"


def _summary(revision: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for state in revision["task_states"].values():
        counts[state["status"]] = counts.get(state["status"], 0) + 1
    statuses = set(counts)
    if counts.get("COMPLETED") == len(revision["task_states"]):
        status = "COMPLETE"
    elif "UNKNOWN" in statuses:
        status = "RECEIPT_INSPECTION_REQUIRED"
    elif "RUNNING" in statuses:
        status = "IN_PROGRESS"
    elif "FAILED" in statuses:
        status = "FAILED"
    elif "BLOCKED" in statuses:
        status = "ACTION_REQUIRED"
    elif "READY" in statuses:
        status = "READY"
    else:
        status = "PENDING"
    return {
        "status": status,
        "resource_plan_id": revision["resource_plan_id"],
        "revision": revision["revision"],
        "plan_hash": revision["plan_hash"],
        "state_sha256": revision["state_sha256"],
        "counts": counts,
        "next_ready_task_ids": [
            identifier for identifier in revision["serial_execution_order"]
            if revision["task_states"][identifier]["status"] == "READY"
        ][:1],
        "maximum_parallel_tasks": 1,
        "task_states": revision["task_states"],
        "static_issues": revision["static_issues"],
        "warnings": revision["warnings"],
    }


def plan_resource_tasks(
    root: str | os.PathLike[str], *, plan_id: str, task_goal: str, tasks: list[dict[str, Any]],
    constraints: dict[str, Any] | None, selected_by: str,
) -> dict[str, Any]:
    base = project_root(root)
    if not base.is_dir():
        raise ResourcePlanError("project_root must be an existing directory")
    plan_id = _identifier(plan_id, "resource_plan_id")
    if selected_by != "main_agent":
        raise ResourcePlanError("resource_selected_by=main_agent is required")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= MAX_TASKS:
        raise ResourcePlanError(f"resource_tasks must contain 1-{MAX_TASKS} tasks")
    profiles, profiles_hash = _profiles()
    normalized_tasks = [_normalize_task(item, profiles) for item in tasks]
    order, waves = _topological(normalized_tasks)
    normalized_constraints = _normalize_constraints(constraints)
    snapshot = inventory_resources(base)
    static_issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for task in normalized_tasks:
        task_issues, task_warnings = _task_issues(base, task, normalized_constraints, snapshot, profiles)
        static_issues.extend(task_issues)
        warnings.extend(task_warnings)
    budget_issues = _budget_issues(normalized_tasks, normalized_constraints)
    static_issues.extend(budget_issues)
    state = _load_state(base, plan_id, required=False) or {
        "schema_version": SCHEMA_VERSION, "resource_plan_id": plan_id, "active_revision": 0, "revisions": [],
    }
    if len(state["revisions"]) >= MAX_REVISIONS:
        raise ResourcePlanError(f"resource plan exceeds the {MAX_REVISIONS}-revision safety bound")
    if state["revisions"]:
        previous = state["revisions"][-1]
        previous["superseded_at"] = utc_now()
        previous["updated_at"] = previous["superseded_at"]
        previous["state_sha256"] = digest(_state_stable(previous))
    revision_number = len(state["revisions"]) + 1
    now = utc_now()
    revision: dict[str, Any] = {
        "resource_plan_id": plan_id,
        "revision": revision_number,
        "task_goal": _text(task_goal, "resource_task_goal", maximum=1200),
        "selected_by": selected_by,
        "constraints": normalized_constraints,
        "resource_snapshot": snapshot,
        "policy_sha256": _policy_hash(),
        "profiles_sha256": profiles_hash,
        "tasks": normalized_tasks,
        "dependency_waves": waves,
        "serial_execution_order": order,
        "static_issues": static_issues,
        "warnings": warnings,
        "plan_budget_issue_codes": [item["code"] for item in budget_issues],
        "task_states": {
            task["task_id"]: {
                "status": "PENDING", "reason": "awaiting admission refresh", "history": [],
                "artifacts": [], "resource_observation": None, "observation_source": None,
                "execution_receipt": None,
            }
            for task in normalized_tasks
        },
        "created_at": now,
        "updated_at": now,
        "superseded_at": None,
    }
    _seal_revision(revision)
    _refresh_states(revision)
    revision["state_sha256"] = digest(_state_stable(revision))
    state["revisions"].append(revision)
    state["active_revision"] = revision_number
    _atomic_json(_plan_path(base, plan_id), state)
    _append_audit(base, "resource_plan_registered", {
        "resource_plan_id": plan_id, "revision": revision_number,
        "plan_hash": revision["plan_hash"], "task_count": len(normalized_tasks),
        "static_issue_codes": sorted({item["code"] for item in static_issues}),
    })
    return {
        **_summary(revision),
        "task_goal": revision["task_goal"],
        "resource_snapshot": snapshot,
        "dependency_waves": waves,
        "serial_execution_order": order,
        "tasks": normalized_tasks,
        "constraints": normalized_constraints,
        "no_user_deadline": normalized_constraints["wall_clock_budget_seconds"] is None,
    }


def _artifact_records(root: Path, paths: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, item in enumerate(paths):
        relative = _relative_artifact(item, f"resource_task_artifacts[{index}]")
        resolved = (root / relative).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ResourcePlanError("resource task artifact escapes project_root") from exc
        if not resolved.is_file():
            raise ResourcePlanError(f"resource task artifact is missing: {relative}")
        records.append({"path": relative, "bytes": resolved.stat().st_size, "sha256": _sha256_file(resolved)})
    return records


def _normalize_observation(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = value or {}
    if not isinstance(raw, dict):
        raise ResourcePlanError("resource_observation must be an object")
    allowed = {
        "peak_worker_bytes", "peak_orchestrator_bytes", "peak_owned_bytes", "disk_written_bytes",
        "downloaded_bytes", "duration_seconds", "external_cost", "receipt_inspected",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ResourcePlanError(f"unknown resource observation fields: {', '.join(unknown)}")
    return {
        "peak_worker_bytes": _nonnegative_int(raw.get("peak_worker_bytes"), "resource_observation.peak_worker_bytes"),
        "peak_orchestrator_bytes": _nonnegative_int(raw.get("peak_orchestrator_bytes"), "resource_observation.peak_orchestrator_bytes"),
        "peak_owned_bytes": _nonnegative_int(raw.get("peak_owned_bytes"), "resource_observation.peak_owned_bytes"),
        "disk_written_bytes": _nonnegative_int(raw.get("disk_written_bytes"), "resource_observation.disk_written_bytes"),
        "downloaded_bytes": _nonnegative_int(raw.get("downloaded_bytes"), "resource_observation.downloaded_bytes"),
        "duration_seconds": _nonnegative_number(raw.get("duration_seconds"), "resource_observation.duration_seconds"),
        "external_cost": _nonnegative_number(raw.get("external_cost"), "resource_observation.external_cost"),
        "receipt_inspected": _boolean(raw.get("receipt_inspected", False), "resource_observation.receipt_inspected"),
    }


def _normalize_execution_receipt(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ResourcePlanError("execution receipt must be an object")
    allowed = {
        "owner", "run_id", "plan_hash", "execution_hash", "execution_mode",
        "reproducibility_status",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ResourcePlanError(f"unknown execution receipt fields: {', '.join(unknown)}")
    if value.get("owner") != "research_integrity.execute_reproducibility":
        raise ResourcePlanError("execution receipt has an unsupported owner")
    if value.get("execution_mode") != "managed":
        raise ResourcePlanError("execution receipt must come from managed reproducibility")
    status = str(value.get("reproducibility_status") or "").strip().upper()
    if status not in {"PASS", "FAILED"}:
        raise ResourcePlanError("execution receipt reproducibility_status must be PASS or FAILED")
    normalized = {
        "owner": value["owner"],
        "run_id": _integrity_identifier(value.get("run_id"), "execution_receipt.run_id"),
        "plan_hash": str(value.get("plan_hash") or "").lower(),
        "execution_hash": str(value.get("execution_hash") or "").lower(),
        "execution_mode": value["execution_mode"],
        "reproducibility_status": status,
    }
    for field in ("plan_hash", "execution_hash"):
        if not re.fullmatch(r"[0-9a-f]{64}", normalized[field]):
            raise ResourcePlanError(f"execution receipt {field} must be a SHA-256 value")
    return normalized


def _validate_observation(revision: dict[str, Any], task: dict[str, Any], observation: dict[str, Any], status: str) -> None:
    profiles, _ = _profiles()
    profile = profiles[task["resource_class"]]
    if status == "completed" and task["resource_class"] in {"managed_standard", "managed_install", "managed_lean"}:
        required = ("peak_worker_bytes", "peak_orchestrator_bytes", "peak_owned_bytes")
        if any(observation[field] is None for field in required):
            raise ResourcePlanError("completed managed tasks require aggregate memory telemetry")
    limits = {
        "peak_worker_bytes": profile.get("worker_limit_bytes"),
        "peak_orchestrator_bytes": profile.get("orchestrator_limit_bytes"),
        "peak_owned_bytes": OWNED_TASK_BUDGET_BYTES,
    }
    for field, limit in limits.items():
        if observation[field] is not None and isinstance(limit, int) and observation[field] > limit:
            raise ResourcePlanError(f"RESOURCE_OBSERVATION_LIMIT_EXCEEDED: {field}")
    constraints = revision["constraints"]
    required_observations = (
        ("max_download_bytes", "downloaded_bytes", task["network_required"]),
        ("max_disk_write_bytes", "disk_written_bytes", True),
        ("wall_clock_budget_seconds", "duration_seconds", True),
    )
    if status == "completed":
        for budget_field, observation_field, applies in required_observations:
            if applies and constraints[budget_field] is not None and observation[observation_field] is None:
                raise ResourcePlanError(f"completed task requires {observation_field} under the explicit budget")
        if constraints["max_external_cost"] is not None and task["resource_class"] in {"llm_assistance", "external_wait"} and observation["external_cost"] is None:
            raise ResourcePlanError("completed external task requires external_cost under the explicit budget")
    aggregate_fields = (
        ("max_download_bytes", "downloaded_bytes"),
        ("max_disk_write_bytes", "disk_written_bytes"),
        ("wall_clock_budget_seconds", "duration_seconds"),
        ("max_external_cost", "external_cost"),
    )
    if status != "completed":
        return
    for budget_field, observation_field in aggregate_fields:
        budget = constraints[budget_field]
        current = observation[observation_field]
        if budget is None or current is None:
            continue
        previous = sum(
            float(state.get("resource_observation", {}).get(observation_field) or 0)
            for identifier, state in revision["task_states"].items()
            if identifier != task["task_id"]
            if isinstance(state.get("resource_observation"), dict)
        )
        if previous + current > budget:
            raise ResourcePlanError(f"RESOURCE_BUDGET_EXCEEDED: {budget_field}")


def record_resource_task(
    root: str | os.PathLike[str], *, plan_id: str, task_id: str, task_status: str,
    artifacts: list[str] | None = None, observation: dict[str, Any] | None = None,
    note: str | None = None, _observation_source: str = "caller_reported",
    _execution_receipt: dict[str, Any] | None = None, _managed_token: object | None = None,
) -> dict[str, Any]:
    base = project_root(root)
    plan_id = _identifier(plan_id, "resource_plan_id")
    task_id = _identifier(task_id, "resource_task_id")
    status = str(task_status or "").strip().lower()
    if status not in RECORD_STATUSES:
        raise ResourcePlanError(f"unsupported resource_task_status: {status}")
    state = _load_state(base, plan_id)
    revision = state["revisions"][-1]
    tasks = _task_map(revision)
    if task_id not in tasks:
        raise ResourcePlanError(f"unknown resource task: {task_id}")
    task = tasks[task_id]
    task_state = revision["task_states"][task_id]
    current = task_state["status"]
    if _observation_source not in {
        "caller_reported", "managed_reproducibility_start", "managed_reproducibility_receipt",
        "managed_reproducibility_failure", "managed_process_guard_failure",
        "managed_reproducibility_unknown",
    }:
        raise ResourcePlanError("unsupported resource observation source")
    if _observation_source != "caller_reported" and _managed_token is not _MANAGED_TRANSITION_TOKEN:
        raise ResourcePlanError("managed transition source is internal to resource_plan_action=execute")
    execution_receipt = _normalize_execution_receipt(_execution_receipt)
    receipt_sources = {"managed_reproducibility_receipt", "managed_reproducibility_failure"}
    if (_observation_source in receipt_sources) != (execution_receipt is not None):
        raise ResourcePlanError("managed reproducibility completion/failure requires its execution receipt")
    if execution_receipt is not None:
        if not task.get("reproducibility_run_id"):
            raise ResourcePlanError("execution receipt requires a linked reproducibility_run_id")
        if execution_receipt["run_id"] != task["reproducibility_run_id"]:
            raise ResourcePlanError("execution receipt run_id does not match the task binding")
        if execution_receipt["plan_hash"] != task.get("reproducibility_plan_hash"):
            raise ResourcePlanError("execution receipt plan_hash does not match the task binding")
    if current == "COMPLETED":
        raise ResourcePlanError("completed tasks are immutable; replan instead of replaying them")
    if current == "BLOCKED" and status not in {"blocked"}:
        raise ResourcePlanError("blocked tasks require replanning before execution")
    if current == "PENDING" and status not in {"blocked"}:
        raise ResourcePlanError("task dependencies are not complete")
    normalized_observation = _normalize_observation(observation)
    if current == "UNKNOWN" and status != "unknown" and normalized_observation["receipt_inspected"] is not True:
        raise ResourcePlanError("RECEIPT_INSPECTION_REQUIRED before resolving unknown completion")
    if status == "running" and current != "READY":
        raise ResourcePlanError("only a READY task can enter RUNNING")
    if status == "completed" and current not in {"READY", "RUNNING", "UNKNOWN"}:
        raise ResourcePlanError("task cannot enter COMPLETED from its current state")
    if (
        status == "completed" and task.get("reproducibility_run_id")
        and _observation_source != "managed_reproducibility_receipt"
    ):
        raise ResourcePlanError(
            "MANAGED_REPRODUCIBILITY_EXECUTION_REQUIRED: linked tasks cannot be completed from caller-reported telemetry"
        )
    if status in {"failed", "unknown"} and current not in {"READY", "RUNNING", "UNKNOWN"}:
        raise ResourcePlanError(f"task cannot enter {status.upper()} from its current state")
    if len(task_state["history"]) >= MAX_TRANSITIONS:
        raise ResourcePlanError("task transition history exceeds the safety bound")
    artifact_records = _artifact_records(base, artifacts or [])
    if status == "completed":
        supplied = {item["path"] for item in artifact_records}
        missing = sorted(set(task["expected_artifacts"]) - supplied)
        if missing:
            raise ResourcePlanError(f"completed task is missing expected artifacts: {', '.join(missing)}")
        if task["resource_class"] == "llm_assistance":
            delegation = llm_assistance_status(base, task["delegation_task_id"])
            if delegation.get("status") != "COMPLETE":
                raise ResourcePlanError("LLM_ASSISTANCE_RECEIPT_REQUIRED before task completion")
    _validate_observation(revision, task, normalized_observation, status)
    note_value = " ".join(str(note or "").split()) or None
    if status in {"failed", "blocked", "unknown"} and not note_value:
        raise ResourcePlanError(f"resource_task_note is required for {status}")
    target = status.upper()
    transition = {
        "at": utc_now(), "from": current, "to": target, "note": note_value,
        "artifacts": artifact_records, "resource_observation": normalized_observation,
        "observation_source": _observation_source, "execution_receipt": execution_receipt,
    }
    transition["transition_sha256"] = digest({key: value for key, value in transition.items() if key != "transition_sha256"})
    task_state["history"].append(transition)
    task_state["status"] = target
    task_state["reason"] = note_value or {
        "RUNNING": "execution started under the admitted profile",
        "COMPLETED": "expected artifacts and declared resource observations were recorded",
    }.get(target, target.lower())
    task_state["artifacts"] = artifact_records
    task_state["resource_observation"] = normalized_observation
    task_state["observation_source"] = _observation_source
    task_state["execution_receipt"] = execution_receipt
    revision["updated_at"] = utc_now()
    _refresh_states(revision)
    revision["state_sha256"] = digest(_state_stable(revision))
    _atomic_json(_plan_path(base, plan_id), state)
    _append_audit(base, "resource_task_transition", {
        "resource_plan_id": plan_id, "revision": revision["revision"], "task_id": task_id,
        "from": current, "to": target, "transition_sha256": transition["transition_sha256"],
        "observation_source": _observation_source,
        "execution_hash": execution_receipt.get("execution_hash") if execution_receipt else None,
    })
    return _summary(revision)


def execute_resource_task(
    root: str | os.PathLike[str], *, plan_id: str, task_id: str,
    process_timeout_seconds: float = 1800.0,
) -> dict[str, Any]:
    """Execute one READY task, or reconcile its already persisted managed receipt."""
    base = project_root(root)
    plan_id = _identifier(plan_id, "resource_plan_id")
    task_id = _identifier(task_id, "resource_task_id")
    timeout = _positive_number(
        process_timeout_seconds, "process_timeout_seconds", optional=False,
    )
    state = _load_state(base, plan_id)
    revision = state["revisions"][-1]
    if revision["policy_sha256"] != _policy_hash():
        raise ResourcePlanError("RESOURCE_POLICY_CHANGED_REPLAN_REQUIRED")
    _, profiles_hash = _profiles()
    if revision["profiles_sha256"] != profiles_hash:
        raise ResourcePlanError("RESOURCE_PROFILES_CHANGED_REPLAN_REQUIRED")
    tasks = _task_map(revision)
    task = tasks.get(task_id)
    if task is None:
        raise ResourcePlanError(f"unknown resource task: {task_id}")
    current = revision["task_states"][task_id]["status"]
    if current not in {"READY", "RUNNING", "UNKNOWN"}:
        raise ResourcePlanError("only a READY task or an interrupted managed task can use execute")
    if current == "READY" and _summary(revision)["next_ready_task_ids"] != [task_id]:
        raise ResourcePlanError("task is not the next admitted serial stage")
    if task["resource_class"] != "managed_standard" or not task.get("reproducibility_run_id"):
        raise ResourcePlanError(
            "resource_plan_action=execute requires managed_standard plus reproducibility_run_id"
        )

    from research_integrity_core import IntegrityError, execute_reproducibility, integrity_status
    from resource_guard import ResourceGuardError

    reproducibility = integrity_status(base, "reproducibility", task["reproducibility_run_id"])
    if reproducibility.get("plan_hash") != task.get("reproducibility_plan_hash"):
        raise ResourcePlanError("linked reproducibility plan hash changed; replan")
    if list(reproducibility.get("outputs") or []) != task["expected_artifacts"]:
        raise ResourcePlanError("linked reproducibility outputs changed; replan")

    def finalize_result(result: dict[str, Any], *, reconciled: bool) -> dict[str, Any]:
        execution = result.get("execution") or {}
        if result.get("status") not in {"PASS", "FAILED"} or not execution:
            raise ResourcePlanError("linked reproducibility result has no final managed receipt")
        usage = execution.get("resource_usage") or {}
        receipt = {
            "owner": "research_integrity.execute_reproducibility",
            "run_id": result.get("run_id"),
            "plan_hash": result.get("plan_hash"),
            "execution_hash": execution.get("execution_hash"),
            "execution_mode": execution.get("execution_mode"),
            "reproducibility_status": result.get("status"),
        }
        observation = {
            "peak_worker_bytes": usage.get("peak_worker_bytes"),
            "peak_orchestrator_bytes": usage.get("peak_orchestrator_bytes"),
            "peak_owned_bytes": usage.get("peak_owned_bytes"),
            "disk_written_bytes": None,
            "downloaded_bytes": None,
            "duration_seconds": execution.get("duration_seconds"),
            "external_cost": None,
            "receipt_inspected": reconciled,
        }
        output_paths = [item["path"] for item in execution.get("outputs") or []]
        passed = result.get("status") == "PASS"
        completion_issue = None
        note = (
            "Recovered the already persisted managed reproducibility receipt without replay."
            if passed and reconciled else None
        )
        try:
            summary = record_resource_task(
                base, plan_id=plan_id, task_id=task_id,
                task_status="completed" if passed else "failed",
                artifacts=output_paths, observation=observation,
                note=note if passed else "Managed reproducibility checks or declared outputs failed.",
                _observation_source=(
                    "managed_reproducibility_receipt" if passed else "managed_reproducibility_failure"
                ),
                _execution_receipt=receipt,
                _managed_token=_MANAGED_TRANSITION_TOKEN,
            )
        except ResourcePlanError as exc:
            if not passed:
                raise
            completion_issue = str(exc)
            summary = record_resource_task(
                base, plan_id=plan_id, task_id=task_id, task_status="failed",
                artifacts=output_paths, observation=observation,
                note=f"Managed execution completed but resource-plan admission failed: {exc}",
                _observation_source="managed_reproducibility_failure",
                _execution_receipt=receipt,
                _managed_token=_MANAGED_TRANSITION_TOKEN,
            )
        return {
            **summary,
            "executed_task_id": task_id,
            "reproducibility_status": result.get("status"),
            "execution_receipt": _normalize_execution_receipt(receipt),
            "resource_completion_issue": completion_issue,
            "reconciled_existing_receipt": reconciled,
            "process_timeout_is_attempt_safety_bound": True,
        }

    if current in {"RUNNING", "UNKNOWN"}:
        if reproducibility.get("status") not in {"PASS", "FAILED"} or not reproducibility.get("execution"):
            raise ResourcePlanError(
                "RECEIPT_INSPECTION_REQUIRED: interrupted managed work has no final receipt; replay is forbidden"
            )
        return finalize_result(reproducibility, reconciled=True)

    if reproducibility.get("status") != "EXECUTION_REQUIRED" or reproducibility.get("execution") is not None:
        raise ResourcePlanError("linked reproducibility plan is no longer executable; replan")
    record_resource_task(
        base, plan_id=plan_id, task_id=task_id, task_status="running",
        _observation_source="managed_reproducibility_start",
        _managed_token=_MANAGED_TRANSITION_TOKEN,
    )
    try:
        result = execute_reproducibility(
            base, task["reproducibility_run_id"], timeout=float(timeout),
        )
    except ResourceGuardError as exc:
        record_resource_task(
            base, plan_id=plan_id, task_id=task_id, task_status="failed",
            note=f"Managed process guard ended the owned process tree: {exc}",
            _observation_source="managed_process_guard_failure",
            _execution_receipt=None,
            _managed_token=_MANAGED_TRANSITION_TOKEN,
        )
        raise ResourcePlanError(f"MANAGED_REPRODUCIBILITY_FAILED: {exc}") from exc
    except IntegrityError as exc:
        record_resource_task(
            base, plan_id=plan_id, task_id=task_id, task_status="unknown",
            note=f"Reproducibility execution did not return a final receipt: {exc}",
            _observation_source="managed_reproducibility_unknown",
            _managed_token=_MANAGED_TRANSITION_TOKEN,
        )
        raise ResourcePlanError(
            f"RECEIPT_INSPECTION_REQUIRED after reproducibility integrity failure: {exc}"
        ) from exc
    except Exception as exc:
        record_resource_task(
            base, plan_id=plan_id, task_id=task_id, task_status="unknown",
            note=f"Reproducibility execution ended without a final receipt: {type(exc).__name__}",
            _observation_source="managed_reproducibility_unknown",
            _managed_token=_MANAGED_TRANSITION_TOKEN,
        )
        raise ResourcePlanError(
            "RECEIPT_INSPECTION_REQUIRED after unexpected reproducibility execution failure"
        ) from exc
    return finalize_result(result, reconciled=False)


def resource_task_plan_status(root: str | os.PathLike[str], plan_id: str | None = None) -> dict[str, Any]:
    base = project_root(root)
    if plan_id:
        identifier = _identifier(plan_id, "resource_plan_id")
        state = _load_state(base, identifier)
        return _summary(state["revisions"][-1])
    directory = base / ".research-guard" / PLAN_DIRECTORY
    if not directory.is_dir():
        return {"status": "NOT_PLANNED", "plans": []}
    plans: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        if not IDENTIFIER.fullmatch(path.stem):
            continue
        state = _load_state(base, path.stem)
        summary = _summary(state["revisions"][-1])
        plans.append({key: summary[key] for key in ("resource_plan_id", "revision", "status", "plan_hash", "counts")})
    return {"status": "PASS", "plans": plans}


def verify_resource_task_plan(root: str | os.PathLike[str], plan_id: str) -> dict[str, Any]:
    base = project_root(root)
    plan_id = _identifier(plan_id, "resource_plan_id")
    try:
        state = _load_state(base, plan_id)
    except ResourcePlanError as exc:
        return {"status": "FAIL", "resource_plan_id": plan_id, "errors": [str(exc)]}
    revision = state["revisions"][-1]
    errors: list[str] = []
    warnings: list[str] = []
    tasks = _task_map(revision)
    if revision["policy_sha256"] != _policy_hash():
        errors.append("RESOURCE_POLICY_CHANGED_REPLAN_REQUIRED")
    _, profiles_hash = _profiles()
    if revision["profiles_sha256"] != profiles_hash:
        errors.append("RESOURCE_PROFILES_CHANGED_REPLAN_REQUIRED")
    for task_id, task_state in revision["task_states"].items():
        for transition in task_state.get("history", []):
            stable = {key: value for key, value in transition.items() if key != "transition_sha256"}
            if digest(stable) != transition.get("transition_sha256"):
                errors.append(f"TASK_TRANSITION_INTEGRITY_FAILURE:{task_id}")
        for artifact in task_state.get("artifacts", []):
            resolved = (base / artifact["path"]).resolve()
            try:
                resolved.relative_to(base)
            except ValueError:
                errors.append(f"ARTIFACT_PATH_ESCAPE:{task_id}:{artifact['path']}")
                continue
            if not resolved.is_file():
                errors.append(f"ARTIFACT_MISSING:{task_id}:{artifact['path']}")
            elif resolved.stat().st_size != artifact.get("bytes") or _sha256_file(resolved) != artifact.get("sha256"):
                errors.append(f"ARTIFACT_HASH_MISMATCH:{task_id}:{artifact['path']}")
        receipt = task_state.get("execution_receipt")
        if receipt is not None:
            try:
                receipt = _normalize_execution_receipt(receipt)
            except ResourcePlanError as exc:
                errors.append(f"EXECUTION_RECEIPT_INVALID:{task_id}:{exc}")
                continue
            task = tasks[task_id]
            if task.get("reproducibility_run_id") != receipt["run_id"]:
                errors.append(f"EXECUTION_RECEIPT_RUN_MISMATCH:{task_id}")
                continue
            if task.get("reproducibility_plan_hash") != receipt["plan_hash"]:
                errors.append(f"EXECUTION_RECEIPT_PLAN_MISMATCH:{task_id}")
                continue
            try:
                from research_integrity_core import IntegrityError, integrity_status
                reproducibility = integrity_status(base, "reproducibility", receipt["run_id"])
            except (IntegrityError, OSError, ValueError) as exc:
                errors.append(f"EXECUTION_RECEIPT_UNAVAILABLE:{task_id}:{exc}")
                continue
            execution = reproducibility.get("execution") or {}
            if reproducibility.get("status") != receipt["reproducibility_status"]:
                errors.append(f"EXECUTION_RECEIPT_STATUS_MISMATCH:{task_id}")
            if reproducibility.get("plan_hash") != receipt["plan_hash"]:
                errors.append(f"EXECUTION_RECEIPT_PLAN_DRIFT:{task_id}")
            if execution.get("execution_hash") != receipt["execution_hash"]:
                errors.append(f"EXECUTION_RECEIPT_HASH_MISMATCH:{task_id}")
            if execution.get("execution_mode") != "managed":
                errors.append(f"EXECUTION_RECEIPT_NOT_MANAGED:{task_id}")
            expected_artifacts = execution.get("outputs") or []
            if task_state.get("artifacts") != expected_artifacts:
                errors.append(f"EXECUTION_RECEIPT_ARTIFACT_MISMATCH:{task_id}")
            observation = task_state.get("resource_observation") or {}
            usage = execution.get("resource_usage") or {}
            for field in ("peak_worker_bytes", "peak_orchestrator_bytes", "peak_owned_bytes"):
                if observation.get(field) != usage.get(field):
                    errors.append(f"EXECUTION_RECEIPT_TELEMETRY_MISMATCH:{task_id}:{field}")
            if observation.get("duration_seconds") != execution.get("duration_seconds"):
                errors.append(f"EXECUTION_RECEIPT_TELEMETRY_MISMATCH:{task_id}:duration_seconds")
    current = inventory_resources(base)
    if current["memory"]["host_available_bytes"] < START_MIN_FREE_BYTES:
        warnings.append("RESOURCE_HEADROOM_INSUFFICIENT_NOW")
    if current["disk"]["user_available_bytes"] < revision["resource_snapshot"]["disk"]["user_available_bytes"]:
        warnings.append("PROJECT_FILESYSTEM_FREE_SPACE_DECREASED")
    summary = _summary(revision)
    return {
        "status": "PASS" if not errors else "FAIL",
        "resource_plan_id": plan_id,
        "revision": revision["revision"],
        "plan_status": summary["status"],
        "plan_hash": revision["plan_hash"],
        "state_sha256": revision["state_sha256"],
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "artifact_count": sum(len(item.get("artifacts", [])) for item in revision["task_states"].values()),
        "current_resource_snapshot_sha256": current["snapshot_sha256"],
        "volatile_snapshot_change_is_not_policy_drift": True,
    }
