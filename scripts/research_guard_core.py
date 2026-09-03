from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from evidence_kernel import (
    EvidenceRecorder,
    evidence_scope,
    record_http_error,
    record_http_response,
    verify_evidence_manifest,
)
from network_config_core import (
    NetworkConfigError,
    foreign_proxy_for as _configured_foreign_proxy_for,
    is_local_endpoint as _configured_is_local_endpoint,
    request_routes as _configured_request_routes,
)


SCHEMA_VERSION = 1
STATE_DIR_NAME = ".research-guard"
PASS_STATUS = "PASS"
METHOD_REQUIRED_FIELDS = ("title", "problem", "mechanism")
USER_AGENT = "research-guard/0.7 (local academic novelty verifier)"
SOURCE_CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills" / "research-novelty-guard" / "references" / "source-catalog.json"
)
def _is_local_endpoint(url: str) -> bool:
    return _configured_is_local_endpoint(url)


def _is_domestic_or_local(url: str) -> bool:
    """Compatibility alias; public country domains are not auto-local."""
    return _is_local_endpoint(url)


def _foreign_proxy_for(url: str) -> str | None:
    try:
        return _configured_foreign_proxy_for(url)
    except NetworkConfigError as exc:
        raise GuardError(str(exc)) from exc


def _request_routes(url: str) -> tuple[tuple[str, str | None], ...]:
    """Return ordered, credential-free routes for one source request.

    Foreign requests use an explicitly configured local proxy first.  With no
    proxy configured they use a direct route, which keeps the public package
    portable across networks.  A transport failure on a configured proxy is
    not evidence that the source is empty, so the request may recover through
    a direct route and records the route used.  Set
    ``RESEARCH_GUARD_DISABLE_FOREIGN_DIRECT_FALLBACK=1`` when a caller needs
    strict proxy-only operation.  Loopback requests always bypass ambient
    proxy variables; public domains, including ``.cn`` sources, follow the
    user's explicit proxy choice or direct fallback rather than inferring a
    user location from the source domain.
    """
    # Keep the novelty adapters on the same route implementation as citation,
    # venue, discipline, payload, and domain clients.  The injected resolver
    # preserves the narrow test seam without allowing this module to drift
    # into a second proxy/direct policy.
    return _configured_request_routes(url, proxy_resolver=_foreign_proxy_for)

# Domain selection is owned by the main agent.  No keyword table, small model,
# or automatic classifier is retained in the runtime admission path.

DOMAIN_ROUTES: dict[str, dict[str, list[str]]] = {
    "computer_science": {
        "required_sources": ["arxiv", "crossref", "dblp"],
        "supplemental_sources": ["semantic_scholar", "datacite", "hal", "openaire", "openalex", "ieee"],
        "index_checks": ["ccf", "ieee"],
        "manual_sources": ["ccf", "ieee", "google_scholar", "pubscholar"],
    },
    "engineering": {
        "required_sources": ["arxiv", "crossref", "datacite"],
        "supplemental_sources": ["semantic_scholar", "dblp", "hal", "openaire", "openalex", "ieee"],
        "index_checks": ["ieee", "wos_sci"],
        "manual_sources": ["ieee", "wos_master_journal_list", "nstl", "nstrs", "pubscholar"],
    },
    "mathematics_statistics": {
        "required_sources": ["arxiv", "crossref", "openalex"],
        "supplemental_sources": ["datacite", "hal", "openaire", "semantic_scholar", "doaj"],
        "index_checks": [],
        "manual_sources": ["zbmath_open", "mathscinet", "google_scholar", "pubscholar"],
    },
    "natural_science": {
        "required_sources": ["arxiv", "crossref", "datacite"],
        "supplemental_sources": ["semantic_scholar", "hal", "openaire", "zenodo", "openalex", "wos_sci"],
        "index_checks": ["wos_sci"],
        "manual_sources": ["wos_master_journal_list", "nstl", "nstrs", "pubscholar", "gooa"],
    },
    "medicine_life_science": {
        "required_sources": ["pubmed", "europe_pmc", "crossref"],
        "supplemental_sources": ["pmc", "biorxiv", "medrxiv", "clinicaltrials", "semantic_scholar", "datacite", "openaire", "openalex", "wos_sci"],
        "index_checks": ["wos_sci"],
        "manual_sources": ["wos_master_journal_list", "pubscholar", "gooa"],
    },
    "social_science": {
        "required_sources": ["crossref", "openaire", "hal"],
        "supplemental_sources": ["semantic_scholar", "datacite", "zenodo", "openalex", "wos_ssci"],
        "index_checks": ["wos_ssci", "cssci", "c_journal"],
        "manual_sources": ["ncpssd", "cssci", "wos_master_journal_list", "google_scholar", "pubscholar"],
    },
    "humanities": {
        "required_sources": ["crossref", "openaire", "hal"],
        "supplemental_sources": ["semantic_scholar", "datacite", "zenodo", "openalex"],
        "index_checks": ["cssci", "c_journal"],
        "manual_sources": ["ncpssd", "cssci", "google_scholar", "pubscholar"],
    },
    "general": {
        "required_sources": ["crossref", "openaire", "datacite"],
        "supplemental_sources": ["semantic_scholar", "hal", "zenodo", "openalex"],
        "index_checks": [],
        "manual_sources": ["google_scholar", "pubscholar", "base"],
    },
}

DOMAIN_EXTENDED_ROUTES: dict[str, dict[str, list[str]]] = {
    "computer_science": {
        "patents": ["google_patents"], "trials": [], "grants": ["openaire_projects"],
        "datasets": ["datacite"], "software": ["github"], "preregistrations": ["osf"],
    },
    "engineering": {
        "patents": ["google_patents"], "trials": [], "grants": ["openaire_projects"],
        "datasets": ["datacite"], "software": ["github"], "preregistrations": ["osf"],
    },
    "mathematics_statistics": {
        "patents": [], "trials": [], "grants": ["openaire_projects"],
        "datasets": ["datacite"], "software": ["github"], "preregistrations": ["osf"],
    },
    "natural_science": {
        "patents": ["google_patents"], "trials": [], "grants": ["openaire_projects"],
        "datasets": ["datacite"], "software": ["github"], "preregistrations": ["osf"],
    },
    "medicine_life_science": {
        "patents": ["google_patents"], "trials": ["clinicaltrials"], "grants": ["nih_reporter", "openaire_projects"],
        "datasets": ["datacite"], "software": ["github"], "preregistrations": ["osf"],
    },
    "social_science": {
        "patents": [], "trials": [], "grants": ["openaire_projects"],
        "datasets": ["datacite"], "software": ["github"], "preregistrations": ["osf"],
    },
    "humanities": {
        "patents": [], "trials": [], "grants": ["openaire_projects"],
        "datasets": ["datacite"], "software": ["github"], "preregistrations": ["osf"],
    },
    "general": {
        "patents": [], "trials": [], "grants": ["openaire_projects"],
        "datasets": ["datacite"], "software": ["github"], "preregistrations": ["osf"],
    },
}

STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "using", "based", "via", "that",
    "this", "method", "model", "system", "approach", "study", "research", "novel",
    "一种", "方法", "模型", "系统", "研究", "基于", "通过", "用于", "提出", "新型",
}

SOURCE_ALIASES = {
    "sci": "wos_sci",
    "ssci": "wos_ssci",
    "web_of_science_sci": "wos_sci",
    "web_of_science_ssci": "wos_ssci",
    "c": "c_journal",
    "c刊": "c_journal",
    "c_journal": "c_journal",
    "ccf": "ccf",
    "cssci": "cssci",
    "ieee": "ieee",
}

MANUAL_SOURCE_CATALOG_ALIASES = {
    "wos_sci": "wos_master_journal_list",
    "wos_ssci": "wos_master_journal_list",
    "c_journal": "cssci",
}

SOURCE_MENTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("wos_ssci", re.compile(r"(?<![A-Za-z])SSCI(?![A-Za-z])|Web\s+of\s+Science\s+SSCI", re.IGNORECASE)),
    ("wos_sci", re.compile(r"(?<![A-Za-z])SCI(?![A-Za-z])|Web\s+of\s+Science\s+SCI", re.IGNORECASE)),
    ("ccf", re.compile(r"(?<![A-Za-z])CCF(?![A-Za-z])", re.IGNORECASE)),
    ("cssci", re.compile(r"(?<![A-Za-z])CSSCI(?![A-Za-z])", re.IGNORECASE)),
    ("c_journal", re.compile(r"C刊|C类期刊|C\s*journal", re.IGNORECASE)),
    ("ieee", re.compile(r"(?<![A-Za-z])IEEE(?![A-Za-z])|IEEE\s+Xplore", re.IGNORECASE)),
    ("cnki", re.compile(r"(?<![A-Za-z])CNKI(?![A-Za-z])|中国知网|知网", re.IGNORECASE)),
    ("wanfang", re.compile(r"万方(?:数据)?", re.IGNORECASE)),
    ("vip", re.compile(r"维普(?:数据库)?", re.IGNORECASE)),
    ("ncpssd", re.compile(r"国家哲学社会科学文献中心|NCPSSD", re.IGNORECASE)),
    ("nstl", re.compile(r"国家科技图书文献中心|(?<![A-Za-z])NSTL(?![A-Za-z])", re.IGNORECASE)),
    ("nstrs", re.compile(r"国家科技报告服务系统|(?<![A-Za-z])NSTRS(?![A-Za-z])", re.IGNORECASE)),
)

MANUAL_EVIDENCE_PURPOSES = {"literature_search", "index_membership"}
MANUAL_EVIDENCE_STATUSES = {
    "zero_results", "hits_present", "index_verified", "index_not_listed", "access_blocked", "inconclusive",
}
CONCLUSIVE_MANUAL_STATUSES = {"zero_results", "hits_present", "index_verified", "index_not_listed"}


class GuardError(RuntimeError):
    pass


class SourceAccessError(GuardError):
    pass


class SourceTransportError(SourceAccessError):
    pass


class SourceHTTPError(SourceAccessError):
    pass


class SourceRateLimitError(SourceHTTPError):
    pass


class SourcePayloadError(SourceAccessError):
    pass


def canonical_source(value: str) -> str:
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return SOURCE_ALIASES.get(normalized, normalized)


def detect_source_mentions(text: str) -> list[str]:
    return [source for source, pattern in SOURCE_MENTION_PATTERNS if pattern.search(str(text))]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def project_root(path: str | os.PathLike[str]) -> Path:
    return Path(path).expanduser().resolve()


def guard_dir(root: str | os.PathLike[str]) -> Path:
    return project_root(root) / STATE_DIR_NAME


def state_path(root: str | os.PathLike[str]) -> Path:
    return guard_dir(root) / "state.json"


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


def _append_audit(root: Path, event: str, details: dict[str, Any]) -> None:
    path = root / STATE_DIR_NAME / "audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"at": utc_now(), "event": event, "details": details}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(record) + "\n")


def load_state(root: str | os.PathLike[str], required: bool = True) -> dict[str, Any] | None:
    path = state_path(root)
    if not path.exists():
        if required:
            raise GuardError(f"No research-guard state at {path}")
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardError(f"Unreadable research-guard state: {exc}") from exc
    if state.get("schema_version") != SCHEMA_VERSION:
        raise GuardError("Unsupported or missing state schema version")
    return state


def save_state(root: str | os.PathLike[str], state: dict[str, Any]) -> None:
    _atomic_json(state_path(root), state)


def _safe_method_file(root: Path, item: str) -> Path:
    candidate = (root / item).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise GuardError(f"Tracked method file escapes project root: {item}") from exc
    return candidate


