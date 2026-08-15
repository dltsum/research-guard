from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = PLUGIN_ROOT / "assets" / "venue-evidence" / "ccf-v7"
CATALOG_PATH = ASSET_ROOT / "catalog.json"

CATEGORY_SOURCES = {
    "architecture": "https://www.ccf.org.cn/Academic_Evaluation/ARCH_DCP_SS/",
    "networks": "https://www.ccf.org.cn/Academic_Evaluation/CN/",
    "security": "https://www.ccf.org.cn/Academic_Evaluation/NIS/",
    "software": "https://www.ccf.org.cn/Academic_Evaluation/TCSE_SS_PDL/",
    "data": "https://www.ccf.org.cn/Academic_Evaluation/DM_CS/",
    "theory": "https://www.ccf.org.cn/Academic_Evaluation/TCS/",
    "graphics": "https://www.ccf.org.cn/Academic_Evaluation/CGAndMT/",
    "ai": "https://www.ccf.org.cn/Academic_Evaluation/AI/",
    "hci": "https://www.ccf.org.cn/Academic_Evaluation/HCIAndPC/",
    "cross": "https://www.ccf.org.cn/Academic_Evaluation/Cross_Compre_Emerging/",
}


class CCFCatalogError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _catalog_digest(value: dict[str, Any]) -> str:
    payload = {key: value[key] for key in value if key != "catalog_sha256"}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _text(fragment: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>", " ", fragment, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html_lib.unescape(value).replace("\xa0", " ").split())


def _https_url(raw: str) -> str:
    value = html_lib.unescape(raw).strip()
    if value.startswith("http://dblp.uni-trier.de/"):
        value = "https://dblp.org/" + value.split("/db/", 1)[1]
    elif value.startswith("http://dblp.org/"):
        value = "https://dblp.org/" + value.split("dblp.org/", 1)[1]
    elif value.startswith("http://"):
        value = "https://" + value[len("http://") :]
    if not value.startswith("https://"):
        raise CCFCatalogError(f"CCF catalog URL is not convertible to HTTPS: {raw}")
    return value


def parse_category(path: Path, category: str, source_url: str) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    marker = "中国计算机学会推荐国际学术会议"
    start = raw.find(marker)
    if start < 0:
        raise CCFCatalogError(f"conference marker missing from {path.name}")
    conference = raw[start:]
    headings = list(re.finditer(r"<h3[^>]*>\s*([ABC])类\s*</h3>", conference, flags=re.I))
    if len(headings) < 3:
        raise CCFCatalogError(f"A/B/C conference headings missing from {path.name}")
    entries: list[dict[str, Any]] = []
    for index, heading in enumerate(headings):
        rank = heading.group(1).upper()
        if rank not in {"A", "B"}:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(conference)
        section = conference[heading.end() : end]
        for li in re.findall(r"<li[^>]*>([\s\S]*?)</li>", section, flags=re.I):
            cells = re.findall(r"<div[^>]*>([\s\S]*?)</div>", li, flags=re.I)
            if len(cells) < 5:
                continue
            sequence, acronym, full_name, publisher = (_text(cell) for cell in cells[:4])
            if not sequence.isdigit() or not acronym or acronym == "刊物名称":
                continue
            link_match = re.search(r"<a[^>]+href=[\"']([^\"']+)[\"']", cells[4], flags=re.I)
            if not link_match:
                raise CCFCatalogError(f"missing CCF link for {category}/{rank}/{acronym}")
            entries.append(
                {
                    "venue": acronym,
                    "canonical": re.sub(r"[^a-z0-9]+", "-", acronym.casefold()).strip("-"),
                    "full_name": full_name,
                    "publisher": publisher,
                    "ccf_class": rank,
                    "category": category,
                    "ccf_record_url": _https_url(link_match.group(1)),
                    "ccf_category_url": source_url,
                    "source_asset": path.name,
                    "source_sha256": _sha256(path),
                    "profile_status": "EXACT_VENUE_EVIDENCE_REQUIRED",
                }
            )
    if not entries:
        raise CCFCatalogError(f"no A/B conference entries parsed from {path.name}")
    return entries


def build_catalog() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    source_assets: list[dict[str, str]] = []
    for category, url in CATEGORY_SOURCES.items():
        path = ASSET_ROOT / f"{category}.html"
        if not path.is_file():
            raise CCFCatalogError(f"missing downloaded CCF page: {path}")
        source_assets.append({"category": category, "url": url, "path": path.name, "sha256": _sha256(path)})
        entries.extend(parse_category(path, category, url))
    identity: set[tuple[str, str, str]] = set()
    for entry in entries:
        key = (entry["category"], entry["ccf_class"], entry["canonical"])
        if key in identity:
            raise CCFCatalogError(f"duplicate CCF catalog entry: {key}")
        identity.add(key)
    counts = {rank: sum(1 for entry in entries if entry["ccf_class"] == rank) for rank in ("A", "B")}
    catalog = {
        "schema_version": 1,
        "edition": "CCF recommended international conferences and journals, seventh edition",
        "edition_release_date": "2026-03-31",
        "official_directory_url": "https://www.ccf.org.cn/Academic_Evaluation/By_category/",
        "scope": "all CCF A and all CCF B conferences; all B is retained instead of making an unsupported strong-B cutoff",
        "authority_boundary": "CCF classifies venues only. Exact current venue/year/track/stage policy and template evidence remains mandatory before writing.",
        "source_assets": source_assets,
        "counts": counts,
        "entries": sorted(entries, key=lambda item: (item["ccf_class"], item["category"], item["venue"].casefold())),
    }
    catalog["catalog_sha256"] = _catalog_digest(catalog)
    return catalog


def write_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    catalog = build_catalog()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return catalog


def load_catalog() -> dict[str, Any]:
    if not CATALOG_PATH.is_file():
        return build_catalog()
    try:
        value = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CCFCatalogError(f"invalid CCF catalog: {exc}") from exc
    if value.get("catalog_sha256") != _catalog_digest(value):
        raise CCFCatalogError("CCF catalog integrity hash is invalid")
    local_sources = [ASSET_ROOT / item["path"] for item in value.get("source_assets") or []]
    if local_sources and all(path.is_file() for path in local_sources):
        rebuilt = build_catalog()
        if value.get("source_assets") != rebuilt["source_assets"] or value.get("entries") != rebuilt["entries"]:
            raise CCFCatalogError("CCF catalog is stale relative to its hash-bound official source pages")
    elif any(path.is_file() for path in local_sources):
        raise CCFCatalogError("CCF source-page cache is incomplete; hydrate all ten pages or remove the partial cache")
    return value


def find_venue(value: str) -> list[dict[str, Any]]:
    query = " ".join(str(value or "").casefold().split())
    if not query:
        return []
    tokens = set(re.findall(r"[a-z0-9]+", query))
    matches: list[tuple[int, dict[str, Any]]] = []
    for entry in load_catalog()["entries"]:
        acronym = entry["venue"].casefold()
        full_name = entry["full_name"].casefold()
        score = 100 if query in {acronym, entry["canonical"]} else 0
        score += 60 if query == full_name else 0
        score += len(tokens & set(re.findall(r"[a-z0-9]+", f"{acronym} {full_name}")))
        if score:
            matches.append((score, entry))
    return [entry for _, entry in sorted(matches, key=lambda item: (-item[0], item[1]["venue"]))[:10]]


if __name__ == "__main__":
    result = write_catalog()
    print(json.dumps({"path": str(CATALOG_PATH), "counts": result["counts"]}, ensure_ascii=False))
