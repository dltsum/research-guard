from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from venue_evidence_core import verify_venue_receipt


class LanguageError(ValueError):
    pass


TEXT_SUFFIXES = {".tex", ".md", ".markdown", ".txt", ".rst", ".qmd"}
HEDGE_TERM = re.compile(
    r"\b(?:may|might|could|perhaps|possibly|potentially|apparently|seem(?:s|ed)?|suggest(?:s|ed)?)\b|"
    r"可能|或许|也许|似乎|大概",
    re.IGNORECASE,
)
MATERIAL_LIMITATION = re.compile(
    r"\b(?:limitation|limited\s+to|sample\b.{0,40}\bonly|does\s+not\s+generalize|"
    r"not\s+apply|out[- ]of[- ]sample|external\s+validity)\b|"
    r"局限|仅限于|样本外|不适用于|外部有效性|仅.{0,20}样本",
    re.IGNORECASE,
)
REQUIRED_DISCLOSURE = re.compile(
    r"\b(?:institutional\s+review\s+board|ethics?\s+(?:approval|committee)|informed\s+consent|"
    r"conflicts?\s+of\s+interest|competing\s+interests?|data\s+availability|license)\b|"
    r"伦理(?:审批|委员会)|知情同意|利益冲突|数据可用性|许可证",
    re.IGNORECASE,
)
HUMAN_DISCLOSURE = re.compile(
    r"\b(?:institutional\s+review\s+board|IRB|ethics?\s+(?:approval|committee)|informed\s+consent)\b|"
    r"伦理(?:审批|委员会)|知情同意",
    re.IGNORECASE,
)
HUMAN_ETHICS_CONTEXT = re.compile(
    r"\b(?:participants?|patients?|human\s+subjects?|interviews?|surveys?|medical\s+records?|"
    r"personal\s+data|personally\s+identifiable|clinical\s+(?:study|trial|data))\b|"
    r"参与者|受试者|患者|人体研究|访谈|问卷|医疗记录|病历|个人数据|个人信息|临床(?:研究|试验|数据)",
    re.IGNORECASE,
)
ANIMAL_ETHICS_CONTEXT = re.compile(
    r"\b(?:animal\s+study|laboratory\s+animals?|mice|mouse|rats?|zebrafish|nonhuman\s+primates?)\b|"
    r"动物实验|实验动物|小鼠|大鼠|斑马鱼|非人灵长类",
    re.IGNORECASE,
)
ANIMAL_DISCLOSURE = re.compile(
    r"\b(?:institutional\s+animal\s+care|IACUC|animal\s+ethics|animal\s+welfare)\b|"
    r"动物伦理|实验动物福利|动物实验伦理",
    re.IGNORECASE,
)
IMAGINED_CRITIC = re.compile(
    r"\b(?:to\s+avoid\s+misunderstanding|for\s+the\s+avoidance\s+of\s+doubt|we\s+do\s+not\s+claim\s+that)\b|"
    r"为避免误解|避免产生误解|我们并非声称|我们不声称",
    re.IGNORECASE,
)
DISCLAIMER_FIRST = re.compile(
    r"^\s*(?:it\s+should\s+be\s+noted\s+that|we\s+(?:must\s+)?emphasize\s+that|"
    r"需要指出的是|值得注意的是|必须说明的是)",
    re.IGNORECASE,
)
INTERNAL_PROCESS = re.compile(
    r"\b(?:in\s+response\s+to\s+the\s+reviewer|we\s+carefully\s+considered\s+the\s+reviewer|"
    r"to\s+address\s+the\s+reviewer's\s+concern)\b|"
    r"为回应审稿人|考虑到审稿人的意见|为了避免审稿人",
    re.IGNORECASE,
)
GENERIC_THROAT_CLEARING = re.compile(
    r"^\s*(?:it\s+is\s+(?:well\s+)?known\s+that|there\s+(?:are|has\s+been)\s+many\s+studies|"
    r"in\s+recent\s+years.{0,60}(?:attention|interest)|众所周知|近年来.{0,30}(?:广泛关注|大量研究))",
    re.IGNORECASE,
)
ASSISTANT_PROCESS_RESIDUE = re.compile(
    r"\b(?:as\s+of\s+my\s+knowledge\s+cutoff|i\s+hope\s+this\s+helps|"
    r"as\s+an\s+ai(?:\s+language\s+model)?|i\s+cannot\s+browse\s+the\s+internet)\b|"
    r"截至我的知识截止|希望这对你有帮助|作为(?:一个)?AI(?:语言模型)?|我无法浏览互联网",
    re.IGNORECASE,
)
VAGUE_PROMOTIONAL_ATTRIBUTION = re.compile(
    r"\b(?:some|many|various)\s+(?:researchers?|experts?|observers?)\s+(?:say|argue|believe|claim).{0,100}"
    r"(?:pivotal\s+moment|groundbreaking|transformative|remarkable|major\s+breakthrough)\b|"
    r"(?:一些|许多|众多)(?:研究者|专家|观察人士)(?:认为|声称|表示).{0,50}(?:里程碑|开创性|变革性|重大突破)",
    re.IGNORECASE,
)
NUMBER_TOKEN = re.compile(r"(?<![\d.])[-+]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)\s*(?:%|％)?")
BRACKET_CITATION = re.compile(r"\[(?:\d+(?:\s*[-,]\s*\d+)*)\]")
LATEX_CITATION = re.compile(r"\\cite[a-zA-Z*]*\{[^}]+\}")
PANDOC_CITATION = re.compile(r"(?<![\w.-])@[A-Za-z0-9_:.+-]+")
URL_TOKEN = re.compile(r"https://[^\s<>\]\[{}()]+")
BACKTICK_IDENTIFIER = re.compile(r"`([A-Za-z_][A-Za-z0-9_.:-]*)`")
LATEX_REFERENCE = re.compile(r"\\(?:ref|eqref|autoref|cref|Cref)\{([^}]+)\}")
LATEX_LABEL = re.compile(r"\\label\{([^}]+)\}")
NEGATION_EN = re.compile(r"\b(?:not|no|never|without|cannot|can't|doesn't|didn't|isn't|aren't|won't)\b", re.IGNORECASE)
NEGATION_ZH = re.compile(r"不|未|无|没有|并非|不能|无法|不得|从未")
CAUSAL_EN = re.compile(r"\b(?:because|due\s+to|therefore|thus|hence|consequently|results?\s+in|causes?)\b", re.IGNORECASE)
CAUSAL_ZH = re.compile(r"因为|由于|因此|所以|从而|导致|造成")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _state_path(root: str | os.PathLike[str]) -> Path:
    return Path(root).expanduser().resolve() / ".research-guard" / "language-state.json"


def _cards_path(root: str | os.PathLike[str]) -> Path:
    return Path(root).expanduser().resolve() / ".research-guard" / "rhetorical-cards.json"


def _project_fingerprint(root: Path) -> str:
    return hashlib.sha256(str(root).casefold().encode("utf-8")).hexdigest()


def _load_state(root: str | os.PathLike[str]) -> dict[str, Any]:
    path = _state_path(root)
    if not path.is_file():
        raise LanguageError("language review has not been planned")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LanguageError(f"language review state is invalid: {exc}") from exc
    if not isinstance(state, dict):
        raise LanguageError("language review state must be an object")
    return state


