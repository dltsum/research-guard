"""Focused repository checks; no preset audit, text-token or digest ceremony."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import yaml

from documentation_parity import validate_documentation
from mcp_server import TOOLS

ROOT=Path(__file__).resolve().parents[1]


def validate() -> dict:
    for name in ("SKILL.md","README.md","README.zh-CN.md","INSTALL_PROMPT.md"):
        path=ROOT/name
        if not path.is_file() or not path.read_text(encoding="utf-8-sig").strip():
            raise RuntimeError(f"missing or empty entry document: {name}")
    skill=(ROOT/"SKILL.md").read_text(encoding="utf-8")
    if not skill.startswith("---\n"):
        raise RuntimeError("SKILL.md needs YAML frontmatter")
    front=yaml.safe_load(skill.split("---",2)[1])
    if not isinstance(front,dict) or not front.get("name") or not front.get("description"):
        raise RuntimeError("Skill frontmatter needs name and description")
    python_files=[p for folder in ("scripts","hooks") for p in (ROOT/folder).glob("*.py")]
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8-sig"),filename=str(path))
    data_files=list((ROOT/"assets").glob("*.json"))+[ROOT/".codex-plugin/plugin.json",ROOT/".mcp.json"]
    for path in data_files:
        json.loads(path.read_text(encoding="utf-8-sig"))
    names=[tool["name"] for tool in TOOLS]
    if len(set(names))!=len(names):
        raise RuntimeError("MCP tool names must be unique")
    plugin=json.loads((ROOT/".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    docs=validate_documentation(ROOT)
    return {"status":"PASS","plugin":plugin.get("name"),"version":plugin.get("version"),
            "python_files_parsed":len(python_files),"json_files_parsed":len(data_files),
            "mcp_tools":len(names),"bilingual_document_pairs":docs["pair_count"],
            "documentation_warnings":docs["warnings"]}


if __name__=="__main__":
    print(json.dumps(validate(),ensure_ascii=False,indent=2))
