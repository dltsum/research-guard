from __future__ import annotations

import datetime as dt
import json
import os
import re
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

from research_guard_core import (
    GuardError,
    declare_method_change,
    digest,
    get_gate_status,
    load_state,
    project_root,
    register_method,
    sync_tracked_method_files,
    verify_receipt,
)


DESIGN_SCHEMA_VERSION = 1
DESIGN_STATE_NAME = "research-design.json"


class DesignError(GuardError):
    pass


LENSES: dict[str, dict[str, Any]] = {
    "problem_first": {
        "prompt": "Hold the problem fixed and vary only the proposed causal or computational mechanism.",
        "keywords": ("problem", "failure", "limitation", "bottleneck", "问题", "失败", "瓶颈"),
    },
    "abstraction": {
        "prompt": "Move one level up or down the abstraction ladder and test whether the problem changes form.",
        "keywords": ("abstract", "general", "specific", "theory", "抽象", "一般化", "具体"),
    },
    "tension": {
        "prompt": "Locate a pair of desirable properties that existing work treats as a trade-off.",
        "keywords": ("tradeoff", "trade-off", "tension", "versus", "conflict", "权衡", "冲突"),
    },
    "structural_analogy": {
        "prompt": "Transfer a causal structure from another field only after mapping corresponding entities and failure modes.",
        "keywords": ("analogy", "cross-domain", "transfer", "other field", "类比", "跨领域", "迁移"),
    },
    "constraint_inversion": {
        "prompt": "Treat the strongest resource or access constraint as a design variable and invert one default assumption.",
        "keywords": ("constraint", "limited", "budget", "compute", "data scarce", "约束", "预算", "算力", "有限"),
    },
    "boundary_probe": {
        "prompt": "Probe where the claimed mechanism should stop working and turn that boundary into a discriminating test.",
        "keywords": ("boundary", "shift", "edge", "failure regime", "distribution", "边界", "分布", "失效"),
    },
    "stakeholder_rotation": {
        "prompt": "Restate success and harm from the perspective of a different affected stakeholder or scientific user.",
        "keywords": ("stakeholder", "user", "patient", "operator", "policy", "用户", "患者", "利益相关"),
    },
    "composition_decomposition": {
        "prompt": "Split the mechanism into separable components or compose two independently justified mechanisms.",
        "keywords": ("component", "module", "compose", "decompose", "pipeline", "组件", "模块", "分解", "组合"),
    },
    "adjacent_possible": {
        "prompt": "Ask which study became feasible only because of a newly available dataset, instrument, method, or policy change.",
        "keywords": ("new dataset", "new tool", "recent", "available", "instrument", "新数据", "新工具", "可用"),
    },
    "simplicity": {
        "prompt": "Search for the smallest adequate mechanism and assign a complexity budget before adding components.",
        "keywords": ("simple", "simpler", "minimal", "complex", "smallest", "简单", "最小", "复杂"),
    },
}

FALLBACK_LENSES = ("problem_first", "boundary_probe", "simplicity")
CANDIDATE_REQUIRED_FIELDS = (
    "candidate_id",
    "title",
    "problem",
    "mechanism",
    "falsifier",
    "minimum_viable_experiment",
    "differentiator",
    "feasibility",
    "lens_id",
)

STRATEGY_MODULES: dict[str, dict[str, Any]] = {
    "objective": {
        "prompt": "Define success, affected stakeholders, criteria, and whose priorities those criteria represent.",
        "keywords": ("success", "objective", "impact", "stakeholder", "成功", "目标", "影响", "利益相关"),
    },
    "assumption_risk": {
        "prompt": "Register assumptions, evidence boundaries, dependencies, early validation tests, and failure responses.",
        "keywords": ("risk", "assumption", "feasibility", "go/no-go", "风险", "假设", "可行", "验证"),
    },
    "parameter_strategy": {
        "prompt": "Mark parameters fixed, floating, or conditional and state when each choice must be reconsidered.",
        "keywords": ("parameter", "constraint", "fixed", "floating", "参数", "约束", "固定", "浮动"),
    },
    "decision_tree": {
        "prompt": "Create evidence-triggered decision nodes with criterion-bearing alternatives and no automatic branch choice.",
        "keywords": ("decision", "branch", "next step", "go/no-go", "决策", "分支", "下一步", "关卡"),
    },
    "adversity": {
        "prompt": "Connect plausible adverse events to mitigations, residual risk, and an existing fallback branch.",
        "keywords": ("adversity", "crisis", "failure", "fallback", "逆境", "危机", "失败", "应急"),
    },
    "inversion": {
        "prompt": "Invert one real constraint, goal, or observed answer and connect the alternative to a decision branch.",
        "keywords": ("invert", "reframe", "stuck", "alternative", "反转", "重新定框", "卡住", "替代"),
    },
}