def method_files_fingerprint(root: str | os.PathLike[str], files: list[str]) -> str:
    base = project_root(root)
    entries: list[dict[str, Any]] = []
    for item in sorted(set(files)):
        path = _safe_method_file(base, item)
        if not path.exists() or not path.is_file():
            entries.append({"path": item, "status": "missing"})
            continue
        entries.append({
            "path": item,
            "status": "present",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    return digest(entries)


def normalize_method(method: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(method, dict):
        raise GuardError("method must be a JSON object")
    missing = [field for field in METHOD_REQUIRED_FIELDS if not str(method.get(field, "")).strip()]
    if missing:
        raise GuardError(f"method is missing required fields: {', '.join(missing)}")
    normalized: dict[str, Any] = {}
    for key, value in sorted(method.items()):
        if value is None or value == "" or value == []:
            continue
        if key == "method_files":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise GuardError("method_files must be a list of project-relative paths")
            normalized[key] = sorted(set(item.replace("\\", "/") for item in value))
        elif isinstance(value, str):
            normalized[key] = " ".join(value.split())
        else:
            normalized[key] = value
    return normalized


def _text_from_method(method: dict[str, Any]) -> str:
    preferred = ("title", "problem", "mechanism", "contributions", "datasets", "evaluation")
    parts: list[str] = []
    for key in preferred:
        value = method.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value is not None:
            parts.append(str(value))
    return " ".join(parts)


def classify_domain(
    *,
    primary_domain: str,
    secondary_domains: list[str] | None,
    selected_by: str,
    selection_rationale: str,
    evidence_urls: list[str] | None = None,
) -> dict[str, Any]:
    """Build a route only from a semantic choice explicitly made by the main agent."""
    if selected_by != "main_agent":
        raise GuardError("selected_by=main_agent is required; automatic domain classification is forbidden")
    primary = str(primary_domain or "").strip()
    secondary = [str(value).strip() for value in (secondary_domains or []) if str(value).strip()]
    selected = [primary, *secondary]
    if not primary:
        raise GuardError("primary_domain is required")
    if len(selected) > 3:
        raise GuardError("Select at most three explicit domains")
    if len(selected) != len(set(selected)):
        raise GuardError("Selected domains contain duplicates")
    unknown = [domain for domain in selected if domain not in DOMAIN_ROUTES]
    if unknown:
        raise GuardError(
            f"Unknown domain ids: {', '.join(unknown)}. Choose from: {', '.join(DOMAIN_ROUTES)}"
        )
    rationale = " ".join(str(selection_rationale or "").split())
    if len(rationale) < 12:
        raise GuardError("selection_rationale must explain the main agent's domain choice")
    links: list[str] = []
    for value in evidence_urls or []:
        url = str(value).strip()
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise GuardError("domain-selection evidence URLs must be credential-free absolute HTTPS URLs")
        if url not in links:
            links.append(url)
    required_sources = _ordered_union(DOMAIN_ROUTES[domain]["required_sources"] for domain in selected)
    supplemental_sources = _ordered_union(DOMAIN_ROUTES[domain]["supplemental_sources"] for domain in selected)
    result = {
        "primary": primary,
        "secondary": secondary,
        "selected_by": selected_by,
        "selection_rationale": rationale,
        "evidence_urls": links,
        "automatic_classification": False,
        "required_sources": required_sources,
        "supplemental_sources": [source for source in supplemental_sources if source not in required_sources],
        "index_checks": _ordered_union(DOMAIN_ROUTES[domain]["index_checks"] for domain in selected),
        "manual_sources": _ordered_union(DOMAIN_ROUTES[domain]["manual_sources"] for domain in selected),
    }
    result["profile_hash"] = digest(result)
    return result


def _ordered_union(groups: Any) -> list[str]:
    output: list[str] = []
    for group in groups:
        for value in group:
            if value not in output:
                output.append(value)
    return output


def _query_piece(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}", str(value))
    return " ".join(words[:14])


def _query_spec(kind: str, text: str, components: list[str]) -> dict[str, Any] | None:
    normalized = " ".join(str(text).split()).strip()
    if not normalized:
        return None
    return {
        "query_id": f"q-{kind.replace('_', '-')}",
        "kind": kind,
        "text": normalized,
        "components": components,
    }


def make_search_plan(
    method: dict[str, Any], profile: dict[str, Any], discipline_overlay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    problem = _query_piece(method.get("problem", ""))
    mechanism = _query_piece(method.get("mechanism", ""))
    contributions = _query_piece(method.get("contributions", ""))
    title = _query_piece(method.get("title", ""))
    datasets = _query_piece(method.get("datasets", ""))
    evaluation = _query_piece(method.get("evaluation", ""))
    aliases = _query_piece(method.get("aliases", method.get("keywords", "")))
    candidates = [
        _query_spec("exact_title", f'"{title}"', ["title"]),
        _query_spec("exact_mechanism", f'"{mechanism}"', ["mechanism"]),
        _query_spec("problem_mechanism", f"{problem} {mechanism}", ["problem", "mechanism"]),
        _query_spec("mechanism_contribution", f"{mechanism} {contributions}", ["mechanism", "contributions"]),
        _query_spec("mechanism_dataset", f"{mechanism} {datasets}", ["mechanism", "datasets"]) if datasets else None,
        _query_spec("mechanism_evaluation", f"{mechanism} {evaluation}", ["mechanism", "evaluation"]) if evaluation else None,
        _query_spec("aliases", f"{aliases} {problem}", ["aliases", "problem"]) if aliases else None,
        _query_spec("survey", f"{problem} review survey", ["problem"]),
    ]
    overlay = discipline_overlay or {}
    for index, lens in enumerate(overlay.get("query_lenses", [])[:2], 1):
        candidates.append(_query_spec(
            f"discipline_lens_{index}",
            f"{problem} {mechanism} {_query_piece(lens)}",
            ["problem", "mechanism", "discipline_lens"],
        ))
    query_specs: list[dict[str, Any]] = []
    seen_text: set[str] = set()
    for item in candidates:
        if not item or item["text"] in seen_text:
            continue
        seen_text.add(item["text"])
        query_specs.append(item)
    queries = [item["text"] for item in query_specs]
    requested = method.get("required_sources", method.get("source_requirements", []))
    if isinstance(requested, str):
        requested = [item for item in re.split(r"[,;，；\s]+", requested) if item]
    if not isinstance(requested, list):
        raise GuardError("required_sources/source_requirements must be a list or delimited string")
    user_required_sources = []
    for value in requested:
        normalized_source = canonical_source(str(value))
        if normalized_source and normalized_source not in user_required_sources:
            user_required_sources.append(normalized_source)
    selected_domains = [profile["primary"], *profile.get("secondary", [])]
    publication_required = _ordered_union([
        profile["required_sources"], overlay.get("required_sources", []),
    ])
    source_families: dict[str, list[str]] = {"publications": publication_required}
    for family in ("patents", "trials", "grants", "datasets", "software", "preregistrations"):
        source_families[family] = _ordered_union(
            DOMAIN_EXTENDED_ROUTES.get(domain, DOMAIN_EXTENDED_ROUTES["general"])[family]
            for domain in selected_domains
        )
    extended_required_sources = _ordered_union(
        source_families[family]
        for family in ("patents", "trials", "grants", "datasets", "software", "preregistrations")
    )
    required_sources = _ordered_union([publication_required, extended_required_sources, user_required_sources])
    supplemental_sources = [
        source for source in _ordered_union([
            profile.get("supplemental_sources", []), overlay.get("supplemental_sources", []),
        ]) if source not in required_sources
    ]
    plan = {
        "domains": selected_domains,
        "queries": queries,
        "query_specs": query_specs,
        "required_sources": required_sources,
        "source_families": source_families,
        "extended_required_sources": extended_required_sources,
        "user_required_sources": user_required_sources,
        "supplemental_sources": supplemental_sources,
        "index_checks": _ordered_union([profile["index_checks"], overlay.get("index_checks", [])]),
        "manual_sources": _ordered_union([
            profile.get("manual_sources", []), overlay.get("manual_sources", []),
        ]),
        "discipline_profile": overlay.get("binding"),
        "discipline_literature_forms": overlay.get("literature_forms", []),
        "discipline_public_catalogs": overlay.get("public_catalogs", []),
        "discipline_venue_families": overlay.get("venue_families", []),
        "discipline_research_methods": overlay.get("research_methods", []),
        "discipline_knowledge_sources": overlay.get("knowledge_sources", []),
        "discipline_data_sources": overlay.get("data_sources", []),
        "discipline_method_families": overlay.get("method_families", []),
        "discipline_journal_watchlist": overlay.get("journal_watchlist", []),
        "discipline_boundaries": overlay.get("boundaries", []),
        "deduplication": ["doi", "normalized_title"],
        "collision_thresholds": {"potential": 0.28, "high": 0.58},
        "source_limit": 12,
    }
    plan["plan_hash"] = digest(plan)
    return plan


def declare_method_change(root: str | os.PathLike[str], prompt: str) -> dict[str, Any]:
    """Invalidate prior novelty evidence as soon as a user declares a method change."""
    base = project_root(root)
    state = load_state(base)
    normalized_prompt = " ".join(str(prompt).split())
    if not normalized_prompt:
        raise GuardError("A non-empty method-change declaration is required")
    prompt_hash = digest({"prompt": normalized_prompt})
    active = state["active_method"]
    previous = state.get("pending_method_change")
    if (
        previous
        and previous.get("prompt_hash") == prompt_hash
        and previous.get("prior_method_hash") == active["hash"]
        and previous.get("prior_method_version") == active["version"]
    ):
        return {"changed": False, "pending_method_change": previous, "gate": state["gate"]}
    declared_at = utc_now()
    pending = {
        "declared_at": declared_at,
        "prompt_hash": prompt_hash,
        "prior_method_hash": active["hash"],
        "prior_method_version": active["version"],
    }
    state["pending_method_change"] = pending
    state["latest_report"] = None
    state["current_receipt"] = None
    state["current_search"] = None
    state["gate"] = {
        "status": "NOVELTY_CHECK_REQUIRED",
        "reason": "The user declared a method adjustment; register the complete adjusted method and search again.",
        "updated_at": declared_at,
    }
    save_state(base, state)
    try:
        from research_integrity_core import invalidate_for_method_change
        invalidate_for_method_change(
            base, active["version"], active["hash"], reason="canonical research method changed",
        )
    except (ImportError, ValueError) as exc:
        raise GuardError(f"Cannot invalidate dependent research-integrity receipts: {exc}") from exc
    _append_audit(base, "method_change_declared", pending)
    return {"changed": True, "pending_method_change": pending, "gate": state["gate"]}


def register_method(root: str | os.PathLike[str], method: dict[str, Any]) -> dict[str, Any]:
    base = project_root(root)
    normalized = normalize_method(method)
    files = normalized.get("method_files", [])
    for item in files:
        _safe_method_file(base, item)
    files_hash = method_files_fingerprint(base, files)
    method_hash = digest({"method": normalized, "method_files_hash": files_hash})
    old = load_state(base, required=False)
    if old and old.get("active_method", {}).get("hash") == method_hash:
        if old.get("pending_method_change"):
            raise GuardError(
                "The declared method adjustment did not change the canonical method; "
                "register the complete adjusted method before searching"
            )
        _append_audit(base, "method_registration_idempotent", {"method_hash": method_hash})
        return {"changed": False, "state": old}
    version = int(old.get("active_method", {}).get("version", 0)) + 1 if old else 1
    active = {
        "version": version,
        "hash": method_hash,
        "registered_at": utc_now(),
        "payload": normalized,
        "method_files_hash": files_hash,
    }
    state = {
        "schema_version": SCHEMA_VERSION,
        "project_root": str(base),
        "active_method": active,
        "domain_profile": None,
        "search_plan": None,
        "manual_evidence": {},
        "collision_resolutions": {},
        "latest_report": None,
        "current_receipt": None,
        "current_search": None,
        "gate": {
            "status": "DOMAIN_SELECTION_REQUIRED",
            "reason": "Method changed; the main agent must register an explicit domain selection before searching.",
            "updated_at": utc_now(),
        },
    }
    method_path = guard_dir(base) / "methods" / f"v{version:04d}-{method_hash[:12]}.json"
    _atomic_json(method_path, active)
    try:
        from research_integrity_core import invalidate_for_method_change
        invalidate_for_method_change(
            base, version, method_hash, reason="canonical research method registered",
        )
    except (ImportError, ValueError) as exc:
        raise GuardError(f"Cannot invalidate dependent research-integrity receipts: {exc}") from exc
    save_state(base, state)
    _append_audit(base, "method_registered", {
        "version": version,
        "method_hash": method_hash,
        "superseded_declared_change": bool(old and old.get("pending_method_change")),
    })
    return {"changed": True, "state": state}


def refresh_domain(
    root: str | os.PathLike[str],
    *,
    primary_domain: str,
    secondary_domains: list[str] | None,
    selected_by: str,
    selection_rationale: str,
    evidence_urls: list[str] | None = None,
    discipline_profile_id: str | None = None,
) -> dict[str, Any]:
    base = project_root(root)
    state = load_state(base)
    profile = classify_domain(
        primary_domain=primary_domain,
        secondary_domains=secondary_domains,
        selected_by=selected_by,
        selection_rationale=selection_rationale,
        evidence_urls=evidence_urls,
    )
    try:
        from discipline_profile_core import resolve_discipline_overlay

        discipline_overlay = resolve_discipline_overlay(base, profile_id=discipline_profile_id)
    except (ImportError, ValueError) as exc:
        raise GuardError(f"Cannot resolve discipline profile: {exc}") from exc
    state["domain_profile"] = profile
    state["search_plan"] = make_search_plan(state["active_method"]["payload"], profile, discipline_overlay)
    state["manual_evidence"] = {}
    state["collision_resolutions"] = {}
    state["latest_report"] = None
    state["current_receipt"] = None
    state["current_search"] = None
    state["gate"] = {"status": "NOVELTY_CHECK_REQUIRED", "reason": "Search plan was rebuilt.", "updated_at": utc_now()}
    save_state(base, state)
    _append_audit(base, "domain_refreshed", {
        "profile_hash": profile["profile_hash"],
        "selected_by": selected_by,
        "selection_rationale": profile["selection_rationale"],
        "discipline_binding_hash": (discipline_overlay.get("binding") or {}).get("binding_hash"),
    })
    return profile


def get_search_plan(root: str | os.PathLike[str]) -> dict[str, Any]:
    plan = load_state(root).get("search_plan")
    if not plan:
        raise GuardError("MAIN_AGENT_SELECTION_REQUIRED: register an explicit domain selection first")
    return plan


def sync_discipline_profile_files(root: str | os.PathLike[str]) -> dict[str, Any]:
    """Fail closed when a bound registry or live field profile changes outside the plan."""
    base = project_root(root)
    state = load_state(base, required=False)
    if not state:
        return {"changed": False, "errors": [], "reason": "no_state"}
    binding = (state.get("search_plan") or {}).get("discipline_profile")
    if not binding:
        return {"changed": False, "errors": [], "reason": "legacy_plan_without_discipline_binding"}
    try:
        from discipline_profile_core import verify_overlay_binding

        errors = verify_overlay_binding(base, binding)
    except (ImportError, ValueError) as exc:
        errors = [f"discipline profile verification failed: {exc}"]
    if not errors:
        return {"changed": False, "errors": [], "binding_hash": binding.get("binding_hash")}
    fingerprint = digest(errors)
    if state.get("observed_discipline_error_hash") == fingerprint:
        return {"changed": False, "errors": errors, "requires_refresh": True}
    state["observed_discipline_error_hash"] = fingerprint
    state["latest_report"] = None
    state["current_receipt"] = None
    state["current_search"] = None
    state["gate"] = {
        "status": "NOVELTY_CHECK_REQUIRED",
        "reason": "The bound discipline registry or live profile changed; rebuild the search plan and rerun the complete collision search.",
        "updated_at": utc_now(),
    }
    save_state(base, state)
    _append_audit(base, "discipline_profile_invalidated", {"errors": errors, "error_hash": fingerprint})
    return {"changed": True, "errors": errors, "requires_refresh": True}


def list_sources(
    *, access: str | None = None, automation: str | None = None, domain: str | None = None,
) -> list[dict[str, Any]]:
    try:
        sources = json.loads(SOURCE_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardError(f"Cannot read source catalog: {exc}") from exc
    if not isinstance(sources, list):
        raise GuardError("Source catalog must be a JSON list")
    output = []
    for source in sources:
        if access and access.lower() not in str(source.get("access", "")).lower():
            continue
        if automation and automation.lower() not in str(source.get("automation", "")).lower():
            continue
        domains = [str(value).lower() for value in source.get("domains", [])]
        if domain and domain.lower() not in domains and "all" not in domains:
            continue
        output.append(source)
    return output


def _source_catalog_entry(source: str) -> dict[str, Any] | None:
    catalog_id = MANUAL_SOURCE_CATALOG_ALIASES.get(source, source)
    return next((item for item in list_sources() if item.get("id") == catalog_id), None)


def _official_hosts(source: str) -> set[str]:
    entry = _source_catalog_entry(source) or {}
    hosts = set()
    for field in ("search_url", "api_url", "docs_url"):
        value = entry.get(field)
        if value:
            host = urllib.parse.urlsplit(str(value).replace("{query}", "x")).hostname
            if host:
                hosts.add(host.lower())
    extras = {
        "wos_sci": {"webofscience.com", "www.webofscience.com", "mjl.clarivate.com", "api.clarivate.com"},
        "wos_ssci": {"webofscience.com", "www.webofscience.com", "mjl.clarivate.com", "api.clarivate.com"},
        "ieee": {"ieeexplore.ieee.org", "developer.ieee.org", "ieeexploreapi.ieee.org"},
        "ccf": {"ccf.org.cn", "www.ccf.org.cn"},
        "cssci": {"cssrac.nju.edu.cn"},
        "c_journal": {"cssrac.nju.edu.cn"},
    }
    return hosts | extras.get(source, set())


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _manual_capture(root: Path, item: str) -> tuple[Path, str]:
    normalized = item.replace("\\", "/")
    if normalized == STATE_DIR_NAME or normalized.startswith(f"{STATE_DIR_NAME}/"):
        raise GuardError("Manual evidence capture must be outside the internal .research-guard state directory")
    path = _safe_method_file(root, normalized)
    if not path.exists() or not path.is_file():
        raise GuardError(f"Manual evidence file does not exist: {normalized}")
    if path.stat().st_size == 0:
        raise GuardError("Manual evidence file is empty")
    return path, normalized


def request_manual_evidence(
    root: str | os.PathLike[str], sources: list[str] | str | None = None,
) -> dict[str, Any]:
    base = project_root(root)
    state = load_state(base)
    plan = state.get("search_plan")
    if not plan:
        raise GuardError(
            "MAIN_AGENT_SELECTION_REQUIRED: register an explicit domain selection before requesting manual evidence"
        )
    if isinstance(sources, str):
        sources = [item for item in re.split(r"[,;，；\s]+", sources) if item]
    requested = [canonical_source(item) for item in (sources or [])]
    if not requested:
        requested = list(plan.get("user_required_sources", []))
        if state.get("latest_report"):
            try:
                report = _read_relative_json(base, state["latest_report"], "collision report")
                requested = _ordered_union([report.get("missing_sources", []), requested])
            except GuardError:
                pass
    registered = state.get("manual_evidence", {})
    targets = [source for source in requested if source and source not in registered]
    requests = []
    for source in targets:
        entry = _source_catalog_entry(source) or {
            "id": source, "name": source, "search_url": None, "docs_url": None,
            "notes": "No catalog entry is available; verify the official source before registration.",
        }
        purpose = "index_membership" if source in {"ccf", "cssci", "c_journal"} else "literature_search"
        statuses = ["index_verified", "index_not_listed"] if purpose == "index_membership" else ["zero_results", "hits_present"]
        requests.append({
            "source": source,
            "name": entry.get("name"),
            "purpose": purpose,
            "search_url": entry.get("search_url"),
            "docs_url": entry.get("docs_url"),
            "accepted_statuses": statuses,
            "accepted_capture_formats": ["csv", "ris", "bib", "json", "xml", "html", "pdf", "png", "jpg", "txt"],
            "required_query_ids": [item["query_id"] for item in plan.get("query_specs", [])] if purpose == "literature_search" else [],
            "required_queries": [item["text"] for item in plan.get("query_specs", [])] if purpose == "literature_search" else [],
            "questions": [
                "请提供在该官方来源中实际使用的完整检索式、筛选条件或待核验的期刊/会议标识。",
                "请提供官方结果页 URL。",
                "请将导出结果、网页保存件或截图保存到当前项目内，并提供项目相对路径。",
                f"请从 {', '.join(statuses)} 中选择结果状态；若为 hits_present，还需提供题名、DOI、年份、载体和 URL 记录。",
            ],
        })
    return {
        "needs_user_input": bool(requests),
        "method_version": state["active_method"]["version"],
        "method_hash": state["active_method"]["hash"],
        "requests": requests,
        "registered_sources": sorted(registered),
        "next_action": "Ask the listed questions, save supplied evidence inside the project, then call register_manual_evidence once per source with the complete query_ids list.",
    }


def register_manual_evidence(
    root: str | os.PathLike[str], *, source: str, purpose: str, query: str, status: str,
    evidence_path: str, evidence_url: str, records: list[dict[str, Any]] | None = None,
    identifier: str | None = None, notes: str | None = None, expected_sha256: str | None = None,
    query_ids: list[str] | None = None,
) -> dict[str, Any]:
    base = project_root(root)
    state = load_state(base)
    normalized_source = canonical_source(source)
    purpose = str(purpose).strip().lower()
    status = str(status).strip().lower()
    query = " ".join(str(query).split())
    if purpose not in MANUAL_EVIDENCE_PURPOSES:
        raise GuardError(f"Unsupported manual evidence purpose: {purpose}")
    if status not in MANUAL_EVIDENCE_STATUSES:
        raise GuardError(f"Unsupported manual evidence status: {status}")
    if not query:
        raise GuardError("Manual evidence query or verification expression is required")
    literature_statuses = {"zero_results", "hits_present", "access_blocked", "inconclusive"}
    index_statuses = {"index_verified", "index_not_listed", "access_blocked", "inconclusive"}
    if purpose == "literature_search" and status not in literature_statuses:
        raise GuardError(f"Status {status} is incompatible with literature_search")
    if purpose == "index_membership" and status not in index_statuses:
        raise GuardError(f"Status {status} is incompatible with index_membership")
    plan = state.get("search_plan")
    if not plan:
        raise GuardError("MAIN_AGENT_SELECTION_REQUIRED: register an explicit domain selection before manual evidence")
    allowed_sources = set(plan.get("required_sources", []))
    allowed_sources.update(plan.get("manual_sources", []))
    allowed_sources.update(plan.get("index_checks", []))
    if normalized_source not in allowed_sources:
        raise GuardError(
            f"Source {normalized_source} is not in the active plan; register the method with this source requirement first"
        )
    capture, relative_capture = _manual_capture(base, evidence_path)
    capture_sha256 = _sha256_file(capture)
    if expected_sha256 and not hmac.compare_digest(capture_sha256, expected_sha256.strip().lower()):
        raise GuardError("Manual evidence file SHA-256 does not match expected_sha256")
    parsed_url = urllib.parse.urlsplit(str(evidence_url).strip())
    if parsed_url.scheme.lower() != "https" or not parsed_url.hostname:
        raise GuardError("Manual evidence URL must be an absolute official HTTPS URL")
    if parsed_url.username is not None or parsed_url.password is not None:
        raise GuardError("Manual evidence URL must not contain embedded credentials")
    allowed_hosts = _official_hosts(normalized_source)
    actual_host = parsed_url.hostname.lower()
    if not allowed_hosts or not any(actual_host == host or actual_host.endswith(f".{host}") for host in allowed_hosts):
        raise GuardError(
            f"Evidence URL host {actual_host} is not an official host configured for {normalized_source}"
        )
    raw_records = records or []
    if not isinstance(raw_records, list) or not all(isinstance(item, dict) for item in raw_records):
        raise GuardError("records must be a list of bibliographic objects")
    if status == "hits_present" and not raw_records:
        raise GuardError("hits_present evidence requires at least one bibliographic record")
    normalized_records = []
    for item in raw_records:
        work = _normalize_work(dict(item), normalized_source)
        if not work["title"]:
            raise GuardError("Every imported bibliographic record requires a title")
        if purpose == "literature_search" and work.get("link_scope") != "primary_record":
            raise GuardError(
                "Every imported literature hit requires a DOI, arXiv identifier, or primary_record_url; a search page is not a primary record"
            )
        if purpose == "literature_search":
            primary_url = urllib.parse.urlsplit(str(work.get("primary_record_url") or ""))
            primary_host = str(primary_url.hostname or "").lower()
            has_portable_identifier = bool(work.get("doi") or work.get("identifiers", {}).get("arxiv"))
            is_official_record = bool(
                primary_host and any(
                    primary_host == host or primary_host.endswith(f".{host}") for host in allowed_hosts
                )
            )
            if not has_portable_identifier and not is_official_record:
                raise GuardError(
                    "A manually imported record without a DOI/arXiv identifier must link to an official host for the selected source"
                )
        normalized_records.append(work)
    if purpose == "index_membership" and not str(identifier or "").strip():
        raise GuardError("index_membership evidence requires the verified venue or journal identifier")
    planned_query_ids = [item["query_id"] for item in state["search_plan"].get("query_specs", [])]
    normalized_query_ids = list(dict.fromkeys(str(value).strip() for value in (query_ids or []) if str(value).strip()))
    if purpose == "literature_search":
        if set(normalized_query_ids) != set(planned_query_ids):
            missing = sorted(set(planned_query_ids) - set(normalized_query_ids))
            unknown = sorted(set(normalized_query_ids) - set(planned_query_ids))
            raise GuardError(f"Manual literature evidence must cover the complete query plan; missing={missing}, unknown={unknown}")
    elif normalized_query_ids:
        raise GuardError("query_ids apply only to literature_search evidence")
    body = {
        "schema_version": SCHEMA_VERSION,
        "registered_at": utc_now(),
        "method_version": state["active_method"]["version"],
        "method_hash": state["active_method"]["hash"],
        "query_plan_hash": state["search_plan"]["plan_hash"],
        "source": normalized_source,
        "purpose": purpose,
        "query": query,
        "query_ids": normalized_query_ids,
        "status": status,
        "conclusive": status in CONCLUSIVE_MANUAL_STATUSES,
        "identifier": " ".join(str(identifier or "").split()) or None,
        "evidence_url": str(evidence_url).strip(),
        "capture_path": relative_capture,
        "capture_sha256": capture_sha256,
        "capture_size": capture.stat().st_size,
        "records": normalized_records,
        "notes": " ".join(str(notes or "").split()) or None,
    }
    body["evidence_hash"] = digest(body)
    evidence_file = (
        guard_dir(base) / "manual_evidence"
        / f"v{state['active_method']['version']:04d}-{normalized_source}-{body['evidence_hash'][:12]}.json"
    )
    existing = state.get("manual_evidence", {}).get(normalized_source)
    relative_evidence = str(evidence_file.relative_to(base)).replace("\\", "/")
    if existing == relative_evidence:
        return {"registered": False, "evidence": body, "rerun_required": True}
    _atomic_json(evidence_file, body)
    state.setdefault("manual_evidence", {})[normalized_source] = relative_evidence
    state.pop("manual_evidence_invalid", None)
    state["latest_report"] = None
    state["current_receipt"] = None
    state["current_search"] = None
    state["gate"] = {
        "status": "NOVELTY_CHECK_REQUIRED",
        "reason": f"Manual evidence registered for {normalized_source}; rerun the version-bound novelty search.",
        "updated_at": utc_now(),
    }
    save_state(base, state)
    _append_audit(base, "manual_evidence_registered", {
        "source": normalized_source, "purpose": purpose, "status": status,
        "evidence_hash": body["evidence_hash"], "capture_sha256": capture_sha256,
        "method_hash": state["active_method"]["hash"],
    })
    return {"registered": True, "evidence": body, "rerun_required": True}


def _registered_manual_evidence(base: Path, state: dict[str, Any], source: str) -> dict[str, Any] | None:
    relative = state.get("manual_evidence", {}).get(source)
    if not relative:
        return None
    evidence = _read_relative_json(base, relative, f"manual evidence for {source}")
    saved_hash = evidence.get("evidence_hash")
    unsigned = {key: value for key, value in evidence.items() if key != "evidence_hash"}
    if digest(unsigned) != saved_hash:
        raise GuardError(f"Manual evidence record hash mismatch for {source}")
    if evidence.get("method_hash") != state["active_method"]["hash"]:
        raise GuardError(f"Manual evidence method hash mismatch for {source}")
    if evidence.get("method_version") != state["active_method"]["version"]:
        raise GuardError(f"Manual evidence method version mismatch for {source}")
    if evidence.get("query_plan_hash") != state["search_plan"]["plan_hash"]:
        raise GuardError(f"Manual evidence query plan mismatch for {source}")
    capture, _ = _manual_capture(base, str(evidence.get("capture_path", "")))
    if not hmac.compare_digest(_sha256_file(capture), str(evidence.get("capture_sha256", ""))):
        raise GuardError(f"Manual evidence capture changed for {source}")
    return evidence


def sync_manual_evidence_files(root: str | os.PathLike[str]) -> dict[str, Any]:
    base = project_root(root)
    state = load_state(base, required=False)
    if not state:
        return {"changed": False, "reason": "no_state", "invalid_sources": []}
    invalid = []
    for source in state.get("manual_evidence", {}):
        try:
            _registered_manual_evidence(base, state, source)
        except GuardError as exc:
            invalid.append({"source": source, "reason": str(exc)})
    previous = state.get("manual_evidence_invalid", [])
    if invalid == previous:
        return {"changed": False, "invalid_sources": invalid}
    if invalid:
        state["manual_evidence_invalid"] = invalid
        state["latest_report"] = None
        state["current_receipt"] = None
        state["current_search"] = None
        state["gate"] = {
            "status": "NOVELTY_CHECK_REQUIRED",
            "reason": "Registered manual evidence changed or became unreadable; import it again.",
            "updated_at": utc_now(),
        }
        save_state(base, state)
        _append_audit(base, "manual_evidence_invalidated", {"invalid_sources": invalid})
        return {"changed": True, "invalid_sources": invalid}
    if "manual_evidence_invalid" in state:
        state.pop("manual_evidence_invalid", None)
        save_state(base, state)
    return {"changed": False, "invalid_sources": []}


def _request(
    url: str, headers: dict[str, str] | None = None, timeout: float = 20.0,
    *, data: bytes | None = None, method: str | None = None,
) -> bytes:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json, application/xml;q=0.9, */*;q=0.1"}
    if headers:
        request_headers.update(headers)
    host = urllib.parse.urlsplit(url).netloc
    route_failures: list[str] = []
    routes = _request_routes(url)
    for route_index, (route_name, proxy) in enumerate(routes):
        # A proxy transport failure should move to the next route immediately.
        # If this is the last available route, retain the historical one retry
        # for a transient socket failure. HTTP retry remains independent below.
        max_transport_attempts = 2 if route_index == len(routes) - 1 else 1
        transport_attempt = 0
        http_retry_used = False
        while True:
            transport_attempt += 1
            started_at = utc_now()
            request = urllib.request.Request(url, headers=request_headers, data=data, method=method)
            try:
                if proxy:
                    # ProxyHandler performs the HTTPS CONNECT handshake correctly.
                    # Request.set_proxy() can send an absolute-form target through
                    # some local forward proxies and produce a synthetic HTTP 400.
                    opener = urllib.request.build_opener(
                        urllib.request.ProxyHandler({"http": proxy, "https": proxy})
                    )
                else:
                    # An empty ProxyHandler explicitly bypasses HTTP_PROXY/HTTPS_PROXY
                    # inherited from the host for direct and fallback routes.
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                response_context = opener.open(request, timeout=timeout)
                with response_context as response:
                    body = response.read()
                    response_headers = getattr(response, "headers", None)
                    media_type = response_headers.get_content_type() if response_headers and hasattr(response_headers, "get_content_type") else None
                    record_http_response(
                        url=url, started_at=started_at, ended_at=utc_now(),
                        status_code=int(getattr(response, "status", 200)), media_type=media_type, body=body,
                        route=route_name,
                    )
                    return body
            except urllib.error.HTTPError as exc:
                try:
                    body = exc.read() if getattr(exc, "fp", None) is not None else b""
                except OSError:
                    body = b""
                media_type = exc.headers.get_content_type() if exc.headers and hasattr(exc.headers, "get_content_type") else None
                error_type = "SourceRateLimitError" if exc.code == 429 else "SourceHTTPError"
                message = f"{host} returned HTTP {exc.code} via {route_name}"
                record_http_error(
                    url=url, started_at=started_at, ended_at=utc_now(), error_type=error_type,
                    message=message, status_code=exc.code, media_type=media_type, body=body or None,
                    route=route_name,
                )
                if exc.code in {429, 500, 502, 503, 504} and not http_retry_used:
                    http_retry_used = True
                    time.sleep(1)
                    continue
                if exc.code == 429:
                    raise SourceRateLimitError(message) from None
                raise SourceHTTPError(message) from None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                reason = getattr(exc, "reason", None)
                detail = type(reason).__name__ if reason is not None else type(exc).__name__
                message = f"{host} transport failure via {route_name}: {detail}"
                record_http_error(
                    url=url, started_at=started_at, ended_at=utc_now(),
                    error_type="SourceTransportError", message=message, route=route_name,
                )
                if transport_attempt < max_transport_attempts:
                    time.sleep(1)
                    continue
                route_failures.append(f"{route_name}={detail}")
                break
    detail = ", ".join(route_failures) if route_failures else "no route completed"
    raise SourceTransportError(f"{host} transport failure; routes attempted: {detail}")


def _json_request(
    url: str, headers: dict[str, str] | None = None, timeout: float = 20.0,
    *, data: Any | None = None, method: str | None = None,
) -> Any:
    encoded = canonical_json(data).encode("utf-8") if data is not None else None
    request_headers = dict(headers or {})
    if encoded is not None:
        request_headers.setdefault("Content-Type", "application/json")
    try:
        payload = json.loads(_request(
            url, headers=request_headers, timeout=timeout, data=encoded, method=method,
        ).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourcePayloadError(f"{urllib.parse.urlsplit(url).netloc} returned malformed JSON: {type(exc).__name__}") from None
    if isinstance(payload, dict) and payload.get("error") and len(payload) <= 5:
        raise SourcePayloadError(f"{urllib.parse.urlsplit(url).netloc} returned an error-shaped success payload")
    return payload


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SourcePayloadError(f"{label} must be a JSON object")
    return value


def _list_field(container: Any, field: str, label: str) -> list[Any]:
    mapping = _mapping(container, label)
    if field not in mapping:
        raise SourcePayloadError(f"{label} is missing required field {field}")
    value = mapping[field]
    if not isinstance(value, list):
        raise SourcePayloadError(f"{label}.{field} must be a JSON array")
    return value


def _first(value: Any, default: str = "") -> str:
    if isinstance(value, list):
        return str(value[0]) if value else default
    return str(value) if value is not None else default


def _year(value: Any) -> int | None:
    text = canonical_json(value) if not isinstance(value, str) else value
    match = re.search(r"(?:19|20)\d{2}", text)
    return int(match.group(0)) if match else None


def _normalize_work(work: dict[str, Any], source: str) -> dict[str, Any]:
    title = " ".join(str(work.get("title", "")).split())
    doi_value = str(work.get("doi") or "").lower().strip()
    if re.match(r"^https?://(?:dx\.)?doi\.org/", doi_value):
        doi = urllib.parse.unquote(urllib.parse.urlsplit(doi_value).path.lstrip("/"))
    else:
        doi = re.sub(r"^doi:\s*", "", doi_value)
    raw_identifiers = work.get("identifiers") or {}
    if not isinstance(raw_identifiers, dict):
        raise SourcePayloadError("bibliographic identifiers must be an object")
    identifiers = {
        str(key): str(value).strip()
        for key, value in raw_identifiers.items()
        if str(value).strip()
    }
    if doi:
        identifiers["doi"] = doi
    for key in ("pmid", "pmcid", "arxiv", "openalex", "semantic_scholar", "nct"):
        value = work.get(key) or work.get(f"{key}_id")
        if value:
            identifiers[key] = str(value).strip()
    authors = work.get("authors") or []
    if isinstance(authors, str):
        authors = [item.strip() for item in re.split(r"[;,]", authors) if item.strip()]
    normalized_authors = []
    for author in authors if isinstance(authors, list) else []:
        if isinstance(author, dict):
            name = author.get("name") or author.get("display_name")
        else:
            name = author
        if str(name or "").strip():
            normalized_authors.append(" ".join(str(name).split()))
    neighbors = work.get("citation_neighbors") or []
    normalized_neighbors = []
    for neighbor in neighbors if isinstance(neighbors, list) else []:
        if not isinstance(neighbor, dict):
            continue
        neighbor_title = " ".join(str(neighbor.get("title") or "").split())
        neighbor_id = str(neighbor.get("paper_id") or neighbor.get("doi") or "").strip()
        if neighbor_title or neighbor_id:
            normalized_neighbors.append({"paper_id": neighbor_id or None, "title": neighbor_title})
    citation_links: list[dict[str, str]] = []
    if doi:
        citation_links.append({"kind": "doi", "url": f"https://doi.org/{doi}"})
    raw_url = str(work.get("url") or "").strip()
    if raw_url.startswith("http://"):
        raw_url = "https://" + raw_url.removeprefix("http://")
    parsed_record_url = urllib.parse.urlsplit(raw_url) if raw_url else None
    if parsed_record_url and (parsed_record_url.username is not None or parsed_record_url.password is not None):
        raise SourcePayloadError("bibliographic URL must not contain embedded credentials")
    if (
        parsed_record_url and parsed_record_url.scheme.lower() == "https" and parsed_record_url.hostname
        and raw_url not in {item["url"] for item in citation_links}
    ):
        citation_links.append({"kind": "record", "url": raw_url})
    if not citation_links and identifiers.get("arxiv"):
        citation_links.append({"kind": "arxiv", "url": f"https://arxiv.org/abs/{identifiers['arxiv']}"})
    if not citation_links:
        query = urllib.parse.urlencode({"q": title}) if title else ""
        suffix = f"?{query}" if query else ""
        citation_links.append({"kind": "verified_search", "url": f"https://search.crossref.org/{suffix}"})
    primary_link = next((item["url"] for item in citation_links if item["kind"] in {"doi", "record", "arxiv"}), None)
    raw_sources = work.get("sources") or []
    if isinstance(raw_sources, str):
        raw_sources = [raw_sources]
    if not isinstance(raw_sources, list):
        raise SourcePayloadError("bibliographic sources must be a string or array")
    sources = [str(value).strip() for value in raw_sources if str(value).strip()]
    if str(source).strip():
        sources.append(str(source).strip())
    return {
        "title": title,
        "doi": doi or None,
        "identifiers": identifiers,
        "authors": sorted(set(normalized_authors)),
        "year": work.get("year"),
        "venue": work.get("venue") or None,
        "abstract": " ".join(str(work.get("abstract") or "").split()),
        "url": work.get("url") or None,
        "citation_url": citation_links[0]["url"],
        "citation_links": citation_links,
        "primary_record_url": primary_link,
        "link_scope": "primary_record" if primary_link else "search_fallback",
        "full_text_url": work.get("full_text_url") or None,
        "is_open_access": bool(work.get("is_open_access", False)),
        "is_preprint": bool(work.get("is_preprint", False)),
        "is_retracted": bool(work.get("is_retracted", False)),
        "publication_types": sorted(set(str(value) for value in (work.get("publication_types") or []) if value)),
        "fields_of_study": sorted(set(str(value) for value in (work.get("fields_of_study") or []) if value)),
        "citation_neighbors": normalized_neighbors,
        "record_family": work.get("record_family") or "publications",
        "resource_type": work.get("resource_type") or None,
        "matched_query_ids": sorted(set(str(value) for value in (work.get("matched_query_ids") or []) if value)),
        "evidence_refs": sorted(set(str(value) for value in (work.get("evidence_refs") or []) if value)),
        "sources": sorted(set(sources)),
    }


def search_crossref(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"query": query, "rows": limit})
    payload = _json_request(f"https://api.crossref.org/works?{params}", timeout=timeout)
    works = []
    message = _mapping(_mapping(payload, "Crossref response").get("message"), "Crossref response.message")
    for item in _list_field(message, "items", "Crossref response.message"):
        works.append(_normalize_work({
            "title": _first(item.get("title")),
            "doi": item.get("DOI"),
            "year": _year(item.get("published") or item.get("created")),
            "venue": _first(item.get("container-title")),
            "abstract": item.get("abstract", ""),
            "url": item.get("URL"),
        }, "crossref"))
    return works


def search_openalex(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    key = os.environ.get("OPENALEX_API_KEY")
    params: dict[str, Any] = {"search": query, "per_page": limit}
    if key:
        params["api_key"] = key
    payload = _json_request(f"https://api.openalex.org/works?{urllib.parse.urlencode(params)}", timeout=timeout)
    works = []
    for item in _list_field(_mapping(payload, "OpenAlex response"), "results", "OpenAlex response"):
        works.append(_normalize_work({
            "title": item.get("display_name", ""),
            "doi": item.get("doi"),
            "year": item.get("publication_year"),
            "venue": (((item.get("primary_location") or {}).get("source")) or {}).get("display_name"),
            "url": item.get("id"),
        }, "openalex"))
    return works


def search_eric(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({
        "search": query, "rows": max(20, min(200, limit)), "start": 0, "format": "json",
    })
    payload = _mapping(_json_request(f"https://api.ies.ed.gov/eric/?{params}", timeout=timeout), "ERIC response")
    response = payload.get("response") if isinstance(payload.get("response"), dict) else payload
    raw_items = response.get("docs") or response.get("records") or response.get("data") or []
    if not isinstance(raw_items, list):
        raise SourcePayloadError("ERIC response records must be an array")
    works = []
    for item in raw_items[:limit]:
        if not isinstance(item, dict):
            raise SourcePayloadError("ERIC record must be an object")
        identifier = str(item.get("id") or item.get("ericid") or "").strip()
        record_url = f"https://eric.ed.gov/?id={urllib.parse.quote(identifier, safe='')}" if identifier else item.get("url")
        works.append(_normalize_work({
            "title": html.unescape(str(item.get("title", ""))),
            "year": _year(item.get("publicationdateyear") or item.get("publicationdate") or item.get("date")),
            "venue": item.get("source") or item.get("institution"),
            "abstract": item.get("description") or item.get("abstract") or "",
            "url": record_url,
            "authors": item.get("author") or item.get("authors") or [],
            "publication_types": item.get("publicationtype") or item.get("publicationtypes") or [],
            "record_family": "publications", "resource_type": "education_record",
        }, "eric"))
    return works


def search_doaj(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote(query, safe="")
    payload = _json_request(
        f"https://doaj.org/api/search/articles/{encoded}?pageSize={limit}", timeout=timeout,
    )
    works = []
    for item in _list_field(_mapping(payload, "DOAJ response"), "results", "DOAJ response"):
        bibjson = _mapping(item.get("bibjson"), "DOAJ result.bibjson")
        identifiers = {
            str(value.get("type") or "").casefold(): value.get("id")
            for value in bibjson.get("identifier", []) if isinstance(value, dict)
        }
        links = [value for value in bibjson.get("link", []) if isinstance(value, dict)]
        primary_url = next((value.get("url") for value in links if value.get("url")), None)
        authors = [
            {"name": value.get("name")} for value in bibjson.get("author", [])
            if isinstance(value, dict) and value.get("name")
        ]
        journal = bibjson.get("journal") or {}
        works.append(_normalize_work({
            "title": bibjson.get("title", ""),
            "doi": identifiers.get("doi"),
            "year": _year(bibjson.get("year")),
            "venue": journal.get("title"),
            "abstract": bibjson.get("abstract", ""),
            "url": primary_url or (f"https://doaj.org/article/{item.get('id')}" if item.get("id") else None),
            "authors": authors,
            "full_text_url": primary_url,
            "is_open_access": True,
        }, "doaj"))
    return works


def search_arxiv(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"search_query": f"all:{query}", "start": 0, "max_results": limit})
    root = ET.fromstring(_request(f"https://export.arxiv.org/api/query?{params}", timeout=timeout))
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    works = []
    for entry in root.findall("atom:entry", ns):
        works.append(_normalize_work({
            "title": entry.findtext("atom:title", default="", namespaces=ns),
            "year": _year(entry.findtext("atom:published", default="", namespaces=ns)),
            "abstract": entry.findtext("atom:summary", default="", namespaces=ns),
            "url": entry.findtext("atom:id", default="", namespaces=ns),
            "venue": "arXiv",
        }, "arxiv"))
    return works


def search_pubmed(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"db": "pubmed", "term": query, "retmode": "json", "retmax": limit})
    found = _json_request(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}", timeout=timeout)
    esearch = _mapping(_mapping(found, "PubMed search response").get("esearchresult"), "PubMed search response.esearchresult")
    ids = _list_field(esearch, "idlist", "PubMed search response.esearchresult")
    if not ids:
        return []
    summary_params = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
    payload = _json_request(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?{summary_params}", timeout=timeout)
    works = []
    result = _mapping(_mapping(payload, "PubMed summary response").get("result"), "PubMed summary response.result")
    for item_id in ids:
        item = _mapping(result.get(item_id), f"PubMed summary response.result.{item_id}")
        doi = next((aid.get("value") for aid in item.get("articleids", []) if aid.get("idtype") == "doi"), None)
        works.append(_normalize_work({
            "title": item.get("title", ""), "doi": doi, "year": _year(item.get("pubdate", "")),
            "venue": item.get("fulljournalname"), "url": f"https://pubmed.ncbi.nlm.nih.gov/{item_id}/",
        }, "pubmed"))
    return works


def search_semantic_scholar(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({
        "query": query,
        "limit": limit,
        "fields": "paperId,title,abstract,year,venue,url,externalIds,authors,isOpenAccess,openAccessPdf,publicationTypes,fieldsOfStudy,citationCount,referenceCount",
    })
    headers = {}
    if os.environ.get("SEMANTIC_SCHOLAR_API_KEY"):
        headers["x-api-key"] = os.environ["SEMANTIC_SCHOLAR_API_KEY"]
    payload = _json_request(
        f"https://api.semanticscholar.org/graph/v1/paper/search?{params}",
        headers=headers, timeout=timeout,
    )
    items = _list_field(_mapping(payload, "Semantic Scholar response"), "data", "Semantic Scholar response")
    return [_normalize_work({
        "title": item.get("title", ""),
        "doi": (item.get("externalIds") or {}).get("DOI"),
        "pmid": (item.get("externalIds") or {}).get("PubMed"),
        "arxiv": (item.get("externalIds") or {}).get("ArXiv"),
        "semantic_scholar": item.get("paperId"),
        "year": item.get("year"),
        "venue": item.get("venue"),
        "abstract": item.get("abstract", ""),
        "url": item.get("url"),
        "authors": item.get("authors") or [],
        "is_open_access": item.get("isOpenAccess", False),
        "full_text_url": (item.get("openAccessPdf") or {}).get("url"),
        "publication_types": item.get("publicationTypes") or [],
        "fields_of_study": item.get("fieldsOfStudy") or [],
    }, "semantic_scholar") for item in items]


def _search_europe_pmc_query(query: str, limit: int, timeout: float, source_label: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"query": query, "pageSize": limit, "format": "json", "resultType": "core"})
    payload = _json_request(
        f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?{params}", timeout=timeout,
    )
    result_list = _mapping(_mapping(payload, "Europe PMC response").get("resultList"), "Europe PMC response.resultList")
    items = _list_field(result_list, "result", "Europe PMC response.resultList")
    works = []
    for item in items:
        full_text_urls = ((item.get("fullTextUrlList") or {}).get("fullTextUrl") or [])
        full_text = next((entry.get("url") for entry in full_text_urls if isinstance(entry, dict) and entry.get("url")), None)
        report_details = item.get("bookOrReportDetails") or {}
        source_id = item.get("source", "")
        record_id = item.get("id", "")
        works.append(_normalize_work({
            "title": item.get("title", ""), "doi": item.get("doi"), "pmid": item.get("pmid"),
            "pmcid": item.get("pmcid"), "year": _year(item.get("pubYear", "")),
            "venue": item.get("journalTitle") or report_details.get("publisher"), "abstract": item.get("abstractText", ""),
            "url": f"https://europepmc.org/article/{source_id}/{record_id}",
            "full_text_url": full_text, "is_open_access": bool(item.get("isOpenAccess") == "Y" or full_text),
            "is_preprint": str(source_id).upper() == "PPR", "is_retracted": bool(item.get("isRetracted") == "Y"),
            "publication_types": item.get("pubTypeList", {}).get("pubType", []),
        }, source_label))
    return works


def search_europe_pmc(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    return _search_europe_pmc_query(query, limit, timeout, "europe_pmc")


def search_pmc(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    return _search_europe_pmc_query(f"({query}) AND SRC:PMC", limit, timeout, "pmc")


def _search_preprint_server(query: str, limit: int, timeout: float, server: str) -> list[dict[str, Any]]:
    works = _search_europe_pmc_query(f"({query}) AND SRC:PPR", max(limit * 3, limit), timeout, server)
    selected = []
    for work in works:
        haystack = f"{work.get('venue', '')} {work.get('url', '')}".lower()
        if server.lower() in haystack:
            selected.append(work)
    return selected[:limit]


def search_biorxiv(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    return _search_preprint_server(query, limit, timeout, "biorxiv")


def search_medrxiv(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    return _search_preprint_server(query, limit, timeout, "medrxiv")


def fetch_opencitations_neighbors(doi: str, timeout: float = 20.0, limit: int = 50) -> dict[str, Any]:
    normalized = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", str(doi).strip().lower())
    if not re.match(r"^10\.\d{4,9}/\S+$", normalized):
        raise GuardError("A valid DOI is required for OpenCitations graph expansion")
    neighbors = []
    for direction, endpoint, field in (
        ("citing", "citations", "citing"), ("referenced", "references", "cited"),
    ):
        payload = _json_request(
            f"https://opencitations.net/index/api/v2/{endpoint}/doi:{urllib.parse.quote(normalized, safe='/')}",
            timeout=timeout,
        )
        if not isinstance(payload, list):
            raise SourcePayloadError(f"OpenCitations {endpoint} response must be a JSON array")
        for item in payload[:limit]:
            identifier = str(item.get(field) or "") if isinstance(item, dict) else ""
            if identifier.startswith("doi:"):
                identifier = identifier[4:]
            if identifier:
                neighbors.append({"direction": direction, "doi": identifier.lower()})
    return {"source": "opencitations", "doi": normalized, "neighbors": neighbors, "checked_at": utc_now()}


def fetch_unpaywall_record(doi: str, timeout: float = 20.0) -> dict[str, Any]:
    normalized = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", str(doi).strip().lower())
    if not re.match(r"^10\.\d{4,9}/\S+$", normalized):
        raise GuardError("A valid DOI is required for Unpaywall lookup")
    email = os.environ.get("UNPAYWALL_EMAIL")
    if not email:
        return {
            "available": False, "status": "credential_required", "source": "unpaywall",
            "doi": normalized, "reason": "UNPAYWALL_EMAIL is required by the official API policy",
        }
    params = urllib.parse.urlencode({"email": email})
    payload = _mapping(_json_request(
        f"https://api.unpaywall.org/v2/{urllib.parse.quote(normalized, safe='/')}?{params}", timeout=timeout,
    ), "Unpaywall response")
    best = payload.get("best_oa_location") or {}
    return {
        "available": bool(payload.get("is_oa")), "status": "open" if payload.get("is_oa") else "closed",
        "source": "unpaywall", "doi": normalized,
        "full_text_url": best.get("url_for_pdf") or best.get("url_for_landing_page"),
        "host_type": best.get("host_type"), "license": best.get("license"), "checked_at": utc_now(),
    }


def search_datacite(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"query": query, "resource-type-id": "dataset", "page[size]": limit})
    payload = _json_request(f"https://api.datacite.org/dois?{params}", timeout=timeout)
    works = []
    for record in _list_field(_mapping(payload, "DataCite response"), "data", "DataCite response"):
        item = record.get("attributes", {})
        titles = item.get("titles") or []
        descriptions = item.get("descriptions") or []
        works.append(_normalize_work({
            "title": titles[0].get("title", "") if titles else "",
            "doi": item.get("doi"),
            "year": item.get("publicationYear"),
            "venue": item.get("publisher"),
            "abstract": " ".join(str(value.get("description", "")) for value in descriptions),
            "url": item.get("url") or f"https://doi.org/{item.get('doi', '')}",
            "record_family": "datasets",
            "resource_type": ((item.get("types") or {}).get("resourceTypeGeneral") or "research_output").casefold(),
        }, "datacite"))
    return works


def search_dblp(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"q": query, "h": limit, "format": "json"})
    payload = _json_request(f"https://dblp.org/search/publ/api?{params}", timeout=timeout)
    result = _mapping(_mapping(payload, "DBLP response").get("result"), "DBLP response.result")
    hits_object = _mapping(result.get("hits"), "DBLP response.result.hits")
    hits = _list_field(hits_object, "hit", "DBLP response.result.hits")
    return [_normalize_work({
        "title": (hit.get("info") or {}).get("title", ""),
        "doi": (hit.get("info") or {}).get("doi"),
        "year": _year((hit.get("info") or {}).get("year", "")),
        "venue": (hit.get("info") or {}).get("venue"),
        "url": (hit.get("info") or {}).get("ee") or (hit.get("info") or {}).get("url"),
    }, "dblp") for hit in hits]


def search_hal(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    fields = "title_s,doiId_s,producedDateY_i,journalTitle_s,uri_s,abstract_s"
    params = urllib.parse.urlencode({"q": query, "rows": limit, "wt": "json", "fl": fields})
    payload = _json_request(f"https://api.archives-ouvertes.fr/search/?{params}", timeout=timeout)
    response = _mapping(_mapping(payload, "HAL response").get("response"), "HAL response.response")
    docs = _list_field(response, "docs", "HAL response.response")
    return [_normalize_work({
        "title": _first(item.get("title_s")),
        "doi": _first(item.get("doiId_s")),
        "year": item.get("producedDateY_i"),
        "venue": _first(item.get("journalTitle_s")),
        "abstract": _first(item.get("abstract_s")),
        "url": item.get("uri_s"),
    }, "hal") for item in docs]


def _openaire_text(value: Any) -> str:
    if isinstance(value, list):
        return _openaire_text(value[0]) if value else ""
    if isinstance(value, dict):
        for key in ("$", "value", "@value"):
            if value.get(key) is not None:
                return str(value[key])
        return ""
    return str(value) if value is not None else ""


def search_openaire(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"keywords": query, "size": limit, "format": "json"})
    payload = _json_request(f"https://api.openaire.eu/search/publications?{params}", timeout=timeout)
    response = _mapping(_mapping(payload, "OpenAIRE response").get("response"), "OpenAIRE response.response")
    results_container = _mapping(response.get("results"), "OpenAIRE response.response.results")
    if "result" not in results_container:
        raise SourcePayloadError("OpenAIRE response.response.results is missing required field result")
    results = results_container["result"]
    if isinstance(results, dict):
        results = [results]
    works = []
    for result in results:
        item = (((result.get("metadata") or {}).get("oaf:entity") or {}).get("oaf:result") or {})
        pids = item.get("pid") or []
        if isinstance(pids, dict):
            pids = [pids]
        doi = next((_openaire_text(pid) for pid in pids if str(pid.get("@classid", "")).lower() == "doi"), None)
        journal = item.get("journal") or {}
        works.append(_normalize_work({
            "title": _openaire_text(item.get("title")),
            "doi": doi,
            "year": _year(_openaire_text(item.get("dateofacceptance"))),
            "venue": _openaire_text(journal.get("$")) or _openaire_text(item.get("publisher")),
            "abstract": _openaire_text(item.get("description")),
            "url": f"https://explore.openaire.eu/search/publication?pid={urllib.parse.quote(doi or _openaire_text(item.get('originalId')), safe='')}",
        }, "openaire"))
    return works


def search_zenodo(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"q": query, "size": limit})
    payload = _json_request(f"https://zenodo.org/api/records?{params}", timeout=timeout)
    works = []
    hits = _mapping(_mapping(payload, "Zenodo response").get("hits"), "Zenodo response.hits")
    for item in _list_field(hits, "hits", "Zenodo response.hits"):
        metadata = item.get("metadata") or {}
        works.append(_normalize_work({
            "title": item.get("title") or metadata.get("title", ""),
            "doi": item.get("doi"),
            "year": _year(metadata.get("publication_date") or item.get("created", "")),
            "venue": metadata.get("journal", {}).get("title") or "Zenodo",
            "abstract": metadata.get("description", ""),
            "url": (item.get("links") or {}).get("html"),
        }, "zenodo"))
    return works


def search_clinicaltrials(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"query.term": query, "pageSize": limit})
    payload = _json_request(f"https://clinicaltrials.gov/api/v2/studies?{params}", timeout=timeout)
    works = []
    for study in _list_field(_mapping(payload, "ClinicalTrials.gov response"), "studies", "ClinicalTrials.gov response"):
        protocol = study.get("protocolSection") or {}
        identification = protocol.get("identificationModule") or {}
        description = protocol.get("descriptionModule") or {}
        status = protocol.get("statusModule") or {}
        nct_id = identification.get("nctId", "")
        works.append(_normalize_work({
            "title": identification.get("briefTitle") or identification.get("officialTitle", ""),
            "year": _year(status.get("studyFirstPostDateStruct") or status.get("startDateStruct") or ""),
            "venue": "ClinicalTrials.gov",
            "abstract": description.get("briefSummary") or description.get("detailedDescription", ""),
            "url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else None,
            "nct": nct_id, "record_family": "trials", "resource_type": "clinical_trial",
        }, "clinicaltrials"))
    return works


def search_github(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"q": query, "per_page": min(limit, 100), "sort": "stars", "order": "desc"})
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = _json_request(f"https://api.github.com/search/repositories?{params}", headers=headers, timeout=timeout)
    return [_normalize_work({
        "title": item.get("full_name") or item.get("name", ""),
        "abstract": item.get("description") or "",
        "year": _year(item.get("created_at") or ""),
        "venue": "GitHub", "url": item.get("html_url"),
        "record_family": "software", "resource_type": "software_repository",
    }, "github") for item in _list_field(_mapping(payload, "GitHub response"), "items", "GitHub response")]


def search_osf(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"filter[title]": query, "page[size]": min(limit, 100)})
    payload = _json_request(f"https://api.osf.io/v2/registrations/?{params}", timeout=timeout)
    works = []
    for item in _list_field(_mapping(payload, "OSF response"), "data", "OSF response"):
        attributes = item.get("attributes") or {}
        links = item.get("links") or {}
        works.append(_normalize_work({
            "title": attributes.get("title", ""), "abstract": attributes.get("description") or "",
            "year": _year(attributes.get("date_registered") or attributes.get("date_created") or ""),
            "venue": "OSF Registries", "url": links.get("html"),
            "record_family": "preregistrations", "resource_type": "registration",
        }, "osf"))
    return works


def search_nih_reporter(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    body = {
        "criteria": {"advanced_text_search": {"operator": "and", "search_field": "projecttitle,abstracttext,terms", "search_text": query}},
        "include_fields": ["ApplId", "ProjectTitle", "AbstractText", "FiscalYear", "AgencyIcAdmin", "ProjectNum"],
        "offset": 0, "limit": min(limit, 500), "sort_field": "project_start_date", "sort_order": "desc",
    }
    payload = _json_request("https://api.reporter.nih.gov/v2/projects/search", timeout=timeout, data=body, method="POST")
    results = _list_field(_mapping(payload, "NIH RePORTER response"), "results", "NIH RePORTER response")
    works = []
    for item in results:
        appl_id = item.get("appl_id") or item.get("ApplId")
        project_num = item.get("project_num") or item.get("ProjectNum")
        record_url = (
            f"https://reporter.nih.gov/project-details/{appl_id}" if appl_id
            else f"https://reporter.nih.gov/search/{urllib.parse.quote(str(project_num or query), safe='')}"
        )
        works.append(_normalize_work({
            "title": item.get("project_title") or item.get("ProjectTitle") or "",
            "abstract": item.get("abstract_text") or item.get("AbstractText") or "",
            "year": item.get("fiscal_year") or item.get("FiscalYear"),
            "venue": item.get("agency_ic_admin") or item.get("AgencyIcAdmin") or "NIH RePORTER",
            "url": record_url, "record_family": "grants", "resource_type": "funded_project",
        }, "nih_reporter"))
    return works


def search_openaire_projects(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"keywords": query, "size": limit, "format": "json"})
    payload = _json_request(f"https://api.openaire.eu/search/projects?{params}", timeout=timeout)
    response = _mapping(_mapping(payload, "OpenAIRE project response").get("response"), "OpenAIRE project response.response")
    results_container = _mapping(response.get("results"), "OpenAIRE project response.response.results")
    results = results_container.get("result") or []
    if isinstance(results, dict):
        results = [results]
    if not isinstance(results, list):
        raise SourcePayloadError("OpenAIRE project results must be an array")
    works = []
    for result in results:
        item = (((result.get("metadata") or {}).get("oaf:entity") or {}).get("oaf:project") or {})
        project_code = _openaire_text(item.get("code")) or _openaire_text(item.get("originalId"))
        works.append(_normalize_work({
            "title": _openaire_text(item.get("title")),
            "abstract": _openaire_text(item.get("summary")),
            "year": _year(_openaire_text(item.get("startdate"))),
            "venue": _openaire_text(item.get("fundingtree")) or "OpenAIRE Projects",
            "url": f"https://explore.openaire.eu/search/project?projectId={urllib.parse.quote(project_code, safe='')}",
            "record_family": "grants", "resource_type": "funded_project",
        }, "openaire_projects"))
    return works


def search_ieee(query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
    key = os.environ.get("IEEE_API_KEY")
    if not key:
        raise GuardError("IEEE_API_KEY is required for IEEE Xplore coverage")
    params = urllib.parse.urlencode({"apikey": key, "querytext": query, "max_records": limit, "start_record": 1})
    payload = _json_request(f"https://ieeexploreapi.ieee.org/api/v1/search/articles?{params}", timeout=timeout)
    articles = _list_field(_mapping(payload, "IEEE response"), "articles", "IEEE response")
    return [_normalize_work({
        "title": item.get("title", ""), "doi": item.get("doi"), "year": item.get("publication_year"),
        "venue": item.get("publication_title"), "abstract": item.get("abstract", ""),
        "url": item.get("html_url") or item.get("pdf_url"),
    }, "ieee") for item in articles]


def search_wos(query: str, limit: int, timeout: float, database: str) -> list[dict[str, Any]]:
    key = os.environ.get("CLARIVATE_WOS_API_KEY")
    if not key:
        raise GuardError("CLARIVATE_WOS_API_KEY is required for Web of Science coverage")
    params = urllib.parse.urlencode({"db": "WOS", "q": f'TS=("{query}")', "limit": limit, "page": 1})
    payload = _json_request(
        f"https://api.clarivate.com/apis/wos-starter/v1/documents?{params}",
        headers={"X-ApiKey": key}, timeout=timeout,
    )
    response = _mapping(payload, "Web of Science response")
    if "hits" in response:
        records = response["hits"]
    elif "documents" in response:
        records = response["documents"]
    else:
        raise SourcePayloadError("Web of Science response is missing hits/documents")
    if not isinstance(records, list):
        raise SourcePayloadError("Web of Science hits/documents must be a JSON array")
    return [_normalize_work({
        "title": item.get("title", ""), "doi": item.get("doi"), "year": _year(item.get("source", {})),
        "venue": (item.get("source") or {}).get("sourceTitle"), "url": (item.get("links") or {}).get("record"),
    }, database) for item in records]


def search_manual_only(source: str) -> list[dict[str, Any]]:
    raise GuardError(f"{source} has no configured independent API adapter; verified export evidence is required")


SEARCHERS: dict[str, Callable[[str, int, float], list[dict[str, Any]]]] = {
    "crossref": search_crossref,
    "openalex": search_openalex,
    "eric": search_eric,
    "doaj": search_doaj,
    "arxiv": search_arxiv,
    "pubmed": search_pubmed,
    "semantic_scholar": search_semantic_scholar,
    "europe_pmc": search_europe_pmc,
    "pmc": search_pmc,
    "biorxiv": search_biorxiv,
    "medrxiv": search_medrxiv,
    "datacite": search_datacite,
    "dblp": search_dblp,
    "hal": search_hal,
    "openaire": search_openaire,
    "zenodo": search_zenodo,
    "clinicaltrials": search_clinicaltrials,
    "github": search_github,
    "osf": search_osf,
    "nih_reporter": search_nih_reporter,
    "openaire_projects": search_openaire_projects,
    "ieee": search_ieee,
    "wos_sci": lambda query, limit, timeout: search_wos(query, limit, timeout, "wos_sci"),
    "wos_ssci": lambda query, limit, timeout: search_wos(query, limit, timeout, "wos_ssci"),
    "cssci": lambda query, limit, timeout: search_manual_only("cssci"),
    "google_patents": lambda query, limit, timeout: search_manual_only("google_patents"),
}


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", title.lower())


def deduplicate(works: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for raw in works:
        work = _normalize_work(raw, _first(raw.get("sources"), "unknown"))
        identifiers = work.get("identifiers", {})
        identity = next(
            (f"{kind}:{identifiers[kind]}" for kind in ("doi", "pmid", "pmcid", "arxiv", "semantic_scholar", "openalex", "nct") if identifiers.get(kind)),
            None,
        )
        key = identity or f"title:{_normalize_title(work['title'])}"
        if key in ("title:", "doi:"):
            continue
        if key not in merged:
            merged[key] = work
            continue
        current = merged[key]
        current_title = _normalize_title(current.get("title", ""))
        incoming_title = _normalize_title(work.get("title", ""))
        if identity and current_title and incoming_title and current_title != incoming_title:
            current_tokens = _tokens(current_title)
            incoming_tokens = _tokens(incoming_title)
            overlap = len(current_tokens & incoming_tokens) / max(1, min(len(current_tokens), len(incoming_tokens)))
            if overlap < 0.8 and current_title not in incoming_title and incoming_title not in current_title:
                raise SourcePayloadError(f"conflicting titles share bibliographic identifier {identity}")
        current["sources"] = sorted(set(current.get("sources", []) + work.get("sources", [])))
        for field in ("doi", "year", "venue", "abstract", "url", "full_text_url"):
            if not current.get(field) and work.get(field):
                current[field] = work[field]
        current["identifiers"].update(work.get("identifiers", {}))
        links: dict[str, dict[str, str]] = {}
        for link in current.get("citation_links", []) + work.get("citation_links", []):
            if isinstance(link, dict) and str(link.get("url") or "").startswith("https://"):
                links[str(link["url"])] = dict(link)
        current["citation_links"] = list(links.values())
        if current["citation_links"]:
            current["citation_url"] = current["citation_links"][0]["url"]
        for field in ("authors", "publication_types", "fields_of_study", "matched_query_ids", "evidence_refs"):
            current[field] = sorted(set(current.get(field, []) + work.get(field, [])))
        current["is_open_access"] = bool(current.get("is_open_access") or work.get("is_open_access"))
        current["is_preprint"] = bool(current.get("is_preprint") or work.get("is_preprint"))
        current["is_retracted"] = bool(current.get("is_retracted") or work.get("is_retracted"))
        neighbors: dict[str, dict[str, Any]] = {}
        for neighbor in current.get("citation_neighbors", []) + work.get("citation_neighbors", []):
            neighbor_key = str(neighbor.get("paper_id") or _normalize_title(neighbor.get("title", "")))
            if neighbor_key:
                neighbors[neighbor_key] = neighbor
        current["citation_neighbors"] = sorted(neighbors.values(), key=lambda item: (str(item.get("paper_id") or ""), item.get("title", "")))
    return sorted(merged.values(), key=lambda item: (-(item.get("year") or 0), item.get("title", "")))


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    latin = {word for word in re.findall(r"[a-z][a-z0-9_-]{2,}", lowered) if word not in STOPWORDS}
    chinese_sequences = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
    chinese: set[str] = set()
    for sequence in chinese_sequences:
        chinese.update(sequence[index:index + 2] for index in range(len(sequence) - 1))
    return latin | chinese


def _token_sequence(text: str) -> list[str]:
    lowered = text.lower()
    latin = [word for word in re.findall(r"[a-z][a-z0-9_-]{2,}", lowered) if word not in STOPWORDS]
    chinese = []
    for sequence in re.findall(r"[\u4e00-\u9fff]{2,}", lowered):
        chinese.extend(sequence[index:index + 2] for index in range(len(sequence) - 1))
    return latin + chinese


def _text_vector(text: str) -> Counter[str]:
    sequence = _token_sequence(text)
    vector: Counter[str] = Counter(f"u:{token}" for token in sequence)
    vector.update(f"b:{left}|{right}" for left, right in zip(sequence, sequence[1:]))
    return vector


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(key, 0) for key, value in left.items())
    left_norm = sum(value * value for value in left.values()) ** 0.5
    right_norm = sum(value * value for value in right.values()) ** 0.5
    return dot / max(1e-12, left_norm * right_norm)


def _component_texts(method: dict[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    for field in ("title", "problem", "mechanism", "contributions", "datasets", "evaluation", "aliases", "keywords"):
        value = method.get(field)
        if isinstance(value, list):
            value = " ".join(str(item) for item in value)
        text = " ".join(str(value or "").split())
        if text:
            output[field] = text
    return output


def _token_containment(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    return len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))


def score_collisions(method: dict[str, Any], works: list[dict[str, Any]], thresholds: dict[str, float]) -> list[dict[str, Any]]:
    aliases = method.get("aliases") or []
    alias_text = aliases if isinstance(aliases, str) else " ".join(str(value) for value in aliases if value)
    method_text = f"{_text_from_method(method)} {alias_text}".strip()
    method_tokens = _tokens(method_text)
    method_vector = _text_vector(method_text)
    components = _component_texts(method)
    component_weights = {
        "problem": 0.22, "mechanism": 0.34, "contributions": 0.20,
        "datasets": 0.08, "evaluation": 0.08, "aliases": 0.04, "keywords": 0.04,
    }
    output = []
    for raw in works:
        work = _normalize_work(raw, _first(raw.get("sources"), "unknown"))
        work_text = f"{work.get('title', '')} {work.get('abstract', '')}"
        work_tokens = _tokens(work_text)
        common = method_tokens & work_tokens
        denominator = max(1, min(len(method_tokens), len(work_tokens)))
        lexical_overlap = len(common) / denominator
        text_vector_similarity = _cosine(method_vector, _text_vector(work_text))
        weighted_coverage = 0.0
        active_weight = 0.0
        per_component: dict[str, float] = {}
        for name, weight in component_weights.items():
            if name not in components:
                continue
            coverage = _token_containment(components[name], work_text)
            per_component[name] = round(coverage, 4)
            weighted_coverage += weight * coverage
            active_weight += weight
        component_coverage = weighted_coverage / max(active_weight, 1e-12)
        matched_queries = work.get("matched_query_ids", [])
        query_diversity = min(1.0, len(set(matched_queries)) / max(1, len(components)))
        neighbor_scores = [
            _token_containment(method_text, str(neighbor.get("title") or ""))
            for neighbor in work.get("citation_neighbors", [])
        ]
        citation_neighbor_similarity = max(neighbor_scores, default=0.0)
        exact = bool(_normalize_title(method.get("title", ""))) and _normalize_title(method.get("title", "")) == _normalize_title(work.get("title", ""))
        score = (
            0.30 * lexical_overlap
            + 0.30 * component_coverage
            + 0.20 * text_vector_similarity
            + 0.10 * query_diversity
            + 0.10 * citation_neighbor_similarity
        )
        mechanism_signal = per_component.get("mechanism", 0.0)
        problem_signal = per_component.get("problem", 0.0)
        score = max(score, 0.45 * mechanism_signal + 0.20 * problem_signal)
        score = 1.0 if exact else min(1.0, score)
        if score >= thresholds["high"]:
            level = "HIGH"
        elif score >= thresholds["potential"]:
            level = "POTENTIAL"
        else:
            level = "LOW"
        candidate = dict(work)
        identity = work.get("doi") or next(iter(sorted(work.get("identifiers", {}).values())), None) or _normalize_title(work.get("title", ""))
        fingerprint = digest({"identity": identity, "title": _normalize_title(work.get("title", ""))})
        candidate.update({
            "collision_id": f"col-{fingerprint[:20]}",
            "collision_fingerprint": fingerprint,
            "collision_score": round(score, 4),
            "collision_level": level,
            "is_exact_identity": exact,
            "shared_terms": sorted(common)[:30],
            "collision_features": {
                "lexical_overlap": round(lexical_overlap, 4),
                "text_vector_similarity": round(text_vector_similarity, 4),
                "component_coverage": round(component_coverage, 4),
                "component_scores": per_component,
                "query_diversity": round(query_diversity, 4),
                "citation_neighbor_similarity": round(citation_neighbor_similarity, 4),
            },
        })
        output.append(candidate)
    return sorted(output, key=lambda item: (-item["collision_score"], item.get("title", "")))


COLLISION_RESOLUTION_DECISIONS = {"differentiated", "duplicate", "needs_review"}


def _collision_resolution(
    base: Path, state: dict[str, Any], candidate: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    relative = state.get("collision_resolutions", {}).get(candidate["collision_id"])
    if not relative:
        return None, None
    try:
        resolution = _read_relative_json(base, relative, f"collision resolution {candidate['collision_id']}")
        saved_hash = resolution.get("resolution_hash")
        unsigned = {key: value for key, value in resolution.items() if key != "resolution_hash"}
        if digest(unsigned) != saved_hash:
            raise GuardError("resolution hash mismatch")
        checks = {
            "method hash": (resolution.get("method_hash"), state["active_method"]["hash"]),
            "method version": (resolution.get("method_version"), state["active_method"]["version"]),
            "query plan hash": (resolution.get("query_plan_hash"), state["search_plan"]["plan_hash"]),
            "collision fingerprint": (resolution.get("collision_fingerprint"), candidate["collision_fingerprint"]),
        }
        for label, (actual, expected) in checks.items():
            if actual != expected:
                raise GuardError(f"{label} mismatch")
        return resolution, None
    except GuardError as exc:
        return None, str(exc)


def record_collision_resolution(
    root: str | os.PathLike[str], *, collision_id: str, decision: str, rationale: str,
    differentiating_components: list[str] | None = None,
) -> dict[str, Any]:
    base = project_root(root)
    state = load_state(base)
    report = _read_relative_json(base, state.get("latest_report"), "collision report")
    candidate = next(
        (item for item in report.get("collision_candidates", []) if item.get("collision_id") == collision_id),
        None,
    )
    if candidate is None:
        raise GuardError(f"Collision {collision_id} is not present in the latest version-bound report")
    normalized_decision = str(decision).strip().lower()
    normalized_rationale = " ".join(str(rationale).split())
    components = sorted(set(" ".join(str(item).split()) for item in (differentiating_components or []) if str(item).strip()))
    if normalized_decision not in COLLISION_RESOLUTION_DECISIONS:
        raise GuardError(f"Unsupported collision resolution decision: {normalized_decision}")
    if len(normalized_rationale) < 40:
        raise GuardError("Collision resolution rationale must contain at least 40 characters")
    if candidate.get("is_exact_identity") and normalized_decision == "differentiated":
        raise GuardError("An exact identity collision cannot be waived; change and re-register the method")
    if normalized_decision == "differentiated" and not components:
        raise GuardError("A differentiated resolution requires at least one differentiating component")
    body = {
        "schema_version": SCHEMA_VERSION,
        "recorded_at": utc_now(),
        "method_version": state["active_method"]["version"],
        "method_hash": state["active_method"]["hash"],
        "query_plan_hash": state["search_plan"]["plan_hash"],
        "collision_id": candidate["collision_id"],
        "collision_fingerprint": candidate["collision_fingerprint"],
        "decision": normalized_decision,
        "rationale": normalized_rationale,
        "differentiating_components": components,
        "admissible_for_pass": normalized_decision == "differentiated" and not candidate.get("is_exact_identity"),
    }
    body["resolution_hash"] = digest(body)
    path = (
        guard_dir(base) / "resolutions"
        / f"v{state['active_method']['version']:04d}-{candidate['collision_id']}-{body['resolution_hash'][:12]}.json"
    )
    _atomic_json(path, body)
    relative = str(path.relative_to(base)).replace("\\", "/")
    existing = state.setdefault("collision_resolutions", {}).get(candidate["collision_id"])
    state["collision_resolutions"][candidate["collision_id"]] = relative
    state["latest_report"] = None
    state["current_receipt"] = None
    state["current_search"] = None
    state["gate"] = {
        "status": "NOVELTY_CHECK_REQUIRED",
        "reason": "A collision resolution was recorded; rerun the complete version-bound search before acceptance.",
        "updated_at": utc_now(),
    }
    save_state(base, state)
    _append_audit(base, "collision_resolution_recorded", {
        "collision_id": candidate["collision_id"], "decision": normalized_decision,
        "resolution_hash": body["resolution_hash"], "method_hash": state["active_method"]["hash"],
    })
    return {"registered": existing != relative, "resolution": body, "resolution_path": relative, "rerun_required": True}


def _signing_key_path() -> Path:
    override = os.environ.get("RESEARCH_GUARD_KEY_FILE")
    if override:
        return Path(override).expanduser().resolve()
    configured_home = os.environ.get("RESEARCH_GUARD_HOME")
    if configured_home:
        # Keep project receipts and their signing key under the same explicit
        # Research Guard home selected by the installer.  Falling back to a
        # different host profile would make a portable installation silently
        # depend on the machine that created it.
        return Path(configured_home).expanduser().resolve() / "signing.key"
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local"))
    return base / "research-guard" / "signing.key"


def _signing_key() -> bytes:
    path = _signing_key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(secrets.token_bytes(32))
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    key = path.read_bytes()
    if len(key) < 32:
        raise GuardError("Signing key is missing or too short")
    return key


def _issue_receipt(state: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema_version": SCHEMA_VERSION,
        "issued_at": utc_now(),
        "project_root": state["project_root"],
        "method_version": state["active_method"]["version"],
        "method_hash": state["active_method"]["hash"],
        "domain_profile_hash": state["domain_profile"]["profile_hash"],
        "query_plan_hash": state["search_plan"]["plan_hash"],
        "coverage_hash": report["coverage_hash"],
        "evidence_manifest_hash": report["evidence_manifest_hash"],
        "results_hash": report["report_hash"],
        "gate_status": report["gate_status"],
    }
    body["signature"] = hmac.new(_signing_key(), canonical_json(body).encode("utf-8"), hashlib.sha256).hexdigest()
    return body


def _search_run_id(state: dict[str, Any]) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"v{state['active_method']['version']:04d}-{stamp}-{secrets.token_hex(4)}"


def _fixture_payload(fixture: Any, spec: dict[str, Any]) -> Any:
    if not isinstance(fixture, dict) or "queries" not in fixture:
        return fixture
    queries = fixture.get("queries")
    if not isinstance(queries, dict):
        raise GuardError("fixture queries must be an object keyed by query_id or query text")
    return queries.get(spec["query_id"], queries.get(spec["text"], []))


def _query_work(raw: dict[str, Any], source: str, spec: dict[str, Any], evidence_refs: list[str]) -> dict[str, Any]:
    work = _normalize_work(dict(raw), source)
    work["matched_query_ids"] = sorted(set(work.get("matched_query_ids", []) + [spec["query_id"]]))
    work["evidence_refs"] = sorted(set(work.get("evidence_refs", []) + evidence_refs))
    return work


def _search_progress_path(base: Path, run_id: str) -> Path:
    return guard_dir(base) / "search-progress" / f"{run_id}.json"


def _save_search_progress(path: Path, progress: dict[str, Any]) -> None:
    body = {key: value for key, value in progress.items() if key != "progress_hash"}
    body["updated_at"] = utc_now()
    body["progress_hash"] = digest(body)
    progress.clear()
    progress.update(body)
    _atomic_json(path, progress)


def _load_search_progress(path: Path) -> dict[str, Any]:
    try:
        progress = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardError(f"Search checkpoint is unreadable: {exc}") from exc
    saved = progress.get("progress_hash")
    unsigned = {key: value for key, value in progress.items() if key != "progress_hash"}
    if not hmac.compare_digest(str(saved or ""), digest(unsigned)):
        raise GuardError("Search checkpoint hash mismatch")
    return progress


def _new_search_progress(state: dict[str, Any], plan: dict[str, Any], limit: int) -> dict[str, Any]:
    run_id = _search_run_id(state)
    required = plan["required_sources"]
    extended = set(plan.get("extended_required_sources", []))
    query_specs = plan.get("query_specs") or [
        {"query_id": f"q-legacy-{index + 1}", "kind": "legacy", "text": query, "components": []}
        for index, query in enumerate(plan["queries"])
    ]
    units = []
    for source in [*required, *plan.get("supplemental_sources", [])]:
        tier = "extended_required" if source in extended else "required" if source in required else "supplemental"
        for spec in query_specs:
            units.append({
                "unit_id": f"u{len(units) + 1:05d}",
                "source": source,
                "tier": tier,
                "query_spec": spec,
                "status": "pending",
                "attempt_count": 0,
                "run": None,
                "works": [],
            })
    return {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": "IN_PROGRESS",
        "method_version": state["active_method"]["version"],
        "method_hash": state["active_method"]["hash"],
        "query_plan_hash": plan["plan_hash"],
        "source_limit": limit,
        "research_deadline": None,
        "stop_policy": "main_agent_coverage_or_explicit_user_constraint",
        "units": units,
    }


def _unit_result(
    base: Path,
    state: dict[str, Any],
    unit: dict[str, Any],
    recorder: EvidenceRecorder,
    *,
    limit: int,
    attempt_timeout_seconds: float,
    fixture_sources: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = unit["source"]
    tier = unit["tier"]
    spec = unit["query_spec"]
    run: dict[str, Any] = {
        "unit_id": unit["unit_id"], "source": source, "tier": tier,
        "query_id": spec["query_id"], "query": spec["text"], "kind": spec["kind"],
        "started_at": utc_now(), "attempt_timeout_seconds": attempt_timeout_seconds,
        "timeout_scope": "single_transport_attempt_only",
    }
    before = len(recorder.attempts)
    normalized: list[dict[str, Any]] = []
    try:
        manual = _registered_manual_evidence(base, state, source)
        if manual is not None:
            expected_purpose = "index_membership" if source in {"ccf", "cssci", "c_journal"} else "literature_search"
            if manual.get("purpose") != expected_purpose:
                raise GuardError(
                    f"Manual evidence for {source} has purpose {manual.get('purpose')}; expected {expected_purpose}"
                )
            if not manual.get("conclusive"):
                raise GuardError(f"Manual evidence for {source} is inconclusive: {manual.get('status')}")
            if expected_purpose == "literature_search" and spec["query_id"] not in manual.get("query_ids", []):
                raise GuardError(f"Manual evidence for {source} does not cover query {spec['query_id']}")
            attempt = recorder.record_manual(source=source, query_id=spec["query_id"], query=spec["text"], evidence=manual)
            raw_works = manual.get("records", [])
            evidence_refs = [attempt["attempt_id"]]
            run["evidence_mode"] = "registered_manual_evidence"
            run["manual_evidence"] = {
                "evidence_hash": manual["evidence_hash"], "capture_sha256": manual["capture_sha256"],
                "status": manual["status"], "evidence_url": manual["evidence_url"],
            }
        elif fixture_sources is not None:
            if source not in fixture_sources:
                message = (
                    "supplemental source absent from deterministic fixture"
                    if tier == "supplemental" else "source absent from deterministic fixture"
                )
                attempt = recorder.record_fixture(
                    source=source, query_id=spec["query_id"], query=spec["text"], payload={"message": message},
                    outcome="not_tested" if tier == "supplemental" else "error",
                    error_type="NotTested" if tier == "supplemental" else "GuardError", message=message,
                )
                run.update({
                    "status": "not_tested" if tier == "supplemental" else "error",
                    "error_type": "NotTested" if tier == "supplemental" else "GuardError",
                    "message": message, "evidence_refs": [attempt["attempt_id"]],
                })
                return run, []
            fixture = _fixture_payload(fixture_sources[source], spec)
            if isinstance(fixture, dict) and (fixture.get("error") or fixture.get("error_type")):
                error_type = str(fixture.get("error_type") or "GuardError")
                message = str(fixture.get("message") or fixture.get("error"))
                attempt = recorder.record_fixture(
                    source=source, query_id=spec["query_id"], query=spec["text"], payload=fixture,
                    outcome="error", error_type=error_type, message=message,
                    status_code=fixture.get("status_code"),
                )
                run.update({
                    "status": "error", "error_type": error_type, "message": message,
                    "status_code": fixture.get("status_code"), "evidence_refs": [attempt["attempt_id"]],
                })
                return run, []
            if not isinstance(fixture, list) or not all(isinstance(item, dict) for item in fixture):
                raise SourcePayloadError("deterministic fixture must be a list of bibliographic objects")
            attempt = recorder.record_fixture(
                source=source, query_id=spec["query_id"], query=spec["text"], payload=fixture,
            )
            raw_works = fixture
            evidence_refs = [attempt["attempt_id"]]
            run["evidence_mode"] = "fixture"
        else:
            searcher = SEARCHERS.get(source)
            if not searcher:
                raise GuardError(f"No adapter configured for {source}")
            with evidence_scope(recorder, source=source, query_id=spec["query_id"], query=spec["text"]):
                raw_works = searcher(spec["text"], limit, attempt_timeout_seconds)
            evidence_refs = [item["attempt_id"] for item in recorder.attempts[before:]]
            run["evidence_mode"] = "live_api"
        normalized = [_query_work(item, source, spec, evidence_refs) for item in raw_works]
        if run.get("evidence_mode") != "fixture":
            missing_primary = [item.get("title") or "<untitled>" for item in normalized if item.get("link_scope") != "primary_record"]
            if missing_primary:
                raise SourcePayloadError(
                    f"{source} returned records without DOI or primary-record URL: {missing_primary[:3]}"
                )
        run.update({"status": "success", "result_count": len(normalized), "evidence_refs": evidence_refs})
    except (GuardError, OSError, ValueError, KeyError, ET.ParseError, urllib.error.URLError, json.JSONDecodeError) as exc:
        evidence_refs = [item["attempt_id"] for item in recorder.attempts[before:]]
        if not evidence_refs:
            attempt = recorder.record_fixture(
                source=source, query_id=spec["query_id"], query=spec["text"],
                payload={"error_type": type(exc).__name__, "message": str(exc)},
                outcome="error", error_type=type(exc).__name__, message=str(exc),
            )
            evidence_refs = [attempt["attempt_id"]]
        run.update({
            "status": "error", "error_type": type(exc).__name__, "message": str(exc),
            "evidence_refs": evidence_refs,
        })
        normalized = []
    finally:
        run["ended_at"] = utc_now()
    return run, normalized


def _coverage_from_units(units: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    coverage: dict[str, dict[str, Any]] = {}
    for source in dict.fromkeys(unit["source"] for unit in units):
        source_units = [unit for unit in units if unit["source"] == source]
        runs = [unit.get("run") or {} for unit in source_units]
        failures = [run for run in runs if run.get("status") != "success"]
        works = [work for unit in source_units for work in unit.get("works", [])]
        tier = source_units[0]["tier"]
        if failures:
            only_not_tested = all(run.get("status") == "not_tested" for run in failures)
            item = {
                "status": "not_tested" if only_not_tested else "error",
                "tier": tier, "result_count": len(works), "query_count": len(runs),
                "successful_query_count": sum(run.get("status") == "success" for run in runs),
                "failed_query_count": len(failures), "checked_at": utc_now(),
                "error_type": failures[0].get("error_type"), "message": failures[0].get("message"),
            }
        else:
            item = {
                "status": "success", "tier": tier, "result_count": len(works),
                "query_count": len(runs), "successful_query_count": len(runs),
                "failed_query_count": 0, "checked_at": utc_now(),
            }
        manual = next((run.get("manual_evidence") for run in runs if run.get("manual_evidence")), None)
        if manual:
            item.update({
                "evidence_mode": "registered_manual_evidence", "evidence_hash": manual["evidence_hash"],
                "capture_sha256": manual["capture_sha256"], "manual_status": manual["status"],
                "evidence_url": manual["evidence_url"],
            })
        coverage[source] = item
    return coverage


def _finalize_search_progress(
    base: Path,
    state: dict[str, Any],
    plan: dict[str, Any],
    progress: dict[str, Any],
    evidence_manifest: str,
    evidence_manifest_body: dict[str, Any],
) -> dict[str, Any]:
    units = progress["units"]
    query_specs = plan.get("query_specs") or []
    query_runs = [unit["run"] for unit in units]
    all_works = [work for unit in units for work in unit.get("works", [])]
    coverage = _coverage_from_units(units)
    required_sources = plan["required_sources"]
    supplemental_sources = plan.get("supplemental_sources", [])
    works = deduplicate(all_works)
    scored = score_collisions(state["active_method"]["payload"], works, plan["collision_thresholds"])
    missing = [source for source in required_sources if coverage.get(source, {}).get("status") != "success"]
    supplemental_gaps = [source for source in supplemental_sources if coverage.get(source, {}).get("status") != "success"]
    collision_candidates = [work for work in scored if work["collision_level"] in ("HIGH", "POTENTIAL")]
    unresolved_collision_candidates = []
    invalid_resolutions = []
    for candidate in collision_candidates:
        resolution, resolution_error = _collision_resolution(base, state, candidate)
        if resolution_error:
            invalid_resolutions.append({"collision_id": candidate["collision_id"], "reason": resolution_error})
        if resolution is not None:
            candidate["resolution"] = resolution
        if not resolution or not resolution.get("admissible_for_pass"):
            unresolved_collision_candidates.append(candidate)
    if missing:
        gate_status = "COVERAGE_INCOMPLETE"
        reason = f"Required sources failed after all planned units were attempted: {', '.join(missing)}"
    elif unresolved_collision_candidates:
        gate_status = "COLLISION_REVIEW_REQUIRED"
        reason = f"{len(unresolved_collision_candidates)} candidate collisions require review or method adjustment."
    else:
        gate_status = PASS_STATUS
        reason = (
            "All detected candidate collisions have valid version-bound differentiation records."
            if collision_candidates else
            "No collision found under the recorded search plan and required source coverage."
        )
        if supplemental_gaps:
            reason += f" Supplemental gaps recorded: {', '.join(supplemental_gaps)}."
    index_results: dict[str, Any] = {}
    for source in plan["index_checks"]:
        try:
            index_evidence = _registered_manual_evidence(base, state, source)
        except GuardError as exc:
            index_results[source] = {"status": "INVALID_EVIDENCE", "reason": str(exc)}
            continue
        if index_evidence and index_evidence.get("purpose") == "index_membership" and index_evidence.get("conclusive"):
            index_results[source] = {
                "status": index_evidence["status"], "identifier": index_evidence.get("identifier"),
                "evidence_hash": index_evidence["evidence_hash"],
                "capture_sha256": index_evidence["capture_sha256"], "evidence_url": index_evidence["evidence_url"],
            }
        else:
            index_results[source] = {"status": "NOT_VERIFIED"}
    discipline_binding = plan.get("discipline_profile") or {}
    report = {
        "created_at": utc_now(), "method_version": state["active_method"]["version"],
        "method_hash": state["active_method"]["hash"], "query_plan_hash": plan["plan_hash"],
        "search_run_id": progress["run_id"],
        "search_protocol": {
            "research_deadline": None,
            "transport_timeout_is_stop_condition": False,
            "stop_policy": progress["stop_policy"],
            "completed_units": len(units),
            "factual_blocker": progress.get("factual_blocker"),
        },
        "queries": [item["text"] for item in query_specs], "query_specs": query_specs,
        "query_runs": query_runs, "evidence_manifest": evidence_manifest,
        "evidence_manifest_hash": evidence_manifest_body["manifest_hash"], "coverage": coverage,
        "missing_sources": missing, "supplemental_gaps": supplemental_gaps,
        "manual_sources": plan.get("manual_sources", []), "index_checks": index_results,
        "source_families": plan.get("source_families", {}), "discipline_profile": discipline_binding,
        "discipline_literature_forms": plan.get("discipline_literature_forms", []),
        "discipline_venue_families": plan.get("discipline_venue_families", []),
        "discipline_research_methods": plan.get("discipline_research_methods", []),
        "discipline_knowledge_sources": plan.get("discipline_knowledge_sources", []),
        "discipline_data_sources": plan.get("discipline_data_sources", []),
        "discipline_method_families": plan.get("discipline_method_families", []),
        "discipline_public_catalogs": plan.get("discipline_public_catalogs", []),
        "discipline_journal_watchlist": plan.get("discipline_journal_watchlist", []),
        "discipline_boundaries": plan.get("discipline_boundaries", []),
        "family_coverage": {
            family: {
                "sources": sources,
                "status": "success" if sources and all(coverage.get(source, {}).get("status") == "success" for source in sources)
                else "not_applicable" if not sources else "incomplete",
            }
            for family, sources in plan.get("source_families", {}).items()
        },
        "works": scored, "collision_candidates": collision_candidates,
        "unresolved_collision_candidates": unresolved_collision_candidates,
        "invalid_resolutions": invalid_resolutions, "gate_status": gate_status, "gate_reason": reason,
    }
    report["coverage_hash"] = digest(coverage)
    report["report_hash"] = digest(report)
    version = state["active_method"]["version"]
    report_path = guard_dir(base) / "reports" / f"v{version:04d}-{report['report_hash'][:12]}.json"
    _atomic_json(report_path, report)
    receipt = _issue_receipt(state, report)
    receipt_path = guard_dir(base) / "receipts" / f"v{version:04d}-{report['report_hash'][:12]}.json"
    _atomic_json(receipt_path, receipt)
    state["latest_report"] = str(report_path.relative_to(base)).replace("\\", "/")
    state["current_receipt"] = str(receipt_path.relative_to(base)).replace("\\", "/")
    state["gate"] = {"status": gate_status, "reason": reason, "updated_at": utc_now()}
    save_state(base, state)
    _append_audit(base, "novelty_search_completed", {
        "method_hash": state["active_method"]["hash"], "report_hash": report["report_hash"],
        "gate_status": gate_status, "run_id": progress["run_id"],
    })
    return {"report": report, "receipt": receipt}


def run_novelty_search(
    root: str | os.PathLike[str], *, attempt_timeout_seconds: float = 20.0,
    source_limit: int | None = None, work_units_per_call: int | None = None,
    retry_unit_ids: list[str] | None = None, blocker_decision: dict[str, Any] | None = None,
    fixture_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Advance a persistent search without imposing a wall-clock research deadline."""
    if not 0 < float(attempt_timeout_seconds) <= 900:
        raise GuardError("attempt_timeout_seconds must be in (0, 900]; it applies only to one I/O attempt")
    if work_units_per_call is not None and not 1 <= int(work_units_per_call) <= 20:
        raise GuardError("work_units_per_call must be between 1 and 20")
    base = project_root(root)
    state = load_state(base)
    if state.get("pending_method_change"):
        raise GuardError("A main-agent-declared method adjustment is pending; register the adjusted method first")
    sync = sync_tracked_method_files(base)
    if sync.get("requires_registration"):
        raise GuardError("A tracked method file changed; register the complete adjusted method before searching")
    discipline_sync = sync_discipline_profile_files(base)
    if discipline_sync.get("errors"):
        raise GuardError("The bound discipline profile changed; register a new explicit domain selection")
    sync_manual_evidence_files(base)
    state = load_state(base)
    plan = state.get("search_plan")
    profile = state.get("domain_profile")
    if not plan or not profile or profile.get("selected_by") != "main_agent":
        raise GuardError("MAIN_AGENT_SELECTION_REQUIRED: register an explicit domain selection before searching")
    limit = int(source_limit or plan.get("source_limit", 12))
    relative = state.get("current_search")
    if relative:
        progress_path = (base / str(relative)).resolve()
        try:
            progress_path.relative_to(base)
        except ValueError as exc:
            raise GuardError("Search checkpoint path escapes project root") from exc
        progress = _load_search_progress(progress_path)
        if (
            progress.get("method_hash") != state["active_method"]["hash"]
            or progress.get("query_plan_hash") != plan["plan_hash"]
        ):
            raise GuardError("Current search checkpoint is bound to a different method or plan")
    else:
        progress = _new_search_progress(state, plan, limit)
        progress_path = _search_progress_path(base, progress["run_id"])
        _save_search_progress(progress_path, progress)
        state["current_search"] = str(progress_path.relative_to(base)).replace("\\", "/")
        state["latest_report"] = None
        state["current_receipt"] = None
        state["gate"] = {
            "status": "SEARCH_IN_PROGRESS",
            "reason": "Collision search has a durable checkpoint and requires further main-agent continuation.",
            "updated_at": utc_now(),
        }
        save_state(base, state)
    known_ids = {unit["unit_id"] for unit in progress["units"]}
    retry_ids = [str(value) for value in (retry_unit_ids or [])]
    unknown_retry = [value for value in retry_ids if value not in known_ids]
    if unknown_retry:
        raise GuardError(f"Unknown retry unit ids: {', '.join(unknown_retry)}")
    if retry_ids:
        for unit in progress["units"]:
            if unit["unit_id"] in retry_ids:
                unit["status"] = "pending"
                unit["run"] = None
                unit["works"] = []
        progress["status"] = "IN_PROGRESS"
        state["latest_report"] = None
        state["current_receipt"] = None
        state["gate"] = {
            "status": "SEARCH_IN_PROGRESS",
            "reason": "The main agent explicitly scheduled failed search units for retry.",
            "updated_at": utc_now(),
        }
        save_state(base, state)
        _save_search_progress(progress_path, progress)
    pending = [unit for unit in progress["units"] if unit["status"] == "pending"]
    budget = len(pending) if fixture_sources is not None and work_units_per_call is None else int(work_units_per_call or 3)
    selected_units = pending[:budget]
    recorder = EvidenceRecorder(base, progress["run_id"], resume=True)
    stage_results = []
    for unit in selected_units:
        run, works = _unit_result(
            base, state, unit, recorder, limit=limit,
            attempt_timeout_seconds=float(attempt_timeout_seconds), fixture_sources=fixture_sources,
        )
        unit["attempt_count"] = int(unit.get("attempt_count", 0)) + 1
        unit["run"] = run
        unit["works"] = works
        unit["status"] = run["status"]
        current_runs = [item["run"] for item in progress["units"] if item.get("run")]
        evidence_manifest, evidence_manifest_body = recorder.finalize(
            method_version=state["active_method"]["version"], method_hash=state["active_method"]["hash"],
            query_plan_hash=plan["plan_hash"], query_runs=current_runs,
        )
        _save_search_progress(progress_path, progress)
        stage_results.append({
            "unit_id": unit["unit_id"], "source": unit["source"], "query_id": unit["query_spec"]["query_id"],
            "status": unit["status"], "result_count": len(works),
            "results": [
                {"title": work.get("title"), "doi": work.get("doi"), "url": work.get("url")}
                for work in works
            ],
            "error_type": run.get("error_type"), "message": run.get("message"),
        })
    remaining = [unit for unit in progress["units"] if unit["status"] == "pending"]
    failed = [unit for unit in progress["units"] if unit["status"] in {"error", "not_tested"}]
    if remaining:
        progress["status"] = "IN_PROGRESS"
        _save_search_progress(progress_path, progress)
        state = load_state(base)
        state["gate"] = {
            "status": "SEARCH_IN_PROGRESS",
            "reason": f"{len(remaining)} persisted search units remain; transport timeouts do not end the research.",
            "updated_at": utc_now(),
        }
        save_state(base, state)
        return {
            "status": "IN_PROGRESS", "continue_required": True, "stop_allowed": False,
            "research_deadline": None, "transport_timeout_is_stop_condition": False,
            "checkpoint": str(progress_path.relative_to(base)).replace("\\", "/"),
            "checkpoint_hash": progress["progress_hash"], "completed_units": len(progress["units"]) - len(remaining),
            "remaining_units": len(remaining), "failed_units": [unit["unit_id"] for unit in failed],
            "stage_results": stage_results,
            "next_action": "Report these factual stage results to the user, then call run_novelty_search again.",
        }
    required_failed = [unit for unit in failed if unit["tier"] in {"required", "extended_required"}]
    if required_failed and blocker_decision is None:
        progress["status"] = "ACTION_REQUIRED"
        _save_search_progress(progress_path, progress)
        state = load_state(base)
        state["gate"] = {
            "status": "COVERAGE_ACTION_REQUIRED",
            "reason": (
                f"{len(required_failed)} required search units failed. The main agent must retry them, "
                "register admissible manual evidence, or explicitly record a factual blocker; no timer decides this choice."
            ),
            "updated_at": utc_now(),
        }
        save_state(base, state)
        return {
            "status": "ACTION_REQUIRED", "continue_required": True, "stop_allowed": False,
            "research_deadline": None, "transport_timeout_is_stop_condition": False,
            "checkpoint": str(progress_path.relative_to(base)).replace("\\", "/"),
            "checkpoint_hash": progress["progress_hash"], "completed_units": len(progress["units"]),
            "remaining_units": 0, "failed_units": [unit["unit_id"] for unit in failed],
            "required_failed_units": [unit["unit_id"] for unit in required_failed],
            "stage_results": stage_results,
            "available_actions": ["retry_unit_ids", "register_manual_evidence", "blocker_decision"],
            "next_action": (
                "Report the saved failures and linked stage evidence. Then use main-agent judgment to retry, "
                "register admissible manual evidence, or submit blocker_decision for every required failed unit."
            ),
        }
    if blocker_decision is not None:
        if not required_failed:
            raise GuardError("blocker_decision is allowed only when required search units remain failed")
        decision = dict(blocker_decision)
        if decision.get("selected_by") != "main_agent" or decision.get("decision") != "stop_with_factual_blocker":
            raise GuardError("blocker_decision requires selected_by=main_agent and decision=stop_with_factual_blocker")
        rationale = " ".join(str(decision.get("rationale") or "").split())
        if len(rationale) < 40:
            raise GuardError("blocker_decision rationale must factually explain why further progress is unavailable")
        decided_ids = [str(value) for value in decision.get("unit_ids") or []]
        required_ids = [unit["unit_id"] for unit in required_failed]
        if len(decided_ids) != len(set(decided_ids)) or set(decided_ids) != set(required_ids):
            raise GuardError("blocker_decision unit_ids must cover every currently failed required unit exactly once")
        evidence_urls = [str(value).strip() for value in decision.get("evidence_urls") or []]
        if any(not value.startswith("https://") for value in evidence_urls):
            raise GuardError("blocker_decision evidence_urls must use HTTPS")
        progress["factual_blocker"] = {
            "selected_at": utc_now(), "selected_by": "main_agent",
            "decision": "stop_with_factual_blocker", "unit_ids": decided_ids,
            "rationale": rationale, "evidence_urls": evidence_urls,
        }
        progress["factual_blocker"]["decision_hash"] = digest(progress["factual_blocker"])
    progress["status"] = "COMPLETE"
    _save_search_progress(progress_path, progress)
    current_runs = [unit["run"] for unit in progress["units"]]
    evidence_manifest, evidence_manifest_body = recorder.finalize(
        method_version=state["active_method"]["version"], method_hash=state["active_method"]["hash"],
        query_plan_hash=plan["plan_hash"], query_runs=current_runs,
    )
    state = load_state(base)
    finalized = _finalize_search_progress(
        base, state, plan, progress, evidence_manifest, evidence_manifest_body,
    )
    finalized.update({
        "status": "BLOCKED" if progress.get("factual_blocker") else "COMPLETE", "continue_required": False,
        "stop_allowed": bool(progress.get("factual_blocker")) or not required_failed,
        "research_deadline": None, "transport_timeout_is_stop_condition": False,
        "checkpoint": str(progress_path.relative_to(base)).replace("\\", "/"),
        "checkpoint_hash": progress["progress_hash"], "completed_units": len(progress["units"]),
        "remaining_units": 0, "failed_units": [unit["unit_id"] for unit in failed],
        "stage_results": stage_results,
        "factual_blocker": progress.get("factual_blocker"),
    })
    return finalized


def _read_relative_json(base: Path, relative: str | None, label: str) -> dict[str, Any]:
    if not relative:
        raise GuardError(f"No {label} is registered")
    path = (base / relative).resolve()
    try:
        path.relative_to(base)
    except ValueError as exc:
        raise GuardError(f"{label} path escapes project root") from exc
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardError(f"Cannot read {label}: {exc}") from exc


def get_collision_report(root: str | os.PathLike[str]) -> dict[str, Any]:
    base = project_root(root)
    sync_discipline_profile_files(base)
    sync_manual_evidence_files(base)
    state = load_state(base)
    return _read_relative_json(base, state.get("latest_report"), "collision report")


def get_gate_status(root: str | os.PathLike[str]) -> dict[str, Any]:
    sync_tracked_method_files(root)
    discipline_sync = sync_discipline_profile_files(root)
    sync_manual_evidence_files(root)
    state = load_state(root)
    return {
        "gate": state["gate"],
        "method_version": state["active_method"]["version"],
        "method_hash": state["active_method"]["hash"],
        "current_receipt": state.get("current_receipt"),
        "pending_method_change": state.get("pending_method_change"),
        "discipline_profile": (state.get("search_plan") or {}).get("discipline_profile"),
        "discipline_profile_errors": discipline_sync.get("errors", []),
    }


def verify_receipt(root: str | os.PathLike[str], strict: bool = False) -> dict[str, Any]:
    base = project_root(root)
    sync_tracked_method_files(base)
    discipline_sync = sync_discipline_profile_files(base)
    sync_manual_evidence_files(base)
    state = load_state(base)
    errors: list[str] = list(discipline_sync.get("errors", []))
    try:
        receipt = _read_relative_json(base, state.get("current_receipt"), "receipt")
        report = _read_relative_json(base, state.get("latest_report"), "collision report")
    except GuardError as exc:
        return {"valid": False, "strict": strict, "errors": [str(exc)], "gate_status": state["gate"]["status"]}
    signature = receipt.get("signature", "")
    unsigned = {key: value for key, value in receipt.items() if key != "signature"}
    expected = hmac.new(_signing_key(), canonical_json(unsigned).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(str(signature), expected):
        errors.append("receipt signature mismatch")
    checks = {
        "method hash": (receipt.get("method_hash"), state["active_method"]["hash"]),
        "method version": (receipt.get("method_version"), state["active_method"]["version"]),
        "domain profile hash": (receipt.get("domain_profile_hash"), state["domain_profile"]["profile_hash"]),
        "query plan hash": (receipt.get("query_plan_hash"), state["search_plan"]["plan_hash"]),
        "coverage hash": (receipt.get("coverage_hash"), report.get("coverage_hash")),
        "evidence manifest hash": (receipt.get("evidence_manifest_hash"), report.get("evidence_manifest_hash")),
        "results hash": (receipt.get("results_hash"), report.get("report_hash")),
        "gate status": (receipt.get("gate_status"), state["gate"]["status"]),
    }
    for label, (actual, wanted) in checks.items():
        if actual != wanted:
            errors.append(f"{label} mismatch")
    recomputed_report = dict(report)
    saved_report_hash = recomputed_report.pop("report_hash", None)
    if digest(recomputed_report) != saved_report_hash:
        errors.append("collision report hash mismatch")
    errors.extend(verify_evidence_manifest(base, str(report.get("evidence_manifest", ""))))
    if strict and state["gate"]["status"] != PASS_STATUS:
        errors.append(f"strict gate is {state['gate']['status']}")
    return {
        "valid": not errors,
        "strict": strict,
        "errors": errors,
        "gate_status": state["gate"]["status"],
        "method_version": state["active_method"]["version"],
        "method_hash": state["active_method"]["hash"],
    }


def sync_tracked_method_files(root: str | os.PathLike[str]) -> dict[str, Any]:
    base = project_root(root)
    state = load_state(base, required=False)
    if not state:
        return {"changed": False, "reason": "no_state"}
    files = state.get("active_method", {}).get("payload", {}).get("method_files", [])
    current = method_files_fingerprint(base, files)
    previous = state.get("active_method", {}).get("method_files_hash")
    if current == previous:
        return {"changed": False, "requires_registration": False, "fingerprint": current}
    already_observed = state.get("observed_method_files_hash") == current
    if already_observed:
        return {"changed": False, "requires_registration": True, "fingerprint": current}
    state["observed_method_files_hash"] = current
    state["latest_report"] = None
    state["current_receipt"] = None
    state["current_search"] = None
    state["gate"] = {
        "status": "NOVELTY_CHECK_REQUIRED",
        "reason": "A tracked method file changed; register the complete adjusted method and search again.",
        "updated_at": utc_now(),
    }
    try:
        from research_integrity_core import invalidate_for_method_change
        invalidate_for_method_change(
            base,
            state["active_method"]["version"],
            state["active_method"]["hash"],
            reason="tracked research method file changed",
        )
    except (ImportError, ValueError) as exc:
        raise GuardError(f"Cannot invalidate dependent research-integrity receipts: {exc}") from exc
    save_state(base, state)
    _append_audit(base, "tracked_method_file_changed", {"old_fingerprint": previous, "new_fingerprint": current})
    return {"changed": True, "requires_registration": True, "fingerprint": current}


def verify_publication(doi: str, timeout: float = 20.0) -> dict[str, Any]:
    normalized = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi.strip().lower())
    doi_url = f"https://doi.org/{normalized}" if normalized else ""
    search_url = f"https://search.crossref.org/?{urllib.parse.urlencode({'q': normalized or doi})}"
    if not re.match(r"^10\.\d{4,9}/\S+$", normalized):
        return {
            "verified": False, "doi": normalized, "reason": "invalid DOI syntax",
            "citation_url": search_url, "citation_links": [{"kind": "verified_search", "url": search_url}],
        }
    try:
        payload = _json_request(f"https://api.crossref.org/works/{urllib.parse.quote(normalized, safe='')}", timeout=timeout)
        item = payload.get("message", {})
        return {
            "verified": bool(item.get("DOI")), "doi": normalized, "title": _first(item.get("title")),
            "venue": _first(item.get("container-title")), "publisher": item.get("publisher"),
            "source": "crossref", "checked_at": utc_now(), "citation_url": doi_url,
            "citation_links": [{"kind": "doi", "url": doi_url}],
        }
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {
            "verified": False, "doi": normalized, "reason": str(exc), "source": "crossref", "checked_at": utc_now(),
            "citation_url": doi_url, "citation_links": [{"kind": "doi", "url": doi_url}],
        }


def verify_index_membership(identifier: str, index: str) -> dict[str, Any]:
    supported = {"ccf", "ieee", "wos_sci", "wos_ssci", "cssci", "c_journal"}
    normalized = index.lower().strip()
    if normalized not in supported:
        return {"verified": False, "identifier": identifier, "index": normalized, "reason": "unsupported index"}
    return {
        "verified": False,
        "identifier": identifier,
        "index": normalized,
        "reason": "No independently validated index-membership record is configured; do not claim membership.",
        "checked_at": utc_now(),
    }
