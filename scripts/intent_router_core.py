from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


MAX_MODULES = 3
SELECTION_SCHEMA_VERSION = 1


INSTRUCTIONS = {
    "venue_evidence": "Resolve the exact venue/year/track/stage from current official evidence before reusing any structure or template.",
    "formula_verification": "Report Lean, Pint, SymPy, Z3, and protocol-admitted numerical checks separately; use one manuscript-wide Lean file and verify every parameter is legal and used.",
    "academic_figure": "Plan, render, audit, and visually inspect evidence-bound academic figures at final physical size.",
    "structured_evidence": "Hash-bind parsed sources and preserve exact claim/evidence locators and parser limitations.",
    "research_integrity": "Use explicit user decisions for protocol freezes, deviations, screening, and other scientific judgments.",
    "research_artifact": "Create and verify hash-bound paper cards, review ledgers, experiment logs, or reviewer-response boards.",
    "paper_audit": "Select only two or three reviewer roles, keep effort at high or below, and verify current facts online.",
    "citation_literature": "Search current primary scholarly sources and return a clickable HTTPS DOI or primary-record link for every item.",
    "self_evolution": "Record evidence and generate a human-reviewed proposal only; never apply self-changes automatically.",
    "domain_skill": "Discover and quarantine one narrow professional Skill, scan it, run two or three optimization rounds, then audit overlap before admission.",
    "discipline_profile": "After the main agent explicitly selects a field profile, inspect current coverage and initialize an unregistered field only through a separate explicit call.",
    "research_strategy": "Use two or three strategy modules, preserve user-owned choices, and route committed method changes through the novelty gate.",
    "academic_language": "Preserve uncertainty; present material limitation and potential ethics decisions to the user.",
    "research_novelty": "Register the complete method and an explicit domain selection, then continue collision search until its coverage contract is complete.",
}


CONFLICTS = {
    frozenset(("formula_verification", "paper_audit")): "formula_verification",
    frozenset(("citation_literature", "research_novelty")): "citation_literature",
    frozenset(("structured_evidence", "paper_audit")): "structured_evidence",
    frozenset(("discipline_profile", "domain_skill")): "discipline_profile",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
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


def list_research_modules() -> dict[str, Any]:
    """Return the registry without making a semantic choice for the caller."""
    return {
        "status": "MAIN_AGENT_SELECTION_REQUIRED",
        "selected_modules": [],
        "module_budget": MAX_MODULES,
        "modules": [
            {"id": module_id, "instruction": instruction}
            for module_id, instruction in INSTRUCTIONS.items()
        ],
        "selection_contract": {
            "selected_by": "main_agent",
            "minimum_modules": 1,
            "maximum_modules": MAX_MODULES,
            "rationale_required": True,
            "automatic_keyword_routing": False,
        },
    }


def _validate_modules(values: list[str]) -> list[str]:
    if not isinstance(values, list):
        raise ValueError("selected_modules must be an array chosen by the main agent")
    modules = [str(value).strip() for value in values if str(value).strip()]
    if not 1 <= len(modules) <= MAX_MODULES:
        raise ValueError(f"Select between one and {MAX_MODULES} research modules")
    if len(modules) != len(set(modules)):
        raise ValueError("selected_modules contains duplicates")
    unknown = [module for module in modules if module not in INSTRUCTIONS]
    if unknown:
        raise ValueError(f"Unknown research modules: {', '.join(unknown)}")
    for pair, owner in CONFLICTS.items():
        if pair.issubset(modules):
            other = next(module for module in pair if module != owner)
            raise ValueError(
                f"Overlapping modules {owner} and {other} cannot both be selected; "
                f"use canonical owner {owner} and its integrated subroute"
            )
    return modules


def select_research_modules(
    project_root: str | os.PathLike[str],
    *,
    request_text: str,
    selected_modules: list[str],
    selection_rationale: str,
    selected_by: str,
    method_change: bool = False,
) -> dict[str, Any]:
    """Validate and persist a semantic decision already made by the main model."""
    if selected_by != "main_agent":
        raise ValueError("selected_by=main_agent is required; automatic and small-model routing are forbidden")
    request = " ".join(str(request_text or "").split())
    rationale = " ".join(str(selection_rationale or "").split())
    if not request:
        raise ValueError("request_text is required")
    if len(rationale) < 12:
        raise ValueError("selection_rationale must explain the main agent's semantic choice")
    modules = _validate_modules(selected_modules)
    base = Path(project_root).expanduser().resolve()
    body = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "selected_at": utc_now(),
        "selected_by": selected_by,
        "request_hash": _digest({"request_text": request}),
        "selected_modules": modules,
        "primary_module": modules[0],
        "secondary_modules": modules[1:],
        "selection_rationale": rationale,
        "method_change": bool(method_change),
        "instructions": [INSTRUCTIONS[module] for module in modules],
        "automatic_keyword_routing": False,
    }
    body["selection_hash"] = _digest(body)
    path = base / ".research-guard" / "module-selections" / f"{body['selection_hash'][:20]}.json"
    _atomic_json(path, body)
    invalidation = None
    if method_change:
        state_path = base / ".research-guard" / "state.json"
        if state_path.is_file():
            from research_guard_core import declare_method_change

            invalidation = declare_method_change(base, request)
    return {
        "status": "SELECTED",
        "selection": body,
        "selection_path": str(path.relative_to(base)).replace("\\", "/"),
        "method_change_invalidation": invalidation,
    }


def route_prompt(prompt: str, **_: Any) -> dict[str, Any]:
    """Compatibility surface that deliberately refuses automatic semantic routing."""
    result = list_research_modules()
    result.update({
        "request_hash": _digest({"request_text": " ".join(str(prompt or "").split())}),
        "primary_module": None,
        "secondary_modules": [],
        "suppressed": [],
        "method_change_overlay": None,
        "hard_overlay_instruction": (
            "The main agent must decide whether the request changes the research method and pass "
            "method_change=true when registering its module selection."
        ),
    })
    return result


if __name__ == "__main__":
    print(json.dumps(list_research_modules(), ensure_ascii=False, indent=2))
