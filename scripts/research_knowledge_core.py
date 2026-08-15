from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import networkx as nx

from ccf_catalog_core import load_catalog


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_REGISTRY = PLUGIN_ROOT / "assets" / "research-repositories" / "registry.json"
STATE_NAME = "research-knowledge.json"
ALLOWED_NODE_TYPES = {"repository", "venue", "skill", "method", "paper", "concept", "dataset", "software"}
ALLOWED_EDGE_TYPES = {
    "supports", "extends", "overlaps", "implements", "applies_to", "published_at", "cites",
    "uses", "evaluates", "contradicts", "supersedes", "domain_adapter_for", "classified_as",
}


class KnowledgeError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _https(value: Any, label: str) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    if parsed.scheme.casefold() != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise KnowledgeError(f"{label} must be a credential-free clickable HTTPS URL")
    return text


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


def _seed() -> dict[str, Any]:
    try:
        repositories = json.loads(REPOSITORY_REGISTRY.read_text(encoding="utf-8"))["repositories"]
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise KnowledgeError(f"repository registry is invalid: {exc}") from exc
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for repository in repositories:
        node_id = f"repository:{repository['id']}"
        nodes.append({
            "id": node_id, "type": "repository", "label": repository["id"],
            "summary": repository["reason"], "source_url": _https(repository["url"], "repository URL"),
            "source_hash": repository["commit"], "license": repository["license"],
            "tags": [repository["category"], repository["verdict"]], "origin": "seed",
        })
        edges.append({
            "source": node_id, "target": f"concept:{repository['category']}", "type": "applies_to",
            "evidence_url": repository["url"], "origin": "seed",
        })
        nodes.append({
            "id": f"concept:{repository['category']}", "type": "concept", "label": repository["category"],
            "summary": "Curated research capability category.", "source_url": repository["url"],
            "source_hash": repository["commit"], "tags": ["capability"], "origin": "seed",
        })
    ccf = load_catalog()
    for venue in ccf["entries"]:
        node_id = f"venue:{venue['category']}:{venue['canonical']}"
        nodes.append({
            "id": node_id, "type": "venue", "label": venue["venue"], "summary": venue["full_name"],
            "source_url": venue["ccf_category_url"], "source_hash": venue["source_sha256"],
            "tags": [f"CCF-{venue['ccf_class']}", venue["category"]], "origin": "seed",
        })
        edges.append({
            "source": node_id, "target": f"concept:ccf-{venue['ccf_class'].casefold()}", "type": "classified_as",
            "evidence_url": venue["ccf_category_url"], "origin": "seed",
        })
        nodes.append({
            "id": f"concept:ccf-{venue['ccf_class'].casefold()}", "type": "concept",
            "label": f"CCF {venue['ccf_class']}", "summary": "CCF venue classification; not a writing-format authority.",
            "source_url": ccf["official_directory_url"], "source_hash": venue["source_sha256"],
            "tags": ["venue-classification"], "origin": "seed",
        })
    dedup_nodes = {node["id"]: node for node in nodes}
    dedup_edges = {(edge["source"], edge["target"], edge["type"]): edge for edge in edges}
    return {"schema_version": 1, "nodes": list(dedup_nodes.values()), "edges": list(dedup_edges.values())}


