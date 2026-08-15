from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import statistics
from pathlib import Path
from typing import Any


class AIReviewerAuditError(ValueError):
    pass


AUDIT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
TEXT_SUFFIXES = {".tex", ".md", ".markdown", ".txt", ".rst", ".qmd"}
FORBIDDEN_EVALUATION_KEYS = {
    "optimization_target", "candidate", "candidate_id", "variant", "variant_id",
    "rank", "selected", "selected_variant", "target_score",
}
OPTIMIZATION_DIMENSIONS = {
    "evidence_framing", "novelty_stance", "scope_framing",
    "title_presentation", "reviewer_navigation", "language_polish",
}
DIRECT_REVIEWER_INSTRUCTIONS = [
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|review)\s+instructions?\b", re.I),
    re.compile(r"\b(?:give|assign|award)\s+(?:this\s+(?:paper|work)\s+)?(?:a\s+)?(?:high|positive|maximum|\d+(?:\.\d+)?)\s+(?:review\s+)?score\b", re.I),
    re.compile(r"\b(?:recommend|mark)\s+(?:this\s+(?:paper|work)\s+)?(?:for\s+)?accept(?:ance|ed)?\b", re.I),
    re.compile(r"\b(?:reviewer|evaluator|judge)\s*:\s*(?:accept|approve|score|rate)\b", re.I),
    re.compile(r"(?:忽略|无视).{0,12}(?:审稿|评审|此前|以上).{0,12}(?:指令|要求)", re.I),
    re.compile(r"(?:审稿人|评审模型).{0,16}(?:给出|打出|评为).{0,10}(?:高分|满分|接收|录用)", re.I),
]
REVIEW_CONTEXT = re.compile(r"\b(?:reviewer|review|evaluator|judge|score|acceptance)\b|审稿|评审|评分|录用|接收", re.I)
HIDDEN_LATEX = re.compile(
    r"\\(?:textcolor\s*\{\s*white\s*\}|color\s*\{\s*white\s*\}|phantom|hphantom|vphantom|fontsize\s*\{0(?:\.0+)?\})",
    re.I,
)
ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")
TITLE_LINE = re.compile(r"^\s*(?:#\s+|\\title\s*\{)(.+?)(?:\}\s*)?$", re.M)
CRITICAL_TOPIC = re.compile(
    r"\b(?:limitation|risk|failure|bias|fairness|ethic|harm|safety|critique|negative result)\w*\b|"
    r"局限|限制|风险|失败|偏差|公平|伦理|伤害|安全|批判|负面结果",
    re.I,
)
PRESTIGE_METADATA = re.compile(
    r"\b(?:affiliation|university|institute|laboratory|professor|senior author|h-index)\b|"
    r"单位|高校|大学|研究所|实验室|教授|资深作者",
    re.I,
)
CITATION_TOKEN = re.compile(r"\\cite[a-zA-Z*]*\{[^}]+\}|(?<![\w.-])@[A-Za-z0-9_:.+-]+")
NUMBER_TOKEN = re.compile(r"(?<![\w.])[-+]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)\s*(?:%|％)?")
MATH_TOKEN = re.compile(
    r"\$\$.*?\$\$|\$[^$\n]+\$|\\\[.*?\\\]|\\\(.*?\\\)|"
    r"\\begin\{(?:equation|align|gather)\*?\}.*?\\end\{(?:equation|align|gather)\*?\}",
    re.S,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _state_path(root: Path, audit_id: str) -> Path:
    return root / ".research-guard" / "ai-reviewer" / f"{audit_id}.json"


def _optimization_path(root: Path, optimization_id: str) -> Path:
    return root / ".research-guard" / "ai-reviewer-optimization" / f"{optimization_id}.json"


def _registry_path() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "review-evidence" / "ai-reviewer-evidence.json"


def _load_registry() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    path = _registry_path()
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AIReviewerAuditError(f"AI-reviewer evidence registry is invalid: {exc}") from exc
    sources = registry.get("sources")
    if not isinstance(sources, list) or not sources:
        raise AIReviewerAuditError("AI-reviewer evidence registry has no sources")
    by_id = {str(item.get("source_id") or ""): item for item in sources if isinstance(item, dict)}
    if len(by_id) != len(sources) or "" in by_id:
        raise AIReviewerAuditError("AI-reviewer evidence registry has duplicate or missing source IDs")
    return registry, by_id


def _safe_id(value: str) -> str:
    audit_id = str(value or "").strip().lower()
    if not AUDIT_ID.fullmatch(audit_id):
        raise AIReviewerAuditError("audit_id must use lowercase letters, digits, and hyphens")
    return audit_id


def _read_manuscripts(root: Path, values: list[str] | None) -> tuple[list[dict[str, Any]], str]:
    if not isinstance(values, list) or not values:
        raise AIReviewerAuditError("AI-reviewer robustness requires manuscript_files")
    tracked: list[dict[str, Any]] = []
    parts: list[str] = []
    seen: set[str] = set()
    for raw in values:
        candidate = Path(str(raw))
        path = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise AIReviewerAuditError(f"manuscript file must stay inside project_root: {raw}") from exc
        if relative in seen or not path.is_file() or path.is_symlink():
            raise AIReviewerAuditError(f"manuscript file is missing, duplicated, or a symlink: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES:
            raise AIReviewerAuditError(f"AI-reviewer audit requires UTF-8 text manuscript input: {relative}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise AIReviewerAuditError(f"manuscript must be UTF-8: {relative}") from exc
        seen.add(relative)
        tracked.append({"path": relative, "sha256": _sha256(path), "bytes": path.stat().st_size})
        parts.append(f"\n--- {relative} ---\n{text}")
    return sorted(tracked, key=lambda item: item["path"]), "".join(parts)


def _content_sha256(tracked: list[dict[str, Any]]) -> str:
    return _hash(sorted(str(item["sha256"]) for item in tracked))


def manuscript_content_sha256(tracked: list[dict[str, Any]]) -> str:
    """Return a path-independent digest for a registered manuscript file set."""
    return _content_sha256(tracked)


def _manipulation_findings(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    hard_failures: list[dict[str, Any]] = []
    review_flags: list[dict[str, Any]] = []
    for pattern in DIRECT_REVIEWER_INSTRUCTIONS:
        for match in pattern.finditer(text):
            context = text[max(0, match.start() - 80):min(len(text), match.end() + 80)].strip()
            hard_failures.append({
                "type": "reviewer_directed_instruction",
                "excerpt": context[:240],
                "action": "remove from the submission and investigate provenance; do not paraphrase it into another reviewer command",
            })
    hidden_matches = [match.group(0) for match in HIDDEN_LATEX.finditer(text)]
    zero_width_count = len(ZERO_WIDTH.findall(text))
    if hidden_matches and REVIEW_CONTEXT.search(text):
        hard_failures.append({
            "type": "hidden_reviewer_content",
            "signals": sorted(set(hidden_matches))[:20],
            "action": "remove hidden content and inspect the manuscript source and build artifacts",
        })
    if zero_width_count:
        review_flags.append({
            "type": "zero_width_characters",
            "count": zero_width_count,
            "action": "inspect exact locations; legitimate typography must be documented and reviewer-directed hiding is forbidden",
        })
    return hard_failures, review_flags


def _content_signature(text: str) -> dict[str, Any]:
    def normalized(values: list[str]) -> list[str]:
        return sorted(" ".join(value.split()) for value in values)

    paragraphs = [" ".join(value.split()) for value in re.split(r"\n\s*\n", text) if value.strip()]
    protected = sorted(value for value in paragraphs if CRITICAL_TOPIC.search(value))
    return {
        "citations": normalized(CITATION_TOKEN.findall(text)),
        "numbers": normalized(NUMBER_TOKEN.findall(text)),
        "formulas": normalized(MATH_TOKEN.findall(text)),
        "protected_critical_paragraphs": protected,
    }


def _fresh_timestamp(value: Any, label: str) -> str:
    raw = str(value or "").strip()
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AIReviewerAuditError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    age = dt.datetime.now(dt.timezone.utc) - parsed.astimezone(dt.timezone.utc)
    if age < dt.timedelta(days=-1) or age > dt.timedelta(days=30):
        raise AIReviewerAuditError(f"{label} is future-dated or older than 30 days")
    return raw


def _venue_reviewer_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AIReviewerAuditError("AI-reviewer optimization requires an exact venue_reviewer_contract")
    required = (
        "venue_name", "year", "track", "stage", "policy_url",
        "reviewer_guidelines_url", "verified_at", "source_type", "status", "criteria",
    )
    missing = [key for key in required if value.get(key) in (None, "", [])]
    if missing:
        raise AIReviewerAuditError("venue_reviewer_contract is missing: " + ", ".join(missing))
    if value.get("source_type") != "official" or value.get("status") != "verified":
        raise AIReviewerAuditError("venue reviewer guidance must be a freshly verified official source")
    for key in ("policy_url", "reviewer_guidelines_url"):
        if not str(value[key]).startswith("https://"):
            raise AIReviewerAuditError(f"venue_reviewer_contract {key} must be a clickable https:// URL")
    criteria = value.get("criteria")
    if not isinstance(criteria, list) or not 2 <= len(criteria) <= 12:
        raise AIReviewerAuditError("venue reviewer criteria must contain two to twelve rubric dimensions")
    normalized_criteria: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, item in enumerate(criteria):
        if not isinstance(item, dict):
            raise AIReviewerAuditError(f"venue criterion {index} must be an object")
        criterion_id = str(item.get("criterion_id") or "").strip().lower()
        if not AUDIT_ID.fullmatch(criterion_id) or criterion_id in ids:
            raise AIReviewerAuditError(f"venue criterion {index} has an invalid or duplicate criterion_id")
        try:
            weight = float(item.get("weight"))
        except (TypeError, ValueError) as exc:
            raise AIReviewerAuditError(f"venue criterion {index} weight must be numeric") from exc
        if weight <= 0:
            raise AIReviewerAuditError(f"venue criterion {index} weight must be positive")
        name = " ".join(str(item.get("name") or "").split())
        if not name:
            raise AIReviewerAuditError(f"venue criterion {index} name is required")
        ids.add(criterion_id)
        normalized_criteria.append({"criterion_id": criterion_id, "name": name, "weight": weight})
    total = sum(item["weight"] for item in normalized_criteria)
    for item in normalized_criteria:
        item["normalized_weight"] = item["weight"] / total
    result = {
        "venue_name": " ".join(str(value["venue_name"]).split()),
        "year": int(value["year"]),
        "track": " ".join(str(value["track"]).split()),
        "stage": " ".join(str(value["stage"]).split()),
        "policy_url": str(value["policy_url"]),
        "reviewer_guidelines_url": str(value["reviewer_guidelines_url"]),
        "verified_at": _fresh_timestamp(value["verified_at"], "venue_reviewer_contract verified_at"),
        "source_type": "official",
        "status": "verified",
        "criteria": normalized_criteria,
    }
    result["contract_sha256"] = _hash(result)
    return result


def _fresh_evidence(values: Any, registry: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(values, list) or len(values) < 3:
        raise AIReviewerAuditError("at least three freshly verified primary AI-reviewer sources are required")
    now = dt.datetime.now(dt.timezone.utc)
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(values):
        if not isinstance(raw, dict):
            raise AIReviewerAuditError(f"online_evidence {index} must be an object")
        source_id = str(raw.get("source_id") or "").strip()
        if source_id in seen or source_id not in registry:
            raise AIReviewerAuditError(f"online_evidence {index} has an unknown or duplicate source_id")
        record = registry[source_id]
        url = str(raw.get("url") or "").strip()
        allowed_urls = {str(record.get("primary_url") or ""), str(record.get("doi_url") or "")}
        allowed_urls.discard("")
        if url not in allowed_urls or not url.startswith("https://"):
            raise AIReviewerAuditError(f"online_evidence {index} URL does not match the primary registry record")
        if str(raw.get("status") or "").strip().lower() != "verified":
            raise AIReviewerAuditError(f"online_evidence {index} status must be verified")
        try:
            accessed = dt.datetime.fromisoformat(str(raw.get("accessed_at") or "").replace("Z", "+00:00"))
        except ValueError as exc:
            raise AIReviewerAuditError(f"online_evidence {index} accessed_at must be ISO-8601") from exc
        if accessed.tzinfo is None:
            accessed = accessed.replace(tzinfo=dt.timezone.utc)
        age = now - accessed.astimezone(dt.timezone.utc)
        if age < dt.timedelta(days=-1) or age > dt.timedelta(days=30):
            raise AIReviewerAuditError(f"online_evidence {index} is future-dated or older than 30 days")
        seen.add(source_id)
        normalized.append({
            "source_id": source_id,
            "title": record["title"],
            "publication_status": record["publication_status"],
            "url": url,
            "accessed_at": str(raw["accessed_at"]),
            "status": "verified",
            "evidence_scope": record["evidence_scope"],
            "safe_use": record["safe_use"],
            "prohibited_use": record["prohibited_use"],
        })
    if not any(item["publication_status"] == "peer_reviewed" for item in normalized):
        raise AIReviewerAuditError("online_evidence must include at least one peer-reviewed primary record")
    return normalized


def _model_sensitivity(values: Any, manuscript_sha256: str) -> dict[str, Any]:
    if values in (None, []):
        return {
            "status": "NOT_TESTED",
            "reason": "No model evaluations were supplied; no claim about cross-model or rerun stability is permitted.",
        }
    if not isinstance(values, list) or len(values) < 2:
        raise AIReviewerAuditError("model_evaluations requires at least two independently identified runs")
    normalized: list[dict[str, Any]] = []
    run_ids: set[str] = set()
    for index, raw in enumerate(values):
        if not isinstance(raw, dict):
            raise AIReviewerAuditError(f"model_evaluations {index} must be an object")
        forbidden = sorted(set(raw) & FORBIDDEN_EVALUATION_KEYS)
        if forbidden:
            raise AIReviewerAuditError(
                "score-targeted manuscript variant selection is forbidden: " + ", ".join(forbidden)
            )
        required = ("run_id", "model_id", "prompt_sha256", "input_sha256", "score", "scale_min", "scale_max")
        missing = [key for key in required if raw.get(key) in (None, "")]
        if missing:
            raise AIReviewerAuditError(f"model_evaluations {index} is missing: {', '.join(missing)}")
        run_id = str(raw["run_id"])
        if not re.fullmatch(r"[0-9a-f]{64}", str(raw["prompt_sha256"]), re.I):
            raise AIReviewerAuditError(f"model_evaluations {index} prompt_sha256 must be a SHA-256 digest")
        if run_id in run_ids or str(raw["input_sha256"]) != manuscript_sha256:
            raise AIReviewerAuditError(f"model_evaluations {index} has a duplicate run or unbound manuscript hash")
        try:
            score, lower, upper = float(raw["score"]), float(raw["scale_min"]), float(raw["scale_max"])
        except (TypeError, ValueError) as exc:
            raise AIReviewerAuditError(f"model_evaluations {index} score scale must be numeric") from exc
        if not lower < upper or not lower <= score <= upper:
            raise AIReviewerAuditError(f"model_evaluations {index} score is outside its declared scale")
        run_ids.add(run_id)
        normalized.append({
            "run_id": run_id,
            "model_id": str(raw["model_id"]),
            "prompt_sha256": str(raw["prompt_sha256"]),
            "input_sha256": manuscript_sha256,
            "score": score,
            "scale_min": lower,
            "scale_max": upper,
            "normalized_score": (score - lower) / (upper - lower),
        })
    scores = [item["normalized_score"] for item in normalized]
    return {
        "status": "OBSERVED",
        "runs": normalized,
        "normalized_min": min(scores),
        "normalized_max": max(scores),
        "normalized_spread": max(scores) - min(scores),
        "models": sorted({item["model_id"] for item in normalized}),
        "prompts": sorted({item["prompt_sha256"] for item in normalized}),
        "conclusion_boundary": "Observed score spread is sensitivity evidence only, not an acceptance probability or a manuscript-quality estimate.",
    }


def audit_ai_reviewer_robustness(
    root: str | os.PathLike[str],
    audit_id: str,
    *,
    manuscript_files: list[str] | None,
    online_evidence: list[dict[str, Any]] | None,
    model_evaluations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    identifier = _safe_id(audit_id)
    if _state_path(base, identifier).exists():
        raise AIReviewerAuditError("AI-reviewer audits are append-only; use a versioned audit_id")
    tracked, text = _read_manuscripts(base, manuscript_files)
    registry_payload, registry = _load_registry()
    sources = _fresh_evidence(online_evidence, registry)
    manuscript_sha256 = _hash(tracked)

    hard_failures, review_flags = _manipulation_findings(text)

    title_match = TITLE_LINE.search(text)
    title = " ".join(title_match.group(1).split()) if title_match else None
    if title:
        review_flags.append({
            "type": "title_presentation_sensitivity",
            "title": title[:300],
            "colon": ":" in title or "：" in title,
            "interrogative": title.rstrip().endswith(("?", "？")),
            "action": "keep the title truthful, specific, and venue-compliant; do not change punctuation or branding to raise an AI score",
        })

    critical_hits = len(CRITICAL_TOPIC.findall(text))
    metadata_hits = len(PRESTIGE_METADATA.findall(text))
    critical_topic = {
        "status": "EXPOSED" if critical_hits else "NOT_DETECTED",
        "signal_count": critical_hits,
        "required_action": "Preserve evidence-bounded limitations, risks, ethics, negative results, and criticism. Review for unfair score sensitivity; never delete them to appease an AI reviewer.",
    }
    metadata = {
        "status": "EXPOSED" if metadata_hits else "NOT_DETECTED",
        "signal_count": metadata_hits,
        "required_action": "Use blinded metadata where the venue protocol permits. Never alter identity or prestige signals to obtain a score advantage.",
    }
    model_sensitivity = _model_sensitivity(model_evaluations, manuscript_sha256)
    result = {
        "schema_version": 1,
        "status": "FAIL" if hard_failures else "PASS",
        "audit_id": identifier,
        "checked_at": utc_now(),
        "manuscript_files": tracked,
        "manuscript_sha256": manuscript_sha256,
        "registry_sha256": _hash(registry_payload),
        "sources": sources,
        "manipulation_integrity": {
            "status": "FAIL" if hard_failures else "PASS",
            "hard_failures": hard_failures,
            "review_flags": review_flags,
        },
        "presentation_sensitivity": {
            "status": "OBSERVED" if title else "NOT_TESTED",
            "title_observation": next((item for item in review_flags if item["type"] == "title_presentation_sensitivity"), None),
        },
        "critical_topic_fairness": critical_topic,
        "metadata_bias_exposure": metadata,
        "model_specificity": model_sensitivity,
        "prohibited_actions": [
            "prompt injection or hidden reviewer instructions",
            "score-targeted paraphrase generation, ranking, or selection",
            "keyword stuffing or prestige signaling",
            "deleting limitations, ethics, risks, negative results, or criticism to improve an AI score",
            "reporting an AI-reviewer score as an acceptance probability",
        ],
        "conclusion_boundary": "PASS means no prohibited reviewer manipulation was detected in the hash-bound text under this audit and the evidence registry was freshly verified. It does not predict acceptance, prove manuscript quality, or prove fairness of any reviewer.",
    }
    result["receipt_sha256"] = _hash(result)
    _atomic_json(_state_path(base, identifier), result)
    return result


def _save_optimization(path: Path, state: dict[str, Any]) -> dict[str, Any]:
    unsigned = {key: value for key, value in state.items() if key != "state_sha256"}
    state["state_sha256"] = _hash(unsigned)
    _atomic_json(path, state)
    return state


def _load_optimization(root: Path, optimization_id: str) -> tuple[Path, dict[str, Any]]:
    path = _optimization_path(root, optimization_id)
    if not path.is_file() or path.is_symlink():
        raise AIReviewerAuditError("AI-reviewer optimization has not been planned")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AIReviewerAuditError(f"AI-reviewer optimization state is invalid: {exc}") from exc
    saved = state.get("state_sha256")
    unsigned = {key: value for key, value in state.items() if key != "state_sha256"}
    if saved != _hash(unsigned):
        raise AIReviewerAuditError("AI-reviewer optimization state integrity check failed")
    return path, state


def plan_ai_reviewer_optimization(
    root: str | os.PathLike[str],
    optimization_id: str,
    *,
    manuscript_files: list[str] | None,
    online_evidence: list[dict[str, Any]] | None,
    venue_reviewer_contract: dict[str, Any] | None,
    selected_by: str,
    optimization_goal: str = "maximize_ai_reviewer_score",
) -> dict[str, Any]:
    """Create an explicit, user-selected plan for score-aware AI-reviewer adaptation."""
    base = Path(root).expanduser().resolve()
    identifier = _safe_id(optimization_id)
    path = _optimization_path(base, identifier)
    if path.exists():
        raise AIReviewerAuditError("AI-reviewer optimizations are append-only; use a versioned optimization_id")
    if selected_by != "user":
        raise AIReviewerAuditError("active AI-reviewer optimization is optional and requires selected_by=user")
    if optimization_goal != "maximize_ai_reviewer_score":
        raise AIReviewerAuditError("optimization_goal must be maximize_ai_reviewer_score")
    tracked, text = _read_manuscripts(base, manuscript_files)
    hard_failures, review_flags = _manipulation_findings(text)
    if hard_failures:
        raise AIReviewerAuditError("baseline manuscript contains prohibited reviewer manipulation")
    registry_payload, registry = _load_registry()
    sources = _fresh_evidence(online_evidence, registry)
    optimization_sources = {"rhetoric-reward-hack-2026", "reviewer-guidelines-2026", "titletrap-2025"}
    missing_sources = sorted(optimization_sources - {item["source_id"] for item in sources})
    if missing_sources:
        raise AIReviewerAuditError(
            "active optimization requires freshly verified strategy evidence: " + ", ".join(missing_sources)
        )
    venue = _venue_reviewer_contract(venue_reviewer_contract)
    baseline = {
        "candidate_id": "baseline",
        "manuscript_files": tracked,
        "manuscript_sha256": _hash(tracked),
        "content_sha256": _content_sha256(tracked),
        "content_signature": _content_signature(text),
        "review_flags": review_flags,
        "revision_dimensions": [],
        "change_summary": "Unmodified baseline manuscript.",
    }
    state = {
        "schema_version": 1,
        "status": "READY_FOR_CANDIDATES",
        "optimization_id": identifier,
        "mode": "active_ai_reviewer_adaptation",
        "selected_by": "user",
        "optimization_goal": optimization_goal,
        "planned_at": utc_now(),
        "registry_sha256": _hash(registry_payload),
        "sources": sources,
        "venue_reviewer_contract": venue,
        "baseline": baseline,
        "strategy_priorities": [
            {
                "dimension": "evidence_framing", "priority": "high",
                "action": "Move exact evidence, uncertainty, and result qualifiers next to each evaluated claim; make support easy to locate.",
                "evidence_source_ids": ["rhetoric-reward-hack-2026", "reviewer-guidelines-2026"],
            },
            {
                "dimension": "novelty_stance", "priority": "high",
                "action": "State the contribution and nearest-prior-work difference explicitly and early, without widening the registered novelty claim.",
                "evidence_source_ids": ["rhetoric-reward-hack-2026"],
            },
            {
                "dimension": "scope_framing", "priority": "medium",
                "action": "Make the supported scope and excluded generalizations explicit so the reviewer can map claims to the venue rubric.",
                "evidence_source_ids": ["rhetoric-reward-hack-2026"],
            },
            {
                "dimension": "title_presentation", "priority": "experimental",
                "action": "Test a truthful branded-colon and a plain descriptive title; keep only gains that transfer across the registered reviewer panel.",
                "evidence_source_ids": ["titletrap-2025"],
            },
            {
                "dimension": "reviewer_navigation", "priority": "medium",
                "action": "Use official reviewer criteria as navigation labels and evidence checkpoints, while retaining holistic prose rather than rubric stuffing.",
                "evidence_source_ids": ["reviewer-guidelines-2026"],
            },
        ],
        "candidate_policy": {
            "batch_size": {"minimum": 1, "maximum": 8},
            "allowed_dimensions": sorted(OPTIMIZATION_DIMENSIONS),
            "selection_rule": "robust_lcb = cross-panel normalized mean - 0.5 * population standard deviation",
            "same_panel_required": True,
            "minimum_distinct_models": 2,
            "unbounded_research_rounds": "Use a new versioned optimization_id for another batch; stop by user budget or lack of robust gain, not an arbitrary wall-clock limit.",
        },
        "integrity_constraints": {
            "citations_preserved": True,
            "numbers_preserved": True,
            "formulas_preserved": True,
            "limitations_ethics_risks_negative_results_preserved": True,
            "hidden_instructions_forbidden": True,
            "fabricated_prestige_forbidden": True,
        },
        "candidates": [],
        "evaluation_contract": None,
        "selection": None,
    }
    return _save_optimization(path, state)


def register_ai_reviewer_candidates(
    root: str | os.PathLike[str], optimization_id: str, *, candidates: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    identifier = _safe_id(optimization_id)
    path, state = _load_optimization(base, identifier)
    if state.get("status") != "READY_FOR_CANDIDATES":
        raise AIReviewerAuditError("candidate registration requires READY_FOR_CANDIDATES state")
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 8:
        raise AIReviewerAuditError("candidate_manuscripts must contain one to eight candidates")
    baseline_signature = state["baseline"]["content_signature"]
    normalized: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, raw in enumerate(candidates):
        if not isinstance(raw, dict):
            raise AIReviewerAuditError(f"candidate {index} must be an object")
        candidate_id = str(raw.get("candidate_id") or "").strip().lower()
        if candidate_id == "baseline" or not AUDIT_ID.fullmatch(candidate_id) or candidate_id in ids:
            raise AIReviewerAuditError(f"candidate {index} has an invalid or duplicate candidate_id")
        tracked, text = _read_manuscripts(base, raw.get("manuscript_files"))
        hard_failures, review_flags = _manipulation_findings(text)
        if hard_failures:
            raise AIReviewerAuditError(f"candidate {candidate_id} contains prohibited reviewer manipulation")
        signature = _content_signature(text)
        changed_invariants = [
            key for key in ("citations", "numbers", "formulas", "protected_critical_paragraphs")
            if signature[key] != baseline_signature[key]
        ]
        if changed_invariants:
            raise AIReviewerAuditError(
                f"candidate {candidate_id} changed protected content: {', '.join(changed_invariants)}"
            )
        dimensions = [str(value).strip() for value in raw.get("revision_dimensions") or []]
        if not dimensions or len(dimensions) != len(set(dimensions)) or set(dimensions) - OPTIMIZATION_DIMENSIONS:
            raise AIReviewerAuditError(f"candidate {candidate_id} has invalid revision_dimensions")
        summary = " ".join(str(raw.get("change_summary") or "").split())
        if len(summary) < 12:
            raise AIReviewerAuditError(f"candidate {candidate_id} requires a concrete change_summary")
        manuscript_sha256 = _hash(tracked)
        content_sha256 = _content_sha256(tracked)
        if content_sha256 == state["baseline"]["content_sha256"]:
            raise AIReviewerAuditError(f"candidate {candidate_id} is byte-identical to the baseline content")
        ids.add(candidate_id)
        normalized.append({
            "candidate_id": candidate_id,
            "manuscript_files": tracked,
            "manuscript_sha256": manuscript_sha256,
            "content_sha256": content_sha256,
            "content_signature": signature,
            "review_flags": review_flags,
            "revision_dimensions": dimensions,
            "change_summary": summary,
        })
    all_candidates = [state["baseline"], *normalized]
    state["candidates"] = normalized
    state["evaluation_contract"] = {
        "rubric_sha256": state["venue_reviewer_contract"]["contract_sha256"],
        "criteria": state["venue_reviewer_contract"]["criteria"],
        "candidate_inputs": [
            {"candidate_id": item["candidate_id"], "input_sha256": item["manuscript_sha256"]}
            for item in all_candidates
        ],
        "required_fields": [
            "run_id", "candidate_id", "model_id", "prompt_sha256", "rubric_sha256",
            "input_sha256", "score", "scale_min", "scale_max", "dimensions",
            "meaning_preserved", "evidence_preserved", "review_text_sha256",
        ],
        "same_panel_for_every_candidate": True,
        "minimum_distinct_models": 2,
    }
    state["status"] = "READY_FOR_EVALUATION"
    return _save_optimization(path, state)


def select_ai_reviewer_candidate(
    root: str | os.PathLike[str], optimization_id: str, *, model_evaluations: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    identifier = _safe_id(optimization_id)
    path, state = _load_optimization(base, identifier)
    if state.get("status") != "READY_FOR_EVALUATION":
        raise AIReviewerAuditError("candidate selection requires READY_FOR_EVALUATION state")
    candidates = {item["candidate_id"]: item for item in [state["baseline"], *state["candidates"]]}
    for candidate_id, candidate in candidates.items():
        for item in candidate.get("manuscript_files") or []:
            manuscript_path = base / str(item.get("path") or "")
            if not manuscript_path.is_file() or _sha256(manuscript_path) != item.get("sha256"):
                raise AIReviewerAuditError(
                    f"candidate {candidate_id} changed after registration; regenerate its evaluations"
                )
    if not isinstance(model_evaluations, list) or not model_evaluations:
        raise AIReviewerAuditError("optimization_model_evaluations are required")
    rubric_sha256 = state["venue_reviewer_contract"]["contract_sha256"]
    criteria = {item["criterion_id"]: item for item in state["venue_reviewer_contract"]["criteria"]}
    grouped: dict[str, list[dict[str, Any]]] = {candidate_id: [] for candidate_id in candidates}
    run_ids: set[str] = set()
    for index, raw in enumerate(model_evaluations):
        if not isinstance(raw, dict):
            raise AIReviewerAuditError(f"optimization evaluation {index} must be an object")
        required = state["evaluation_contract"]["required_fields"]
        missing = [key for key in required if raw.get(key) in (None, "", {})]
        if missing:
            raise AIReviewerAuditError(f"optimization evaluation {index} is missing: {', '.join(missing)}")
        candidate_id = str(raw["candidate_id"])
        if candidate_id not in candidates:
            raise AIReviewerAuditError(f"optimization evaluation {index} has an unknown candidate_id")
        run_id = str(raw["run_id"])
        if run_id in run_ids:
            raise AIReviewerAuditError(f"optimization evaluation {index} has a duplicate run_id")
        for digest_key in ("prompt_sha256", "review_text_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", str(raw[digest_key]), re.I):
                raise AIReviewerAuditError(f"optimization evaluation {index} {digest_key} must be a SHA-256 digest")
        if raw["rubric_sha256"] != rubric_sha256 or raw["input_sha256"] != candidates[candidate_id]["manuscript_sha256"]:
            raise AIReviewerAuditError(f"optimization evaluation {index} is not bound to the registered rubric and candidate")
        if raw["meaning_preserved"] is not True or raw["evidence_preserved"] is not True:
            raise AIReviewerAuditError(f"optimization evaluation {index} failed meaning/evidence preservation")
        try:
            score, lower, upper = float(raw["score"]), float(raw["scale_min"]), float(raw["scale_max"])
        except (TypeError, ValueError) as exc:
            raise AIReviewerAuditError(f"optimization evaluation {index} score scale must be numeric") from exc
        if not lower < upper or not lower <= score <= upper:
            raise AIReviewerAuditError(f"optimization evaluation {index} score is outside its declared scale")
        dimensions = raw["dimensions"]
        if not isinstance(dimensions, dict) or set(dimensions) != set(criteria):
            raise AIReviewerAuditError(f"optimization evaluation {index} dimensions do not match the official venue rubric")
        normalized_dimensions: dict[str, float] = {}
        for criterion_id, value in dimensions.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError) as exc:
                raise AIReviewerAuditError(f"optimization evaluation {index} dimension {criterion_id} is not numeric") from exc
            if not lower <= numeric <= upper:
                raise AIReviewerAuditError(f"optimization evaluation {index} dimension {criterion_id} is outside the declared scale")
            normalized_dimensions[criterion_id] = (numeric - lower) / (upper - lower)
        run_ids.add(run_id)
        grouped[candidate_id].append({
            "run_id": run_id,
            "candidate_id": candidate_id,
            "model_id": str(raw["model_id"]),
            "prompt_sha256": str(raw["prompt_sha256"]),
            "rubric_sha256": rubric_sha256,
            "input_sha256": str(raw["input_sha256"]),
            "review_text_sha256": str(raw["review_text_sha256"]),
            "score": score,
            "scale_min": lower,
            "scale_max": upper,
            "normalized_score": (score - lower) / (upper - lower),
            "dimensions": normalized_dimensions,
            "meaning_preserved": True,
            "evidence_preserved": True,
        })
    panel_sets: dict[str, set[tuple[str, str, float, float]]] = {}
    for candidate_id, evaluations in grouped.items():
        if not evaluations:
            raise AIReviewerAuditError(f"candidate {candidate_id} has no model evaluations")
        panel_slots = [
            (item["model_id"], item["prompt_sha256"], item["scale_min"], item["scale_max"])
            for item in evaluations
        ]
        if len(panel_slots) != len(set(panel_slots)):
            raise AIReviewerAuditError(
                f"candidate {candidate_id} has duplicate model/prompt panel slots"
            )
        panel_sets[candidate_id] = set(panel_slots)
    baseline_panel = panel_sets["baseline"]
    if len({item[0] for item in baseline_panel}) < 2:
        raise AIReviewerAuditError("AI-reviewer optimization requires at least two distinct reviewer models")
    mismatched = [candidate_id for candidate_id, panel in panel_sets.items() if panel != baseline_panel]
    if mismatched:
        raise AIReviewerAuditError("every candidate must be evaluated by the same model/prompt panel: " + ", ".join(mismatched))

    rankings: list[dict[str, Any]] = []
    for candidate_id, evaluations in grouped.items():
        values = [item["normalized_score"] for item in evaluations]
        mean = statistics.fmean(values)
        spread = statistics.pstdev(values)
        dimension_means = {
            criterion_id: statistics.fmean(item["dimensions"][criterion_id] for item in evaluations)
            for criterion_id in criteria
        }
        weighted_rubric = sum(
            dimension_means[criterion_id] * criteria[criterion_id]["normalized_weight"]
            for criterion_id in criteria
        )
        rankings.append({
            "candidate_id": candidate_id,
            "normalized_mean": mean,
            "normalized_standard_deviation": spread,
            "robust_lcb": mean - 0.5 * spread,
            "worst_panel_score": min(values),
            "weighted_rubric_score": weighted_rubric,
            "dimension_means": dimension_means,
            "evaluation_count": len(evaluations),
            "revision_dimensions": candidates[candidate_id]["revision_dimensions"],
        })
    rankings.sort(
        key=lambda item: (item["robust_lcb"], item["weighted_rubric_score"], item["worst_panel_score"], -len(item["revision_dimensions"])),
        reverse=True,
    )
    baseline_result = next(item for item in rankings if item["candidate_id"] == "baseline")
    selected = rankings[0]
    improvement = selected["robust_lcb"] - baseline_result["robust_lcb"]
    selected_candidate = candidates[selected["candidate_id"]]
    result_status = "SELECTED" if selected["candidate_id"] != "baseline" and improvement > 0 else "NO_ROBUST_IMPROVEMENT"
    selection = {
        "status": result_status,
        "selected_candidate_id": selected["candidate_id"],
        "selected_candidate_content_sha256": selected_candidate["content_sha256"],
        "robust_improvement_over_baseline": improvement,
        "selection_rule": state["candidate_policy"]["selection_rule"],
        "rankings": rankings,
        "model_evaluations": [item for candidate_id in sorted(grouped) for item in grouped[candidate_id]],
        "next_iteration": (
            "Apply the selected candidate, rerun novelty/citation/language/formula/figure gates, and use a new versioned optimization_id only if useful work remains."
            if result_status == "SELECTED" else
            "Keep the baseline or generate a new evidence-bounded batch; do not continue merely to chase one model's score."
        ),
        "claim_boundary": "This is an explicit score-aware adaptation to the registered AI-reviewer panel. It is not an acceptance probability and may not transfer to other models, prompts, venues, or human reviewers.",
    }
    selection["receipt_sha256"] = _hash(selection)
    state["status"] = result_status
    state["selected_at"] = utc_now()
    state["selection"] = selection
    return _save_optimization(path, state)


def get_ai_reviewer_optimization_status(root: str | os.PathLike[str], optimization_id: str) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    identifier = _safe_id(optimization_id)
    path = _optimization_path(base, identifier)
    if not path.is_file() or path.is_symlink():
        return {"status": "NOT_FOUND", "optimization_id": identifier}
    _path, state = _load_optimization(base, identifier)
    changes: list[str] = []
    for candidate in [state.get("baseline") or {}, *(state.get("candidates") or [])]:
        for item in candidate.get("manuscript_files") or []:
            file_path = base / str(item.get("path") or "")
            if not file_path.is_file() or _sha256(file_path) != item.get("sha256"):
                changes.append(str(item.get("path") or "<missing>"))
    registry_payload, _registry = _load_registry()
    if state.get("registry_sha256") != _hash(registry_payload):
        changes.append("AI-reviewer evidence registry")
    try:
        _fresh_timestamp((state.get("venue_reviewer_contract") or {}).get("verified_at"), "venue reviewer evidence")
        for item in state.get("sources") or []:
            _fresh_timestamp(item.get("accessed_at"), "AI-reviewer online evidence")
    except AIReviewerAuditError as exc:
        changes.append(str(exc))
    if changes:
        return {**state, "status": "AUDIT_REQUIRED", "reason": "optimization inputs changed: " + ", ".join(sorted(set(changes)))}
    return state


def get_ai_reviewer_robustness_status(root: str | os.PathLike[str], audit_id: str) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    identifier = _safe_id(audit_id)
    path = _state_path(base, identifier)
    if not path.is_file() or path.is_symlink():
        return {"status": "NOT_FOUND", "audit_id": identifier}
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AIReviewerAuditError(f"AI-reviewer audit state is invalid: {exc}") from exc
    saved = result.get("receipt_sha256")
    unsigned = {key: value for key, value in result.items() if key != "receipt_sha256"}
    if saved != _hash(unsigned):
        raise AIReviewerAuditError("AI-reviewer audit receipt integrity check failed")
    changes = []
    for item in result.get("manuscript_files", []):
        candidate = base / str(item.get("path") or "")
        if not candidate.is_file() or _sha256(candidate) != item.get("sha256"):
            changes.append(str(item.get("path") or "<missing>"))
    registry_payload, _registry = _load_registry()
    if result.get("registry_sha256") != _hash(registry_payload):
        changes.append("AI-reviewer evidence registry")
    now = dt.datetime.now(dt.timezone.utc)
    for source in result.get("sources", []):
        try:
            accessed = dt.datetime.fromisoformat(str(source.get("accessed_at") or "").replace("Z", "+00:00"))
        except ValueError:
            changes.append("AI-reviewer evidence timestamp")
            continue
        if accessed.tzinfo is None:
            accessed = accessed.replace(tzinfo=dt.timezone.utc)
        if now - accessed.astimezone(dt.timezone.utc) > dt.timedelta(days=30):
            changes.append("stale AI-reviewer online evidence")
    if changes:
        return {
            **result,
            "status": "AUDIT_REQUIRED",
            "reason": "audit inputs changed: " + ", ".join(sorted(set(changes))),
        }
    return result
