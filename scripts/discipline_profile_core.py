from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = PLUGIN_ROOT / "assets" / "discipline-registry.json"
STATE_DIRECTORY = ".research-guard"
PROFILE_DIRECTORY = "discipline-profiles"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_JOURNALS = 20
MAX_BOOKS = 12
MAX_PRIMARY_SOURCES = 12
USER_AGENT = "research-guard/0.6 (bounded discipline initializer)"
DOMESTIC_OR_LOCAL_SUFFIXES = (".cn", ".com.cn", ".edu.cn", ".org.cn")


class DisciplineProfileError(ValueError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
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


def _https(value: Any, field: str) -> str:
    text = str(value or "").strip()
    parsed = urllib.parse.urlsplit(text)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise DisciplineProfileError(f"{field} must be an absolute HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise DisciplineProfileError(f"{field} must not contain embedded credentials")
    return text


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", str(value).strip().casefold()).strip("-")
    if not normalized:
        raise DisciplineProfileError("A non-empty discipline is required")
    encoded = normalized.encode("utf-8")
    if len(encoded) > 80:
        normalized = f"discipline-{hashlib.sha256(encoded).hexdigest()[:16]}"
    return normalized


def _profile_root(project_root: str | os.PathLike[str]) -> Path:
    return Path(project_root).expanduser().resolve() / STATE_DIRECTORY / PROFILE_DIRECTORY


def _profile_path(project_root: str | os.PathLike[str], profile_id: str) -> Path:
    return _profile_root(project_root) / _slug(profile_id) / "profile.json"


def load_registry() -> dict[str, Any]:
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DisciplineProfileError(f"Cannot read discipline registry: {exc}") from exc
    if registry.get("schema_version") != SCHEMA_VERSION:
        raise DisciplineProfileError("Unsupported discipline registry schema")
    disciplines = registry.get("disciplines")
    if not isinstance(disciplines, list) or not disciplines:
        raise DisciplineProfileError("Discipline registry must contain profiles")
    ids: set[str] = set()
    for item in disciplines:
        if not isinstance(item, dict):
            raise DisciplineProfileError("Every discipline profile must be an object")
        profile_id = str(item.get("id") or "")
        if not re.fullmatch(r"[a-z0-9_-]+", profile_id) or profile_id in ids:
            raise DisciplineProfileError(f"Invalid or duplicate discipline id: {profile_id}")
        ids.add(profile_id)
        if item.get("kind") not in {"broad", "specialized"}:
            raise DisciplineProfileError(f"Invalid discipline kind: {profile_id}")
        for field in ("keywords", "literature_forms", "required_sources", "supplemental_sources", "query_lenses", "catalogs", "boundaries"):
            if not isinstance(item.get(field), list):
                raise DisciplineProfileError(f"{profile_id}.{field} must be a list")
    for catalog_id, catalog in (registry.get("public_catalogs") or {}).items():
        _https(catalog.get("url"), f"public_catalogs.{catalog_id}.url")
    registry["registry_hash"] = digest({key: value for key, value in registry.items() if key != "registry_hash"})
    return registry


def _entry_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): item for item in registry["disciplines"]}


def _match_term(text: str, term: str) -> bool:
    lowered = term.casefold()
    if re.search(r"[a-z0-9]", lowered):
        return re.search(rf"(?<![a-z0-9_]){re.escape(lowered)}(?![a-z0-9_])", text) is not None
    return lowered in text