def _load(root: Path) -> dict[str, Any]:
    path = _path(root)
    if not path.is_file():
        value = {**_seed(), "generated_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        value["graph_hash"] = _digest({"nodes": value["nodes"], "edges": value["edges"]})
        _atomic(path, value)
        return value
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KnowledgeError(f"knowledge graph is invalid: {exc}") from exc
    if value.get("graph_hash") != _digest({"nodes": value.get("nodes"), "edges": value.get("edges")}):
        raise KnowledgeError("knowledge graph integrity check failed")
    return value


def sync_knowledge(project_root: str) -> dict[str, Any]:
    root = _root(project_root)
    existing = _load(root)
    seed = _seed()
    project_nodes = [node for node in existing["nodes"] if node.get("origin") == "project"]
    project_edges = [edge for edge in existing["edges"] if edge.get("origin") == "project"]
    nodes = {node["id"]: node for node in seed["nodes"] + project_nodes}
    edges = {(edge["source"], edge["target"], edge["type"]): edge for edge in seed["edges"] + project_edges}
    value = {
        "schema_version": 1, "nodes": list(nodes.values()), "edges": list(edges.values()),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    value["graph_hash"] = _digest({"nodes": value["nodes"], "edges": value["edges"]})
    _atomic(_path(root), value)
    return {"status": "PASS", "nodes": len(value["nodes"]), "edges": len(value["edges"]), "graph_hash": value["graph_hash"]}


def register_knowledge(project_root: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    root = _root(project_root)
    value = _load(root)
    existing = {node["id"]: node for node in value["nodes"]}
    for raw in nodes or []:
        if not isinstance(raw, dict):
            raise KnowledgeError("knowledge node must be an object")
        node_type = str(raw.get("type") or "").casefold()
        node_id = str(raw.get("id") or "").strip()
        label = " ".join(str(raw.get("label") or "").split())
        summary = " ".join(str(raw.get("summary") or "").split())
        source_hash = str(raw.get("source_hash") or "").strip().casefold()
        if node_type not in ALLOWED_NODE_TYPES or not re.fullmatch(r"[a-z][a-z0-9_-]*:[^\s]{2,160}", node_id):
            raise KnowledgeError("knowledge node has an invalid type or id")
        if not label or not 20 <= len(summary) <= 1500:
            raise KnowledgeError("knowledge node needs a label and a 20-1500 character compact summary")
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}|10\.\d{4,9}/\S+", source_hash):
            raise KnowledgeError("knowledge node source_hash must be a commit, SHA-256, or DOI")
        candidate = {
            "id": node_id, "type": node_type, "label": label, "summary": summary,
            "source_url": _https(raw.get("source_url"), "knowledge node source URL"),
            "source_hash": source_hash, "tags": sorted(set(str(tag).casefold() for tag in raw.get("tags") or [])),
            "origin": "project",
        }
        if node_id in existing and existing[node_id] != candidate:
            raise KnowledgeError(f"knowledge node {node_id} is append-only; use a versioned id")
        existing[node_id] = candidate
    edge_map = {(edge["source"], edge["target"], edge["type"]): edge for edge in value["edges"]}
    for raw in edges or []:
        if not isinstance(raw, dict):
            raise KnowledgeError("knowledge edge must be an object")
        edge_type = str(raw.get("type") or "").casefold()
        source, target = str(raw.get("source") or ""), str(raw.get("target") or "")
        if edge_type not in ALLOWED_EDGE_TYPES or source not in existing or target not in existing:
            raise KnowledgeError("knowledge edge type or endpoints are invalid")
        edge = {"source": source, "target": target, "type": edge_type, "evidence_url": _https(raw.get("evidence_url"), "edge evidence URL"), "origin": "project"}
        edge_map[(source, target, edge_type)] = edge
    value["nodes"], value["edges"] = list(existing.values()), list(edge_map.values())
    value["generated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    value["graph_hash"] = _digest({"nodes": value["nodes"], "edges": value["edges"]})
    _atomic(_path(root), value)
    return {"status": "PASS", "nodes": len(value["nodes"]), "edges": len(value["edges"]), "graph_hash": value["graph_hash"]}


def search_knowledge(project_root: str, query: str, limit: int = 10) -> dict[str, Any]:
    value = _load(_root(project_root))
    words = set(re.findall(r"[a-z0-9][a-z0-9_.+-]{1,}|[\u4e00-\u9fff]{2,}", str(query or "").casefold()))
    if not words:
        raise KnowledgeError("knowledge query is empty")
    graph = nx.MultiDiGraph()
    nodes = {node["id"]: node for node in value["nodes"]}
    for node in value["nodes"]:
        graph.add_node(node["id"])
    for edge in value["edges"]:
        graph.add_edge(edge["source"], edge["target"], relation=edge["type"], evidence_url=edge["evidence_url"])
    ranked: list[tuple[float, dict[str, Any]]] = []
    for node in value["nodes"]:
        text = " ".join([node["label"], node["summary"], *node.get("tags", [])]).casefold()
        tokens = set(re.findall(r"[a-z0-9][a-z0-9_.+-]{1,}|[\u4e00-\u9fff]{2,}", text))
        overlap = len(words & tokens)
        phrase = 2 if str(query).casefold() in text else 0
        if overlap or phrase:
            ranked.append((overlap + phrase, node))
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    results: list[dict[str, Any]] = []
    for score, node in ranked[: max(1, min(int(limit), 20))]:
        neighbors: list[dict[str, str]] = []
        for source, target, data in graph.in_edges(node["id"], data=True):
            neighbors.append({"direction": "in", "node_id": source, "label": nodes[source]["label"], "relation": data["relation"], "evidence_url": data["evidence_url"]})
        for source, target, data in graph.out_edges(node["id"], data=True):
            neighbors.append({"direction": "out", "node_id": target, "label": nodes[target]["label"], "relation": data["relation"], "evidence_url": data["evidence_url"]})
        results.append({**node, "score": score, "neighbors": neighbors[:8]})
    return {"status": "PASS", "query": query, "results": results, "graph_hash": value["graph_hash"], "all_sources_clickable": True}


def knowledge_status(project_root: str) -> dict[str, Any]:
    value = _load(_root(project_root))
    return {"status": "PASS", "nodes": len(value["nodes"]), "edges": len(value["edges"]), "graph_hash": value["graph_hash"], "path": str(_path(_root(project_root)))}
