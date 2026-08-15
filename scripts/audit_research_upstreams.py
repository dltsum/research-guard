from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


REPOSITORIES = {
    "academic-research-skills": "academic-research-skills",
    "ai-research-skills": "AI-Research-SKILLS",
    "aris": "Auto-claude-code-research-in-sleep",
    "nature-skills": "nature-skills",
    "paper-craft-skills": "paper-craft-skills",
    "paperspine": "PaperSpine",
    "research-paper-writing-skills": "Research-Paper-Writing-Skills",
    "scientific-agent-skills": "scientific-agent-skills",
}

OWNER_RULES = (
    ("academic-figure", ("figure", "plot", "visual", "diagram", "infographic", "illustration", "poster", "slides", "ppt", "comic")),
    ("paper-audit", ("audit", "reviewer", "review", "citation", "proof", "formula", "integrity", "result-to-claim")),
    ("academic-language", ("writing", "polish", "translation", "response", "rebuttal", "paper-spine", "paper-write")),
    ("research-design", ("idea", "hypothesis", "experiment", "ablation", "strategy", "risk", "decision", "proposal")),
    ("research-novelty", ("literature", "search", "arxiv", "openalex", "deepxiv", "prior-art", "novelty")),
    ("self-evolution", ("meta-optimize", "meta-apply", "autoskill", "evolv", "autoresearch")),
)


def _git(repo: Path, *arguments: str) -> str:
    run = subprocess.run(["git", "-C", str(repo), *arguments], text=True, capture_output=True, encoding="utf-8")
    if run.returncode:
        raise RuntimeError(run.stderr.strip())
    return run.stdout


def _batch_show(repo: Path, paths: list[str]) -> dict[str, str]:
    tree: dict[str, str] = {}
    for line in _git(repo, "ls-tree", "-r", "HEAD").splitlines():
        header, path = line.split("\t", 1)
        object_id = header.split()[2]
        tree[path] = object_id
    missing = [path for path in paths if path not in tree]
    if missing:
        raise RuntimeError(f"Git tree is missing requested paths: {missing[:5]}")
    process = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    raw, error = process.communicate("".join(f"{tree[path]}\n" for path in paths).encode("ascii"))
    if process.returncode:
        raise RuntimeError(error.decode("utf-8", errors="replace").strip())
    offset = 0
    result: dict[str, str] = {}
    for path in paths:
        end = raw.find(b"\n", offset)
        if end < 0:
            raise RuntimeError(f"git cat-file response ended before {path}")
        header = raw[offset:end].decode("ascii", errors="strict").split()
        if len(header) != 3 or header[1] != "blob":
            raise RuntimeError(f"git cat-file returned an invalid header for {path}: {header}")
        size = int(header[2])
        start = end + 1
        result[path] = raw[start : start + size].decode("utf-8", errors="replace")
        offset = start + size + 1
    return result


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\s*\n([\s\S]+?)\n---", text)
    if not match:
        return {}
    result: dict[str, str] = {}
    lines = match.group(1).splitlines()
    current: str | None = None
    for line in lines:
        field = re.match(r"^([a-zA-Z][a-zA-Z0-9_-]*):\s*(.*)$", line)
        if field:
            current = field.group(1)
            result[current] = field.group(2).strip().strip('"\'')
        elif current == "description" and line.startswith((" ", "\t")):
            result[current] = " ".join((result[current], line.strip())).strip()
    return result


def _owner(name: str, description: str, path: str, repository_id: str) -> tuple[str, str]:
    text = f"{name} {description} {path}".casefold()
    for owner, terms in OWNER_RULES:
        if any(term in text for term in terms):
            if owner == "self-evolution":
                return owner, "reference_only_proposal_boundary"
            return owner, "overlap_keep_canonical_owner"
    if repository_id in {"scientific-agent-skills", "ai-research-skills"}:
        return "domain-skill", "just_in_time_domain_candidate"
    return "research-artifact", "selective_contract_candidate"


def build(mirror_root: Path) -> dict[str, Any]:
    registry = json.loads((Path(__file__).resolve().parents[1] / "assets" / "research-repositories" / "registry.json").read_text(encoding="utf-8"))
    metadata = {item["id"]: item for item in registry["repositories"]}
    entries: list[dict[str, Any]] = []
    repositories: list[dict[str, Any]] = []
    for repository_id, directory in REPOSITORIES.items():
        repo = mirror_root / directory
        commit = _git(repo, "rev-parse", "HEAD").strip()
        expected = metadata[repository_id]["commit"]
        if commit != expected:
            raise RuntimeError(f"{repository_id} is at {commit}, expected {expected}")
        paths = [line for line in _git(repo, "ls-tree", "-r", "--name-only", "HEAD").splitlines() if line]
        skill_paths = [path for path in paths if path.casefold().endswith("skill.md")]
        skill_texts = _batch_show(repo, skill_paths)
        repositories.append({
            "repository_id": repository_id, "url": metadata[repository_id]["url"], "commit": commit,
            "license": metadata[repository_id]["license"], "tree_files": len(paths), "skill_entrypoints": len(skill_paths),
        })
        for path in skill_paths:
            text = skill_texts[path]
            frontmatter = _frontmatter(text)
            name = frontmatter.get("name") or Path(path).parent.name
            description = " ".join((frontmatter.get("description") or "").split())
            prefix = Path(path).parent.as_posix().rstrip("/") + "/"
            related = [item for item in paths if item.startswith(prefix)]
            owner, disposition = _owner(name, description, path, repository_id)
            entries.append({
                "repository_id": repository_id, "path": path, "name": name, "description": description,
                "declared_license": frontmatter.get("license"), "implementation": {
                    "files_in_skill_directory": len(related),
                    "scripts": sum("/scripts/" in f"/{item}" for item in related),
                    "references": sum("/references/" in f"/{item}" for item in related),
                    "templates": sum("/templates/" in f"/{item}" for item in related),
                    "declares_allowed_tools": "allowed-tools" in frontmatter,
                },
                "canonical_owner": owner, "disposition": disposition,
            })
    return {
        "schema_version": 1,
        "scope": "Every SKILL.md entrypoint in the original eight repositories at the pinned commits; descriptions are source frontmatter and implementation counts are from the immutable Git tree.",
        "repositories": repositories,
        "summary": {
            "repositories": len(repositories), "skill_entrypoints": len(entries),
            "by_owner": {owner: sum(item["canonical_owner"] == owner for item in entries) for owner in sorted({item["canonical_owner"] for item in entries})},
            "by_disposition": {decision: sum(item["disposition"] == decision for item in entries) for decision in sorted({item["disposition"] for item in entries})},
        },
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mirror-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    value = build(arguments.mirror_root.resolve())
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(value["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
