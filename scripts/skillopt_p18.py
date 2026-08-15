from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from resource_guard import require_orchestrator_budget, require_start_headroom, run_managed


PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / "p18-skillopt"
RUNTIME_FILES = (
    "scripts/ai_reviewer_robustness_core.py",
    "scripts/paper_audit_core.py",
    "scripts/mcp_server.py",
    "skills/paper-audit-guard/SKILL.md",
    "skills/paper-audit-guard/references/ai-reviewer-optimization.md",
    "skills/academic-language-guard/SKILL.md",
    "docs/PAPER_WRITING_CAPABILITIES.md",
    "README.md",
)


def _architecture_candidates() -> list[dict[str, Any]]:
    return [
        {
            "candidate": "prompt-only advice to please AI reviewers",
            "executable_candidate_binding": False,
            "same_panel_comparison": False,
            "user_opt_in": False,
            "decision": "REJECT",
        },
        {
            "candidate": "automatic unconditional score optimization",
            "executable_candidate_binding": True,
            "same_panel_comparison": False,
            "user_opt_in": False,
            "decision": "REJECT",
        },
        {
            "candidate": "new top-level optimizer tool",
            "executable_candidate_binding": True,
            "same_panel_comparison": True,
            "preserves_17_tool_surface": False,
            "decision": "REJECT",
        },
        {
            "candidate": "optional paper_audit plan-register-select subroutes with robust same-panel scoring",
            "executable_candidate_binding": True,
            "same_panel_comparison": True,
            "user_opt_in": True,
            "preserves_17_tool_surface": True,
            "decision": "ADMIT",
        },
    ]


def _static_contract() -> dict[str, Any]:
    texts = {relative: (PLUGIN / relative).read_text(encoding="utf-8") for relative in RUNTIME_FILES}
    core = texts["scripts/ai_reviewer_robustness_core.py"]
    combined = "\n".join(texts.values())
    from mcp_server import TOOLS

    paper = next(item for item in TOOLS if item["name"] == "paper_audit")
    props = paper["inputSchema"]["properties"]
    actions = props["review_action"]["enum"]
    checks = {
        "top-level MCP surface remains 17": len(TOOLS) == 17,
        "active optimization is an existing-paper subroute": all(
            action in actions for action in (
                "ai_optimize_plan", "ai_optimize_register", "ai_optimize_select", "ai_optimize_status",
            )
        ),
        "active mode requires explicit user opt-in": 'selected_by != "user"' in core,
        "official venue reviewer guidance is required": "venue_reviewer_contract" in core and "source_type" in core,
        "current empirical strategy sources are required": all(
            source_id in core for source_id in (
                "rhetoric-reward-hack-2026", "reviewer-guidelines-2026", "titletrap-2025",
            )
        ),
        "candidate citations numbers formulas and critical paragraphs are frozen": all(
            marker in core for marker in (
                '"citations", "numbers", "formulas", "protected_critical_paragraphs"',
                "changed protected content",
            )
        ),
        "same panel and two distinct models are executable gates": all(
            marker in core for marker in (
                "every candidate must be evaluated by the same model/prompt panel",
                "at least two distinct reviewer models",
            )
        ),
        "selector penalizes cross-panel variance": "mean - 0.5 * spread" in core,
        "baseline can win when no robust gain exists": "NO_ROBUST_IMPROVEMENT" in core,
        "robustness and active modes stay separate": "FORBIDDEN_EVALUATION_KEYS" in core and "ai_optimize_plan" in actions,
        "documentation names active optimization": "主动适配优化" in combined and "active AI-reviewer adaptation" in combined,
        "score is not represented as acceptance probability": "not an acceptance probability" in core,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "architecture_candidates": _architecture_candidates(),
        "admitted_candidate": "optional paper_audit plan-register-select subroutes with robust same-panel scoring",
        "selection_algorithm_comparison": [
            {"algorithm": "maximum single-model score", "variance_penalty": False, "decision": "REJECT"},
            {"algorithm": "cross-panel mean only", "variance_penalty": False, "decision": "REJECT"},
            {"algorithm": "cross-panel mean minus 0.5 population standard deviation", "variance_penalty": True, "decision": "ADMIT"},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated P18 active AI-reviewer adaptation SkillOpt gates")
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
                "-s", "tests", "-p", "test_p18_*.py", "-v",
            ],
            cwd=PLUGIN,
            timeout=900,
        )
        record = {
            "round": index,
            "status": "PASS" if completed.returncode == 0 and static["status"] == "PASS" else "FAIL",
            "optimization_target": "optional truthful presentation adaptation for a registered AI-reviewer panel",
            "automatic_semantic_router_optimized": False,
            "active_ai_reviewer_score_optimization": True,
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
        "active_ai_reviewer_score_optimization": True,
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