def detect_discipline(
    request_text: str,
    discipline: str | None = None,
    *,
    broad_domain: str | None = None,
) -> dict[str, Any]:
    """Resolve only an explicit main-agent selection; never infer a field from request text."""
    registry = load_registry()
    explicit = " ".join(str(discipline or "").split())
    if not explicit:
        raise DisciplineProfileError(
            "MAIN_AGENT_SELECTION_REQUIRED: discipline must be selected explicitly; request_text is not classified"
        )
    normalized = explicit.casefold()
    for entry in registry["disciplines"]:
        labels = [str(value).casefold() for value in (entry.get("labels") or {}).values()]
        if normalized == str(entry["id"]).casefold() or normalized in labels:
            return {
                "registered": True,
                "profile_id": entry["id"],
                "label": entry["labels"],
                "broad_domain": entry["broad_domain"],
                "kind": entry["kind"],
                "selected_explicitly": True,
                "registry_entry_hash": digest(entry),
            }
    allowed_broad = {str(item["broad_domain"]) for item in registry["disciplines"]} | {"general"}
    selected_broad = str(broad_domain or "").strip()
    if selected_broad not in allowed_broad:
        raise DisciplineProfileError(
            "An unregistered discipline requires an explicit broad_domain chosen by the main agent; "
            f"choose from: {', '.join(sorted(allowed_broad))}"
        )
    label = explicit
    return {
        "registered": False,
        "profile_id": _slug(label),
        "label": {"en": label, "zh": label},
        "broad_domain": selected_broad,
        "kind": "dynamic",
        "selected_explicitly": True,
        "registry_entry_hash": None,
    }


def _foreign_proxy_for(url: str) -> str | None:
    host = (urllib.parse.urlsplit(url).hostname or "").casefold()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(DOMESTIC_OR_LOCAL_SUFFIXES):
        return None
    value = os.environ.get("RESEARCH_GUARD_FOREIGN_PROXY", "http://127.0.0.1:7897").strip()
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise DisciplineProfileError("RESEARCH_GUARD_FOREIGN_PROXY must be a credential-free HTTP(S) proxy URL")
    return value