def _track_files(root: Path, values: list[str] | None) -> list[dict[str, str]]:
    tracked: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in values or []:
        candidate = Path(raw)
        path = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise LanguageError(f"manuscript file must stay inside project_root: {raw}") from exc
        if relative in seen:
            raise LanguageError(f"duplicate manuscript file: {relative}")
        if not path.is_file():
            raise LanguageError(f"manuscript file does not exist: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES:
            raise LanguageError(f"language review requires a UTF-8 text manuscript: {relative}")
        try:
            path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise LanguageError(f"language review cannot read UTF-8 manuscript: {relative}") from exc
        seen.add(relative)
        tracked.append({"path": relative, "sha256": _sha256(path), "kind": "manuscript"})
    return sorted(tracked, key=lambda item: item["path"])


def _source_texts(
    root: Path,
    state: dict[str, Any],
    draft_text: str | None,
    source_text: str | None = None,
) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    for item in state.get("tracked_files", []):
        path = root / item["path"]
        if not path.is_file() or _sha256(path) != item["sha256"]:
            raise LanguageError(f"tracked manuscript changed; replan language review: {item['path']}")
        sources.append((item["path"], path.read_text(encoding="utf-8")))
    expected_inline = state.get("inline_text_sha256")
    if expected_inline:
        if draft_text is None:
            raise LanguageError("the hash-bound draft_text must be supplied for analysis")
        actual = hashlib.sha256(str(draft_text).encode("utf-8")).hexdigest()
        if actual != expected_inline:
            raise LanguageError("draft_text changed; replan language review")
        sources.append(("<inline>", str(draft_text)))
    elif draft_text is not None:
        raise LanguageError("draft_text was not hash-bound during planning")
    expected_source = state.get("source_text_sha256")
    if expected_source:
        if source_text is None:
            raise LanguageError("the hash-bound translation source_text must be supplied for analysis")
        actual = hashlib.sha256(str(source_text).encode("utf-8")).hexdigest()
        if actual != expected_source:
            raise LanguageError("translation source_text changed; replan language review")
    elif source_text is not None:
        raise LanguageError("source_text was not hash-bound during planning")
    if not sources:
        raise LanguageError("language review needs a manuscript file or draft_text")
    return sources


def _normalize_protected(values: Any, combined_text: str) -> list[dict[str, str]]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise LanguageError("protected_spans must be an array")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(values):
        if not isinstance(raw, dict):
            raise LanguageError(f"protected span {index} must be an object")
        text = str(raw.get("text") or "").strip()
        reason = str(raw.get("reason") or "").strip()
        if not text or len(reason) < 8:
            raise LanguageError(f"protected span {index} needs text and a concrete reason")
        if text not in combined_text:
            raise LanguageError(f"protected span is absent from the hash-bound manuscript: {text}")
        if text in seen:
            raise LanguageError(f"duplicate protected span: {text}")
        seen.add(text)
        result.append({"text": text, "reason": reason})
    return result


def _normalize_terminology(values: Any, source_text: str, target_text: str) -> list[dict[str, str]]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise LanguageError("terminology must be an array")
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(values):
        if not isinstance(raw, dict):
            raise LanguageError(f"terminology item {index} must be an object")
        source_term = str(raw.get("source_term") or "").strip()
        target_term = str(raw.get("target_term") or "").strip()
        if not source_term or not target_term:
            raise LanguageError(f"terminology item {index} requires source_term and target_term")
        if source_term.casefold() not in source_text.casefold():
            raise LanguageError(f"terminology source term is absent from source_text: {source_term}")
        key = (source_term.casefold(), target_term.casefold())
        if key in seen:
            raise LanguageError(f"duplicate terminology item: {source_term} -> {target_term}")
        seen.add(key)
        result.append({"source_term": source_term, "target_term": target_term})
    return result


def _normalize_venue_contract(value: Any, task_mode: str) -> dict[str, Any] | None:
    if task_mode != "conference_writing":
        if value not in (None, {}):
            raise LanguageError("venue_contract is only valid for task_mode=conference_writing")
        return None
    if value is None:
        return None
    if not isinstance(value, dict):
        raise LanguageError("venue_contract must be an object")
    required = ("venue_name", "policy_url", "template_url", "verified_at", "source_type", "status")
    missing = [field for field in required if not str(value.get(field) or "").strip()]
    if missing:
        raise LanguageError(f"venue_contract is missing: {', '.join(missing)}")
    normalized = {field: str(value[field]).strip() for field in required}
    normalized["policy_url"] = _https_url(normalized["policy_url"], "venue policy")
    normalized["template_url"] = _https_url(normalized["template_url"], "venue template")
    if normalized["source_type"].casefold() != "official":
        raise LanguageError("venue_contract source_type must be official")
    if normalized["status"].casefold() != "verified":
        raise LanguageError("venue_contract status must be verified")
    try:
        verified = dt.datetime.fromisoformat(normalized["verified_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise LanguageError("venue_contract verified_at must be an ISO-8601 date or timestamp") from exc
    if verified.tzinfo is None:
        verified = verified.replace(tzinfo=dt.timezone.utc)
    now = dt.datetime.now(dt.timezone.utc)
    if verified > now + dt.timedelta(days=1):
        raise LanguageError("venue_contract verified_at is in the future")
    if now - verified > dt.timedelta(days=180):
        raise LanguageError("venue_contract is stale; reverify the official policy and template")
    sections = value.get("required_sections", [])
    if not isinstance(sections, list) or any(not str(item).strip() for item in sections):
        raise LanguageError("venue_contract required_sections must be an array of non-empty strings")
    normalized["required_sections"] = [str(item).strip() for item in sections]
    normalized["verified_at"] = verified.isoformat()
    return normalized


def _normalized_number(value: str) -> str:
    return re.sub(r"\s+", "", str(value)).replace("％", "%")


def _translation_invariants(text: str) -> dict[str, list[str]]:
    citations = [*LATEX_CITATION.findall(text), *BRACKET_CITATION.findall(text), *PANDOC_CITATION.findall(text)]
    urls = [item.rstrip(".,;!?，。；：！？") for item in URL_TOKEN.findall(text)]
    return {
        "number": [_normalized_number(item) for item in NUMBER_TOKEN.findall(text)],
        "citation": [re.sub(r"\s+", "", item) for item in citations],
        "url": urls,
        "identifier": BACKTICK_IDENTIFIER.findall(text),
        "latex_reference": LATEX_REFERENCE.findall(text),
    }


def plan_language_review(
    root: str | os.PathLike[str],
    request_text: str,
    *,
    manuscript_files: list[str] | None = None,
    draft_text: str | None = None,
    claim_ids: list[str] | None = None,
    protected_spans: list[dict[str, Any]] | None = None,
    section: str | None = None,
    discipline: str | None = None,
    venue: str | None = None,
    language: str | None = None,
    task_mode: str = "academic_polish",
    source_text: str | None = None,
    source_language: str | None = None,
    target_language: str | None = None,
    terminology: list[dict[str, Any]] | None = None,
    venue_contract: dict[str, Any] | None = None,
    venue_year: int | None = None,
    venue_track: str = "main",
    venue_stage: str = "submission",
    venue_receipt_sha256: str | None = None,
) -> dict[str, Any]:
    if not str(request_text).strip():
        raise LanguageError("request_text is required")
    base = Path(root).expanduser().resolve()
    normalized_mode = str(task_mode or "academic_polish").strip().casefold()
    if normalized_mode not in {"academic_polish", "translation", "conference_writing"}:
        raise LanguageError("task_mode must be academic_polish, translation, or conference_writing")
    translation_source_text = None if source_text is None else str(source_text)
    tracked = _track_files(base, manuscript_files)
    if draft_text is None and not tracked:
        raise LanguageError("language review needs a manuscript file or draft_text")
    normalized_claims = [str(item).strip() for item in claim_ids or []]
    if any(not item for item in normalized_claims) or len(normalized_claims) != len(set(normalized_claims)):
        raise LanguageError("claim_ids must be unique non-empty identifiers")
    combined_text = "\n".join((base / item["path"]).read_text(encoding="utf-8") for item in tracked)
    if draft_text is not None:
        combined_text = f"{combined_text}\n{draft_text}"
    protected = _normalize_protected(protected_spans, combined_text)
    normalized_terms: list[dict[str, str]] = []
    source_invariants = None
    if normalized_mode == "translation":
        if not translation_source_text:
            raise LanguageError("translation requires source_text")
        if not str(source_language or "").strip() or not str(target_language or "").strip():
            raise LanguageError("translation requires source_language and target_language")
        if str(source_language).strip().casefold() == str(target_language).strip().casefold():
            raise LanguageError("translation source_language and target_language must differ")
        normalized_terms = _normalize_terminology(terminology, translation_source_text, combined_text)
        source_invariants = _translation_invariants(translation_source_text)
    elif any(value not in (None, [], "") for value in (translation_source_text, source_language, target_language, terminology)):
        raise LanguageError("translation fields require task_mode=translation")
    normalized_venue = _normalize_venue_contract(venue_contract, normalized_mode)
    venue_profile = None
    if normalized_mode == "conference_writing":
        if venue_receipt_sha256:
            venue_status = verify_venue_receipt(base, venue_receipt_sha256)
            if venue_status.get("status") != "PASS":
                raise LanguageError(
                    "conference writing requires an exact verified venue-evidence receipt; "
                    f"resolve or reacquire it first: {venue_status.get('reason')}"
                )
            profile = venue_status["profile"]
            requested_venue = str(venue or "").strip().casefold()
            aliases = {str(profile.get("venue") or "").casefold(), str(profile.get("display_name") or "").casefold()}
            if requested_venue and requested_venue not in aliases:
                raise LanguageError("resolved venue profile does not match the requested venue")
            if venue_year is not None and int(venue_year) != int(profile["year"]):
                raise LanguageError("resolved venue profile does not match venue_year")
            if str(venue_track or "main").casefold() != str(profile["track"]).casefold():
                raise LanguageError("resolved venue profile does not match venue_track")
            if str(venue_stage or "submission").casefold() != str(profile["stage"]).casefold():
                raise LanguageError("resolved venue profile does not match venue_stage")
            venue_profile = {
                "venue": profile["venue"], "display_name": profile.get("display_name"),
                "year": profile["year"], "track": profile["track"], "stage": profile["stage"],
                "policy_url": profile["policy_url"], "template_url": profile["template_url"],
                "required_sections": profile.get("required_sections", []),
                "layout_rules": profile.get("layout_rules", []),
                "observed_section_sequences": profile.get("observed_section_sequences", []),
                "narrative_evidence": profile.get("narrative_evidence"),
                "venue_receipt_sha256": venue_receipt_sha256,
            }
            normalized_venue = None
        elif normalized_venue is not None and (tracked or re.search(r"\\(?:sub)*section\*?\{|^#{1,6}\s+", combined_text, re.MULTILINE)):
            normalized_venue["provenance_scope"] = "audit_supplied_manuscript_only"
        else:
            raise LanguageError(
                "conference writing or outline generation requires venue_action=resolve and a verified "
                "venue_receipt_sha256; a free-form venue contract cannot authorize chapter names, layout, or narrative"
            )
    elif any(value not in (None, "") for value in (venue_year, venue_receipt_sha256)):
        raise LanguageError("venue evidence fields require task_mode=conference_writing")
    plan_payload = {
        "request_text": str(request_text).strip(),
        "tracked_files": tracked,
        "inline_text_sha256": hashlib.sha256(str(draft_text).encode("utf-8")).hexdigest() if draft_text is not None else None,
        "claim_ids": normalized_claims,
        "protected_spans": protected,
        "task_mode": normalized_mode,
        "source_text_sha256": (
            hashlib.sha256(translation_source_text.encode("utf-8")).hexdigest()
            if translation_source_text is not None else None
        ),
        "translation_invariants": source_invariants,
        "terminology": normalized_terms,
        "venue_contract": normalized_venue,
        "venue_profile": venue_profile,
        "context": {
            "section": str(section or "").strip() or None,
            "discipline": str(discipline or "").strip() or None,
            "venue": str(venue or "").strip() or None,
            "language": str(language or "").strip() or None,
            "source_language": str(source_language or "").strip() or None,
            "target_language": str(target_language or "").strip() or None,
        },
        "project_fingerprint": _project_fingerprint(base),
    }
    state = {
        "schema_version": 2,
        **plan_payload,
        "plan_hash": _digest(plan_payload),
        "planned_at": utc_now(),
        "status": "REVIEW_REQUIRED",
        "reason": "language analysis has not been completed",
        "findings": [],
        "analysis_hash": None,
        "resolutions": [],
        "decision_checklist": [],
        "decisions": [],
        "translation_check": None,
        "document_check": None,
        "retrieved_cards": [],
        "receipt": None,
    }
    _atomic_json(_state_path(base), state)
    return state


def _reviewable_lines(text: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    in_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence or stripped.startswith(">"):
            continue
        result.append((line_number, line))
    return result


def _sentences(text: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for line_number, line in _reviewable_lines(text):
        for segment in re.split(r"(?<=[.!?。！？])\s*", line):
            normalized = " ".join(segment.strip().split())
            if normalized:
                result.append((line_number, normalized))
    return result


def _is_meta_or_quoted(sentence: str) -> bool:
    stripped = sentence.strip()
    if not stripped:
        return True
    if stripped.startswith(('"', "'", "“", "‘")) and stripped.endswith(('"', "'", "”", "’")):
        return True
    return bool(re.search(
        r"\b(?:phrase|sentence|wording|expression|example|quotation|quoted)\b.{0,80}[\"“‘]|"
        r"(?:短语|句子|措辞|表达|例子|示例|引文|引用).{0,40}[\"“‘]",
        sentence,
        re.IGNORECASE,
    ))


def _issue(
    state: dict[str, Any], source: str, line: int, category: str, excerpt: str, *,
    blocking: bool, meaning_risk: bool, recommended_action: str, rationale: str,
    epistemic_status: str = "deterministic_textual_finding",
) -> dict[str, Any]:
    issue_id = "lang-" + hashlib.sha256(
        f"{state['plan_hash']}\n{source}\n{line}\n{category}\n{excerpt}".encode("utf-8")
    ).hexdigest()[:20]
    return {
        "issue_id": issue_id,
        "category": category,
        "source": source,
        "line": line,
        "excerpt": excerpt,
        "blocking": blocking,
        "meaning_risk": meaning_risk,
        "recommended_action": recommended_action,
        "rationale": rationale,
        "epistemic_status": epistemic_status,
    }


def _decision_item(
    state: dict[str, Any], source: str, line: int, kind: str, excerpt: str, *, rationale: str,
) -> dict[str, Any]:
    decision_id = "decision-" + hashlib.sha256(
        f"{state['plan_hash']}\n{source}\n{line}\n{kind}\n{excerpt}".encode("utf-8")
    ).hexdigest()[:20]
    if kind == "material_limitation":
        choices = [
            {"action": "retain_as_written", "effect": "Keep the scope boundary unchanged."},
            {"action": "revise_preserving_substance", "effect": "Edit for clarity without weakening the limitation; then replan."},
            {"action": "omit_with_justification", "effect": "Remove only after the user supplies a scientific justification and edits/replans."},
        ]
    else:
        choices = [
            {"action": "add_disclosure", "effect": "Add the applicable ethics disclosure and replan."},
            {"action": "not_applicable_with_justification", "effect": "Record why no disclosure applies."},
            {"action": "already_disclosed_at_locator", "effect": "Point to the existing disclosure for verification."},
        ]
    return {
        "decision_id": decision_id,
        "kind": kind,
        "source": source,
        "line": line,
        "excerpt": excerpt,
        "question": (
            "How should this material limitation be handled?"
            if kind == "material_limitation"
            else "Does this study context require an ethics or consent disclosure, and where is it satisfied?"
        ),
        "choices": choices,
        "selected_by": "user",
        "epistemic_status": (
            "detected_material_boundary" if kind == "material_limitation" else "candidate_for_user_review"
        ),
        "rationale": rationale,
    }


def _translation_check(state: dict[str, Any], target_text: str, source_text: str | None) -> dict[str, Any] | None:
    if state.get("task_mode") != "translation":
        return None
    source = state.get("translation_invariants") or {}
    target = _translation_invariants(target_text)
    missing: list[dict[str, str]] = []
    unexpected: list[dict[str, str]] = []
    for kind in ("number", "citation", "url", "identifier", "latex_reference"):
        source_counts = Counter(str(item) for item in source.get(kind, []))
        target_counts = Counter(str(item) for item in target.get(kind, []))
        for value, count in sorted((source_counts - target_counts).items()):
            missing.extend({"kind": kind, "value": value} for _ in range(count))
        for value, count in sorted((target_counts - source_counts).items()):
            unexpected.extend({"kind": kind, "value": value} for _ in range(count))
    folded = target_text.casefold()
    for term in state.get("terminology", []):
        if str(term["target_term"]).casefold() not in folded:
            missing.append({
                "kind": "terminology",
                "value": f"{term['source_term']} -> {term['target_term']}",
            })
    source_text = str(source_text or "")
    boundary_pairs = (
        ("epistemic_qualifier", bool(HEDGE_TERM.search(source_text)), bool(HEDGE_TERM.search(target_text))),
        ("material_limitation", bool(MATERIAL_LIMITATION.search(source_text)), bool(MATERIAL_LIMITATION.search(target_text))),
        (
            "negation",
            bool(NEGATION_EN.search(source_text) or NEGATION_ZH.search(source_text)),
            bool(NEGATION_EN.search(target_text) or NEGATION_ZH.search(target_text)),
        ),
        (
            "causal_relation",
            bool(CAUSAL_EN.search(source_text) or CAUSAL_ZH.search(source_text)),
            bool(CAUSAL_EN.search(target_text) or CAUSAL_ZH.search(target_text)),
        ),
    )
    for boundary, present_in_source, present_in_target in boundary_pairs:
        if present_in_source and not present_in_target:
            missing.append({"kind": "semantic_boundary", "value": boundary})
    payload = {"status": "PASS" if not missing and not unexpected else "BLOCKED", "missing": missing, "unexpected": unexpected}
    payload["check_sha256"] = _digest(payload)
    return payload


def _document_check(state: dict[str, Any], sources: list[tuple[str, str]]) -> dict[str, Any] | None:
    if state.get("task_mode") != "conference_writing":
        return None
    combined = "\n".join(text for _, text in sources)
    issues: list[dict[str, Any]] = []
    contract = state.get("venue_profile") or state.get("venue_contract") or {}
    headings: set[str] = set()
    for match in re.finditer(r"\\(?:sub)*section\*?\{([^}]+)\}|^#{1,6}\s+(.+)$", combined, re.MULTILINE):
        headings.update(str(value).strip().casefold() for value in match.groups() if value)
    for section_value in contract.get("required_sections", []):
        section = section_value.get("name") if isinstance(section_value, dict) else section_value
        if str(section).strip().casefold() not in headings:
            issues.append({"code": "missing_required_section", "value": str(section)})
    labels = set(LATEX_LABEL.findall(combined))
    for reference in sorted(set(LATEX_REFERENCE.findall(combined)) - labels):
        issues.append({"code": "undefined_reference", "value": reference})
    for environment in ("figure", "table"):
        pattern = re.compile(rf"\\begin\{{{environment}\*?\}}(.*?)\\end\{{{environment}\*?\}}", re.DOTALL)
        for index, match in enumerate(pattern.finditer(combined), start=1):
            body = match.group(1)
            if not re.search(r"\\caption\{", body):
                issues.append({"code": f"{environment}_missing_caption", "value": str(index)})
            if not re.search(r"\\label\{", body):
                issues.append({"code": f"{environment}_missing_label", "value": str(index)})
    payload = {"status": "PASS" if not issues else "BLOCKED", "issues": issues}
    payload["check_sha256"] = _digest(payload)
    return payload


def analyze_language(
    root: str | os.PathLike[str], *, draft_text: str | None = None, source_text: str | None = None,
) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    state = _load_state(base)
    sources = _source_texts(base, state, draft_text, source_text)
    findings: list[dict[str, Any]] = []
    decision_checklist: list[dict[str, Any]] = []
    protected = state.get("protected_spans", [])
    for source, text in sources:
        sentences = _sentences(text)
        for protected_item in protected:
            if protected_item["text"] in text:
                line, excerpt = next(
                    ((number, sentence) for number, sentence in sentences if protected_item["text"] in sentence),
                    (1, protected_item["text"]),
                )
                findings.append(_issue(
                    state, source, line, "protected_epistemic_qualifier", excerpt,
                    blocking=False, meaning_risk=True, recommended_action="preserve",
                    rationale=protected_item["reason"],
                ))
        for line, sentence in sentences:
            if MATERIAL_LIMITATION.search(sentence):
                limitation = _issue(
                    state, source, line, "material_limitation", sentence,
                    blocking=False, meaning_risk=True, recommended_action="preserve",
                    rationale="A real scope, sampling, generalization, or external-validity boundary must remain visible.",
                )
                findings.append(limitation)
                decision_checklist.append(_decision_item(
                    state, source, line, "material_limitation", sentence,
                    rationale="The text contains an explicit scope boundary. The tool preserves it and asks the user how to handle it.",
                ))
            if REQUIRED_DISCLOSURE.search(sentence):
                findings.append(_issue(
                    state, source, line, "required_disclosure", sentence,
                    blocking=False, meaning_risk=True, recommended_action="preserve",
                    rationale="Ethical, legal, licensing, and venue-required disclosures must not be removed.",
                ))
            if _is_meta_or_quoted(sentence):
                continue
            if len(HEDGE_TERM.findall(sentence)) >= 3:
                findings.append(_issue(
                    state, source, line, "unsupported_hedge_stack", sentence,
                    blocking=True, meaning_risk=True, recommended_action="calibrate_one_qualifier",
                    rationale="Repeated modality obscures the evidence boundary; retain the one qualifier justified by evidence.",
                ))
            if IMAGINED_CRITIC.search(sentence):
                findings.append(_issue(
                    state, source, line, "imagined_critic_disclaimer", sentence,
                    blocking=True, meaning_risk=True, recommended_action="lead_with_claim_then_boundary",
                    rationale="The sentence addresses an imagined objection before stating the evidence-bounded claim.",
                ))
            if DISCLAIMER_FIRST.search(sentence):
                findings.append(_issue(
                    state, source, line, "disclaimer_first_framing", sentence,
                    blocking=True, meaning_risk=True, recommended_action="lead_with_claim_then_boundary",
                    rationale="A generic preface delays the claim and may conceal whether the following limit is material.",
                ))
            if INTERNAL_PROCESS.search(sentence):
                findings.append(_issue(
                    state, source, line, "internal_process_narration", sentence,
                    blocking=True, meaning_risk=False, recommended_action="remove_process_narration",
                    rationale="Reviewer-response process belongs outside the manuscript's scientific argument.",
                ))
            if GENERIC_THROAT_CLEARING.search(sentence):
                findings.append(_issue(
                    state, source, line, "generic_throat_clearing", sentence,
                    blocking=True, meaning_risk=False, recommended_action="replace_with_specific_evidence",
                    rationale="The generic opening supplies no concrete research object, evidence, or unresolved boundary.",
                ))
            if ASSISTANT_PROCESS_RESIDUE.search(sentence):
                findings.append(_issue(
                    state, source, line, "assistant_process_residue", sentence,
                    blocking=True, meaning_risk=False, recommended_action="remove_non_manuscript_process_text",
                    rationale="This is conversational system/process residue, not manuscript argumentation. It is a textual pattern, not proof of authorship.",
                    epistemic_status="textual_pattern_only",
                ))
            if VAGUE_PROMOTIONAL_ATTRIBUTION.search(sentence):
                findings.append(_issue(
                    state, source, line, "vague_promotional_attribution", sentence,
                    blocking=True, meaning_risk=True, recommended_action="replace_with_attributed_evidence_or_remove_promotion",
                    rationale="The sentence combines untraceable attribution with promotional evaluation. This is a textual pattern only and does not establish who authored it.",
                    epistemic_status="textual_pattern_only",
                ))
    ethics_sources = list(sources)
    if source_text is not None:
        ethics_sources.append(("<translation-source>", str(source_text)))
    combined_review_text = "\n".join(text for _, text in ethics_sources)
    if HUMAN_ETHICS_CONTEXT.search(combined_review_text) and not HUMAN_DISCLOSURE.search(combined_review_text):
        source, line, excerpt = next(
            (
                (source_name, number, sentence)
                for source_name, text in ethics_sources
                for number, sentence in _sentences(text)
                if HUMAN_ETHICS_CONTEXT.search(sentence)
            ),
            ("<manuscript>", 1, "Human-participant or sensitive-data context detected."),
        )
        decision_checklist.append(_decision_item(
            state, source, line, "potential_ethics_omission", excerpt,
            rationale="Human-participant or sensitive-data wording is present, but no ethics/consent disclosure was detected in the hash-bound manuscript. This candidate alone does not establish an omission.",
        ))
    if ANIMAL_ETHICS_CONTEXT.search(combined_review_text) and not ANIMAL_DISCLOSURE.search(combined_review_text):
        source, line, excerpt = next(
            (
                (source_name, number, sentence)
                for source_name, text in ethics_sources
                for number, sentence in _sentences(text)
                if ANIMAL_ETHICS_CONTEXT.search(sentence)
            ),
            ("<manuscript>", 1, "Animal-study context detected."),
        )
        decision_checklist.append(_decision_item(
            state, source, line, "potential_ethics_omission", excerpt,
            rationale="Animal-study wording is present, but no animal-ethics disclosure was detected in the hash-bound manuscript. This candidate alone does not establish an omission.",
        ))
    unique: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    for item in findings:
        unique[(item["category"], item["source"], item["line"], item["excerpt"])] = item
    normalized = sorted(unique.values(), key=lambda item: (item["source"], item["line"], item["category"], item["issue_id"]))
    unique_decisions = {item["decision_id"]: item for item in decision_checklist}
    normalized_decisions = sorted(unique_decisions.values(), key=lambda item: item["decision_id"])
    blocking_count = sum(bool(item["blocking"]) for item in normalized)
    target_text = "\n".join(text for _, text in sources)
    translation_check = _translation_check(state, target_text, source_text)
    document_check = _document_check(state, sources)
    analysis_payload = {
        "plan_hash": state["plan_hash"],
        "findings": normalized,
        "blocking_count": blocking_count,
        "decision_checklist": normalized_decisions,
        "translation_check": translation_check,
        "document_check": document_check,
    }
    contract_blocked = any(
        check is not None and check.get("status") != "PASS"
        for check in (translation_check, document_check)
    )
    if normalized_decisions:
        status = "USER_DECISION_REQUIRED"
        reason = f"{len(normalized_decisions)} limitation/ethics checklist item(s) require an explicit user choice"
    elif blocking_count or contract_blocked:
        status = "REVIEW_REQUIRED"
        reason = f"{blocking_count} blocking language issue(s) and {int(contract_blocked)} contract check(s) require resolution"
    else:
        status = "READY_TO_FINALIZE"
        reason = "language analysis found no blocking issues or unresolved user decisions"
    state.update({
        "status": status,
        "reason": reason,
        "findings": normalized,
        "decision_checklist": normalized_decisions,
        "analysis_hash": _digest(analysis_payload),
        "analyzed_at": utc_now(),
        "resolutions": [],
        "decisions": [],
        "translation_check": translation_check,
        "document_check": document_check,
        "receipt": None,
    })
    _atomic_json(_state_path(base), state)
    return {"status": state["status"], "reason": reason, **analysis_payload}


CARD_REQUIRED_FIELDS = (
    "card_id", "title", "source_url", "source_locator", "section", "rhetorical_move",
    "paragraph_role", "evidence_pattern", "reusable_technique",
)
CARD_OPTIONAL_FIELDS = (
    "discipline", "venue", "evidence_type", "transition_relation", "verification_excerpt", "anti_patterns",
)
FORBIDDEN_CARD_FIELDS = {"body", "full_text", "paragraph", "raw_text", "template"}


def _https_url(value: Any, label: str) -> str:
    url = str(value or "").strip()
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise LanguageError(f"{label} must be a clickable https:// URL")
    if parsed.username is not None or parsed.password is not None:
        raise LanguageError(f"{label} must not contain credentials")
    return url


def _load_cards(root: str | os.PathLike[str]) -> dict[str, Any]:
    path = _cards_path(root)
    if not path.is_file():
        return {"schema_version": 1, "cards": [], "store_sha256": _digest({"schema_version": 1, "cards": []})}
    try:
        store = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LanguageError(f"rhetorical card store is invalid: {exc}") from exc
    if not isinstance(store, dict) or store.get("schema_version") != 1 or not isinstance(store.get("cards"), list):
        raise LanguageError("rhetorical card store has an invalid schema")
    expected_store = _digest({"schema_version": 1, "cards": store["cards"]})
    if store.get("store_sha256") != expected_store:
        raise LanguageError("rhetorical card store integrity check failed")
    seen: set[str] = set()
    for index, item in enumerate(store["cards"]):
        if not isinstance(item, dict):
            raise LanguageError(f"rhetorical card {index} must be an object")
        card_id = str(item.get("card_id") or "")
        if not card_id or card_id in seen:
            raise LanguageError("rhetorical card identifiers must be unique")
        seen.add(card_id)
        saved = item.get("card_sha256")
        unsigned = {key: value for key, value in item.items() if key != "card_sha256"}
        if saved != _digest(unsigned):
            raise LanguageError(f"rhetorical card integrity check failed: {card_id}")
        _https_url(item.get("source_url"), f"rhetorical card {card_id} source")
    return store


def _save_cards(root: str | os.PathLike[str], cards: list[dict[str, Any]]) -> dict[str, Any]:
    store = {"schema_version": 1, "cards": cards}
    store["store_sha256"] = _digest(store)
    _atomic_json(_cards_path(root), store)
    return store


def register_rhetorical_card(root: str | os.PathLike[str], card: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(card, dict):
        raise LanguageError("rhetorical card must be an object")
    forbidden = sorted(FORBIDDEN_CARD_FIELDS & set(card))
    if forbidden:
        raise LanguageError(f"raw prose fields are forbidden in rhetorical cards: {', '.join(forbidden)}")
    normalized: dict[str, Any] = {}
    for field in CARD_REQUIRED_FIELDS:
        value = str(card.get(field) or "").strip()
        if not value:
            raise LanguageError(f"rhetorical card requires {field}")
        normalized[field] = value
    normalized["source_url"] = _https_url(normalized["source_url"], "rhetorical card source")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", normalized["card_id"]):
        raise LanguageError("card_id contains illegal characters")
    for field in CARD_OPTIONAL_FIELDS:
        if field not in card or card[field] in (None, "", []):
            continue
        if field == "anti_patterns":
            if not isinstance(card[field], list) or not all(str(item).strip() for item in card[field]):
                raise LanguageError("anti_patterns must be an array of non-empty strings")
            normalized[field] = [str(item).strip() for item in card[field]]
        else:
            normalized[field] = str(card[field]).strip()
    excerpt = normalized.get("verification_excerpt")
    if excerpt and len(excerpt) > 240:
        raise LanguageError("verification_excerpt must not exceed 240 characters")
    normalized["registered_at"] = utc_now()
    normalized["card_sha256"] = _digest(normalized)
    store = _load_cards(root)
    if any(item["card_id"] == normalized["card_id"] for item in store["cards"]):
        raise LanguageError(f"duplicate rhetorical card identifier: {normalized['card_id']}")
    cards = sorted([*store["cards"], normalized], key=lambda item: item["card_id"])
    _save_cards(root, cards)
    return dict(normalized)


def _tokens(value: str) -> list[str]:
    lowered = str(value).casefold()
    latin = re.findall(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", lowered)
    cjk_runs = re.findall(r"[\u3400-\u9fff]+", lowered)
    cjk: list[str] = []
    for run in cjk_runs:
        cjk.extend(list(run) if len(run) == 1 else [run[index:index + 2] for index in range(len(run) - 1)])
    return latin + cjk


def _card_search_text(card: dict[str, Any]) -> str:
    weighted = [
        card.get("title", ""), card.get("title", ""),
        card.get("rhetorical_move", ""), card.get("rhetorical_move", ""),
        card.get("paragraph_role", ""), card.get("paragraph_role", ""),
        card.get("reusable_technique", ""), card.get("evidence_pattern", ""),
        card.get("transition_relation", ""), card.get("discipline", ""), card.get("venue", ""),
        card.get("section", ""), card.get("evidence_type", ""),
    ]
    return " ".join(str(value) for value in weighted if value)


def retrieve_rhetorical_cards(
    root: str | os.PathLike[str],
    query: str,
    *,
    discipline: str | None = None,
    venue: str | None = None,
    section: str | None = None,
    paragraph_role: str | None = None,
    evidence_type: str | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    query_tokens = _tokens(str(query))
    if not query_tokens:
        raise LanguageError("retrieval query must contain searchable terms")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 4:
        raise LanguageError("retrieval limit must be an integer from 1 to 4")
    store = _load_cards(root)
    filters = {
        "discipline": discipline, "venue": venue, "section": section,
        "paragraph_role": paragraph_role, "evidence_type": evidence_type,
    }
    candidates = []
    for card in store["cards"]:
        if any(
            value is not None and str(card.get(field) or "").casefold() != str(value).strip().casefold()
            for field, value in filters.items()
        ):
            continue
        candidates.append(card)
    document_tokens = [_tokens(_card_search_text(card)) for card in candidates]
    document_frequency = {
        token: sum(token in set(tokens) for tokens in document_tokens)
        for token in set(query_tokens)
    }
    scored: list[tuple[float, str, dict[str, Any]]] = []
    count = max(len(candidates), 1)
    for card, tokens in zip(candidates, document_tokens):
        length = max(len(tokens), 1)
        score = 0.0
        for token in query_tokens:
            frequency = tokens.count(token)
            if not frequency:
                continue
            inverse = math.log(1 + (count - document_frequency[token] + 0.5) / (document_frequency[token] + 0.5))
            score += inverse * (frequency * 2.2) / (frequency + 1.2 * (0.25 + 0.75 * length / max(length, 20)))
        if score > 0:
            scored.append((round(score, 12), card["card_id"], card))
    scored.sort(key=lambda item: (-item[0], item[1]))
    results: list[dict[str, Any]] = []
    for score, _, card in scored[:limit]:
        results.append({
            "card_id": card["card_id"],
            "title": card["title"],
            "source_url": card["source_url"],
            "source_locator": card["source_locator"],
            "section": card["section"],
            "rhetorical_move": card["rhetorical_move"],
            "paragraph_role": card["paragraph_role"],
            "evidence_pattern": card["evidence_pattern"],
            "reusable_technique": card["reusable_technique"],
            "transition_relation": card.get("transition_relation"),
            "score": score,
            "card_sha256": card["card_sha256"],
        })
    response = {
        "query": str(query).strip(),
        "filters": {key: value for key, value in filters.items() if value is not None},
        "results": results,
        "usage_boundary": "Use the rhetorical structure only; do not copy source wording. Verify every scientific claim through the paper-audit evidence owner.",
    }
    state_path = _state_path(root)
    if state_path.is_file():
        state = _load_state(root)
        state["retrieved_cards"] = [
            {"card_id": item["card_id"], "card_sha256": item["card_sha256"], "source_url": item["source_url"]}
            for item in results
        ]
        if state.get("receipt") is not None:
            state.update({"status": "REVIEW_REQUIRED", "reason": "rhetorical retrieval changed after finalization", "receipt": None})
        _atomic_json(state_path, state)
    return response


def _tracked_changes(root: Path, state: dict[str, Any]) -> list[str]:
    changes: list[str] = []
    for item in state.get("tracked_files", []):
        path = (root / str(item.get("path") or "")).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            changes.append(str(item.get("path") or "<outside-project>"))
            continue
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            changes.append(str(item.get("path") or "<missing-path>"))
    return sorted(set(changes))


def _plan_payload_from_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_text": state.get("request_text"),
        "tracked_files": state.get("tracked_files"),
        "inline_text_sha256": state.get("inline_text_sha256"),
        "claim_ids": state.get("claim_ids"),
        "protected_spans": state.get("protected_spans"),
        "task_mode": state.get("task_mode"),
        "source_text_sha256": state.get("source_text_sha256"),
        "translation_invariants": state.get("translation_invariants"),
        "terminology": state.get("terminology"),
        "venue_contract": state.get("venue_contract"),
        "venue_profile": state.get("venue_profile"),
        "context": state.get("context"),
        "project_fingerprint": state.get("project_fingerprint"),
    }


def _analysis_hash_from_state(state: dict[str, Any]) -> str | None:
    if state.get("analysis_hash") is None:
        return None
    findings = state.get("findings")
    if not isinstance(findings, list):
        return "invalid"
    return _digest({
        "plan_hash": state.get("plan_hash"),
        "findings": findings,
        "blocking_count": sum(bool(item.get("blocking")) for item in findings if isinstance(item, dict)),
        "decision_checklist": state.get("decision_checklist"),
        "translation_check": state.get("translation_check"),
        "document_check": state.get("document_check"),
    })


def resolve_language_issues(
    root: str | os.PathLike[str], resolutions: list[dict[str, Any]], *,
    decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    state = _load_state(base)
    changes = _tracked_changes(base, state)
    if changes:
        raise LanguageError(f"tracked manuscript changed; replan language review: {', '.join(changes)}")
    if not state.get("analysis_hash") or not isinstance(state.get("findings"), list):
        raise LanguageError("language analysis must run before issue resolution")
    if not isinstance(resolutions, list):
        raise LanguageError("resolutions must be an array")
    if decisions is not None and not isinstance(decisions, list):
        raise LanguageError("decisions must be an array")
    if not resolutions and not decisions:
        raise LanguageError("at least one resolution or user decision is required")
    findings = {item["issue_id"]: item for item in state["findings"]}
    existing = {item["issue_id"]: item for item in state.get("resolutions", []) if isinstance(item, dict)}
    supplied: set[str] = set()
    for index, raw in enumerate(resolutions):
        if not isinstance(raw, dict):
            raise LanguageError(f"resolution {index} must be an object")
        issue_id = str(raw.get("issue_id") or "").strip()
        if issue_id in supplied:
            raise LanguageError(f"duplicate issue resolution: {issue_id or '<empty>'}")
        supplied.add(issue_id)
        finding = findings.get(issue_id)
        if finding is None:
            raise LanguageError(f"unknown language issue: {issue_id or '<empty>'}")
        action = str(raw.get("action") or "").strip()
        rationale = str(raw.get("rationale") or "").strip()
        if len(rationale) < 30:
            raise LanguageError(f"resolution {issue_id} needs a concrete rationale of at least 30 characters")
        if not finding.get("blocking"):
            if action != "preserve":
                raise LanguageError(f"protected/non-blocking issue {issue_id} can only be preserved")
        else:
            if action in {"rewrite", "rewrite_preserving_meaning", "remove", "delete"}:
                raise LanguageError(
                    f"resolution {issue_id} changes manuscript text; edit the tracked file and replan instead of waiving it"
                )
            if action not in {"retain_with_justification", "false_positive"}:
                raise LanguageError(f"resolution {issue_id} has an invalid action")
        existing[issue_id] = {
            "issue_id": issue_id,
            "action": action,
            "rationale": rationale,
            "resolved_at": utc_now(),
            "finding_sha256": _digest(finding),
        }
    checklist = {item["decision_id"]: item for item in state.get("decision_checklist", []) if isinstance(item, dict)}
    existing_decisions = {
        item["decision_id"]: item for item in state.get("decisions", []) if isinstance(item, dict)
    }
    supplied_decisions: set[str] = set()
    edit_required: list[str] = []
    for index, raw in enumerate(decisions or []):
        if not isinstance(raw, dict):
            raise LanguageError(f"decision {index} must be an object")
        decision_id = str(raw.get("decision_id") or "").strip()
        if decision_id in supplied_decisions:
            raise LanguageError(f"duplicate user decision: {decision_id or '<empty>'}")
        supplied_decisions.add(decision_id)
        item = checklist.get(decision_id)
        if item is None:
            raise LanguageError(f"unknown user decision: {decision_id or '<empty>'}")
        if str(raw.get("selected_by") or "").strip() != "user":
            raise LanguageError(f"decision {decision_id} must be selected_by=user")
        action = str(raw.get("action") or "").strip()
        valid_actions = {choice["action"] for choice in item.get("choices", [])}
        if action not in valid_actions:
            raise LanguageError(f"decision {decision_id} has an invalid action")
        rationale = str(raw.get("rationale") or "").strip()
        if len(rationale) < 30:
            raise LanguageError(f"decision {decision_id} needs a concrete rationale of at least 30 characters")
        requires_edit = action in {"revise_preserving_substance", "omit_with_justification", "add_disclosure"}
        evidence_locator = str(raw.get("evidence_locator") or "").strip() or None
        if action == "already_disclosed_at_locator" and not evidence_locator:
            raise LanguageError(f"decision {decision_id} already_disclosed_at_locator requires evidence_locator")
        if requires_edit:
            edit_required.append(decision_id)
        existing_decisions[decision_id] = {
            "decision_id": decision_id,
            "action": action,
            "selected_by": "user",
            "rationale": rationale,
            "evidence_locator": evidence_locator,
            "requires_edit_and_replan": requires_edit,
            "decided_at": utc_now(),
            "checklist_item_sha256": _digest(item),
        }
    blockers = {item["issue_id"] for item in state["findings"] if item.get("blocking")}
    resolved_blockers = blockers & set(existing)
    unresolved = sorted(blockers - resolved_blockers)
    unresolved_decisions = sorted(set(checklist) - set(existing_decisions))
    for item in existing_decisions.values():
        if item.get("requires_edit_and_replan") and item["decision_id"] not in edit_required:
            edit_required.append(item["decision_id"])
    contract_blocked = any(
        isinstance(check, dict) and check.get("status") != "PASS"
        for check in (state.get("translation_check"), state.get("document_check"))
    )
    if edit_required:
        status = "EDIT_REQUIRED"
        reason = f"edit the manuscript and replan for decisions: {', '.join(sorted(set(edit_required)))}"
    elif unresolved_decisions:
        status = "USER_DECISION_REQUIRED"
        reason = f"unresolved user decisions: {', '.join(unresolved_decisions)}"
    elif unresolved or contract_blocked:
        status = "REVIEW_REQUIRED"
        reason = f"unresolved language issues: {', '.join(unresolved)}" if unresolved else "translation or document contract is blocked"
    else:
        status = "READY_TO_FINALIZE"
        reason = "all blocking language issues and user decisions have explicit verified outcomes"
    state.update({
        "resolutions": sorted(existing.values(), key=lambda item: item["issue_id"]),
        "decisions": sorted(existing_decisions.values(), key=lambda item: item["decision_id"]),
        "status": status,
        "reason": reason,
        "receipt": None,
    })
    _atomic_json(_state_path(base), state)
    return {
        "status": state["status"],
        "resolved_issue_ids": sorted(resolved_blockers),
        "unresolved_issue_ids": unresolved,
        "decided_item_ids": sorted(set(existing_decisions)),
        "unresolved_decision_ids": unresolved_decisions,
        "edit_required_decision_ids": sorted(set(edit_required)),
    }


def _verify_retrieved_cards(root: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    bound = state.get("retrieved_cards") or []
    if not bound:
        return []
    store = _load_cards(root)
    cards = {item["card_id"]: item for item in store["cards"]}
    normalized: list[dict[str, str]] = []
    for item in bound:
        card = cards.get(str(item.get("card_id") or ""))
        if card is None or card.get("card_sha256") != item.get("card_sha256"):
            raise LanguageError(f"retrieved rhetorical card changed or disappeared: {item.get('card_id')}")
        if card.get("source_url") != item.get("source_url"):
            raise LanguageError(f"retrieved rhetorical card source changed: {item.get('card_id')}")
        normalized.append({
            "card_id": card["card_id"], "card_sha256": card["card_sha256"], "source_url": card["source_url"],
        })
    return sorted(normalized, key=lambda item: item["card_id"])


def finalize_language_review(root: str | os.PathLike[str]) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    state = _load_state(base)
    changes = _tracked_changes(base, state)
    if changes:
        raise LanguageError(f"tracked manuscript changed; replan language review: {', '.join(changes)}")
    if state.get("plan_hash") != _digest(_plan_payload_from_state(state)):
        raise LanguageError("language review plan integrity check failed")
    if state.get("venue_profile"):
        venue_status = verify_venue_receipt(base, state["venue_profile"].get("venue_receipt_sha256"))
        if venue_status.get("status") != "PASS":
            raise LanguageError(f"venue evidence changed; resolve and replan: {venue_status.get('reason')}")
    if not state.get("analysis_hash") or state.get("analysis_hash") != _analysis_hash_from_state(state):
        raise LanguageError("language analysis is missing or failed integrity verification")
    blockers = {item["issue_id"] for item in state.get("findings", []) if item.get("blocking")}
    resolutions = {item["issue_id"]: item for item in state.get("resolutions", []) if isinstance(item, dict)}
    unresolved = sorted(blockers - set(resolutions))
    if unresolved:
        raise LanguageError(f"unresolved language issues prevent PASS: {', '.join(unresolved)}")
    for issue_id, resolution in resolutions.items():
        finding = next((item for item in state["findings"] if item["issue_id"] == issue_id), None)
        if finding is None or resolution.get("finding_sha256") != _digest(finding):
            raise LanguageError(f"language resolution is stale or invalid: {issue_id}")
        if len(str(resolution.get("rationale") or "").strip()) < 30:
            raise LanguageError(f"language resolution rationale is stale or invalid: {issue_id}")
        valid_actions = {"retain_with_justification", "false_positive"} if finding.get("blocking") else {"preserve"}
        if resolution.get("action") not in valid_actions:
            raise LanguageError(f"language resolution action is stale or invalid: {issue_id}")
    checklist = {item["decision_id"]: item for item in state.get("decision_checklist", []) if isinstance(item, dict)}
    decisions = {item["decision_id"]: item for item in state.get("decisions", []) if isinstance(item, dict)}
    unresolved_decisions = sorted(set(checklist) - set(decisions))
    if unresolved_decisions:
        raise LanguageError(f"unresolved limitation/ethics decisions prevent PASS: {', '.join(unresolved_decisions)}")
    for decision_id, decision in decisions.items():
        item = checklist.get(decision_id)
        if item is None or decision.get("checklist_item_sha256") != _digest(item):
            raise LanguageError(f"language user decision is stale or invalid: {decision_id}")
        if decision.get("selected_by") != "user":
            raise LanguageError(f"language decision was not selected by the user: {decision_id}")
        action = str(decision.get("action") or "")
        valid_actions = {choice["action"] for choice in item.get("choices", [])}
        if action not in valid_actions or len(str(decision.get("rationale") or "").strip()) < 30:
            raise LanguageError(f"language user decision content is stale or invalid: {decision_id}")
        requires_edit = action in {"revise_preserving_substance", "omit_with_justification", "add_disclosure"}
        if bool(decision.get("requires_edit_and_replan")) != requires_edit:
            raise LanguageError(f"language user decision edit flag is stale or invalid: {decision_id}")
        if action == "already_disclosed_at_locator" and not str(decision.get("evidence_locator") or "").strip():
            raise LanguageError(f"language user decision locator is stale or invalid: {decision_id}")
        if requires_edit:
            raise LanguageError(f"language decision requires a manuscript edit and replan: {decision_id}")
    for name in ("translation_check", "document_check"):
        check = state.get(name)
        if isinstance(check, dict) and check.get("status") != "PASS":
            raise LanguageError(f"{name.replace('_', ' ')} prevents PASS")
    retrieved = _verify_retrieved_cards(base, state)
    receipt_payload = {
        "project_fingerprint": state["project_fingerprint"],
        "plan_hash": state["plan_hash"],
        "analysis_hash": state["analysis_hash"],
        "tracked_files": state["tracked_files"],
        "inline_text_sha256": state.get("inline_text_sha256"),
        "claim_ids": state["claim_ids"],
        "protected_spans_sha256": _digest(state["protected_spans"]),
        "finding_ids": [item["issue_id"] for item in state["findings"]],
        "resolved_issue_ids": sorted(blockers),
        "resolutions_sha256": _digest(state.get("resolutions", [])),
        "decided_item_ids": sorted(decisions),
        "decisions_sha256": _digest(state.get("decisions", [])),
        "translation_check_sha256": (state.get("translation_check") or {}).get("check_sha256"),
        "document_check_sha256": (state.get("document_check") or {}).get("check_sha256"),
        "retrieved_cards": retrieved,
        "issued_at": utc_now(),
    }
    receipt_payload["receipt_sha256"] = _digest(receipt_payload)
    state.update({
        "status": "PASS",
        "reason": "language findings, protections, and provenance passed deterministic verification",
        "receipt": receipt_payload,
    })
    _atomic_json(_state_path(base), state)
    return {"status": "PASS", **receipt_payload}


def _invalidate_state(path: Path, state: dict[str, Any], reason: str) -> dict[str, Any]:
    state.update({"status": "REVIEW_REQUIRED", "reason": reason, "receipt": None})
    _atomic_json(path, state)
    return state


def get_language_status(root: str | os.PathLike[str]) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    path = _state_path(base)
    if not path.is_file():
        return {"status": "NOT_PLANNED", "reason": "language review has not been planned"}
    state = _load_state(base)
    if state.get("project_fingerprint") != _project_fingerprint(base):
        return _invalidate_state(path, state, "language receipt belongs to a different project root")
    if state.get("plan_hash") != _digest(_plan_payload_from_state(state)):
        return _invalidate_state(path, state, "language review plan integrity check failed")
    if state.get("venue_profile"):
        venue_status = verify_venue_receipt(base, state["venue_profile"].get("venue_receipt_sha256"))
        if venue_status.get("status") != "PASS":
            return _invalidate_state(path, state, f"venue evidence changed: {venue_status.get('reason')}")
    changes = _tracked_changes(base, state)
    if changes:
        return _invalidate_state(path, state, f"tracked manuscript changed: {', '.join(changes)}")
    if state.get("analysis_hash") is not None and state.get("analysis_hash") != _analysis_hash_from_state(state):
        return _invalidate_state(path, state, "language analysis integrity check failed")
    if state.get("status") == "PASS":
        receipt = state.get("receipt")
        if not isinstance(receipt, dict):
            return _invalidate_state(path, state, "language receipt is missing or invalid")
        saved = receipt.get("receipt_sha256")
        unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        if saved != _digest(unsigned):
            return _invalidate_state(path, state, "language receipt integrity check failed")
        try:
            retrieved = _verify_retrieved_cards(base, state)
        except LanguageError as exc:
            return _invalidate_state(path, state, str(exc))
        if receipt.get("retrieved_cards") != retrieved:
            return _invalidate_state(path, state, "language receipt rhetorical-card binding failed")
        blockers = {item["issue_id"]: item for item in state.get("findings", []) if item.get("blocking")}
        resolutions = {item["issue_id"]: item for item in state.get("resolutions", []) if isinstance(item, dict)}
        if set(blockers) != set(resolutions):
            return _invalidate_state(path, state, "language receipt blocker-resolution coverage failed")
        if any(
            resolution.get("finding_sha256") != _digest(blockers[issue_id])
            or len(str(resolution.get("rationale") or "").strip()) < 30
            or resolution.get("action") not in {"retain_with_justification", "false_positive"}
            for issue_id, resolution in resolutions.items()
        ):
            return _invalidate_state(path, state, "language blocker-resolution integrity check failed")
        if receipt.get("resolutions_sha256") != _digest(state.get("resolutions", [])):
            return _invalidate_state(path, state, "language receipt blocker-resolution binding failed")
        checklist = {item["decision_id"]: item for item in state.get("decision_checklist", []) if isinstance(item, dict)}
        decisions = {item["decision_id"]: item for item in state.get("decisions", []) if isinstance(item, dict)}
        if set(checklist) != set(decisions):
            return _invalidate_state(path, state, "language receipt has unresolved limitation/ethics decisions")
        invalid_decision = False
        for decision_id, decision in decisions.items():
            item = checklist[decision_id]
            action = str(decision.get("action") or "")
            valid_actions = {choice["action"] for choice in item.get("choices", [])}
            requires_edit = action in {"revise_preserving_substance", "omit_with_justification", "add_disclosure"}
            if (
                decision.get("selected_by") != "user"
                or action not in valid_actions
                or len(str(decision.get("rationale") or "").strip()) < 30
                or bool(decision.get("requires_edit_and_replan")) != requires_edit
                or requires_edit
                or decision.get("checklist_item_sha256") != _digest(item)
                or (action == "already_disclosed_at_locator" and not str(decision.get("evidence_locator") or "").strip())
            ):
                invalid_decision = True
                break
        if invalid_decision:
            return _invalidate_state(path, state, "language user-decision integrity check failed")
        if receipt.get("decisions_sha256") != _digest(state.get("decisions", [])):
            return _invalidate_state(path, state, "language receipt user-decision binding failed")
        if receipt.get("decided_item_ids") != sorted(decisions):
            return _invalidate_state(path, state, "language receipt decision coverage failed")
        for name in ("translation_check", "document_check"):
            check = state.get(name)
            if isinstance(check, dict):
                if check.get("status") != "PASS" or check.get("check_sha256") != _digest({
                    key: value for key, value in check.items() if key != "check_sha256"
                }):
                    return _invalidate_state(path, state, f"language {name.replace('_', ' ')} integrity check failed")
                if receipt.get(f"{name}_sha256") != check.get("check_sha256"):
                    return _invalidate_state(path, state, f"language receipt {name.replace('_', ' ')} binding failed")
    return state


def verify_language_receipt(
    root: str | os.PathLike[str],
    *,
    expected_files: list[dict[str, Any]] | None = None,
    expected_claim_ids: list[str] | None = None,
) -> dict[str, Any]:
    state = get_language_status(root)
    if state.get("status") != "PASS" or not isinstance(state.get("receipt"), dict):
        raise LanguageError(f"language review is not PASS: {state.get('reason')}")
    receipt = state["receipt"]
    if expected_files is not None:
        expected = sorted(
            [
                {"path": str(item.get("path") or ""), "sha256": str(item.get("sha256") or ""), "kind": "manuscript"}
                for item in expected_files
            ],
            key=lambda item: item["path"],
        )
        if receipt.get("tracked_files") != expected:
            raise LanguageError("language receipt does not match the paper-audit manuscript hashes")
    if expected_claim_ids is not None and receipt.get("claim_ids") != list(expected_claim_ids):
        raise LanguageError("language receipt does not match the paper-audit claim inventory")
    return {"status": "PASS", "receipt_sha256": receipt["receipt_sha256"], "receipt": receipt}