STRATEGY_FALLBACK_MODULES = ("objective", "assumption_risk", "decision_tree")
AUTOMATIC_CHOICE_FIELDS = {
    "winner", "ranking", "rank", "score", "recommended_branch", "best_option", "automatic_choice", "auto_decision",
}
AUTOMATIC_CHOICE_KEY_SIGNATURES = {
    re.sub(r"[^a-z0-9]", "", field.casefold()) for field in AUTOMATIC_CHOICE_FIELDS
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def design_state_path(root: str | os.PathLike[str]) -> Path:
    return project_root(root) / ".research-guard" / DESIGN_STATE_NAME


def _atomic_json(path: Path, value: Any) -> None:
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


def _append_design_audit(root: Path, event: str, details: dict[str, Any]) -> None:
    path = root / ".research-guard" / "research-design-audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"at": utc_now(), "event": event, "details": details}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def _load_design(root: str | os.PathLike[str], *, required: bool = True) -> dict[str, Any] | None:
    path = design_state_path(root)
    if not path.exists():
        if required:
            raise DesignError("No research-design state; run plan_ideation first")
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DesignError(f"Unreadable research-design state: {exc}") from exc
    if state.get("schema_version") != DESIGN_SCHEMA_VERSION:
        raise DesignError("Unsupported research-design state schema")
    _verify_design_integrity(state)
    return state


def _verify_design_integrity(state: dict[str, Any]) -> None:
    plan = state.get("plan")
    if not isinstance(plan, dict):
        raise DesignError("research-design integrity failure: plan is missing")
    stable_plan = {
        "request_text": plan.get("request_text"),
        "problem_anchor": plan.get("problem_anchor"),
        "constraints": plan.get("constraints"),
        "selected_lens_ids": plan.get("selected_lens_ids"),
        "effort_cap": plan.get("effort_cap"),
    }
    if digest(stable_plan) != plan.get("plan_hash"):
        raise DesignError("research-design integrity failure: plan hash mismatch")
    candidates = state.get("candidates")
    if not isinstance(candidates, list):
        raise DesignError("research-design integrity failure: candidates must be an array")
    if state.get("candidates_hash") is not None:
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise DesignError("research-design integrity failure: candidate must be an object")
            saved = candidate.get("candidate_hash")
            unsigned = {key: value for key, value in candidate.items() if key != "candidate_hash"}
            if saved != digest(unsigned):
                raise DesignError("research-design integrity failure: candidate hash mismatch")
        if digest(candidates) != state.get("candidates_hash"):
            raise DesignError("research-design integrity failure: candidate set hash mismatch")
    committed = state.get("committed_candidate")
    if committed:
        candidate = next((item for item in candidates if item.get("candidate_id") == committed.get("candidate_id")), None)
        if candidate is None or candidate.get("candidate_hash") != committed.get("candidate_hash"):
            raise DesignError("research-design integrity failure: committed candidate binding mismatch")
    hypothesis = state.get("hypothesis")
    if hypothesis:
        expected = digest({"method_hash": hypothesis.get("method_hash"), "hypothesis": hypothesis.get("hypothesis")})
        if expected != hypothesis.get("hypothesis_hash"):
            raise DesignError("research-design integrity failure: hypothesis hash mismatch")
    experiment = state.get("experiment")
    if experiment:
        expected = digest({
            "method_hash": experiment.get("method_hash"),
            "hypothesis_hash": experiment.get("hypothesis_hash"),
            "experiment": experiment.get("experiment"),
        })
        if expected != experiment.get("experiment_hash"):
            raise DesignError("research-design integrity failure: experiment hash mismatch")
    strategy_plan = state.get("strategy_plan")
    if strategy_plan:
        stable_strategy_plan = {
            "request_text": strategy_plan.get("request_text"),
            "method_hash": strategy_plan.get("method_hash"),
            "candidate_hash": strategy_plan.get("candidate_hash"),
            "selected_module_ids": strategy_plan.get("selected_module_ids"),
            "effort_cap": strategy_plan.get("effort_cap"),
        }
        if digest(stable_strategy_plan) != strategy_plan.get("strategy_plan_hash"):
            raise DesignError("research-design integrity failure: strategy plan hash mismatch")
    strategy = state.get("strategy")
    if strategy:
        expected = digest({
            "strategy_plan_hash": strategy.get("strategy_plan_hash"),
            "method_hash": strategy.get("method_hash"),
            "candidate_hash": strategy.get("candidate_hash"),
            "strategy": strategy.get("strategy"),
        })
        if expected != strategy.get("strategy_hash"):
            raise DesignError("research-design integrity failure: strategy hash mismatch")
    decisions = state.get("strategy_decisions", [])
    if not isinstance(decisions, list):
        raise DesignError("research-design integrity failure: strategy decisions must be an array")
    if decisions and not strategy:
        raise DesignError("research-design integrity failure: strategy decisions have no strategy")
    for decision in decisions:
        stable_decision = {
            "strategy_hash": decision.get("strategy_hash"),
            "decision_id": decision.get("decision_id"),
            "branch_id": decision.get("branch_id"),
            "selected_by": decision.get("selected_by"),
            "rationale": decision.get("rationale"),
            "changes_method": decision.get("changes_method"),
        }
        if (
            decision.get("strategy_hash") != strategy.get("strategy_hash")
            or decision.get("selected_by") != "user"
            or digest(stable_decision) != decision.get("decision_hash")
        ):
            raise DesignError("research-design integrity failure: strategy decision hash mismatch")


def _save_design(root: str | os.PathLike[str], state: dict[str, Any]) -> None:
    _atomic_json(design_state_path(root), state)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise DesignError(f"{field} must be a string")
    normalized = " ".join(str(value or "").split())
    if not normalized:
        raise DesignError(f"{field} is required")
    return normalized


def _strings(value: Any, field: str, *, required: bool = False) -> list[str]:
    if value is None:
        values: list[Any] = []
    elif isinstance(value, list):
        values = value
    else:
        raise DesignError(f"{field} must be a list")
    normalized = [" ".join(str(item).split()) for item in values if " ".join(str(item).split())]
    if required and not normalized:
        raise DesignError(f"{field} requires at least one item")
    return normalized


def _https_literature(items: Any, field: str) -> list[dict[str, Any]]:
    if items is None:
        return []
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise DesignError(f"{field} must be a list of literature objects")
    output = []
    for index, item in enumerate(items):
        title = _text(item.get("title"), f"{field}[{index}].title")
        url = _text(item.get("url"), f"{field}[{index}].url")
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise DesignError(f"{field}[{index}] requires a clickable HTTPS URL")
        record = {"title": title, "url": url}
        for key in ("doi", "year", "venue", "authors", "source_id", "support_note"):
            if item.get(key) not in (None, "", []):
                record[key] = item[key]
        output.append(record)
    return output


def _objects(value: Any, field: str, *, required: bool = False) -> list[dict[str, Any]]:
    if value is None:
        items: list[Any] = []
    elif isinstance(value, list):
        items = value
    else:
        raise DesignError(f"{field} must be a list")
    if not all(isinstance(item, dict) for item in items):
        raise DesignError(f"{field} must contain only objects")
    if required and not items:
        raise DesignError(f"{field} requires at least one item")
    return items


def _reject_automatic_choice(value: Any, field: str) -> None:
    if isinstance(value, dict):
        forbidden = sorted(
            str(key) for key in value
            if re.sub(r"[^a-z0-9]", "", str(key).casefold()) in AUTOMATIC_CHOICE_KEY_SIGNATURES
        )
        if forbidden:
            raise DesignError(f"{field} contains automatic-choice fields: {', '.join(forbidden)}")
        for key, item in value.items():
            _reject_automatic_choice(item, f"{field}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_automatic_choice(item, f"{field}[{index}]")


def _acyclic(edges: dict[str, set[str]], field: str) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise DesignError(f"{field} contains a cycle")
        if node in visited:
            return
        visiting.add(node)
        for target in edges.get(node, set()):
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in edges:
        visit(node)


def _mechanical_signature(title: str, mechanism: str) -> str:
    return re.sub(r"[^\w]+", "", f"{title} {mechanism}".casefold(), flags=re.UNICODE)


def _selected_lenses(text: str) -> list[dict[str, str]]:
    lowered = text.casefold()
    scores = {
        lens_id: sum(1 for keyword in spec["keywords"] if keyword.casefold() in lowered)
        for lens_id, spec in LENSES.items()
    }
    ranked = sorted(LENSES, key=lambda lens_id: (-scores[lens_id], list(LENSES).index(lens_id)))
    selected = [lens_id for lens_id in ranked if scores[lens_id] > 0][:3]
    for lens_id in FALLBACK_LENSES:
        if len(selected) >= 3:
            break
        if lens_id not in selected:
            selected.append(lens_id)
    return [
        {"lens_id": lens_id, "prompt": str(LENSES[lens_id]["prompt"]), "match_score": scores[lens_id]}
        for lens_id in selected[:3]
    ]


def _selected_strategy_modules(text: str) -> list[dict[str, str]]:
    lowered = text.casefold()
    scores = {
        module_id: sum(1 for keyword in spec["keywords"] if keyword.casefold() in lowered)
        for module_id, spec in STRATEGY_MODULES.items()
    }
    order = list(STRATEGY_MODULES)
    ranked = sorted(order, key=lambda module_id: (-scores[module_id], order.index(module_id)))
    selected = [module_id for module_id in ranked if scores[module_id] > 0][:3]
    for module_id in STRATEGY_FALLBACK_MODULES:
        if len(selected) >= 3:
            break
        if module_id not in selected:
            selected.append(module_id)
    return [
        {
            "module_id": module_id,
            "prompt": str(STRATEGY_MODULES[module_id]["prompt"]),
            "match_score": scores[module_id],
        }
        for module_id in selected[:3]
    ]


def plan_ideation(
    root: str | os.PathLike[str], *, request_text: str, problem: str, constraints: list[str] | None = None,
) -> dict[str, Any]:
    base = project_root(root)
    request = _text(request_text, "request_text")
    anchor = _text(problem, "problem")
    normalized_constraints = _strings(constraints, "constraints")
    lenses = _selected_lenses(" ".join([request, anchor, *normalized_constraints]))
    stable = {
        "request_text": request,
        "problem_anchor": anchor,
        "constraints": normalized_constraints,
        "selected_lens_ids": [item["lens_id"] for item in lenses],
        "effort_cap": "high",
    }
    plan_hash = digest(stable)
    existing = _load_design(base, required=False)
    if existing and existing.get("plan", {}).get("plan_hash") == plan_hash:
        return existing["plan"]
    plan = {
        **stable,
        "selected_lenses": lenses,
        "plan_hash": plan_hash,
        "planned_at": utc_now(),
        "human_selection_required": True,
        "automatic_scientific_ranking": False,
    }
    state = {
        "schema_version": DESIGN_SCHEMA_VERSION,
        "project_root": str(base),
        "plan": plan,
        "candidates": [],
        "candidates_hash": None,
        "duplicates": [],
        "committed_candidate": None,
        "hypothesis": None,
        "experiment": None,
        "strategy_plan": None,
        "strategy": None,
        "strategy_decisions": [],
    }
    _save_design(base, state)
    _append_design_audit(base, "ideation_planned", {"plan_hash": plan_hash, "lens_ids": stable["selected_lens_ids"]})
    return plan


def _normalize_candidate(item: Any, selected_lens_ids: set[str], index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise DesignError(f"candidates[{index}] must be an object")
    forbidden = sorted({"rank", "ranking", "score", "winner", "selected"} & set(item))
    if forbidden:
        raise DesignError(f"candidates[{index}] contains automatic-ranking fields: {', '.join(forbidden)}")
    normalized = {field: _text(item.get(field), f"candidates[{index}].{field}") for field in CANDIDATE_REQUIRED_FIELDS}
    if normalized["lens_id"] not in selected_lens_ids:
        raise DesignError(f"candidates[{index}].lens_id was not selected by the active ideation plan")
    normalized["prior_work"] = _https_literature(item.get("prior_work"), f"candidates[{index}].prior_work")
    for key in ("assumptions", "boundary_conditions", "uncertainties"):
        values = _strings(item.get(key), f"candidates[{index}].{key}")
        if values:
            normalized[key] = values
    normalized["candidate_hash"] = digest(normalized)
    return normalized


def register_candidates(
    root: str | os.PathLike[str], *, plan_hash: str, candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_design(base)
    if str(plan_hash) != state["plan"]["plan_hash"]:
        raise DesignError("plan_hash is stale or does not match the active ideation plan")
    if not isinstance(candidates, list) or not candidates:
        raise DesignError("candidates requires at least one candidate object")
    if len(candidates) > 50:
        raise DesignError("candidates is bounded to 50 records per registration")
    lens_ids = set(state["plan"]["selected_lens_ids"])
    normalized: list[dict[str, Any]] = []
    duplicates: list[dict[str, str]] = []
    ids: set[str] = set()
    signatures: dict[str, str] = {}
    for index, raw in enumerate(candidates):
        item = _normalize_candidate(raw, lens_ids, index)
        candidate_id = item["candidate_id"]
        if candidate_id in ids:
            raise DesignError(f"Duplicate candidate_id: {candidate_id}")
        ids.add(candidate_id)
        signature = _mechanical_signature(item["title"], item["mechanism"])
        if signature in signatures:
            duplicates.append({"duplicate_id": candidate_id, "kept_id": signatures[signature]})
            continue
        signatures[signature] = candidate_id
        normalized.append(item)
    candidates_hash = digest(normalized)
    changed = candidates_hash != state.get("candidates_hash")
    if changed:
        state.update({
            "candidates": normalized,
            "candidates_hash": candidates_hash,
            "duplicates": duplicates,
            "committed_candidate": None,
            "hypothesis": None,
            "experiment": None,
            "strategy_plan": None,
            "strategy": None,
            "strategy_decisions": [],
        })
        _save_design(base, state)
        _append_design_audit(base, "candidates_registered", {
            "plan_hash": plan_hash,
            "candidates_hash": candidates_hash,
            "candidate_ids": [item["candidate_id"] for item in normalized],
            "duplicate_ids": [item["duplicate_id"] for item in duplicates],
        })
    return {
        "changed": changed,
        "plan_hash": plan_hash,
        "candidates_hash": candidates_hash,
        "candidates": normalized,
        "duplicates": duplicates,
        "human_selection_required": True,
        "automatic_scientific_ranking": False,
    }


def _candidate_by_id(state: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    normalized_id = _text(candidate_id, "candidate_id")
    for candidate in state.get("candidates", []):
        if candidate.get("candidate_id") == normalized_id:
            return candidate
    raise DesignError(f"Unknown candidate: {normalized_id}")


def commit_candidate(
    root: str | os.PathLike[str], *, candidate_id: str, selected_by: str, method: dict[str, Any],
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_design(base)
    if str(selected_by).strip().lower() != "user":
        raise DesignError("selected_by must be 'user'; the system cannot choose the scientific candidate")
    candidate = _candidate_by_id(state, candidate_id)
    if not isinstance(method, dict):
        raise DesignError("method must be an object")
    bound_method = dict(method)
    for field in ("title", "problem", "mechanism"):
        supplied = _text(bound_method.get(field), f"method.{field}")
        if supplied != candidate[field]:
            raise DesignError(f"method.{field} must match the explicitly selected candidate")
        bound_method[field] = supplied
    reserved = {
        "design_candidate_id": candidate["candidate_id"],
        "design_candidate_hash": candidate["candidate_hash"],
    }
    for field, expected in reserved.items():
        if field in bound_method and bound_method[field] != expected:
            raise DesignError(f"method.{field} conflicts with the selected candidate binding")
        bound_method[field] = expected
    registration = register_method(base, bound_method)
    method_state = registration["state"]["active_method"]
    previous_hash = (state.get("committed_candidate") or {}).get("method_hash")
    committed = {
        "candidate_id": candidate["candidate_id"],
        "candidate_hash": candidate["candidate_hash"],
        "method_hash": method_state["hash"],
        "method_version": method_state["version"],
        "selected_by": "user",
        "committed_at": utc_now(),
    }
    state["committed_candidate"] = committed
    if previous_hash != method_state["hash"]:
        state["hypothesis"] = None
        state["experiment"] = None
        state["strategy_plan"] = None
        state["strategy"] = None
        state["strategy_decisions"] = []
    _save_design(base, state)
    _append_design_audit(base, "candidate_committed", {
        "candidate_id": candidate["candidate_id"],
        "candidate_hash": candidate["candidate_hash"],
        "method_hash": method_state["hash"],
        "method_version": method_state["version"],
        "method_changed": bool(registration["changed"]),
    })
    return {
        "changed": bool(registration["changed"]),
        **committed,
        "gate": registration["state"]["gate"],
        "next_action": "Run the complete collision search for this method version before treating the design as execution-ready.",
    }


def plan_strategy(root: str | os.PathLike[str], *, request_text: str) -> dict[str, Any]:
    base = project_root(root)
    state = _load_design(base)
    committed, _ = _require_current_commit(base, state)
    request = _text(request_text, "request_text")
    modules = _selected_strategy_modules(request)
    stable = {
        "request_text": request,
        "method_hash": committed["method_hash"],
        "candidate_hash": committed["candidate_hash"],
        "selected_module_ids": [item["module_id"] for item in modules],
        "effort_cap": "high",
    }
    plan_hash = digest(stable)
    existing = state.get("strategy_plan")
    if existing and existing.get("strategy_plan_hash") == plan_hash:
        return existing
    plan = {
        **stable,
        "selected_modules": modules,
        "strategy_plan_hash": plan_hash,
        "planned_at": utc_now(),
        "human_decision_required": True,
        "automatic_scientific_ranking": False,
    }
    state["strategy_plan"] = plan
    state["strategy"] = None
    state["strategy_decisions"] = []
    state["experiment"] = None
    _save_design(base, state)
    _append_design_audit(base, "strategy_planned", {
        "strategy_plan_hash": plan_hash,
        "method_hash": committed["method_hash"],
        "module_ids": stable["selected_module_ids"],
    })
    return plan


def _normalize_objective(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DesignError("strategy.objective must be an object")
    criteria: list[dict[str, str]] = []
    criterion_ids: set[str] = set()
    for index, item in enumerate(_objects(value.get("criteria"), "strategy.objective.criteria", required=True)):
        record = {
            field: _text(item.get(field), f"strategy.objective.criteria[{index}].{field}")
            for field in ("criterion_id", "name", "definition", "priority", "priority_source")
        }
        if record["priority_source"].casefold() != "user":
            raise DesignError(f"strategy.objective.criteria[{index}].priority_source must be user")
        record["priority_source"] = "user"
        if record["criterion_id"] in criterion_ids:
            raise DesignError(f"Duplicate criterion_id: {record['criterion_id']}")
        criterion_ids.add(record["criterion_id"])
        criteria.append(record)
    return {
        "framework": _text(value.get("framework"), "strategy.objective.framework"),
        "success_definition": _text(value.get("success_definition"), "strategy.objective.success_definition"),
        "stakeholders": _strings(value.get("stakeholders"), "strategy.objective.stakeholders", required=True),
        "time_horizon": _text(value.get("time_horizon"), "strategy.objective.time_horizon"),
        "criteria": criteria,
        "literature_benchmarks": _https_literature(
            value.get("literature_benchmarks"), "strategy.objective.literature_benchmarks",
        ),
    }


def _normalize_assumptions(value: Any) -> list[dict[str, Any]]:
    assumptions: list[dict[str, Any]] = []
    ids: set[str] = set()
    allowed_types = {"empirical", "technical", "measurement", "analysis", "operational", "resource", "governance", "other"}
    allowed_statuses = {"untested", "user_estimate", "evidence_supported", "contradicted", "inconclusive"}
    for index, item in enumerate(_objects(value, "strategy.assumptions", required=True)):
        assumption_id = _text(item.get("assumption_id"), f"strategy.assumptions[{index}].assumption_id")
        if assumption_id in ids:
            raise DesignError(f"Duplicate assumption_id: {assumption_id}")
        ids.add(assumption_id)
        kind = _text(item.get("type"), f"strategy.assumptions[{index}].type").lower()
        if kind not in allowed_types:
            raise DesignError(f"strategy.assumptions[{index}].type is unsupported")
        epistemic_status = _text(
            item.get("epistemic_status"), f"strategy.assumptions[{index}].epistemic_status",
        ).lower()
        if epistemic_status not in allowed_statuses:
            raise DesignError(f"strategy.assumptions[{index}].epistemic_status is unsupported")
        evidence = _https_literature(item.get("evidence_items"), f"strategy.assumptions[{index}].evidence_items")
        if epistemic_status == "evidence_supported" and not evidence:
            raise DesignError(f"strategy.assumptions[{index}] marked evidence_supported requires evidence_items")
        record: dict[str, Any] = {
            "assumption_id": assumption_id,
            "type": kind,
            "statement": _text(item.get("statement"), f"strategy.assumptions[{index}].statement"),
            "epistemic_status": epistemic_status,
            "evidence_items": evidence,
            "validation_test": _text(item.get("validation_test"), f"strategy.assumptions[{index}].validation_test"),
            "pass_criterion": _text(item.get("pass_criterion"), f"strategy.assumptions[{index}].pass_criterion"),
            "failure_response": _text(item.get("failure_response"), f"strategy.assumptions[{index}].failure_response"),
            "depends_on": _strings(item.get("depends_on"), f"strategy.assumptions[{index}].depends_on"),
        }
        likelihood = item.get("likelihood")
        if likelihood is not None:
            if not isinstance(likelihood, dict):
                raise DesignError(f"strategy.assumptions[{index}].likelihood must be an object")
            selected_by = _text(
                likelihood.get("selected_by"), f"strategy.assumptions[{index}].likelihood.selected_by",
            ).lower()
            if selected_by != "user":
                raise DesignError(f"strategy.assumptions[{index}].likelihood.selected_by must be user")
            record["likelihood"] = {
                "label": _text(likelihood.get("label"), f"strategy.assumptions[{index}].likelihood.label"),
                "selected_by": "user",
                "rationale": _text(likelihood.get("rationale"), f"strategy.assumptions[{index}].likelihood.rationale"),
            }
        assumptions.append(record)
    for item in assumptions:
        unknown = sorted(set(item["depends_on"]) - ids)
        if unknown:
            raise DesignError(f"assumption {item['assumption_id']} references unknown dependencies: {', '.join(unknown)}")
    _acyclic({item["assumption_id"]: set(item["depends_on"]) for item in assumptions}, "assumption dependencies")
    return assumptions


def _normalize_parameters(value: Any) -> list[dict[str, str]]:
    parameters: list[dict[str, str]] = []
    ids: set[str] = set()
    for index, item in enumerate(_objects(value, "strategy.parameters", required=True)):
        record = {
            field: _text(item.get(field), f"strategy.parameters[{index}].{field}")
            for field in ("parameter_id", "category", "value", "status", "rationale", "reconsider_when", "set_by")
        }
        record["status"] = record["status"].lower()
        if record["status"] not in {"fixed", "floating", "conditional"}:
            raise DesignError(f"strategy.parameters[{index}].status is unsupported")
        if record["set_by"].casefold() != "user":
            raise DesignError(f"strategy.parameters[{index}].set_by must be user")
        record["set_by"] = "user"
        if record["parameter_id"] in ids:
            raise DesignError(f"Duplicate parameter_id: {record['parameter_id']}")
        ids.add(record["parameter_id"])
        parameters.append(record)
    return parameters


def _normalize_decisions(
    value: Any, assumption_ids: set[str], parameter_ids: set[str],
) -> tuple[list[dict[str, Any]], set[str]]:
    decisions: list[dict[str, Any]] = []
    decision_ids: set[str] = set()
    branch_ids: set[str] = set()
    for index, item in enumerate(_objects(value, "strategy.decisions", required=True)):
        decision_id = _text(item.get("decision_id"), f"strategy.decisions[{index}].decision_id")
        if decision_id in decision_ids:
            raise DesignError(f"Duplicate decision_id: {decision_id}")
        decision_ids.add(decision_id)
        raw_required = item.get("requires_current_choice")
        if not isinstance(raw_required, bool):
            raise DesignError(f"strategy.decisions[{index}].requires_current_choice must be boolean")
        raw_branches = _objects(item.get("branches"), f"strategy.decisions[{index}].branches", required=True)
        if len(raw_branches) < 2:
            raise DesignError(f"strategy.decisions[{index}] requires at least two branches")
        branches: list[dict[str, Any]] = []
        for branch_index, branch in enumerate(raw_branches):
            record: dict[str, Any] = {
                field: _text(
                    branch.get(field), f"strategy.decisions[{index}].branches[{branch_index}].{field}",
                )
                for field in ("branch_id", "label", "condition", "action")
            }
            if record["branch_id"] in branch_ids:
                raise DesignError(f"Duplicate branch_id: {record['branch_id']}")
            branch_ids.add(record["branch_id"])
            if not isinstance(branch.get("changes_method"), bool):
                raise DesignError(
                    f"strategy.decisions[{index}].branches[{branch_index}].changes_method must be boolean"
                )
            record["changes_method"] = branch["changes_method"]
            record["assumption_ids"] = _strings(
                branch.get("assumption_ids"),
                f"strategy.decisions[{index}].branches[{branch_index}].assumption_ids",
            )
            record["parameter_ids"] = _strings(
                branch.get("parameter_ids"),
                f"strategy.decisions[{index}].branches[{branch_index}].parameter_ids",
            )
            unknown_assumptions = sorted(set(record["assumption_ids"]) - assumption_ids)
            unknown_parameters = sorted(set(record["parameter_ids"]) - parameter_ids)
            if unknown_assumptions:
                raise DesignError(f"branch {record['branch_id']} references unknown assumptions: {', '.join(unknown_assumptions)}")
            if unknown_parameters:
                raise DesignError(f"branch {record['branch_id']} references unknown parameters: {', '.join(unknown_parameters)}")
            if branch.get("next_decision_id") not in (None, ""):
                record["next_decision_id"] = _text(
                    branch.get("next_decision_id"),
                    f"strategy.decisions[{index}].branches[{branch_index}].next_decision_id",
                )
            branches.append(record)
        decisions.append({
            "decision_id": decision_id,
            "question": _text(item.get("question"), f"strategy.decisions[{index}].question"),
            "trigger": _text(item.get("trigger"), f"strategy.decisions[{index}].trigger"),
            "evidence_needed": _strings(
                item.get("evidence_needed"), f"strategy.decisions[{index}].evidence_needed", required=True,
            ),
            "requires_current_choice": raw_required,
            "branches": branches,
        })
    edges: dict[str, set[str]] = {}
    for decision in decisions:
        targets = {branch["next_decision_id"] for branch in decision["branches"] if branch.get("next_decision_id")}
        unknown = sorted(targets - decision_ids)
        if unknown:
            raise DesignError(f"decision {decision['decision_id']} references unknown next decision: {', '.join(unknown)}")
        edges[decision["decision_id"]] = targets
    _acyclic(edges, "strategy decision graph")
    return decisions, branch_ids


def _normalize_adversities(value: Any, assumption_ids: set[str], branch_ids: set[str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, item in enumerate(_objects(value, "strategy.adversities")):
        scenario_id = _text(item.get("scenario_id"), f"strategy.adversities[{index}].scenario_id")
        if scenario_id in ids:
            raise DesignError(f"Duplicate scenario_id: {scenario_id}")
        ids.add(scenario_id)
        linked_assumptions = _strings(
            item.get("assumption_ids"), f"strategy.adversities[{index}].assumption_ids", required=True,
        )
        unknown = sorted(set(linked_assumptions) - assumption_ids)
        if unknown:
            raise DesignError(f"adversity {scenario_id} references unknown assumptions: {', '.join(unknown)}")
        fallback = _text(item.get("fallback_branch_id"), f"strategy.adversities[{index}].fallback_branch_id")
        if fallback not in branch_ids:
            raise DesignError(f"strategy.adversities[{index}].fallback_branch_id is unknown")
        output.append({
            "scenario_id": scenario_id,
            "trigger": _text(item.get("trigger"), f"strategy.adversities[{index}].trigger"),
            "assumption_ids": linked_assumptions,
            "mitigation": _text(item.get("mitigation"), f"strategy.adversities[{index}].mitigation"),
            "residual_risk": _text(item.get("residual_risk"), f"strategy.adversities[{index}].residual_risk"),
            "fallback_branch_id": fallback,
        })
    return output


def _normalize_inversions(value: Any, parameter_ids: set[str], branch_ids: set[str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, item in enumerate(_objects(value, "strategy.inversions")):
        inversion_id = _text(item.get("inversion_id"), f"strategy.inversions[{index}].inversion_id")
        if inversion_id in ids:
            raise DesignError(f"Duplicate inversion_id: {inversion_id}")
        ids.add(inversion_id)
        linked_parameters = _strings(
            item.get("parameter_ids"), f"strategy.inversions[{index}].parameter_ids", required=True,
        )
        unknown = sorted(set(linked_parameters) - parameter_ids)
        if unknown:
            raise DesignError(f"inversion {inversion_id} references unknown parameter IDs: {', '.join(unknown)}")
        branch_id = _text(item.get("branch_id"), f"strategy.inversions[{index}].branch_id")
        if branch_id not in branch_ids:
            raise DesignError(f"strategy.inversions[{index}].branch_id is unknown")
        output.append({
            "inversion_id": inversion_id,
            "kind": _text(item.get("kind"), f"strategy.inversions[{index}].kind"),
            "current_constraint": _text(
                item.get("current_constraint"), f"strategy.inversions[{index}].current_constraint",
            ),
            "parameter_ids": linked_parameters,
            "alternative_question_or_goal": _text(
                item.get("alternative_question_or_goal"),
                f"strategy.inversions[{index}].alternative_question_or_goal",
            ),
            "evidence_needed": _text(item.get("evidence_needed"), f"strategy.inversions[{index}].evidence_needed"),
            "branch_id": branch_id,
        })
    return output


def register_strategy(
    root: str | os.PathLike[str], *, strategy_plan_hash: str, strategy: dict[str, Any],
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_design(base)
    committed, _ = _require_current_commit(base, state)
    plan = state.get("strategy_plan")
    if not plan:
        raise DesignError("A current strategy plan is required; run plan_strategy first")
    if str(strategy_plan_hash) != plan.get("strategy_plan_hash"):
        raise DesignError("strategy_plan_hash is stale or does not match the active strategy plan")
    if plan.get("method_hash") != committed.get("method_hash"):
        raise DesignError("The strategy plan is stale relative to the committed method")
    if not isinstance(strategy, dict):
        raise DesignError("strategy must be an object")
    _reject_automatic_choice(strategy, "strategy")
    if _text(strategy.get("defined_by"), "strategy.defined_by").lower() != "user":
        raise DesignError("strategy.defined_by must be user")
    assumptions = _normalize_assumptions(strategy.get("assumptions"))
    parameters = _normalize_parameters(strategy.get("parameters"))
    assumption_ids = {item["assumption_id"] for item in assumptions}
    parameter_ids = {item["parameter_id"] for item in parameters}
    decisions, branch_ids = _normalize_decisions(strategy.get("decisions"), assumption_ids, parameter_ids)
    normalized = {
        "defined_by": "user",
        "objective": _normalize_objective(strategy.get("objective")),
        "assumptions": assumptions,
        "parameters": parameters,
        "decisions": decisions,
        "adversities": _normalize_adversities(strategy.get("adversities"), assumption_ids, branch_ids),
        "inversions": _normalize_inversions(strategy.get("inversions"), parameter_ids, branch_ids),
    }
    strategy_hash = digest({
        "strategy_plan_hash": plan["strategy_plan_hash"],
        "method_hash": committed["method_hash"],
        "candidate_hash": committed["candidate_hash"],
        "strategy": normalized,
    })
    previous_hash = (state.get("strategy") or {}).get("strategy_hash")
    record = {
        "strategy_plan_hash": plan["strategy_plan_hash"],
        "method_hash": committed["method_hash"],
        "candidate_hash": committed["candidate_hash"],
        "strategy_hash": strategy_hash,
        "registered_at": utc_now(),
        "strategy": normalized,
    }
    state["strategy"] = record
    if previous_hash != strategy_hash:
        state["strategy_decisions"] = []
        state["experiment"] = None
    _save_design(base, state)
    _append_design_audit(base, "strategy_registered", {
        "strategy_plan_hash": plan["strategy_plan_hash"],
        "strategy_hash": strategy_hash,
        "method_hash": committed["method_hash"],
        "changed": previous_hash != strategy_hash,
    })
    return {
        "changed": previous_hash != strategy_hash,
        **record,
        "automatic_selection": False,
        "human_decision_required": True,
    }


def decide_strategy_branch(
    root: str | os.PathLike[str], *, decision_id: str, branch_id: str,
    selected_by: str, rationale: str,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_design(base)
    committed, _ = _require_current_commit(base, state)
    record = state.get("strategy")
    if not record or record.get("method_hash") != committed.get("method_hash"):
        raise DesignError("A current strategy contract is required before selecting a branch")
    if str(selected_by).strip().lower() != "user":
        raise DesignError("selected_by must be 'user'; the system cannot choose a strategy branch")
    normalized_decision_id = _text(decision_id, "decision_id")
    normalized_branch_id = _text(branch_id, "branch_id")
    normalized_rationale = _text(rationale, "rationale")
    if len(normalized_rationale) < 40:
        raise DesignError("rationale requires at least 40 characters")
    decision = next(
        (item for item in record["strategy"]["decisions"] if item["decision_id"] == normalized_decision_id), None,
    )
    if decision is None:
        raise DesignError(f"Unknown strategy decision: {normalized_decision_id}")
    branch = next(
        (item for item in decision["branches"] if item["branch_id"] == normalized_branch_id), None,
    )
    if branch is None:
        raise DesignError(f"Unknown branch {normalized_branch_id} for decision {normalized_decision_id}")
    stable = {
        "strategy_hash": record["strategy_hash"],
        "decision_id": normalized_decision_id,
        "branch_id": normalized_branch_id,
        "selected_by": "user",
        "rationale": normalized_rationale,
        "changes_method": branch["changes_method"],
    }
    decision_record = {**stable, "decision_hash": digest(stable), "decided_at": utc_now()}
    invalidation = None
    if branch["changes_method"]:
        invalidation = declare_method_change(
            base,
            f"User selected method-changing strategy branch {normalized_decision_id}/{normalized_branch_id}: "
            f"{branch['action']} Rationale: {normalized_rationale}",
        )
    existing = [
        item for item in state.get("strategy_decisions", [])
        if item.get("decision_id") != normalized_decision_id
    ]
    state["strategy_decisions"] = [*existing, decision_record]
    _save_design(base, state)
    _append_design_audit(base, "strategy_branch_decided", {
        "strategy_hash": record["strategy_hash"],
        "decision_id": normalized_decision_id,
        "branch_id": normalized_branch_id,
        "changes_method": branch["changes_method"],
    })
    return {
        **decision_record,
        "branch": branch,
        "method_change_invalidation": invalidation,
        "next_action": (
            "Register the complete adjusted method, then rerun the collision search."
            if branch["changes_method"]
            else "Continue only within the selected branch and current method contract."
        ),
    }


def _require_current_commit(base: Path, state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    committed = state.get("committed_candidate")
    if not committed:
        raise DesignError("An explicitly user-selected candidate must be committed before this action")
    tracked = sync_tracked_method_files(base)
    if tracked.get("requires_registration"):
        raise DesignError("A tracked method file changed; register the complete adjusted method before continuing")
    method_state = load_state(base, required=False)
    if (method_state or {}).get("pending_method_change"):
        raise DesignError("A user-declared method adjustment is pending; register the complete adjusted method before continuing")
    active = (method_state or {}).get("active_method", {})
    if active.get("hash") != committed.get("method_hash"):
        raise DesignError("The committed candidate is stale relative to the active method")
    return committed, method_state


def _normalize_observation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DesignError("observation must be an object")
    result = {
        "statement": _text(value.get("statement"), "observation.statement"),
        "provenance": _text(value.get("provenance"), "observation.provenance"),
    }
    for field in ("source_ids", "uncertainties"):
        items = _strings(value.get(field), f"observation.{field}")
        if items:
            result[field] = items
    return result


def _normalize_rivals(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise DesignError("hypothesis requires at least one rival explanation")
    output = []
    ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DesignError(f"rivals[{index}] must be an object")
        rival = {
            "rival_id": _text(item.get("rival_id"), f"rivals[{index}].rival_id"),
            "statement": _text(item.get("statement"), f"rivals[{index}].statement"),
            "mechanism": _text(item.get("mechanism"), f"rivals[{index}].mechanism"),
        }
        if rival["rival_id"] in ids:
            raise DesignError(f"Duplicate rival_id: {rival['rival_id']}")
        ids.add(rival["rival_id"])
        output.append(rival)
    return output


def _normalize_predictions(value: Any, rival_ids: set[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise DesignError("hypothesis requires at least one discriminating prediction")
    output = []
    ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DesignError(f"predictions[{index}] must be an object")
        prediction = {
            field: _text(item.get(field), f"predictions[{index}].{field}")
            for field in ("prediction_id", "statement", "observable", "expected_pattern", "falsifier")
        }
        if prediction["prediction_id"] in ids:
            raise DesignError(f"Duplicate prediction_id: {prediction['prediction_id']}")
        ids.add(prediction["prediction_id"])
        discriminates = _strings(
            item.get("discriminates_against"), f"predictions[{index}].discriminates_against", required=True,
        )
        unknown = sorted(set(discriminates) - rival_ids)
        if unknown:
            raise DesignError(f"predictions[{index}] references unknown rival IDs: {', '.join(unknown)}")
        prediction["discriminates_against"] = discriminates
        output.append(prediction)
    covered = set().union(*(set(item["discriminates_against"]) for item in output))
    missing = sorted(rival_ids - covered)
    if missing:
        raise DesignError(f"Every rival needs a discriminating prediction; missing: {', '.join(missing)}")
    return output


def _normalize_operationalizations(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise DesignError("hypothesis requires at least one operationalization")
    fields = ("construct", "variable", "role", "definition", "measurement_method", "unit", "timing")
    output = []
    variables: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DesignError(f"operationalizations[{index}] must be an object")
        record = {field: _text(item.get(field), f"operationalizations[{index}].{field}") for field in fields}
        if record["variable"] in variables:
            raise DesignError(f"Duplicate operationalized variable: {record['variable']}")
        variables.add(record["variable"])
        output.append(record)
    return output


def register_hypothesis(root: str | os.PathLike[str], hypothesis: dict[str, Any]) -> dict[str, Any]:
    base = project_root(root)
    state = _load_design(base)
    committed, _ = _require_current_commit(base, state)
    if not isinstance(hypothesis, dict):
        raise DesignError("hypothesis must be an object")
    status = _text(hypothesis.get("status"), "hypothesis.status").lower()
    if status != "candidate":
        raise DesignError("hypothesis.status must remain 'candidate'; the system cannot accept it as true")
    rivals = _normalize_rivals(hypothesis.get("rivals"))
    rival_ids = {item["rival_id"] for item in rivals}
    normalized = {
        "hypothesis_id": _text(hypothesis.get("hypothesis_id"), "hypothesis.hypothesis_id"),
        "status": "candidate",
        "observation": _normalize_observation(hypothesis.get("observation")),
        "research_question": _text(hypothesis.get("research_question"), "hypothesis.research_question"),
        "statement": _text(hypothesis.get("statement"), "hypothesis.statement"),
        "mechanism": _text(hypothesis.get("mechanism"), "hypothesis.mechanism"),
        "rivals": rivals,
        "predictions": _normalize_predictions(hypothesis.get("predictions"), rival_ids),
        "operationalizations": _normalize_operationalizations(hypothesis.get("operationalizations")),
        "evidence_boundary": _text(hypothesis.get("evidence_boundary"), "hypothesis.evidence_boundary"),
        "literature_items": _https_literature(hypothesis.get("literature_items"), "hypothesis.literature_items"),
    }
    for field in ("assumptions", "boundary_conditions", "uncertainties"):
        values = _strings(hypothesis.get(field), f"hypothesis.{field}")
        if values:
            normalized[field] = values
    if hypothesis.get("estimand") not in (None, ""):
        normalized["estimand"] = _text(hypothesis.get("estimand"), "hypothesis.estimand")
    hypothesis_hash = digest({"method_hash": committed["method_hash"], "hypothesis": normalized})
    previous_hash = (state.get("hypothesis") or {}).get("hypothesis_hash")
    record = {
        "method_hash": committed["method_hash"],
        "candidate_hash": committed["candidate_hash"],
        "hypothesis_hash": hypothesis_hash,
        "registered_at": utc_now(),
        "hypothesis": normalized,
    }
    state["hypothesis"] = record
    if previous_hash != hypothesis_hash:
        state["experiment"] = None
    _save_design(base, state)
    _append_design_audit(base, "hypothesis_registered", {
        "method_hash": committed["method_hash"],
        "hypothesis_id": normalized["hypothesis_id"],
        "hypothesis_hash": hypothesis_hash,
        "changed": previous_hash != hypothesis_hash,
    })
    return {"changed": previous_hash != hypothesis_hash, **record, "automatic_selection": False}


def _normalize_power(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise DesignError("experiment.power must be an object")
    mode = _text(value.get("mode"), "experiment.power.mode").lower()
    allowed = {"analytic", "simulation", "precision", "resource_constrained", "not_applicable"}
    if mode not in allowed:
        raise DesignError(f"Unsupported experiment.power.mode: {mode}")
    if mode == "not_applicable":
        return {
            "mode": mode,
            "not_applicable_reason": _text(
                value.get("not_applicable_reason"), "experiment.power.not_applicable_reason",
            ),
        }
    result = {
        "mode": mode,
        "basis": _text(value.get("basis"), "experiment.power.basis"),
        "target_power_or_precision": _text(
            value.get("target_power_or_precision"), "experiment.power.target_power_or_precision",
        ),
        "sample_size": _text(value.get("sample_size"), "experiment.power.sample_size"),
        "sensitivity_plan": _text(value.get("sensitivity_plan"), "experiment.power.sensitivity_plan"),
    }
    placeholders = re.compile(r"^(?:tbd|todo|unknown|later|placeholder|待定|稍后)$", re.IGNORECASE)
    for field, item in result.items():
        if field != "mode" and placeholders.fullmatch(item.strip()):
            raise DesignError(f"experiment.power.{field} contains an unsupported placeholder")
    if re.fullmatch(r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)", result["sample_size"]):
        if float(result["sample_size"]) <= 0:
            raise DesignError("experiment.power.sample_size must be positive")
    return result


def _normalize_run_order(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise DesignError("experiment.run_order requires at least one bounded run")
    output = []
    ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DesignError(f"experiment.run_order[{index}] must be an object")
        record = {
            field: _text(item.get(field), f"experiment.run_order[{index}].{field}")
            for field in ("run_id", "purpose", "priority", "stop_go")
        }
        if record["priority"] not in {"must_run", "nice_to_have"}:
            raise DesignError(f"experiment.run_order[{index}].priority must be must_run or nice_to_have")
        if record["run_id"] in ids:
            raise DesignError(f"Duplicate run_id: {record['run_id']}")
        ids.add(record["run_id"])
        output.append(record)
    if not any(item["priority"] == "must_run" for item in output):
        raise DesignError("experiment.run_order needs at least one must_run item")
    return output


def _normalize_ablations(value: Any, not_applicable_reason: Any) -> tuple[list[dict[str, str]], str | None]:
    if not isinstance(value, list):
        raise DesignError("experiment.ablations must be a list")
    if not value:
        reason = " ".join(str(not_applicable_reason or "").split())
        if not reason:
            raise DesignError("An empty ablation list requires ablation_not_applicable_reason")
        return [], reason
    fields = (
        "ablation_id", "component", "what_it_tests", "expected_if_matters",
        "failure_interpretation", "priority", "compute",
    )
    output = []
    ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DesignError(f"experiment.ablations[{index}] must be an object")
        record = {field: _text(item.get(field), f"experiment.ablations[{index}].{field}") for field in fields}
        if record["priority"] not in {"must_run", "nice_to_have"}:
            raise DesignError(f"experiment.ablations[{index}].priority must be must_run or nice_to_have")
        if record["ablation_id"] in ids:
            raise DesignError(f"Duplicate ablation_id: {record['ablation_id']}")
        ids.add(record["ablation_id"])
        output.append(record)
    return output, None


def _normalize_ethics(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DesignError("experiment.ethics_and_feasibility must be an object")
    status = _text(value.get("status"), "experiment.ethics_and_feasibility.status").lower()
    if status not in {"cleared", "pending", "blocked", "not_applicable"}:
        raise DesignError("experiment.ethics_and_feasibility.status is unsupported")
    result = {
        "status": status,
        "required_reviews": _strings(value.get("required_reviews"), "experiment.ethics_and_feasibility.required_reviews"),
        "unresolved_blocks": _strings(value.get("unresolved_blocks"), "experiment.ethics_and_feasibility.unresolved_blocks"),
    }
    if status == "cleared" and result["unresolved_blocks"]:
        raise DesignError("cleared ethics_and_feasibility cannot contain unresolved blocks")
    return result


def register_experiment(root: str | os.PathLike[str], experiment: dict[str, Any]) -> dict[str, Any]:
    base = project_root(root)
    state = _load_design(base)
    committed, _ = _require_current_commit(base, state)
    hypothesis_record = state.get("hypothesis")
    if not hypothesis_record or hypothesis_record.get("method_hash") != committed.get("method_hash"):
        raise DesignError("A current registered hypothesis is required before experiment registration")
    if not isinstance(experiment, dict):
        raise DesignError("experiment must be an object")
    hypothesis = hypothesis_record["hypothesis"]
    prediction_ids = {item["prediction_id"] for item in hypothesis["predictions"]}
    claims_tested = _strings(experiment.get("claims_tested"), "experiment.claims_tested", required=True)
    unknown_claims = sorted(set(claims_tested) - prediction_ids)
    if unknown_claims:
        raise DesignError(f"experiment.claims_tested references unknown prediction IDs: {', '.join(unknown_claims)}")
    experimental_unit = _text(experiment.get("experimental_unit"), "experiment.experimental_unit")
    analysis_unit = _text(experiment.get("analysis_unit"), "experiment.analysis_unit")
    unit_mapping = " ".join(str(experiment.get("unit_mapping") or "").split())
    if experimental_unit.casefold() != analysis_unit.casefold() and not unit_mapping:
        raise DesignError(
            "experiment.unit_mapping is required when analysis_unit differs from experimental_unit to prevent pseudoreplication"
        )
    outcome_variables = {item["variable"] for item in hypothesis["operationalizations"]}
    primary_outcomes = _strings(experiment.get("primary_outcomes"), "experiment.primary_outcomes", required=True)
    unknown_outcomes = sorted(set(primary_outcomes) - outcome_variables)
    if unknown_outcomes:
        raise DesignError(f"experiment.primary_outcomes lacks hypothesis operationalization: {', '.join(unknown_outcomes)}")
    ablations, ablation_reason = _normalize_ablations(
        experiment.get("ablations"), experiment.get("ablation_not_applicable_reason"),
    )
    normalized: dict[str, Any] = {
        "experiment_id": _text(experiment.get("experiment_id"), "experiment.experiment_id"),
        "design_type": _text(experiment.get("design_type"), "experiment.design_type"),
        "claims_tested": claims_tested,
        "experimental_unit": experimental_unit,
        "analysis_unit": analysis_unit,
        "independence_justification": _text(
            experiment.get("independence_justification"), "experiment.independence_justification",
        ),
        "assignment": _text(experiment.get("assignment"), "experiment.assignment"),
        "controls": _strings(experiment.get("controls"), "experiment.controls", required=True),
        "primary_outcomes": primary_outcomes,
        "estimand": _text(experiment.get("estimand"), "experiment.estimand"),
        "power": _normalize_power(experiment.get("power")),
        "missing_data_plan": _text(experiment.get("missing_data_plan"), "experiment.missing_data_plan"),
        "multiplicity_plan": _text(experiment.get("multiplicity_plan"), "experiment.multiplicity_plan"),
        "stopping_rule": _text(experiment.get("stopping_rule"), "experiment.stopping_rule"),
        "success_criteria": _text(experiment.get("success_criteria"), "experiment.success_criteria"),
        "failure_interpretation": _text(
            experiment.get("failure_interpretation"), "experiment.failure_interpretation",
        ),
        "run_order": _normalize_run_order(experiment.get("run_order")),
        "ablations": ablations,
        "ethics_and_feasibility": _normalize_ethics(experiment.get("ethics_and_feasibility")),
    }
    if unit_mapping:
        normalized["unit_mapping"] = unit_mapping
    if experiment.get("blocking") not in (None, ""):
        normalized["blocking"] = _text(experiment.get("blocking"), "experiment.blocking")
    if ablation_reason:
        normalized["ablation_not_applicable_reason"] = ablation_reason
    experiment_hash = digest({
        "method_hash": committed["method_hash"],
        "hypothesis_hash": hypothesis_record["hypothesis_hash"],
        "experiment": normalized,
    })
    previous_hash = (state.get("experiment") or {}).get("experiment_hash")
    record = {
        "method_hash": committed["method_hash"],
        "hypothesis_hash": hypothesis_record["hypothesis_hash"],
        "experiment_hash": experiment_hash,
        "registered_at": utc_now(),
        "experiment": normalized,
    }
    state["experiment"] = record
    _save_design(base, state)
    _append_design_audit(base, "experiment_registered", {
        "method_hash": committed["method_hash"],
        "hypothesis_hash": hypothesis_record["hypothesis_hash"],
        "experiment_id": normalized["experiment_id"],
        "experiment_hash": experiment_hash,
        "changed": previous_hash != experiment_hash,
    })
    return {"changed": previous_hash != experiment_hash, **record}


def get_research_design_status(root: str | os.PathLike[str], *, verify: bool = False) -> dict[str, Any]:
    base = project_root(root)
    design = _load_design(base, required=False)
    if not design:
        return {"status": "NOT_STARTED", "ready": False, "next_action": "Run plan_ideation."}
    committed = design.get("committed_candidate")
    if not committed:
        return {
            "status": "CANDIDATE_SELECTION_REQUIRED",
            "ready": False,
            "plan_hash": design["plan"]["plan_hash"],
            "candidate_count": len(design.get("candidates", [])),
            "next_action": "Ask the user to select a registered candidate, then call commit_candidate.",
        }
    tracked = sync_tracked_method_files(base)
    method_state = load_state(base, required=False)
    if tracked.get("requires_registration") or (method_state or {}).get("pending_method_change"):
        return {
            "status": "STALE_METHOD",
            "ready": False,
            "committed_method_hash": committed.get("method_hash"),
            "active_method_hash": (method_state or {}).get("active_method", {}).get("hash"),
            "next_action": "Register the complete adjusted method, then rerun the collision search.",
        }
    if not method_state or method_state.get("active_method", {}).get("hash") != committed.get("method_hash"):
        return {
            "status": "STALE_METHOD",
            "ready": False,
            "committed_method_hash": committed.get("method_hash"),
            "active_method_hash": (method_state or {}).get("active_method", {}).get("hash"),
            "next_action": "Re-register candidates or explicitly commit the user-selected candidate against the active method.",
        }
    strategy_plan = design.get("strategy_plan")
    strategy = design.get("strategy")
    if strategy_plan:
        if strategy_plan.get("method_hash") != committed.get("method_hash"):
            return {
                "status": "STALE_STRATEGY",
                "ready": False,
                "next_action": "Plan a new research strategy for the current committed method.",
            }
        if not strategy:
            return {
                "status": "STRATEGY_REQUIRED",
                "ready": False,
                "strategy_plan_hash": strategy_plan["strategy_plan_hash"],
                "selected_module_ids": strategy_plan["selected_module_ids"],
                "next_action": "Register the evidence-bounded strategy contract for the active plan.",
            }
        if (
            strategy.get("method_hash") != committed.get("method_hash")
            or strategy.get("strategy_plan_hash") != strategy_plan.get("strategy_plan_hash")
        ):
            return {
                "status": "STALE_STRATEGY",
                "ready": False,
                "next_action": "Register a new strategy contract for the active plan and method.",
            }
        decided = {
            item.get("decision_id") for item in design.get("strategy_decisions", [])
            if item.get("strategy_hash") == strategy.get("strategy_hash")
        }
        required_decisions = {
            item["decision_id"] for item in strategy["strategy"]["decisions"]
            if item["requires_current_choice"]
        }
        unresolved = sorted(required_decisions - decided)
        if unresolved:
            return {
                "status": "STRATEGY_DECISION_REQUIRED",
                "ready": False,
                "strategy_hash": strategy["strategy_hash"],
                "unresolved_decision_ids": unresolved,
                "next_action": "Present every branch and criterion to the user, then record only the user's explicit choice.",
            }
    hypothesis = design.get("hypothesis")
    if not hypothesis:
        return {
            "status": "HYPOTHESIS_REQUIRED",
            "ready": False,
            "method_hash": committed["method_hash"],
            "novelty_gate": method_state["gate"],
            "next_action": "Register a candidate hypothesis with rivals, discriminating predictions, falsifiers, and operationalization.",
        }
    if hypothesis.get("method_hash") != committed.get("method_hash"):
        return {"status": "STALE_METHOD", "ready": False, "next_action": "Register a new hypothesis for the active method."}
    experiment = design.get("experiment")
    if not experiment:
        return {
            "status": "EXPERIMENT_REQUIRED",
            "ready": False,
            "method_hash": committed["method_hash"],
            "hypothesis_hash": hypothesis.get("hypothesis_hash"),
            "novelty_gate": method_state["gate"],
            "next_action": "Register the experiment contract." ,
        }
    if (
        experiment.get("method_hash") != committed.get("method_hash")
        or experiment.get("hypothesis_hash") != hypothesis.get("hypothesis_hash")
    ):
        return {"status": "STALE_DESIGN", "ready": False, "next_action": "Register a new experiment for the current method and hypothesis."}
    ethics = experiment.get("experiment", {}).get("ethics_and_feasibility", {})
    if ethics.get("unresolved_blocks") or ethics.get("status") in {"pending", "blocked"}:
        return {
            "status": "ETHICS_REVIEW_REQUIRED",
            "ready": False,
            "unresolved_blocks": ethics.get("unresolved_blocks", []),
            "next_action": "Resolve the declared ethics, safety, governance, or feasibility blocks.",
        }
    gate = get_gate_status(base)
    if gate["gate"]["status"] != "PASS":
        return {
            "status": "NOVELTY_CHECK_REQUIRED",
            "ready": False,
            "novelty_gate": gate["gate"],
            "method_hash": gate["method_hash"],
            "next_action": "Complete the collision search and resolve every candidate collision for the active method version.",
        }
    if not verify:
        return {
            "status": "NOVELTY_RECEIPT_VERIFICATION_REQUIRED",
            "ready": False,
            "novelty_gate": gate["gate"],
            "next_action": "Call research_design with action=verify to validate the current novelty receipt.",
        }
    receipt = verify_receipt(base, strict=True)
    if not receipt.get("valid"):
        return {
            "status": "NOVELTY_RECEIPT_INVALID",
            "ready": False,
            "novelty_gate": gate["gate"],
            "receipt_errors": receipt.get("errors", []),
            "next_action": "Rerun or repair the active collision search; do not execute this design.",
        }
    return {
        "status": "PASS",
        "ready": True,
        "method_hash": committed["method_hash"],
        "hypothesis_hash": hypothesis["hypothesis_hash"],
        "experiment_hash": experiment["experiment_hash"],
        "novelty_receipt": receipt,
    }
