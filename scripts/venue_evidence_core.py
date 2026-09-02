from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote_plus, urlparse
from urllib.request import ProxyHandler, Request, build_opener

from ccf_catalog_core import CCFCatalogError, find_venue as find_ccf_venue, load_catalog as load_ccf_catalog
from network_config_core import NetworkConfigError, foreign_proxy_for

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - reported explicitly when PDF work is requested
    PdfReader = None  # type: ignore[assignment]


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = PLUGIN_ROOT / "assets" / "venue-evidence"
SEED_REGISTRY = ASSET_ROOT / "registry.json"
STATE_NAME = "venue-state.json"
LOCAL_REGISTRY_NAME = "venue-registry.json"
MAX_PROFILE_AGE_DAYS = 180
ONLINE_RECEIPT_AGE_DAYS = 30
DOMESTIC_HOSTS = (".cn", "cnki.net", "wanfangdata.com.cn", "cqvip.com")


class VenueEvidenceError(ValueError):
    pass


def _digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    block = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            block.update(chunk)
    return block.hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _state_path(root: Path) -> Path:
    return root / ".research-guard" / STATE_NAME


def _local_registry_path(root: Path) -> Path:
    return root / ".research-guard" / LOCAL_REGISTRY_NAME


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VenueEvidenceError(f"{label} is invalid: {exc}") from exc
    if not isinstance(value, dict):
        raise VenueEvidenceError(f"{label} must be a JSON object")
    return value


def _https(value: Any, label: str) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    if parsed.scheme.casefold() != "https" or not parsed.netloc:
        raise VenueEvidenceError(f"{label} must be a clickable HTTPS URL")
    return text


