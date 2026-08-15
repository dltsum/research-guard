from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from resource_guard import require_orchestrator_budget, require_start_headroom, run_managed


PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / "p17-skillopt"
RUNTIME_FILES = (
    "scripts/ai_reviewer_robustness_core.py",
    "scripts/academic_figure_core.py",
    "scripts/paper_audit_core.py",
    "scripts/mcp_server.py",
    "skills/academic-language-guard/SKILL.md",
    "skills/academic-figure-guard/SKILL.md",
    "skills/paper-audit-guard/SKILL.md",
    "docs/PAPER_WRITING_CAPABILITIES.md",
    "references/research-progression-contract.md",
)


def _architecture_candidates() -> list[dict[str, Any]]:
    return [
        {
            "candidate": "prompt-only reviewer advice",
            "executable_gate": False,
            "preserves_17_tool_surface": True,
            "hash_bound": False,
            "anti_gaming": False,
            "decision": "REJECT",
        },
        {
            "candidate": "new standalone AI reviewer tool",
            "executable_gate": True,
            "preserves_17_tool_surface": False,
            "hash_bound": True,
            "anti_gaming": True,
            "decision": "REJECT",
        },
        {
            "candidate": "paper_audit AI-robustness subroute plus explicit figure roles",
            "executable_gate": True,
            "preserves_17_tool_surface": True,
            "hash_bound": True,
            "anti_gaming": True,
            "decision": "ADMIT",
        },
    ]


def _static_contract() -> dict[str, Any]:
    texts = {relative: (PLUGIN / relative).read_text(encoding="utf-8") for relative in RUNTIME_FILES}
    combined = "\n".join(texts.values())
    from mcp_server import TOOLS

    paper = next(item for item in TOOLS if item["name"] == "paper_audit")
    props = paper["inputSchema"]["properties"]
    checks = {
        "top-level MCP surface remains 17": len(TOOLS) == 17,
        "AI review is a paper subroute": "ai_robustness" in props["review_action"]["enum"],
        "AI-reviewer feature has a mandatory role": '"ai_reviewer": "ai_reviewer_robustness"' in texts["scripts/paper_audit_core.py"],
        "score-targeted variants are rejected": "FORBIDDEN_EVALUATION_KEYS" in texts["scripts/ai_reviewer_robustness_core.py"],
        "critical topics are preserved": "Preserve evidence-bounded limitations" in texts["scripts/ai_reviewer_robustness_core.py"],
        "primary source URLs remain in output": "primary_url" in (PLUGIN / "assets/review-evidence/ai-reviewer-evidence.json").read_text(encoding="utf-8"),
        "figure role auto-selection is absent": "def _select_roles" not in texts["scripts/academic_figure_core.py"],
        "figure roles require main-agent selection": "automatic figure-role selection is forbidden" in texts["scripts/academic_figure_core.py"],
        "occlusion is an explicit final-size gate": "no_content_occlusion" in texts["scripts/academic_figure_core.py"],
        "space and alignment are explicit gates": all(marker in texts["scripts/academic_figure_core.py"] for marker in ("space_utilization_balanced", "text_and_line_alignment", "margins_and_gutters_balanced")),
        "exact venue rules are freshness bound": "older than 30 days" in texts["scripts/academic_figure_core.py"],
        "Nature profile is bounded from venue format": "not a universal Nature format" in texts["skills/academic-language-guard/SKILL.md"],
        "long work has no arbitrary whole-task timeout": "Do not impose an arbitrary whole-task timeout" in texts["references/research-progression-contract.md"],
        "complete paper capability document is linked": "PAPER_WRITING_CAPABILITIES.md" in combined,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "architecture_candidates": _architecture_candidates(),
        "admitted_candidate": "paper_audit AI-robustness subroute plus explicit figure roles",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated P17 writing, AI-reviewer, figure, and progression SkillOpt gates")
    parser.add_argument("--rounds", type=int, default=4, choices=(3, 4, 5))
    arguments = parser.parse_args()
    require_start_headroom()
    require_orchestrator_budget()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rounds: list[dict[str, Any]] = []
    for index in range(1, arguments.rounds + 1):
        static = _static_contract()
        completed = run_managed(
            [
                sys.executable, "-X", "utf8", "-m", "unittest", "discover",
                "-s", "tests", "-p", "test_p17_*.py", "-v",
            ],
            cwd=PLUGIN,
            timeout=900,
        )
        record = {
            "round": index,
            "status": "PASS" if completed.returncode == 0 and static["status"] == "PASS" else "FAIL",
            "optimization_target": "executable anti-gaming, explicit-role routing, final-size figure quality, and durable research progression",
            "semantic_router_optimized": False,
            "manuscript_score_optimized": False,
            "static_contract": static,
            "test_returncode": completed.returncode,
            "test_output_sha256": hashlib.sha256(
                ((completed.stdout or "") + (completed.stderr or "")).encode("utf-8")
            ).hexdigest(),
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
        "round_count": len(rounds),
        "requested_rounds": arguments.rounds,
        "automatic_semantic_selection": False,
        "ai_reviewer_score_optimization": False,
        "rounds": rounds,
    }
    report["report_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    (EVIDENCE / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
