from __future__ import annotations

import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from citation_formatter import Citation, FORMATTERS, STYLES, check_citation
from network_config_core import NetworkConfigError, foreign_proxy_for


class CitationGuardError(ValueError):
    pass


def _doi(value: Any) -> str:
    text = urllib.parse.unquote(str(value or "").strip())
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text, flags=re.I)
    text = re.sub(r"^doi:\s*", "", text, flags=re.I).rstrip(". ")
    if not re.fullmatch(r"10\.\d{4,9}/\S+", text):
        raise CitationGuardError("A valid DOI is required before citation formatting")
    return text.casefold()


def _crossref(doi: str, timeout: float) -> dict[str, Any]:
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}"
    request = urllib.request.Request(url, headers={"User-Agent": "ResearchGuardCitation/1.0"})
    try:
        proxy = foreign_proxy_for(url)
    except NetworkConfigError as exc:
        raise CitationGuardError(str(exc)) from exc
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
    )
    try:
        with opener.open(request, timeout=float(timeout)) as response:
            value = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise CitationGuardError(f"Crossref DOI verification failed: {exc}") from exc
    message = value.get("message")
    if not isinstance(message, dict) or str(message.get("DOI") or "").casefold() != doi:
        raise CitationGuardError("Crossref did not return an exact DOI record")
    return message


def _year(item: dict[str, Any]) -> str:
    for field in ("published-print", "published-online", "published", "issued", "created"):
        parts = (item.get(field) or {}).get("date-parts")
        if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
            return str(parts[0][0])
    return ""


def _authors(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for author in item.get("author") or []:
        if not isinstance(author, dict):
            continue
        family = " ".join(str(author.get("family") or "").split())
        given = " ".join(str(author.get("given") or "").split())
        name = f"{family}, {given}".strip(", ")
        if name:
            values.append(name)
    return values


def _first(value: Any) -> str:
    if isinstance(value, list):
        return str(value[0] if value else "").strip()
    return str(value or "").strip()


def crossref_to_citation(item: dict[str, Any]) -> Citation:
    entry_type = "book" if str(item.get("type") or "").casefold() in {"book", "monograph", "edited-book"} else "article"
    return Citation(
        authors=_authors(item),
        year=_year(item),
        title=_first(item.get("title")),
        journal=_first(item.get("container-title")),
        volume=str(item.get("volume") or ""),
        issue=str(item.get("issue") or ""),
        pages=str(item.get("page") or item.get("article-number") or ""),
        publisher=str(item.get("publisher") or ""),
        doi=str(item.get("DOI") or ""),
        url=f"https://doi.org/{item.get('DOI')}",
        entry_type=entry_type,
        edition=str(item.get("edition-number") or ""),
    )


def verify_and_format_citation(doi: str, style: str, number: int = 1, timeout: float = 20) -> dict[str, Any]:
    normalized_style = str(style or "").casefold()
    if normalized_style not in STYLES:
        raise CitationGuardError(f"style must be one of {', '.join(STYLES)}")
    normalized_doi = _doi(doi)
    item = _crossref(normalized_doi, timeout)
    citation = crossref_to_citation(item)
    hard_missing = [field for field in ("authors", "year", "title") if not getattr(citation, field)]
    if citation.entry_type == "article" and not citation.journal:
        hard_missing.append("journal")
    if hard_missing:
        raise CitationGuardError(f"verified DOI metadata is incomplete: {', '.join(hard_missing)}")
    formatter = FORMATTERS[normalized_style]
    formatted = formatter(citation, number=int(number)) if normalized_style == "ieee" else formatter(citation)
    findings = check_citation(citation, normalized_style)
    return {
        "status": "PASS",
        "verified": True,
        "source": "Crossref",
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "doi": normalized_doi,
        "citation_url": f"https://doi.org/{normalized_doi}",
        "citation_links": [{"kind": "doi", "url": f"https://doi.org/{normalized_doi}"}],
        "metadata": citation.to_dict(),
        "style": normalized_style,
        "formatted": formatted,
        "format_findings": findings,
        "warning": "Formatting is deterministic, but style output does not prove that the cited work supports a manuscript claim.",
    }


def format_structured_citation(record: dict[str, Any], style: str, number: int = 1) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise CitationGuardError("record must be an object")
    doi = record.get("doi")
    if not doi:
        raise CitationGuardError("unverified structured records cannot be formatted as validated citations; provide DOI and use verify_format")
    raise CitationGuardError("use citation_action=verify_format so DOI metadata is fetched and verified before rendering")
