from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
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
