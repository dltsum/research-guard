from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


STATE_NAME = "evolution-ledger.json"
ALLOWED_CATEGORIES = {"trigger_miss", "trigger_confusion", "tool_failure", "user_correction", "context_cost", "regression"}


class EvolutionError(ValueError):
    pass


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _root(value: str) -> Path:
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
        return {"schema_version": 1, "observations": [], "proposals": [], "ledger_hash": _digest({"observations": [], "proposals": []})}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvolutionError(f"evolution ledger is invalid: {exc}") from exc
    if value.get("ledger_hash") != _digest({"observations": value.get("observations"), "proposals": value.get("proposals")}):
        raise EvolutionError("evolution ledger integrity check failed")
    return value


def _save(root: Path, value: dict[str, Any]) -> None:
    value["ledger_hash"] = _digest({"observations": value["observations"], "proposals": value["proposals"]})
    _atomic(_path(root), value)


def _https_list(values: list[Any] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        text = str(value or "").strip()
        parsed = urlparse(text)
        if parsed.scheme.casefold() != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise EvolutionError("evolution evidence URLs must be credential-free HTTPS links")
        result.append(text)
    return sorted(set(result))


def record_evolution_observation(
    project_root: str, category: str, component: str, expected: str, observed: str,
    evidence_urls: list[str] | None = None, evidence_hash: str | None = None,
) -> dict[str, Any]:
    root = _root(project_root)
    category = str(category or "").casefold()
    if category not in ALLOWED_CATEGORIES:
        raise EvolutionError(f"category must be one of {', '.join(sorted(ALLOWED_CATEGORIES))}")
    component = " ".join(str(component or "").split())
    expected = " ".join(str(expected or "").split())
    observed = " ".join(str(observed or "").split())
    if not component or len(expected) < 10 or len(observed) < 10:
        raise EvolutionError("component, expected, and observed evidence are required")
    digest_value = str(evidence_hash or "").casefold()
    if digest_value and not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", digest_value):
        raise EvolutionError("evidence_hash must be a commit or SHA-256")
    observation = {
        "observation_id": "obs-" + _digest([category, component, expected, observed, evidence_urls, digest_value])[:20],
        "category": category, "component": component, "expected": expected, "observed": observed,
        "evidence_urls": _https_list(evidence_urls), "evidence_hash": digest_value or None, "recorded_at": _now(),
    }
    state = _load(root)
    if any(item["observation_id"] == observation["observation_id"] for item in state["observations"]):
        return observation
    state["observations"].append(observation)
    _save(root, state)
    return observation


def propose_evolution(project_root: str, component: str) -> dict[str, Any]:
    root = _root(project_root)
    state = _load(root)
    component = " ".join(str(component or "").split())
    observations = [item for item in state["observations"] if item["component"] == component]
    if len(observations) < 5:
        raise EvolutionError("at least five component-specific observations are required before proposing evolution")
    categories: dict[str, int] = {}
    for item in observations:
        categories[item["category"]] = categories.get(item["category"], 0) + 1
    dominant = sorted(categories.items(), key=lambda item: (-item[1], item[0]))[0][0]
    proposal = {
        "proposal_id": "proposal-" + _digest([component, [item["observation_id"] for item in observations]])[:20],
        "component": component, "status": "HUMAN_REVIEW_REQUIRED", "dominant_failure": dominant,
        "observation_ids": [item["observation_id"] for item in observations],
        "change_boundary": "proposal only; no corpus, hook, MCP, marketplace, or graph mutation is authorized",
        "recommended_change": {
            "trigger_miss": "Add the smallest missing positive trigger while freezing existing negatives.",
            "trigger_confusion": "Adjust owner precedence or narrow the overlapping trigger; do not add another owner.",
            "tool_failure": "Fix the failing external enforcement path and preserve explicit failure semantics.",
            "user_correction": "Translate the recurring correction into a machine-checkable contract or test.",
            "context_cost": "Move conditional detail to an on-demand reference without removing hard gates.",
            "regression": "Restore the frozen contract before considering any capability expansion.",
        }[dominant],
        "required_validation": [
            "freeze positive, negative, mixed, and adversarial trigger cases",
            "run at least three bounded SkillOpt cycles",
            "perform overlap, license, security, and regression audits",
            "require explicit human application outside this mechanism",
        ],
        "proposed_at": _now(),
    }
    if not any(item["proposal_id"] == proposal["proposal_id"] for item in state["proposals"]):
        state["proposals"].append(proposal)
        _save(root, state)
    return proposal


def evolution_status(project_root: str) -> dict[str, Any]:
    state = _load(_root(project_root))
    return {
        "status": "PASS", "observations": len(state["observations"]), "proposals": len(state["proposals"]),
        "apply_route_exposed": False, "ledger_hash": state["ledger_hash"],
    }
