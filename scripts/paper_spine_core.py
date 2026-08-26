"""Executable contract for macro-first paper spines and title candidates.

The language model still owns the scientific synthesis.  This module makes the
important boundary explicit and durable: a local observation must be lifted to
a macro problem, a unifying method, and falsifiable cross-context evidence
before titles are drafted.  Novelty/collision evidence is bound afterwards by
the canonical research-novelty owner; it is not used as a creativity objective.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


class PaperSpineError(ValueError):
    """Raised when a macro-first paper-spine contract is incomplete or stale."""


SCHEMA_VERSION = 1
STATE_NAME = "paper-spine-state.json"
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{2,79}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TITLE_LEVELS = {"macro", "meso", "local"}
COLLISION_STATES = {"PENDING", "IN_PROGRESS", "ACTION_REQUIRED", "PASS"}
FORBIDDEN_SELECTION_KEYS = {
    "winner", "winning_title", "selected_title", "ranking", "rank", "score",
    "recommended", "recommendation", "best_option", "automatic_choice",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _base(root: str | os.PathLike[str]) -> Path:
    path = Path(root).expanduser().resolve()
    if not path.is_dir():
        raise PaperSpineError("project_root must be an existing directory")
    return path


def _state_path(root: Path) -> Path:
    return root / ".research-guard" / STATE_NAME


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


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


def _text(value: Any, field: str, *, minimum: int = 3, maximum: int = 1200) -> str:
    if not isinstance(value, str):
        raise PaperSpineError(f"{field} must be a string")
    normalized = " ".join(value.split())
    if len(normalized) < minimum:
        raise PaperSpineError(f"{field} must contain at least {minimum} non-whitespace characters")
    if len(normalized) > maximum:
        raise PaperSpineError(f"{field} exceeds the {maximum}-character bound")
    return normalized


def _identifier(value: Any, field: str) -> str:
    normalized = str(value or "").strip()
    if not IDENTIFIER.fullmatch(normalized):
        raise PaperSpineError(f"{field} is not a valid paper-spine identifier")
    return normalized


def _hash(value: Any, field: str) -> str:
    normalized = str(value or "").strip().lower()
    if not SHA256.fullmatch(normalized):
        raise PaperSpineError(f"{field} must be a 64-character lowercase SHA-256 hash")
    return normalized


def _strings(value: Any, field: str, *, required: bool = False, minimum: int = 0, maximum: int = 12) -> list[str]:
    if value is None:
        values: list[Any] = []
    elif isinstance(value, list):
        values = value
    else:
        raise PaperSpineError(f"{field} must be an array")
    if len(values) > maximum:
        raise PaperSpineError(f"{field} has more than {maximum} items")
    result = [_text(item, f"{field}[{index}]", minimum=3, maximum=600) for index, item in enumerate(values)]
    if required and len(result) < max(1, minimum):
        raise PaperSpineError(f"{field} requires at least {max(1, minimum)} items")
    if len(result) != len(set(result)):
        raise PaperSpineError(f"{field} contains duplicates")
    return result


def _https_url(value: Any, field: str) -> str:
    url = str(value or "").strip()
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise PaperSpineError(f"{field} must be a credential-free clickable HTTPS URL")
    if any(character.isspace() for character in url):
        raise PaperSpineError(f"{field} must not contain whitespace")
    return url


def _reject_selection_fields(value: Any, field: str = "spine") -> None:
    if isinstance(value, dict):
        forbidden = sorted(
            key for key in value
            if re.sub(r"[^a-z0-9]", "", str(key).casefold())
            in {re.sub(r"[^a-z0-9]", "", item.casefold()) for item in FORBIDDEN_SELECTION_KEYS}
        )
        if forbidden:
            raise PaperSpineError(f"{field} contains automatic title/choice fields: {', '.join(forbidden)}")
        for key, nested in value.items():
            _reject_selection_fields(nested, f"{field}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_selection_fields(nested, f"{field}[{index}]")


def _objects(value: Any, field: str, *, minimum: int, maximum: int) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise PaperSpineError(f"{field} must contain between {minimum} and {maximum} objects")
    if not all(isinstance(item, dict) for item in value):
        raise PaperSpineError(f"{field} must contain only objects")
    return value


def _plan_stable(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: plan.get(key) for key in ("spine_id", "request_text", "local_observation", "domain_scope")}


def _stable_spine(spine: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in spine.items() if key not in {"spine_hash", "registered_at", "revision"}}


def _load(root: Path) -> dict[str, Any]:
    path = _state_path(root)
    if not path.is_file():
        raise PaperSpineError("No paper-spine plan; call spine_action=plan first")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PaperSpineError(f"paper-spine state is unreadable: {exc}") from exc
    if not isinstance(state, dict) or state.get("schema_version") != SCHEMA_VERSION:
        raise PaperSpineError("unsupported paper-spine state schema")
    plan = state.get("plan")
    if not isinstance(plan, dict) or _digest(_plan_stable(plan)) != plan.get("plan_hash"):
        raise PaperSpineError("paper-spine plan integrity check failed")
    current = state.get("current")
    if current is not None:
        if not isinstance(current, dict) or _digest(_stable_spine(current)) != current.get("spine_hash"):
            raise PaperSpineError("paper-spine registration integrity check failed")
    history = state.get("history", [])
    if not isinstance(history, list):
        raise PaperSpineError("paper-spine history must be an array")
    return state


def _save(root: Path, state: dict[str, Any]) -> None:
    _atomic_json(_state_path(root), state)


def _generation_contract() -> dict[str, Any]:
    return {
        "sequence": [
            "Name the local observation without making it the entire contribution.",
            "Lift it to a macro problem that matters beyond the named case.",
            "State one unifying method, mechanism, or invariant that can travel across contexts.",
            "Write cross-context predictions and falsifiers before choosing a title.",
            "Draft five unranked titles across macro, meso, and local levels.",
            "Run the canonical collision search on the exact method revision after the candidate is formed.",
        ],
        "required_layers": ["local_observation", "macro_problem", "unifying_method", "cross_context_evidence"],
        "anti_patterns": [
            "Do not shrink the research question merely because a nearby paper exists.",
            "Do not treat no detected collision as proof of global novelty.",
            "Do not select one title automatically; the user owns the final framing choice.",
            "Do not claim transfer beyond the registered contexts and evidence plan.",
        ],
        "collision_boundary": "Collision evidence checks differentiation after macro framing; every semantic method revision requires a fresh canonical search.",
    }


def plan_paper_spine(
    root: str | os.PathLike[str], *, spine_id: str, request_text: str,
    local_observation: str, domain_scope: str,
) -> dict[str, Any]:
    base = _base(root)
    identifier = _identifier(spine_id, "spine_id")
    request = _text(request_text, "request_text", minimum=8)
    observation = _text(local_observation, "local_observation", minimum=12)
    scope = _text(domain_scope, "domain_scope", minimum=3, maximum=300)
    stable = {
        "spine_id": identifier,
        "request_text": request,
        "local_observation": observation,
        "domain_scope": scope,
    }
    plan = {
        **stable,
        "plan_hash": _digest(stable),
        "generation_contract": _generation_contract(),
        "planned_at": utc_now(),
        "selected_by": "main_agent",
        "automatic_domain_inference": False,
        "automatic_title_selection": False,
    }
    existing = None
    path = _state_path(base)
    if path.is_file():
        existing = _load(base)
        if existing.get("spine_id") != identifier:
            raise PaperSpineError(
                f"an active paper-spine plan already exists for {existing.get('spine_id')}; use a new spine_id"
            )
        if existing.get("plan", {}).get("plan_hash") == plan["plan_hash"]:
            return {"status": "READY_FOR_MACRO_DRAFT", "plan": existing["plan"]}
        history = list(existing.get("history") or [])
        if existing.get("current") is not None:
            history.append({"kind": "plan_revision", "plan": existing["plan"], "spine": existing["current"]})
    else:
        history = []
    state = {
        "schema_version": SCHEMA_VERSION,
        "spine_id": identifier,
        "plan": plan,
        "current": None,
        "history": history,
        "events": [{"at": utc_now(), "event": "planned", "plan_hash": plan["plan_hash"]}],
    }
    _save(base, state)
    return {"status": "READY_FOR_MACRO_DRAFT", "plan": plan}


def _normalize_prediction(item: dict[str, Any], index: int) -> dict[str, str]:
    return {
        key: _text(item.get(key), f"cross_context_predictions[{index}].{key}", minimum=12, maximum=800)
        for key in ("context", "prediction", "test", "failure_condition")
    }


def _normalize_evidence(item: dict[str, Any], index: int) -> dict[str, Any]:
    evidence_id = _identifier(item.get("evidence_id"), f"evidence_plan[{index}].evidence_id")
    record = {
        "evidence_id": evidence_id,
        "claim": _text(item.get("claim"), f"evidence_plan[{index}].claim", minimum=12, maximum=800),
        "evidence_type": _text(item.get("evidence_type"), f"evidence_plan[{index}].evidence_type", minimum=3, maximum=160),
        "test": _text(item.get("test"), f"evidence_plan[{index}].test", minimum=12, maximum=800),
    }
    raw_links = item.get("source_links")
    if not isinstance(raw_links, list) or not raw_links:
        raise PaperSpineError(f"evidence_plan[{index}].source_links requires at least one HTTPS source")
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for link_index, link in enumerate(raw_links):
        if not isinstance(link, dict):
            raise PaperSpineError(f"evidence_plan[{index}].source_links[{link_index}] must be an object")
        title = _text(link.get("title"), f"evidence_plan[{index}].source_links[{link_index}].title", minimum=3, maximum=300)
        url = _https_url(link.get("url"), f"evidence_plan[{index}].source_links[{link_index}].url")
        if url in seen:
            raise PaperSpineError(f"duplicate evidence URL in evidence_plan[{index}]")
        seen.add(url)
        links.append({"title": title, "url": url})
    record["source_links"] = links
    return record


def _normalize_title(item: dict[str, Any], index: int) -> dict[str, str]:
    title_id = _identifier(item.get("title_id"), f"title_candidates[{index}].title_id")
    level = str(item.get("level") or "").strip().lower()
    if level not in TITLE_LEVELS:
        raise PaperSpineError(f"title_candidates[{index}].level must be macro, meso, or local")
    return {
        "title_id": title_id,
        "title": _text(item.get("title"), f"title_candidates[{index}].title", minimum=12, maximum=300),
        "level": level,
        "rationale": _text(item.get("rationale"), f"title_candidates[{index}].rationale", minimum=12, maximum=600),
        "claim_scope": _text(item.get("claim_scope"), f"title_candidates[{index}].claim_scope", minimum=12, maximum=500),
    }


def _normalize_collision(value: Any, method_hash: str) -> dict[str, Any]:
    if value in (None, {}):
        return {
            "status": "PENDING", "method_hash": method_hash, "receipt_sha256": None,
            "report_hash": None, "query_plan_hash": None, "literature_links": [],
        }
    if not isinstance(value, dict):
        raise PaperSpineError("collision must be an object")
    status = str(value.get("status") or "PENDING").strip().upper()
    if status not in COLLISION_STATES:
        raise PaperSpineError("collision.status is unsupported")
    if status == "PASS":
        raise PaperSpineError("collision PASS can only be attached by bind_collision after canonical verification")
    return {
        "status": status,
        "method_hash": method_hash,
        "receipt_sha256": None,
        "report_hash": None,
        "query_plan_hash": None,
        "literature_links": [],
        "note": _text(value.get("note"), "collision.note", minimum=8, maximum=600) if value.get("note") else None,
    }


def register_paper_spine(
    root: str | os.PathLike[str], *, spine_id: str, plan_hash: str, spine: dict[str, Any],
    selected_by: str = "main_agent",
) -> dict[str, Any]:
    base = _base(root)
    state = _load(base)
    identifier = _identifier(spine_id, "spine_id")
    if state.get("spine_id") != identifier:
        raise PaperSpineError("spine_id does not match the active plan")
    if str(plan_hash or "") != state["plan"]["plan_hash"]:
        raise PaperSpineError("spine_plan_hash is stale or does not match the active plan")
    if selected_by != "main_agent":
        raise PaperSpineError("selected_by=main_agent is required for semantic spine formation")
    if not isinstance(spine, dict):
        raise PaperSpineError("spine must be an object")
    _reject_selection_fields(spine)
    plan = state["plan"]
    observation = _text(spine.get("local_observation"), "spine.local_observation", minimum=12)
    if observation != plan["local_observation"]:
        raise PaperSpineError("spine.local_observation must match the hash-bound plan")
    method_hash = _hash(spine.get("method_hash"), "spine.method_hash")
    macro_problem = _text(spine.get("macro_problem"), "spine.macro_problem", minimum=24, maximum=1000)
    if macro_problem.casefold() == observation.casefold():
        raise PaperSpineError("macro_problem must lift the local observation rather than repeat it")
    normalized: dict[str, Any] = {
        "spine_id": identifier,
        "method_hash": method_hash,
        "local_observation": observation,
        "macro_problem": macro_problem,
        "unifying_method": _text(spine.get("unifying_method"), "spine.unifying_method", minimum=24, maximum=1000),
        "mechanism": _text(spine.get("mechanism"), "spine.mechanism", minimum=24, maximum=1000),
        "central_claim": _text(spine.get("central_claim"), "spine.central_claim", minimum=24, maximum=1000),
        "generality_target": _text(spine.get("generality_target"), "spine.generality_target", minimum=12, maximum=600),
        "abstraction_move": {},
    }
    raw_move = spine.get("abstraction_move")
    if not isinstance(raw_move, dict):
        raise PaperSpineError("spine.abstraction_move must be an object")
    normalized["abstraction_move"] = {
        key: _text(raw_move.get(key), f"spine.abstraction_move.{key}", minimum=12, maximum=700)
        for key in ("from_local_case", "to_macro_question", "unifying_invariant", "why_general", "anti_overclaim")
    }
    predictions = _objects(spine.get("cross_context_predictions"), "cross_context_predictions", minimum=2, maximum=8)
    normalized["cross_context_predictions"] = [_normalize_prediction(item, index) for index, item in enumerate(predictions)]
    contexts = {item["context"].casefold() for item in normalized["cross_context_predictions"]}
    if len(contexts) < 2:
        raise PaperSpineError("cross_context_predictions must cover at least two distinct contexts")
    normalized["falsifiers"] = _strings(spine.get("falsifiers"), "falsifiers", required=True, minimum=2, maximum=8)
    normalized["scope_boundary"] = _strings(spine.get("scope_boundary"), "scope_boundary", required=True, minimum=2, maximum=8)
    evidence = _objects(spine.get("evidence_plan"), "evidence_plan", minimum=2, maximum=10)
    normalized["evidence_plan"] = [_normalize_evidence(item, index) for index, item in enumerate(evidence)]
    evidence_ids = [item["evidence_id"] for item in normalized["evidence_plan"]]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise PaperSpineError("evidence_plan contains duplicate evidence_id values")
    titles = _objects(spine.get("title_candidates"), "title_candidates", minimum=5, maximum=8)
    normalized["title_candidates"] = [_normalize_title(item, index) for index, item in enumerate(titles)]
    title_ids = [item["title_id"] for item in normalized["title_candidates"]]
    title_texts = [item["title"].casefold() for item in normalized["title_candidates"]]
    if len(title_ids) != len(set(title_ids)) or len(title_texts) != len(set(title_texts)):
        raise PaperSpineError("title_candidates identifiers and titles must be unique")
    levels = {item["level"] for item in normalized["title_candidates"]}
    if not {"macro", "meso"}.issubset(levels) or sum(item["level"] == "macro" for item in normalized["title_candidates"]) < 2:
        raise PaperSpineError("title_candidates must include at least two macro titles and one meso title")
    previous = state.get("current")
    normalized["collision"] = _normalize_collision(spine.get("collision"), method_hash)
    # A title/claim framing revision with the same canonical method does not
    # invalidate method-level collision evidence.  An omitted collision field
    # carries that receipt forward; an explicit PENDING/IN_PROGRESS field asks
    # for a fresh search.  A changed method hash can never carry it forward.
    if (
        previous is not None
        and previous.get("method_hash") == method_hash
        and spine.get("collision") in (None, {})
        and (previous.get("collision") or {}).get("status") == "PASS"
    ):
        normalized["collision"] = copy.deepcopy(previous["collision"])
    if previous is not None and previous.get("method_hash") != method_hash and normalized["collision"]["status"] == "PASS":
        raise PaperSpineError("method revision requires a fresh canonical collision search")
    if previous is not None and _digest(_stable_spine(previous)) == _digest(normalized):
        return {
            "status": _status_for(normalized), "changed": False, "spine": previous,
            "automatic_title_selection": False, "user_title_selection_required": True,
        }
    revision = int(previous.get("revision", 0)) + 1 if previous else 1
    normalized["revision"] = revision
    normalized["registered_at"] = utc_now()
    normalized["spine_hash"] = _digest(_stable_spine(normalized))
    history = list(state.get("history") or [])
    if previous is not None:
        history.append({"kind": "spine_revision", "spine": previous})
    state.update({
        "current": normalized,
        "history": history,
        "events": [*state.get("events", []), {
            "at": utc_now(), "event": "spine_registered", "revision": revision,
            "spine_hash": normalized["spine_hash"], "method_hash": method_hash,
            "collision_status": normalized["collision"]["status"],
        }],
    })
    _save(base, state)
    return {
        "status": _status_for(normalized), "changed": True, "spine": normalized,
        "automatic_title_selection": False, "user_title_selection_required": True,
        "next_action": "Run the canonical collision search for this exact method revision, then bind it with spine_action=bind_collision.",
    }


def _status_for(spine: dict[str, Any]) -> str:
    status = (spine.get("collision") or {}).get("status")
    return {
        "PASS": "PASS",
        "IN_PROGRESS": "COLLISION_SEARCH_IN_PROGRESS",
        "ACTION_REQUIRED": "ACTION_REQUIRED",
    }.get(status, "COLLISION_SEARCH_REQUIRED")


def _report_links(report: dict[str, Any]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for work in report.get("works", []) if isinstance(report.get("works"), list) else []:
        if not isinstance(work, dict):
            continue
        title = " ".join(str(work.get("title") or "").split()) or "Collision-search result"
        candidates = work.get("citation_links") if isinstance(work.get("citation_links"), list) else []
        if not candidates and work.get("primary_record_url"):
            candidates = [{"url": work.get("primary_record_url")}]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            try:
                url = _https_url(candidate.get("url"), "collision literature link")
            except PaperSpineError:
                continue
            if url not in seen:
                seen.add(url)
                links.append({"title": title, "url": url})
    return links


def bind_paper_spine_collision(root: str | os.PathLike[str], *, spine_id: str) -> dict[str, Any]:
    """Attach only the current canonical strict novelty receipt to a spine."""
    base = _base(root)
    state = _load(base)
    identifier = _identifier(spine_id, "spine_id")
    current = state.get("current")
    if not isinstance(current, dict) or current.get("spine_id") != identifier:
        raise PaperSpineError("no current spine exists for spine_id")
    try:
        from research_guard_core import get_collision_report, get_gate_status, verify_receipt

        verification = verify_receipt(base, strict=True)
        gate = get_gate_status(base)
        report = get_collision_report(base)
    except Exception as exc:  # the canonical owner exposes the factual blocker
        raise PaperSpineError(f"canonical collision evidence is unavailable: {exc}") from exc
    if not verification.get("valid") or gate.get("method_hash") != current.get("method_hash"):
        raise PaperSpineError("canonical collision receipt is invalid or belongs to a different method revision")
    if report.get("method_hash") != current.get("method_hash"):
        raise PaperSpineError("canonical collision report belongs to a different method revision")
    if report.get("gate_status") != "PASS":
        raise PaperSpineError(f"canonical collision gate is {report.get('gate_status')}, not PASS")
    receipt_relative = str(gate.get("current_receipt") or "")
    receipt_path = (base / receipt_relative).resolve()
    try:
        receipt_path.relative_to(base)
    except ValueError as exc:
        raise PaperSpineError("canonical receipt path escapes project_root") from exc
    if not receipt_path.is_file():
        raise PaperSpineError("canonical collision receipt file is missing")
    links = _report_links(report)
    current["collision"] = {
        "status": "PASS",
        "method_hash": current["method_hash"],
        "receipt_sha256": _sha256_file(receipt_path),
        "report_hash": str(report.get("report_hash") or ""),
        "query_plan_hash": str(report.get("query_plan_hash") or ""),
        "literature_links": links,
        "checked_at": utc_now(),
        "claim_scope": "no unresolved collision under the recorded sources, queries, coverage, and date",
    }
    current["spine_hash"] = _digest(_stable_spine(current))
    state["current"] = current
    state["events"] = [*state.get("events", []), {
        "at": utc_now(), "event": "collision_bound", "spine_hash": current["spine_hash"],
        "method_hash": current["method_hash"], "report_hash": report.get("report_hash"),
    }]
    _save(base, state)
    return {"status": "PASS", "spine": current, "literature_links": links}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_paper_spine(root: str | os.PathLike[str], *, spine_id: str | None = None) -> dict[str, Any]:
    base = _base(root)
    try:
        state = _load(base)
    except PaperSpineError as exc:
        return {"status": "NOT_PLANNED", "valid": False, "errors": [str(exc)]}
    current = state.get("current")
    errors: list[str] = []
    if not isinstance(current, dict):
        errors.append("MACRO_SPINE_REQUIRED")
        return {"status": "MACRO_SPINE_REQUIRED", "valid": False, "errors": errors, "plan": state["plan"]}
    if spine_id is not None and current.get("spine_id") != str(spine_id).strip():
        errors.append("SPINE_ID_MISMATCH")
    if len(current.get("cross_context_predictions") or []) < 2:
        errors.append("CROSS_CONTEXT_EVIDENCE_REQUIRED")
    if len(current.get("title_candidates") or []) < 5:
        errors.append("TITLE_SET_INCOMPLETE")
    if not current.get("macro_problem") or not current.get("unifying_method"):
        errors.append("MACRO_PROBLEM_OR_UNIFYING_METHOD_MISSING")
    try:
        from research_guard_core import get_gate_status, verify_receipt

        verification = verify_receipt(base, strict=True)
        gate = get_gate_status(base)
    except Exception as exc:
        verification = {"valid": False, "errors": [str(exc)]}
        gate = {}
    collision = current.get("collision") or {}
    if collision.get("status") != "PASS":
        errors.append("COLLISION_SEARCH_REQUIRED")
    else:
        if not verification.get("valid"):
            errors.append("CANONICAL_COLLISION_RECEIPT_INVALID")
        if gate.get("method_hash") != current.get("method_hash"):
            errors.append("COLLISION_METHOD_REVISION_MISMATCH")
        if collision.get("method_hash") != current.get("method_hash"):
            errors.append("BOUND_COLLISION_METHOD_MISMATCH")
        if not SHA256.fullmatch(str(collision.get("receipt_sha256") or "")):
            errors.append("BOUND_COLLISION_RECEIPT_HASH_MISSING")
    status = "PASS" if not errors else "COLLISION_SEARCH_REQUIRED" if all(
        item.startswith("COLLISION") or item.startswith("CANONICAL") or item.startswith("BOUND_COLLISION")
        for item in errors
    ) else "REVIEW_REQUIRED"
    return {
        "status": status,
        "valid": not errors,
        "errors": errors,
        "spine_id": current.get("spine_id"),
        "revision": current.get("revision"),
        "spine_hash": current.get("spine_hash"),
        "macro_spine": current,
        "automatic_title_selection": False,
        "user_title_selection_required": True,
    }


def get_paper_spine_status(root: str | os.PathLike[str], *, spine_id: str | None = None) -> dict[str, Any]:
    return verify_paper_spine(root, spine_id=spine_id)