def _fetch_json(url: str, timeout: float) -> tuple[Any, bytes]:
    _https(url, "request_url")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    proxy = _foreign_proxy_for(url)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
    )
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with opener.open(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise DisciplineProfileError(f"Response exceeded {MAX_RESPONSE_BYTES} bytes")
            return json.loads(raw.decode("utf-8")), raw
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_error = exc
            retryable = not isinstance(exc, urllib.error.HTTPError) or exc.code in {429, 500, 502, 503, 504}
            if attempt == 0 and retryable:
                time.sleep(1)
                continue
            break
    raise DisciplineProfileError(f"{urllib.parse.urlsplit(url).hostname} discovery failed: {type(last_error).__name__}") from None


def _source_urls(label: str, include_humanities: bool) -> dict[str, str]:
    quoted = urllib.parse.quote(label, safe="")
    encoded = urllib.parse.urlencode({"query.bibliographic": label, "filter": "type:journal-article", "rows": 12})
    urls = {
        "openalex": f"https://api.openalex.org/works?search={quoted}&filter=type:article&per_page=12",
        "crossref": f"https://api.crossref.org/works?{encoded}",
        "doaj": f"https://doaj.org/api/search/journals/{quoted}?pageSize=12",
    }
    if include_humanities:
        book_query = urllib.parse.urlencode({"q": label, "fields": "key,title,author_name,first_publish_year,isbn,edition_count", "limit": 8})
        loc_query = urllib.parse.urlencode({"q": label, "fo": "json", "at": "results", "c": 8})
        urls["openlibrary"] = f"https://openlibrary.org/search.json?{book_query}"
        urls["library_of_congress"] = f"https://www.loc.gov/search/?{loc_query}"
    return urls


def _issns(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    result = []
    for item in values:
        normalized = re.sub(r"[^0-9Xx]", "", str(item or "")).upper()
        if len(normalized) == 8:
            formatted = f"{normalized[:4]}-{normalized[4:]}"
            if formatted not in result:
                result.append(formatted)
    return result


def _candidate_key(title: str, issns: list[str]) -> str:
    if issns:
        return f"issn:{sorted(issns)[0]}"
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", title.casefold())
    return f"title:{normalized}"


def _merge_journal(target: dict[str, dict[str, Any]], *, title: Any, issns: Any, source: str, evidence_urls: list[Any]) -> None:
    normalized_title = " ".join(str(title or "").split())
    normalized_issns = _issns(issns)
    if not normalized_title:
        return
    key = _candidate_key(normalized_title, normalized_issns)
    for candidate_key, candidate in target.items():
        if normalized_issns and set(normalized_issns) & set(candidate["issns"]):
            key = candidate_key
            break
    item = target.setdefault(key, {
        "title": normalized_title,
        "issns": [],
        "sources": [],
        "evidence_urls": [],
        "observed_records": 0,
    })
    item["issns"] = sorted(set(item["issns"] + normalized_issns))
    item["sources"] = sorted(set(item["sources"] + [source]))
    safe_urls = []
    for value in evidence_urls:
        try:
            safe_urls.append(_https(value, "journal evidence URL"))
        except DisciplineProfileError:
            continue
    item["evidence_urls"] = sorted(set(item["evidence_urls"] + safe_urls))
    item["observed_records"] += 1


def _extract_journals(payloads: dict[str, Any]) -> list[dict[str, Any]]:
    journals: dict[str, dict[str, Any]] = {}
    for item in (payloads.get("openalex") or {}).get("results", []):
        source = ((item.get("primary_location") or {}).get("source") or {}) if isinstance(item, dict) else {}
        if not source:
            continue
        urls = [source.get("id"), item.get("id"), item.get("doi")]
        _merge_journal(
            journals, title=source.get("display_name"), issns=source.get("issn") or source.get("issn_l"),
            source="openalex", evidence_urls=urls,
        )
    crossref_items = ((payloads.get("crossref") or {}).get("message") or {}).get("items", [])
    for item in crossref_items:
        if not isinstance(item, dict):
            continue
        titles = item.get("container-title") or []
        title = titles[0] if isinstance(titles, list) and titles else titles
        issns = _issns(item.get("ISSN") or [])
        journal_url = f"https://api.crossref.org/journals/{urllib.parse.quote(issns[0], safe='')}" if issns else None
        doi = str(item.get("DOI") or "").strip()
        _merge_journal(
            journals, title=title, issns=issns, source="crossref",
            evidence_urls=[journal_url, f"https://doi.org/{doi}" if doi else item.get("URL")],
        )
    for item in (payloads.get("doaj") or {}).get("results", []):
        if not isinstance(item, dict):
            continue
        bibjson = item.get("bibjson") or {}
        issns = _issns([bibjson.get("pissn"), bibjson.get("eissn")])
        record_url = f"https://doaj.org/toc/{urllib.parse.quote(issns[0], safe='')}" if issns else f"https://doaj.org/api/journals/{item.get('id')}"
        _merge_journal(
            journals, title=bibjson.get("title"), issns=issns, source="doaj", evidence_urls=[record_url],
        )
    ordered = sorted(
        journals.values(),
        key=lambda item: (-len(item["sources"]), -item["observed_records"], item["title"].casefold()),
    )[:MAX_JOURNALS]
    for index, item in enumerate(ordered, 1):
        item["candidate_order"] = index
        item["interpretation"] = "discovery candidate, not quality rank or index-membership evidence"
    return ordered


def _extract_books(payload: Any) -> list[dict[str, Any]]:
    books = []
    for item in (payload or {}).get("docs", [])[:MAX_BOOKS]:
        key = str(item.get("key") or "")
        url = f"https://openlibrary.org{key}" if key.startswith("/") else ""
        if not url:
            continue
        books.append({
            "title": " ".join(str(item.get("title") or "").split()),
            "authors": [" ".join(str(value).split()) for value in (item.get("author_name") or [])[:8]],
            "first_publish_year": item.get("first_publish_year"),
            "isbn": [str(value) for value in (item.get("isbn") or [])[:5]],
            "record_url": _https(url, "Open Library record URL"),
            "source": "openlibrary",
        })
    return [item for item in books if item["title"]]


def _extract_primary_sources(payload: Any) -> list[dict[str, Any]]:
    records = []
    for item in (payload or {}).get("results", [])[:MAX_PRIMARY_SOURCES]:
        if not isinstance(item, dict):
            continue
        raw_url = str(item.get("id") or item.get("url") or "")
        if raw_url.startswith("http://"):
            raw_url = "https://" + raw_url.removeprefix("http://")
        try:
            record_url = _https(raw_url, "Library of Congress record URL")
        except DisciplineProfileError:
            continue
        title = " ".join(str(item.get("title") or "").split())
        if title:
            records.append({
                "title": title,
                "date": item.get("date"),
                "original_format": item.get("original_format") or [],
                "record_url": record_url,
                "source": "library_of_congress",
                "interpretation": "catalog discovery record; relevance and primary-source status require human verification",
            })
    return records


def _static_contract(detected: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    if not detected["registered"]:
        return {
            "id": detected["profile_id"], "kind": "dynamic", "broad_domain": detected["broad_domain"],
            "labels": detected["label"], "literature_forms": ["journal_article", "book", "book_chapter", "review"],
            "required_sources": ["openalex"], "supplemental_sources": ["doaj"],
            "index_checks": [], "manual_sources": [],
            "query_lenses": ["field terminology", "review and prior work"], "catalogs": [],
            "boundaries": ["The dynamic profile is provisional and source-bounded."],
        }
    return dict(_entry_map(registry)[detected["profile_id"]])


def _catalog_records(contract: dict[str, Any], registry: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    catalog = registry.get("public_catalogs") or {}
    for catalog_id in contract.get("catalogs", []):
        item = dict(catalog.get(catalog_id) or {})
        if not item:
            raise DisciplineProfileError(f"Unknown public catalog: {catalog_id}")
        item["id"] = catalog_id
        item["url"] = _https(item.get("url"), f"catalog {catalog_id}")
        records.append(item)
    return records


def _read_profile(path: Path, project_root: Path | None = None) -> dict[str, Any]:
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DisciplineProfileError(f"Cannot read discipline profile {path}: {exc}") from exc
    if profile.get("schema_version") != SCHEMA_VERSION:
        raise DisciplineProfileError("Unsupported discipline profile schema")
    saved_hash = profile.get("profile_hash")
    unsigned = {key: value for key, value in profile.items() if key != "profile_hash"}
    if not hmac.compare_digest(str(saved_hash or ""), digest(unsigned)):
        raise DisciplineProfileError("Discipline profile hash mismatch")
    root = project_root or path.parents[3]
    for run in profile.get("source_runs", []):
        relative = run.get("evidence_path")
        expected = run.get("response_sha256")
        if not relative:
            continue
        evidence = (root / relative).resolve()
        try:
            evidence.relative_to(root)
        except ValueError as exc:
            raise DisciplineProfileError("Discipline evidence path escapes project root") from exc
        if not evidence.is_file() or not hmac.compare_digest(_sha256(evidence), str(expected or "")):
            raise DisciplineProfileError(f"Discipline evidence changed: {relative}")
    return profile


def _existing_profile(project_root: Path, profile_id: str) -> dict[str, Any] | None:
    path = _profile_path(project_root, profile_id)
    if not path.is_file():
        return None
    return _read_profile(path, project_root)


def initialize_discipline(
    project_root: str | os.PathLike[str], *, discipline: str, request_text: str = "",
    broad_domain: str | None = None, selected_by: str, selection_rationale: str,
    force: bool = False, attempt_timeout_seconds: float = 30.0,
    fixture_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if selected_by != "main_agent":
        raise DisciplineProfileError("selected_by=main_agent is required for discipline initialization")
    rationale = " ".join(str(selection_rationale or "").split())
    if len(rationale) < 12:
        raise DisciplineProfileError("selection_rationale must explain the main agent's discipline choice")
    base = Path(project_root).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    detected = detect_discipline(request_text, discipline, broad_domain=broad_domain)
    profile_id = detected["profile_id"]
    path = _profile_path(base, profile_id)
    if not force and path.is_file():
        existing = _read_profile(path, base)
        return {
            "status": existing["status"], "reused": True, "profile": existing,
            "first_build_notice": load_registry()["first_build_notice"],
        }
    registry = load_registry()
    contract = _static_contract(detected, registry)
    label = " ".join(str(discipline or (contract.get("labels") or {}).get("en") or profile_id).split())
    include_humanities = contract.get("broad_domain") == "humanities" or contract.get("id") == "history"
    source_urls = _source_urls(label, include_humanities)
    payloads: dict[str, Any] = {}
    source_runs = []
    source_mode = "fixture" if fixture_sources is not None else "live"
    evidence_root = path.parent / "evidence"
    for source, url in source_urls.items():
        started_at = utc_now()
        try:
            if fixture_sources is not None:
                if source not in fixture_sources:
                    raise DisciplineProfileError(f"fixture source missing: {source}")
                payload = fixture_sources[source]
                raw = canonical_json(payload).encode("utf-8")
            else:
                payload, raw = _fetch_json(url, attempt_timeout_seconds)
            if not isinstance(payload, dict):
                raise DisciplineProfileError(f"{source} response must be a JSON object")
            response_hash = hashlib.sha256(raw).hexdigest()
            evidence_path = evidence_root / f"{source}-{response_hash[:16]}.json"
            _atomic_json(evidence_path, payload)
            relative = str(evidence_path.relative_to(base)).replace("\\", "/")
            payloads[source] = payload
            source_runs.append({
                "source": source, "status": "success", "mode": source_mode,
                "request_url": _https(url, f"{source} request URL"),
                "started_at": started_at, "ended_at": utc_now(),
                "response_bytes": len(raw), "response_sha256": _sha256(evidence_path),
                "evidence_path": relative,
            })
        except DisciplineProfileError as exc:
            source_runs.append({
                "source": source, "status": "error", "mode": source_mode,
                "request_url": _https(url, f"{source} request URL"),
                "started_at": started_at, "ended_at": utc_now(),
                "error_type": type(exc).__name__, "message": str(exc),
            })
    journals = _extract_journals(payloads)
    required_live_sources = list(registry["live_journal_sources"])
    missing = [source for source in required_live_sources if not any(run["source"] == source and run["status"] == "success" for run in source_runs)]
    if source_mode != "live":
        status = "FIXTURE_ONLY"
    elif missing or not journals:
        status = "COVERAGE_INCOMPLETE"
    else:
        status = "PASS"
    body = {
        "schema_version": SCHEMA_VERSION,
        "profile_id": profile_id,
        "label": label,
        "detected": detected,
        "selected_by": selected_by,
        "selection_rationale": rationale,
        "automatic_classification": False,
        "registered_static": bool(detected["registered"]),
        "broad_domain": contract.get("broad_domain", "general"),
        "initialized_at": utc_now(),
        "source_mode": source_mode,
        "status": status,
        "admissible_for_novelty": status == "PASS",
        "required_live_sources": required_live_sources,
        "missing_live_sources": missing,
        "static_contract": contract,
        "public_catalogs": _catalog_records(contract, registry),
        "journal_candidates": journals,
        "book_candidates": _extract_books(payloads.get("openlibrary")),
        "primary_source_candidates": _extract_primary_sources(payloads.get("library_of_congress")),
        "source_runs": source_runs,
        "interpretation_boundary": registry["interpretation_boundary"],
        "first_build_notice": registry["first_build_notice"],
        "registry_hash": registry["registry_hash"],
    }
    body["profile_hash"] = digest(body)
    previous_hash = None
    if path.is_file():
        try:
            previous_hash = _read_profile(path, base).get("profile_hash")
        except DisciplineProfileError:
            previous_hash = "invalid"
    _atomic_json(path, body)
    domain_reselection_required = bool(
        previous_hash != body["profile_hash"] and (base / STATE_DIRECTORY / "state.json").is_file()
    )
    return {
        "status": status,
        "reused": False,
        "profile": body,
        "novelty_plan_refreshed": False,
        "domain_reselection_required": domain_reselection_required,
        "complete_collision_rerun_required": domain_reselection_required,
        "first_build_notice": registry["first_build_notice"],
    }


def analyze_discipline(
    project_root: str | os.PathLike[str], *, request_text: str, discipline: str | None = None,
    broad_domain: str | None = None, selected_by: str, selection_rationale: str,
) -> dict[str, Any]:
    if selected_by != "main_agent":
        raise DisciplineProfileError("selected_by=main_agent is required for discipline analysis")
    rationale = " ".join(str(selection_rationale or "").split())
    if len(rationale) < 12:
        raise DisciplineProfileError("selection_rationale must explain the main agent's discipline choice")
    detected = detect_discipline(request_text, discipline, broad_domain=broad_domain)
    registry = load_registry()
    if not detected["registered"]:
        return {
            "status": "INITIALIZATION_REQUIRED",
            "detected": detected,
            "selected_by": selected_by,
            "selection_rationale": rationale,
            "automatic_initialization": False,
            "first_build_notice": registry["first_build_notice"],
            "next_action": "Call discipline_action=initialize with the same explicit selection after informing the user.",
        }
    entry = _entry_map(registry)[detected["profile_id"]]
    try:
        live = _existing_profile(Path(project_root).expanduser().resolve(), detected["profile_id"])
    except DisciplineProfileError as exc:
        live = {"status": "INVALID", "error": str(exc)}
    return {
        "status": "REGISTERED_LIVE" if live and live.get("status") == "PASS" else "REGISTERED_STATIC",
        "detected": detected,
        "selected_by": selected_by,
        "selection_rationale": rationale,
        "automatic_initialization": False,
        "current_optimizations": entry,
        "public_catalogs": _catalog_records(entry, registry),
        "live_profile": live,
        "live_initialization_recommended": not bool(live and live.get("status") == "PASS"),
        "first_build_notice": registry["first_build_notice"],
    }


def resolve_discipline_overlay(
    project_root: str | os.PathLike[str], *, profile_id: str | None,
) -> dict[str, Any]:
    """Bind only a profile id already selected by the main agent."""
    if not profile_id:
        return {
            "binding": None,
            "required_sources": [],
            "supplemental_sources": [],
            "index_checks": [],
            "manual_sources": [],
            "query_lenses": [],
            "literature_forms": [],
            "public_catalogs": [],
            "journal_watchlist": [],
            "boundaries": [],
        }
    registry = load_registry()
    entries = _entry_map(registry)
    selected_id = _slug(profile_id)
    contract = entries.get(selected_id)
    base = Path(project_root).expanduser().resolve()
    live_error = None
    try:
        live = _existing_profile(base, selected_id)
    except DisciplineProfileError as exc:
        live = None
        live_error = str(exc)
    if contract is None and live is None:
        raise DisciplineProfileError(
            f"DISCIPLINE_INITIALIZATION_REQUIRED: explicit profile {selected_id} is not registered; "
            "initialize it before binding the domain route"
        )
    if contract is None:
        contract = dict(live.get("static_contract") or {})
    live_admissible = bool(live and live.get("admissible_for_novelty"))
    binding = {
        "profile_id": selected_id,
        "label": (contract.get("labels") or (live or {}).get("detected", {}).get("label") or {"en": selected_id}),
        "broad_domain": contract.get("broad_domain", "general"),
        "registered_static": selected_id in entries,
        "selected_by": "main_agent",
        "automatic_classification": False,
        "registry_hash": registry["registry_hash"],
        "registry_entry_hash": digest(contract),
        "live_profile_path": (
            str(_profile_path(base, selected_id).relative_to(base)).replace("\\", "/")
            if live is not None else None
        ),
        "live_profile_hash": live.get("profile_hash") if live else None,
        "live_profile_status": live.get("status") if live else "NOT_INITIALIZED",
        "live_profile_error": live_error,
        "initialization_required": False,
        "first_build_notice": registry["first_build_notice"],
    }
    binding["binding_hash"] = digest(binding)
    return {
        "binding": binding,
        "required_sources": list(contract.get("required_sources", [])),
        "supplemental_sources": list(contract.get("supplemental_sources", [])),
        "index_checks": list(contract.get("index_checks", [])),
        "manual_sources": list(contract.get("manual_sources", [])),
        "query_lenses": list(contract.get("query_lenses", []))[:2],
        "literature_forms": list(contract.get("literature_forms", [])),
        "public_catalogs": _catalog_records(contract, registry),
        "journal_watchlist": (live.get("journal_candidates", [])[:12] if live_admissible else []),
        "boundaries": list(contract.get("boundaries", [])),
    }


def verify_overlay_binding(project_root: str | os.PathLike[str], binding: dict[str, Any]) -> list[str]:
    errors = []
    saved_binding_hash = binding.get("binding_hash")
    unsigned_binding = {key: value for key, value in binding.items() if key != "binding_hash"}
    if not hmac.compare_digest(str(saved_binding_hash or ""), digest(unsigned_binding)):
        errors.append("discipline binding hash mismatch")
    registry = load_registry()
    if binding.get("registry_hash") != registry["registry_hash"]:
        errors.append("discipline registry hash mismatch")
    profile_id = str(binding.get("profile_id") or "")
    if binding.get("registered_static"):
        entry = _entry_map(registry).get(profile_id)
        if entry is None or digest(entry) != binding.get("registry_entry_hash"):
            errors.append("discipline registry entry mismatch")
    relative = binding.get("live_profile_path")
    if relative:
        base = Path(project_root).expanduser().resolve()
        path = (base / str(relative)).resolve()
        try:
            path.relative_to(base)
            profile = _read_profile(path, base)
            if profile.get("profile_hash") != binding.get("live_profile_hash"):
                errors.append("discipline live profile hash mismatch")
            if profile.get("status") != binding.get("live_profile_status"):
                errors.append("discipline live profile status mismatch")
        except (ValueError, DisciplineProfileError) as exc:
            errors.append(str(exc))
    return errors


def discipline_status(
    project_root: str | os.PathLike[str], *, discipline: str | None = None, verify: bool = False,
) -> dict[str, Any]:
    base = Path(project_root).expanduser().resolve()
    registry = load_registry()
    selected_id = None
    if discipline:
        explicit = str(discipline).strip().casefold()
        selected = next((
            item for item in registry["disciplines"]
            if explicit == str(item["id"]).casefold()
            or explicit in {str(value).casefold() for value in (item.get("labels") or {}).values()}
        ), None)
        selected_id = str(selected["id"]) if selected else _slug(discipline)
    records = []
    for path in sorted(_profile_root(base).glob("*/profile.json")):
        if selected_id and path.parent.name != _slug(selected_id):
            continue
        try:
            profile = _read_profile(path, base)
            records.append({
                "profile_id": profile["profile_id"], "label": profile["label"],
                "status": profile["status"], "profile_hash": profile["profile_hash"],
                "initialized_at": profile["initialized_at"], "valid": True,
                "journal_count": len(profile.get("journal_candidates", [])),
                "path": str(path.relative_to(base)).replace("\\", "/"),
            })
        except DisciplineProfileError as exc:
            records.append({"profile_id": path.parent.name, "status": "INVALID", "valid": False, "error": str(exc)})
    return {
        "status": "PASS" if (not verify or all(item["valid"] for item in records)) else "INVALID",
        "verify": verify,
        "registered_static_profiles": len(registry["disciplines"]),
        "broad_coverage_audit": registry["broad_coverage_audit"],
        "profiles": records,
        "first_build_notice": registry["first_build_notice"],
        "registry_hash": registry["registry_hash"],
    }
