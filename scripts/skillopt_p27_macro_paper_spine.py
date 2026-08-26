from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from resource_guard import require_orchestrator_budget, require_start_headroom, run_managed


PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / "p27-macro-paper-spine"
RUNTIME_FILES = (
    "scripts/paper_spine_core.py",
    "scripts/mcp_server.py",
    "scripts/research_guard_core.py",
    "hooks/guard_hook.py",
    "skills/academic-language-guard/SKILL.md",
    "skills/paper-audit-guard/SKILL.md",
    "skills/research-design-guard/SKILL.md",
    "skills/academic-language-guard/references/paper-spine-contract.md",
    "docs/PAPER_WRITING_CAPABILITIES.md",
    "README.md",
    "README.zh-CN.md",
)


def _static_contract() -> dict[str, Any]:
    texts = {relative: (PLUGIN / relative).read_text(encoding="utf-8") for relative in RUNTIME_FILES}
    combined = "\n".join(texts.values())
    from mcp_server import TOOLS

    language = next(item for item in TOOLS if item["name"] == "language_assist")
    properties = language["inputSchema"]["properties"]
    core = texts["scripts/paper_spine_core.py"]
    checks = {
        "keeps one canonical 17-tool surface": len(TOOLS) == 17,
        "spine is a language-assist subroute": set(("plan", "register", "bind_collision", "status", "verify")) <= set(properties["spine_action"]["enum"]),
        "macro layer is required": all(marker in core for marker in ("macro_problem", "unifying_method", "generality_target")),
        "cross-context evidence is required": "cross_context_predictions" in core and "distinct contexts" in core,
        "five title levels and no automatic winner": "minimum=5" in core and "automatic_title_selection" in core and "FORBIDDEN_SELECTION_KEYS" in core,
        "collision is bound after formation": "bind_paper_spine_collision" in core and "verify_receipt(base, strict=True)" in core,
        "collision does not narrow the idea": "not a reason to retreat" in combined or "not the contribution ceiling" in combined,
        "every literature source stays clickable": "clickable HTTPS" in core and "source_links" in core,
        "domain inference remains explicit": "automatic_domain_inference" in core and "does not classify the domain" in combined,
        "user retains title choice": "user_title_selection_required" in core and ("user owns the final framing choice" in combined or "user chooses the final title" in combined),
        "writing and audit hook exposes spine route": "language_assist spine_action=plan" in texts["hooks/guard_hook.py"] and "never force a retreat" in texts["hooks/guard_hook.py"],
        "ideation cannot replace semantic framing": "keyword heuristic" in texts["skills/research-design-guard/SKILL.md"] and "scientific framing" in texts["skills/research-design-guard/SKILL.md"],
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "architecture_candidates": [
            {"candidate": "collision-first narrow title generation", "decision": "REJECT"},
            {"candidate": "prompt-only macro advice", "decision": "REJECT"},
            {"candidate": "automatic title winner", "decision": "REJECT"},
            {"candidate": "macro-first spine contract with canonical collision binding", "decision": "ADMIT"},
        ],
        "admitted_candidate": "macro-first spine contract with canonical collision binding",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated macro-first paper-spine SkillOpt gates")
    parser.add_argument("--rounds", type=int, default=3, choices=(3, 4, 5))
    arguments = parser.parse_args()
    require_start_headroom()
    require_orchestrator_budget()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rounds: list[dict[str, Any]] = []
    for index in range(1, arguments.rounds + 1):
        static = _static_contract()
        completed = run_managed(
            [sys.executable, "-X", "utf8", "-m", "unittest", "tests.test_p27_macro_paper_spine", "-v"],
            cwd=PLUGIN,
            timeout=300,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        record = {
            "round": index,
            "status": "PASS" if static["status"] == "PASS" and completed.returncode == 0 else "FAIL",
            "optimization_target": "macro problem and unifying method before collision-based differentiation",
            "automatic_domain_or_title_selection": False,
            "static_contract": static,
            "test_returncode": completed.returncode,
            "test_output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            "resource_usage": completed.resource_usage,
        }
        (EVIDENCE / f"round-{index:02d}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        rounds.append(record)
        if record["status"] != "PASS":
            break
    report = {
        "schema_version": 1,
        "status": "PASS" if len(rounds) == arguments.rounds and all(item["status"] == "PASS" for item in rounds) else "FAIL",
        "requested_rounds": arguments.rounds,
        "round_count": len(rounds),
        "rounds": rounds,
    }
    report["report_sha256"] = hashlib.sha256(
        json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    (EVIDENCE / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