def _verified_time(value: Any) -> str:
    text = str(value or "").strip()
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VenueEvidenceError("verified_at must be an ISO-8601 date or timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    now = dt.datetime.now(dt.timezone.utc)
    if parsed > now + dt.timedelta(days=1):
        raise VenueEvidenceError("verified_at cannot be in the future")
    if now - parsed > dt.timedelta(days=MAX_PROFILE_AGE_DAYS):
        raise VenueEvidenceError("venue profile is stale; online policy and template acquisition is required")
    return parsed.astimezone(dt.timezone.utc).isoformat()


def _online_receipts(profile: dict[str, Any], timeout: float = 20) -> list[dict[str, Any]]:
    urls = [_https(profile.get("policy_url"), "policy_url"), _https(profile.get("template_url"), "template_url")]
    for exemplar in profile.get("exemplars", []):
        urls.extend(_https(exemplar.get(field), f"exemplar {field}") for field in ("award_url", "record_url", "pdf_url"))
    receipts: list[dict[str, Any]] = []
    for url in dict.fromkeys(urls):
        host = (urlparse(url).hostname or "").casefold()
        domestic = any(host == suffix.lstrip(".") or host.endswith(suffix) for suffix in DOMESTIC_HOSTS)
        if domestic:
            opener = build_opener(ProxyHandler({}))
            route = "domestic_direct"
        else:
            try:
                proxy = foreign_proxy_for(url)
            except NetworkConfigError as exc:
                raise VenueEvidenceError(str(exc)) from exc
            opener = build_opener(ProxyHandler({"http": proxy, "https": proxy} if proxy else {}))
            route = "foreign_proxy" if proxy else "foreign_direct"
        request = Request(url, headers={"User-Agent": "ResearchGuardVenueEvidence/1.0"}, method="HEAD")
        try:
            response = opener.open(request, timeout=float(timeout))
        except Exception:
            request = Request(
                url, headers={"User-Agent": "ResearchGuardVenueEvidence/1.0", "Range": "bytes=0-4095"}, method="GET",
            )
            try:
                response = opener.open(request, timeout=float(timeout))
            except Exception as exc:
                raise VenueEvidenceError(f"live venue source verification failed for {url}: {exc}") from exc
        with response:
            final_url = _https(response.geturl(), "redirected venue source")
            status = int(getattr(response, "status", 0) or response.getcode())
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().casefold()
        if not 200 <= status < 400:
            raise VenueEvidenceError(f"live venue source returned HTTP {status}: {url}")
        receipts.append({
            "url": url, "final_url": final_url, "http_status": status, "content_type": content_type,
            "route": route, "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        })
    return receipts


def _validate_online_receipts(profile: dict[str, Any]) -> None:
    receipts = profile.get("online_receipts")
    if not isinstance(receipts, list) or not receipts:
        raise VenueEvidenceError("project-imported venue profile lacks live URL verification receipts")
    required = {profile["policy_url"], profile["template_url"]}
    for exemplar in profile.get("exemplars", []):
        required.update(exemplar[field] for field in ("award_url", "record_url", "pdf_url"))
    covered: set[str] = set()
    now = dt.datetime.now(dt.timezone.utc)
    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise VenueEvidenceError("online venue receipt must be an object")
        url = _https(receipt.get("url"), "online receipt URL")
        _https(receipt.get("final_url"), "online receipt final URL")
        try:
            status = int(receipt.get("http_status"))
            verified = dt.datetime.fromisoformat(str(receipt.get("verified_at")).replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise VenueEvidenceError("online venue receipt has invalid status or timestamp") from exc
        if verified.tzinfo is None:
            verified = verified.replace(tzinfo=dt.timezone.utc)
        if not 200 <= status < 400 or now - verified > dt.timedelta(days=ONLINE_RECEIPT_AGE_DAYS):
            raise VenueEvidenceError(f"online venue receipt is stale or unsuccessful: {url}")
        covered.add(url)
    if required != covered:
        raise VenueEvidenceError(f"online venue receipt coverage mismatch: missing={sorted(required - covered)}")


def resolve_seed_asset(relative: str) -> Path:
    raw = str(relative or "").replace("\\", "/")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or ".." in pure.parts:
        raise VenueEvidenceError("seed asset path must stay inside the venue evidence library")
    path = (ASSET_ROOT / Path(*pure.parts)).resolve()
    try:
        path.relative_to(ASSET_ROOT.resolve())
    except ValueError as exc:
        raise VenueEvidenceError("seed asset escaped the venue evidence library") from exc
    if not path.is_file():
        raise VenueEvidenceError(f"seed asset does not exist: {raw}")
    return path


def _project_asset(root: Path, relative: str) -> Path:
    raw = str(relative or "").replace("\\", "/")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or ".." in pure.parts:
        raise VenueEvidenceError("project evidence path must be relative and remain inside project_root")
    path = (root / Path(*pure.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise VenueEvidenceError("project evidence path escaped project_root") from exc
    if not path.is_file():
        raise VenueEvidenceError(f"project evidence file does not exist: {raw}")
    return path


def _zip_members(path: Path) -> list[zipfile.ZipInfo]:
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise VenueEvidenceError(f"template archive is not a valid ZIP: {path.name}") from exc
    with archive:
        members = archive.infolist()
        for member in members:
            normalized = member.filename.replace("\\", "/")
            pure = PurePosixPath(normalized)
            if pure.is_absolute() or ".." in pure.parts or re.match(r"^[A-Za-z]:", normalized):
                raise VenueEvidenceError(f"template archive contains an unsafe path: {member.filename}")
        return members


def _tex_headings(text: str) -> list[str]:
    found: list[str] = []
    for match in re.finditer(r"\\(?:sub)*section\*?\{([^{}]+)\}", text):
        heading = re.sub(r"\\[A-Za-z]+\s*", "", match.group(1)).strip()
        if heading and heading not in found:
            found.append(heading)
    return found


def inspect_template_archive(path: str | os.PathLike[str]) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    members = _zip_members(target)
    tex_files = sorted(member.filename for member in members if member.filename.casefold().endswith(".tex"))
    headings: list[dict[str, Any]] = []
    documentclasses: list[dict[str, str]] = []
    with zipfile.ZipFile(target) as archive:
        for name in tex_files:
            try:
                text = archive.read(name).decode("utf-8", errors="ignore")
            except (KeyError, OSError):
                continue
            for heading in _tex_headings(text):
                item = {"heading": heading, "source_file": name, "scope": "template_example_or_instruction"}
                if item not in headings:
                    headings.append(item)
            for match in re.finditer(r"\\documentclass(?:\[([^\]]*)\])?\{([^{}]+)\}", text):
                item = {"class": match.group(2).strip(), "options": (match.group(1) or "").strip(), "source_file": name}
                if item not in documentclasses:
                    documentclasses.append(item)
    return {
        "status": "PASS",
        "archive_sha256": _file_sha(target),
        "tex_files": tex_files,
        "documentclasses": documentclasses,
        "observed_headings": headings,
        "layout_authority": "official_template_only",
        "warning": "Template headings are examples or instructions, not mandatory paper chapters unless an official policy locator says so.",
    }


def _paper_heading_candidates(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    named = {"abstract", "introduction", "related work", "background", "method", "methods", "methodology", "experiments", "results", "discussion", "limitations", "conclusion", "conclusions", "impact statement"}
    numbered = re.compile(r"^(\d+(?:\.\d+)*\.?)\s+([A-Za-z][A-Za-z0-9 ,:&'()\-/]{2,90})$")
    roman = re.compile(r"^([IVXLCDM]+)\.\s+([A-Za-z][A-Za-z0-9 ,:&'()\-/]{2,90})$", re.IGNORECASE)
    alpha = re.compile(r"^([A-Z])\.\s+([A-Za-z][A-Za-z0-9 ,:&'()\-/]{2,90})$")
    last_top = 0
    current_top = 0
    roman_order = {value: index for index, value in enumerate(("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"), start=1)}
    last_roman = 0
    for raw in text.splitlines():
        line = " ".join(raw.split()).strip()
        lowered = line.casefold().strip(" .:")
        heading = None
        kind = "unnumbered"
        if lowered in named:
            heading = line
        else:
            match = numbered.match(line)
            if match and not re.search(r"\bet al\b|\bfig(?:ure)?\b|\btable\b|\bO\s*\(", line, re.IGNORECASE):
                index = tuple(int(part) for part in match.group(1).strip(".").split("."))
                if len(index) == 1 and index[0] == last_top + 1:
                    heading = line
                    last_top = index[0]
                    current_top = index[0]
                    kind = "numbered_section"
                elif len(index) > 1 and index[0] == current_top:
                    heading = line
                    kind = "numbered_subsection"
            if heading is None:
                match = roman.match(line)
                value = roman_order.get(match.group(1).upper(), 0) if match else 0
                if match and value == last_roman + 1:
                    heading = line
                    last_roman = value
                    kind = "roman_section"
            if heading is None:
                match = alpha.match(line)
                if match and last_roman:
                    heading = line
                    kind = "roman_subsection"
        if heading and heading not in [item["heading"] for item in candidates]:
            candidates.append({"heading": heading, "scope": "observed_in_this_paper", "kind": kind})
    return candidates


def inspect_paper_pdf(path: str | os.PathLike[str]) -> dict[str, Any]:
    if PdfReader is None:
        raise VenueEvidenceError("pypdf is required for deterministic paper inspection")
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        raise VenueEvidenceError(f"paper PDF does not exist: {target}")
    try:
        reader = PdfReader(str(target))
    except Exception as exc:
        raise VenueEvidenceError(f"paper is not a readable PDF: {target.name}: {exc}") from exc
    headings: list[dict[str, Any]] = []
    page_sizes: list[dict[str, float]] = []
    for index, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        for item in _paper_heading_candidates(text):
            located = {**item, "page": index + 1}
            if item["heading"] not in [existing["heading"] for existing in headings]:
                headings.append(located)
        box = page.mediabox
        size = {"width_pt": round(float(box.width), 2), "height_pt": round(float(box.height), 2)}
        if size not in page_sizes:
            page_sizes.append(size)
    return {
        "status": "PASS",
        "pdf_sha256": _file_sha(target),
        "page_count": len(reader.pages),
        "page_sizes": page_sizes,
        "observed_headings": headings,
        "heading_scope": "observed_in_this_paper",
        "warning": "Observed headings and order describe this paper only; column layout and mandatory chapters must come from official policy/template evidence.",
    }


def _seed_registry() -> dict[str, Any]:
    value = _load_json(SEED_REGISTRY, "seed venue registry")
    if value.get("schema_version") != 1 or not isinstance(value.get("profiles"), list):
        raise VenueEvidenceError("seed venue registry has an unsupported schema")
    return value


def _local_registry(root: Path) -> dict[str, Any]:
    path = _local_registry_path(root)
    if not path.is_file():
        return {"schema_version": 1, "profiles": []}
    value = _load_json(path, "project venue registry")
    if value.get("schema_version") != 1 or not isinstance(value.get("profiles"), list):
        raise VenueEvidenceError("project venue registry has an unsupported schema")
    return value


def _canonical_venue(value: Any, seed: dict[str, Any]) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    for canonical, aliases in seed.get("aliases", {}).items():
        if text == canonical or text in [str(alias).casefold() for alias in aliases]:
            return canonical
    return text


def _asset_path(root: Path, origin: str, relative: str) -> Path:
    return resolve_seed_asset(relative) if origin == "seed" else _project_asset(root, relative)


def _text_contains(path: Path, locator: str) -> bool:
    needle = " ".join(str(locator).split()).casefold()
    try:
        if path.suffix.casefold() == ".pdf":
            if PdfReader is None:
                return False
            text = "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
        elif path.suffix.casefold() == ".zip":
            _zip_members(path)
            parts: list[str] = []
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.casefold().endswith((".tex", ".txt", ".md", ".html")):
                        parts.append(archive.read(name).decode("utf-8", errors="ignore"))
            text = "\n".join(parts)
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    haystack = " ".join(text.split()).casefold()
    return needle in haystack


def _validate_profile(root: Path, raw: dict[str, Any], origin: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(raw, dict):
        raise VenueEvidenceError("venue profile must be an object")
    profile = copy.deepcopy(raw)
    for field in ("venue", "track", "stage"):
        text = str(profile.get(field) or "").strip().casefold()
        if not text:
            raise VenueEvidenceError(f"venue profile is missing {field}")
        profile[field] = text
    try:
        profile["year"] = int(profile.get("year"))
    except (TypeError, ValueError) as exc:
        raise VenueEvidenceError("venue profile year must be an integer") from exc
    if profile["year"] < 1900 or profile["year"] > 2200:
        raise VenueEvidenceError("venue profile year is outside the supported range")
    profile["policy_url"] = _https(profile.get("policy_url"), "policy_url")
    profile["template_url"] = _https(profile.get("template_url"), "template_url")
    profile["verified_at"] = _verified_time(profile.get("verified_at"))

    verified_assets: list[dict[str, Any]] = []
    assets = profile.get("assets")
    if not isinstance(assets, list) or not assets:
        raise VenueEvidenceError("venue profile needs local policy and official_template assets")
    kinds: set[str] = set()
    asset_by_path: dict[str, Path] = {}
    for item in assets:
        if not isinstance(item, dict):
            raise VenueEvidenceError("venue asset must be an object")
        kind = str(item.get("kind") or "").strip()
        relative = str(item.get("path") or "").replace("\\", "/")
        expected = str(item.get("sha256") or "").strip().casefold()
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise VenueEvidenceError(f"venue asset has invalid sha256: {relative}")
        path = _asset_path(root, origin, relative)
        actual = _file_sha(path)
        if actual != expected:
            raise VenueEvidenceError(f"venue asset hash mismatch: {relative}")
        if kind == "official_template":
            inspect_template_archive(path)
        kinds.add(kind)
        asset_by_path[relative] = path
        verified_assets.append({"kind": kind, "path": relative, "sha256": actual})
    if not {"policy", "official_template"}.issubset(kinds):
        raise VenueEvidenceError("venue profile needs both policy and official_template assets")

    sections = profile.get("required_sections", [])
    if not isinstance(sections, list):
        raise VenueEvidenceError("required_sections must be an array of source-located objects")
    normalized_sections: list[dict[str, str]] = []
    policy_paths = [item["path"] for item in verified_assets if item["kind"] == "policy"]
    for item in sections:
        if not isinstance(item, dict):
            raise VenueEvidenceError("required section must carry name, source, and locator")
        name = str(item.get("name") or "").strip()
        locator = str(item.get("locator") or "").strip()
        relative = str(item.get("source_path") or "").replace("\\", "/")
        if not relative:
            source = str(item.get("source") or "").strip()
            if source != "policy" or not policy_paths:
                raise VenueEvidenceError(f"required section {name!r} lacks an official policy source")
            relative = policy_paths[0]
        if not name or not locator or relative not in asset_by_path:
            raise VenueEvidenceError("required section must reference a registered official evidence asset")
        if not _text_contains(asset_by_path[relative], locator):
            raise VenueEvidenceError(f"required section locator was not found in official evidence: {name}")
        normalized_sections.append({"name": name, "source_path": relative, "locator": locator})
    profile["required_sections"] = normalized_sections

    exemplars = profile.get("exemplars")
    if not isinstance(exemplars, list) or not exemplars:
        raise VenueEvidenceError("venue profile needs at least one award/high-quality exemplar")
    for exemplar in exemplars:
        if not isinstance(exemplar, dict) or not str(exemplar.get("title") or "").strip():
            raise VenueEvidenceError("each exemplar needs a title")
        for field in ("award_url", "record_url", "pdf_url"):
            exemplar[field] = _https(exemplar.get(field), f"exemplar {field}")
        relative = str(exemplar.get("path") or "").replace("\\", "/")
        expected = str(exemplar.get("sha256") or "").strip().casefold()
        path = _asset_path(root, origin, relative)
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or _file_sha(path) != expected:
            raise VenueEvidenceError(f"exemplar asset hash mismatch: {relative}")
        inspection = inspect_paper_pdf(path)
        exemplar["observed_headings"] = inspection["observed_headings"]
        cards = exemplar.get("narrative_cards", [])
        if not isinstance(cards, list):
            raise VenueEvidenceError("narrative_cards must be an array")
        for card in cards:
            if not isinstance(card, dict) or not str(card.get("locator") or "").strip() or len(str(card.get("observation") or "").strip()) < 30:
                raise VenueEvidenceError("every narrative observation needs a locator and a substantive structured description")
        verified_assets.append({"kind": "exemplar", "path": relative, "sha256": expected})
    if origin == "project":
        _validate_online_receipts(profile)
    profile["assets_verified"] = True
    return profile, verified_assets


def _public_profile(profile: dict[str, Any]) -> dict[str, Any]:
    exemplar_count = len(profile["exemplars"])
    return {
        **profile,
        "paper_links": [item["pdf_url"] for item in profile["exemplars"]],
        "observed_section_sequences": [
            {"title": item["title"], "headings": item.get("observed_headings", []), "scope": "observed_in_this_paper"}
            for item in profile["exemplars"]
        ],
        "narrative_evidence": {
            "exemplar_count": exemplar_count,
            "scope": "cross_exemplar_pattern" if exemplar_count >= 2 else "sample_specific",
            "venue_norm_authorized": exemplar_count >= 2,
            "cards": [
                {"title": item["title"], "version": item.get("version"), **card}
                for item in profile["exemplars"] for card in item.get("narrative_cards", [])
            ],
            "warning": "These are source-located observations, not mandatory venue chapters or a recipe for imitation.",
        },
    }


def _online_required(venue: str, year: int, track: str, stage: str) -> dict[str, Any]:
    phrase = quote_plus(f"{venue} {year} {track} {stage} author guidelines official template")
    award = quote_plus(f"{venue} {year} best paper award official")
    try:
        ccf_matches = find_ccf_venue(venue)
    except CCFCatalogError as exc:
        raise VenueEvidenceError(f"CCF venue catalog is invalid: {exc}") from exc
    exact_ccf = next(
        (
            item for item in ccf_matches
            if venue.casefold() in {item["venue"].casefold(), item["canonical"].casefold()}
        ),
        None,
    )
    return {
        "status": "ONLINE_ACQUISITION_REQUIRED",
        "reason": "no exact verified venue-year-track-stage profile is available; do not invent chapter names, layout, formatting, or narrative",
        "requested": {"venue": venue, "year": year, "track": track, "stage": stage},
        "queries": [
            f"{venue} {year} {track} {stage} official author guidelines template",
            f"{venue} {year} official best paper award proceedings PDF",
        ],
        "required_sources": [
            {"kind": "official_policy_and_template", "url": f"https://www.google.com/search?q={phrase}"},
            {"kind": "official_award_and_paper_records", "url": f"https://www.google.com/search?q={award}"},
            {"kind": "open_scholarly_record", "url": f"https://api.openalex.org/works?search={quote_plus(venue + ' ' + str(year))}"},
        ],
        "ccf_catalog_match": exact_ccf,
        "ccf_boundary": "CCF A/B classification can route discovery but cannot authorize current format, layout, headings, or narrative.",
        "next_action": "Search live, download the exact official policy/template and identified paper copies, inspect them, then call venue_action=register before writing.",
    }


def _all_profiles(root: Path) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
    seed = _seed_registry()
    pairs = [("project", item) for item in _local_registry(root).get("profiles", [])]
    pairs.extend(("seed", item) for item in seed.get("profiles", []))
    return seed, pairs


def list_venue_profiles(root: str | os.PathLike[str]) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    seed, pairs = _all_profiles(base)
    profiles: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str, str]] = set()
    for origin, raw in pairs:
        key = (
            _canonical_venue(raw.get("venue"), seed), int(raw.get("year")),
            str(raw.get("track") or "").casefold(), str(raw.get("stage") or "").casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        profiles.append({
            "venue": key[0], "display_name": raw.get("display_name", raw.get("venue")), "year": key[1],
            "track": key[2], "stage": key[3], "domain": raw.get("domain"), "origin": origin,
            "policy_url": _https(raw.get("policy_url"), "policy_url"),
            "template_url": _https(raw.get("template_url"), "template_url"),
            "paper_links": [_https(item.get("pdf_url"), "paper PDF") for item in raw.get("exemplars", [])],
        })
    try:
        ccf = load_ccf_catalog()
    except CCFCatalogError as exc:
        raise VenueEvidenceError(f"CCF venue catalog is invalid: {exc}") from exc
    return {
        "status": "PASS",
        "profiles": profiles,
        "ccf_catalog": {
            "edition": ccf["edition"], "counts": ccf["counts"], "total": len(ccf["entries"]),
            "directory_url": ccf["official_directory_url"],
            "scope": ccf["scope"],
        },
        "hard_rule_authority": "official_policy_and_template_only",
    }


def resolve_venue_profile(
    root: str | os.PathLike[str], venue: str, year: int, track: str = "main", stage: str = "submission",
) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    seed, pairs = _all_profiles(base)
    canonical = _canonical_venue(venue, seed)
    try:
        target_year = int(year)
    except (TypeError, ValueError):
        raise VenueEvidenceError("venue year must be an integer")
    target = (canonical, target_year, str(track or "main").strip().casefold(), str(stage or "submission").strip().casefold())
    match: tuple[str, dict[str, Any]] | None = None
    for origin, raw in pairs:
        key = (
            _canonical_venue(raw.get("venue"), seed), int(raw.get("year")),
            str(raw.get("track") or "").casefold(), str(raw.get("stage") or "").casefold(),
        )
        if key == target:
            match = (origin, raw)
            break
    if match is None:
        return _online_required(*target)
    origin, raw = match
    try:
        profile, assets = _validate_profile(base, raw, origin)
    except VenueEvidenceError as exc:
        required = _online_required(*target)
        required["reason"] = f"exact profile exists but failed verification: {exc}"
        required["status"] = "ONLINE_ACQUISITION_REQUIRED"
        return required
    public = _public_profile(profile)
    receipt_payload = {
        "profile_key": {"venue": target[0], "year": target[1], "track": target[2], "stage": target[3]},
        "profile_sha256": _digest(profile),
        "assets": assets,
        "origin": origin,
        "issued_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    receipt_sha = _digest(receipt_payload)
    state = {"status": "PASS", "profile": profile, "receipt": receipt_payload, "receipt_sha256": receipt_sha}
    state["state_sha256"] = _digest(state)
    _atomic_json(_state_path(base), state)
    return {"status": "PASS", "profile": public, **receipt_payload, "receipt_sha256": receipt_sha}


def get_venue_status(root: str | os.PathLike[str]) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    path = _state_path(base)
    if not path.is_file():
        return {"status": "NOT_RESOLVED", "reason": "no venue evidence profile has been resolved"}
    try:
        state = _load_json(path, "venue state")
        saved_state = state.get("state_sha256")
        unsigned_state = {key: value for key, value in state.items() if key != "state_sha256"}
        if saved_state != _digest(unsigned_state):
            raise VenueEvidenceError("venue state integrity check failed")
        receipt = state.get("receipt")
        if not isinstance(receipt, dict) or state.get("receipt_sha256") != _digest(receipt):
            raise VenueEvidenceError("venue receipt integrity check failed")
        if receipt.get("profile_sha256") != _digest(state.get("profile")):
            raise VenueEvidenceError("venue profile receipt binding failed")
        profile, assets = _validate_profile(base, state["profile"], str(receipt.get("origin")))
        if _digest(profile) != receipt.get("profile_sha256") or assets != receipt.get("assets"):
            raise VenueEvidenceError("venue evidence assets or profile changed")
    except (VenueEvidenceError, KeyError) as exc:
        return {"status": "RESEARCH_REQUIRED", "reason": str(exc), "receipt_sha256": None}
    return {
        "status": "PASS", "reason": "exact venue profile and local assets passed hash verification",
        "profile": _public_profile(state["profile"]), "receipt_sha256": state["receipt_sha256"],
    }


def verify_venue_receipt(root: str | os.PathLike[str], expected_sha256: str | None = None) -> dict[str, Any]:
    status = get_venue_status(root)
    if status.get("status") != "PASS":
        return status
    if expected_sha256 and str(expected_sha256).casefold() != status.get("receipt_sha256"):
        return {"status": "RESEARCH_REQUIRED", "reason": "venue receipt does not match the requested writing plan", "receipt_sha256": None}
    return status


def register_venue_profile(root: str | os.PathLike[str], profile: dict[str, Any]) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    candidate = copy.deepcopy(profile)
    candidate["online_receipts"] = _online_receipts(candidate)
    normalized, _ = _validate_profile(base, candidate, "project")
    registry = _local_registry(base)
    key = (normalized["venue"], normalized["year"], normalized["track"], normalized["stage"])
    retained = [
        item for item in registry.get("profiles", [])
        if (str(item.get("venue")).casefold(), int(item.get("year")), str(item.get("track")).casefold(), str(item.get("stage")).casefold()) != key
    ]
    clean = candidate
    clean["venue"] = normalized["venue"]
    clean["year"] = normalized["year"]
    clean["track"] = normalized["track"]
    clean["stage"] = normalized["stage"]
    retained.append(clean)
    _atomic_json(_local_registry_path(base), {"schema_version": 1, "profiles": retained})
    return resolve_venue_profile(base, *key)
