"""CiteSpace-style frontier analysis: co-occurrence, co-citation, bursts.

Builds a keyword co-occurrence network and a reference co-citation network
from a supplied work set, detects burst keywords with a two-state Kleinberg
automaton, ranks pivotal nodes by betweenness centrality, and derives a
deterministic frontier ranking (recent bursts plus structural centrality).

The analysis is fail-closed and deterministic: malformed works are rejected,
all outputs are sorted, and the persisted state is hash-bound so downstream
receipts can verify that a frontier claim matches the analyzed corpus.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import networkx as nx


STATE_NAME = "frontier-analysis.json"
MAX_WORKS = 5000
MAX_KEYWORDS_PER_WORK = 100
DEFAULT_BURST_WINDOW_YEARS = 3
BURST_GAMMA = 2.0


class FrontierAnalysisError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _root(value: str | os.PathLike[str]) -> Path:
    root = Path(value).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _path(root: Path) -> Path:
    return root / ".research-guard" / STATE_NAME


def _atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _normalize_keyword(value: Any) -> str:
    text = " ".join(str(value or "").strip().casefold().split())
    if not text or len(text) > 200:
        raise FrontierAnalysisError("keywords must be non-empty strings of at most 200 characters")
    return text


def _normalize_works(works: Any) -> list[dict[str, Any]]:
    if not isinstance(works, list) or not works:
        raise FrontierAnalysisError("works must be a non-empty list of bibliographic objects")
    if len(works) > MAX_WORKS:
        raise FrontierAnalysisError(f"works is bounded at {MAX_WORKS} records per analysis")
    normalized = []
    seen_ids: set[str] = set()
    for index, item in enumerate(works):
        if not isinstance(item, dict):
            raise FrontierAnalysisError(f"works[{index}] must be an object")
        work_id = str(item.get("work_id") or item.get("doi") or "").strip()
        if not work_id:
            raise FrontierAnalysisError(f"works[{index}].work_id is required")
        if work_id in seen_ids:
            raise FrontierAnalysisError(f"works[{index}].work_id duplicates an earlier record: {work_id}")
        seen_ids.add(work_id)
        year = item.get("year")
        if isinstance(year, bool) or not isinstance(year, int) or not 1900 <= year <= 2100:
            raise FrontierAnalysisError(f"works[{index}].year must be an integer within 1900..2100")
        keywords = item.get("keywords") or []
        if not isinstance(keywords, list) or len(keywords) > MAX_KEYWORDS_PER_WORK:
            raise FrontierAnalysisError(f"works[{index}].keywords must be a list of at most {MAX_KEYWORDS_PER_WORK}")
        references = item.get("references") or []
        if not isinstance(references, list) or not all(isinstance(ref, str) and ref.strip() for ref in references):
            raise FrontierAnalysisError(f"works[{index}].references must be a list of non-empty strings")
        normalized.append({
            "work_id": work_id,
            "year": year,
            "title": str(item.get("title") or "").strip(),
            "keywords": sorted({_normalize_keyword(keyword) for keyword in keywords}),
            "references": sorted({ref.strip() for ref in references}),
        })
    return normalized


def _cooccurrence_edges(works: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
    edges: dict[tuple[str, str], int] = {}
    for work in works:
        keywords = work["keywords"]
        for i, left in enumerate(keywords):
            for right in keywords[i + 1:]:
                key = (left, right)
                edges[key] = edges.get(key, 0) + 1
    return edges


def _cocitation_edges(works: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
    edges: dict[tuple[str, str], int] = {}
    for work in works:
        refs = work["references"]
        for i, left in enumerate(refs):
            for right in refs[i + 1:]:
                key = (left, right) if left < right else (right, left)
                edges[key] = edges.get(key, 0) + 1
    return edges


def _kleinberg_bursts(
    per_year_counts: dict[int, tuple[int, int]], gamma: float = BURST_GAMMA
) -> list[tuple[int, int, float]]:
    """Two-state Kleinberg burst automaton over per-year (keyword, total) counts.

    Returns maximal state-1 intervals as (start_year, end_year, strength),
    where strength is the accumulated log-likelihood gain over the baseline.
    """
    years = sorted(per_year_counts)
    if not years:
        return []
    total_keyword = sum(counts[0] for counts in per_year_counts.values())
    total_works = sum(counts[1] for counts in per_year_counts.values())
    if total_keyword == 0 or total_works == 0:
        return []
    p0 = min(total_keyword / total_works, 1.0)
    p1 = min(p0 * gamma, 1.0)
    if p1 <= p0:
        return []

    def cost(state: int, count: int, total: int) -> float:
        p = p1 if state == 1 else p0
        p = min(max(p, 1e-12), 1.0)
        value = 0.0
        if count:
            value -= count * math.log(p)
        if total - count:
            value -= (total - count) * math.log(1.0 - p) if p < 1.0 else 0.0
        return value

    n = len(years)
    transition = math.log(max(total_works, 2))
    # dp[i][s] = minimal cost covering years[:i+1] ending in state s.
    dp = [[math.inf, math.inf] for _ in range(n)]
    back = [[0, 0] for _ in range(n)]
    for i, year in enumerate(years):
        count, total = per_year_counts[year]
        for state in (0, 1):
            emission = cost(state, count, total)
            if i == 0:
                dp[i][state] = emission
                continue
            candidates = []
            for prev in (0, 1):
                penalty = (state - prev) * transition if state > prev else 0.0
                candidates.append(dp[i - 1][prev] + emission + penalty)
            best = min(range(2), key=lambda prev: candidates[prev])
            dp[i][state] = candidates[best]
            back[i][state] = best
    end_state = 0 if dp[n - 1][0] <= dp[n - 1][1] else 1
    states = [0] * n
    states[n - 1] = end_state
    for i in range(n - 1, 0, -1):
        states[i - 1] = back[i][states[i]]

    bursts: list[tuple[int, int, float]] = []
    start = None
    strength = 0.0
    for i, year in enumerate(years):
        count, total = per_year_counts[year]
        if states[i] == 1:
            if start is None:
                start = year
                strength = 0.0
            strength += cost(0, count, total) - cost(1, count, total)
        elif start is not None:
            bursts.append((start, years[i - 1], round(strength, 6)))
            start = None
    if start is not None:
        bursts.append((start, years[-1], round(strength, 6)))
    return [burst for burst in bursts if burst[2] > 0]


def _betweenness(nodes: list[str], edges: dict[tuple[str, str], int]) -> dict[str, float]:
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    for (left, right), weight in edges.items():
        graph.add_edge(left, right, weight=weight)
    if graph.number_of_edges() == 0:
        return {node: 0.0 for node in nodes}
    return {node: round(score, 6) for node, score in nx.betweenness_centrality(graph, weight="weight").items()}


def run_frontier_analysis(
    root: str | os.PathLike[str],
    works: Any,
    *,
    analysis_id: str,
    burst_window_years: int = DEFAULT_BURST_WINDOW_YEARS,
    min_cooccurrence: int = 2,
    top: int = 50,
) -> dict[str, Any]:
    """Analyze a work set and persist a hash-bound frontier state."""
    base = _root(root)
    label = str(analysis_id or "").strip()
    if not label or len(label) > 100:
        raise FrontierAnalysisError("analysis_id must be a non-empty string of at most 100 characters")
    if isinstance(burst_window_years, bool) or not isinstance(burst_window_years, int) or burst_window_years < 1:
        raise FrontierAnalysisError("burst_window_years must be a positive integer")
    if isinstance(min_cooccurrence, bool) or not isinstance(min_cooccurrence, int) or min_cooccurrence < 1:
        raise FrontierAnalysisError("min_cooccurrence must be a positive integer")
    if isinstance(top, bool) or not isinstance(top, int) or top < 1:
        raise FrontierAnalysisError("top must be a positive integer")

    normalized = _normalize_works(works)
    years = [work["year"] for work in normalized]
    min_year, max_year = min(years), max(years)

    keyword_counts: dict[str, int] = {}
    keyword_years: dict[str, dict[int, tuple[int, int]]] = {}
    works_per_year: dict[int, int] = {}
    for work in normalized:
        works_per_year[work["year"]] = works_per_year.get(work["year"], 0) + 1
    for work in normalized:
        for keyword in work["keywords"]:
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
            yearly = keyword_years.setdefault(keyword, {})
            count, _ = yearly.get(work["year"], (0, 0))
            yearly[work["year"]] = (count + 1, works_per_year[work["year"]])
    # Fill (0, total) pairs so every keyword spans the full corpus timeline.
    for keyword, yearly in keyword_years.items():
        for year in range(min_year, max_year + 1):
            if year not in yearly:
                yearly[year] = (0, works_per_year.get(year, 0))

    all_edges = _cooccurrence_edges(normalized)
    edges = {pair: weight for pair, weight in all_edges.items() if weight >= min_cooccurrence}
    active_keywords = sorted({node for pair in edges for node in pair})
    centrality = _betweenness(active_keywords, edges)

    cocitation = _cocitation_edges(normalized)
    cocitation_sorted = sorted(cocitation.items(), key=lambda item: (-item[1], item[0]))

    bursts: list[dict[str, Any]] = []
    for keyword in sorted(keyword_years):
        for start, end, strength in _kleinberg_bursts(keyword_years[keyword]):
            bursts.append({
                "keyword": keyword, "begin": start, "end": end,
                "strength": strength,
                "recent": end >= max_year - burst_window_years + 1,
            })
    bursts.sort(key=lambda item: (-item["strength"], item["keyword"]))

    max_centrality = max(centrality.values(), default=0.0)
    frontier: list[dict[str, Any]] = []
    recent_bursts = {item["keyword"]: item["strength"] for item in bursts if item["recent"]}
    max_burst = max(recent_bursts.values(), default=0.0)
    for keyword in active_keywords:
        burst_component = (recent_bursts.get(keyword, 0.0) / max_burst) if max_burst else 0.0
        centrality_component = (centrality.get(keyword, 0.0) / max_centrality) if max_centrality else 0.0
        score = round(0.6 * burst_component + 0.4 * centrality_component, 6)
        frontier.append({
            "keyword": keyword, "frontier_score": score,
            "recent_burst_strength": round(recent_bursts.get(keyword, 0.0), 6),
            "betweenness": centrality.get(keyword, 0.0),
            "occurrences": keyword_counts.get(keyword, 0),
        })
    frontier.sort(key=lambda item: (-item["frontier_score"], item["keyword"]))

    graph = nx.Graph()
    graph.add_nodes_from(active_keywords)
    for (left, right), weight in edges.items():
        graph.add_edge(left, right, weight=weight)
    clusters = []
    for component in sorted(nx.connected_components(graph), key=lambda c: (-len(c), sorted(c)[0])):
        members = sorted(component)
        clusters.append({
            "label": max(members, key=lambda k: (keyword_counts.get(k, 0), k)),
            "size": len(members),
            "keywords": members,
        })

    record = {
        "schema_version": 1,
        "analysis_id": label,
        "work_count": len(normalized),
        "year_range": [min_year, max_year],
        "parameters": {
            "burst_window_years": burst_window_years,
            "min_cooccurrence": min_cooccurrence,
            "top": top,
            "burst_gamma": BURST_GAMMA,
        },
        "keyword_graph": {
            "node_count": len(active_keywords),
            "edge_count": len(edges),
            "top_edges": [
                {"pair": [left, right], "weight": weight}
                for (left, right), weight in sorted(edges.items(), key=lambda item: (-item[1], item[0]))[:top]
            ],
        },
        "cocitation_graph": {
            "edge_count": len(cocitation),
            "top_pairs": [
                {"pair": [left, right], "weight": weight}
                for (left, right), weight in cocitation_sorted[:top]
            ],
        },
        "clusters": clusters[:top],
        "bursts": bursts[:top],
        "frontier": frontier[:top],
    }
    record["analysis_hash"] = _digest(record)
    _atomic(_path(base), record)
    return record


def frontier_status(root: str | os.PathLike[str]) -> dict[str, Any]:
    """Return the persisted frontier analysis, verifying its hash."""
    path = _path(_root(root))
    if not path.is_file():
        return {"status": "FRONTIER_ANALYSIS_REQUIRED", "ready": False}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FrontierAnalysisError(f"invalid frontier analysis state: {path}") from exc
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise FrontierAnalysisError(f"invalid frontier analysis schema: {path}")
    stored_hash = state.pop("analysis_hash", None)
    if _digest(state) != stored_hash:
        raise FrontierAnalysisError(f"frontier analysis state hash mismatch: {path}")
    state["analysis_hash"] = stored_hash
    return {"status": "PASS", "ready": True, **state}
