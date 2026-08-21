from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from resource_guard import ResourceGuardError, require_orchestrator_budget, require_start_headroom, run_managed


PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / "direction-exploration-skillopt"
CONTRACT_FILES = (
    "assets/direction-exploration-contract.json",
    "scripts/direction_exploration_core.py",
    "scripts/resource_guard.py",
    "scripts/resource_task_planner_core.py",
    "scripts/research_integrity_core.py",
    "scripts/research_guard_core.py",
    "scripts/mcp_server.py",
    "hooks/guard_hook.py",
    "SKILL.md",
    "skills/research-design-guard/SKILL.md",
    "skills/research-design-guard/references/direction-exploration-contract.md",
    "docs/DIRECTION_EXPLORATION.md",
    "docs/provenance/P20_DIRECTION_EXPLORATION.md",
    "README.md",
    "README.zh-CN.md",
)


def _static_contract() -> dict[str, Any]:
    texts = {name: (PLUGIN / name).read_text(encoding="utf-8") for name in CONTRACT_FILES}
    contract = json.loads(texts["assets/direction-exploration-contract.json"])
    from mcp_server import TOOLS

    design = next(item for item in TOOLS if item["name"] == "research_design")
    properties = design["inputSchema"]["properties"]
    combined = "\n".join(texts.values())
    checks = {
        "one canonical owner and 17-tool surface": len(TOOLS) == 17 and "direction_action" in properties,
        "authorization is user-owned": "DIRECTION_EXPLORATION_USER_AUTHORIZATION_REQUIRED" in combined
        and "direction_authorized_by" in properties,
        "inventory is reused and GPU stays off": "inventory_resources" in combined
        and contract.get("gpu_allowed") is False,
        "pool and final cardinality are exact": contract.get("candidate_pool_minimum") == 5
        and contract.get("candidate_pool_maximum") == 15
        and contract.get("final_choice_count") == 5,
        "automatic ranking and winner selection are rejected": contract.get("automatic_ranking_allowed") is False
        and contract.get("automatic_winner_selection_allowed") is False
        and "FORBIDDEN_SELECTION_FIELDS" in combined,
        "managed reproducibility remains command owner": "integrity_status" in combined
        and 'execution.get("execution_mode") != "managed"' in combined,
        "collision receipt is strict and version bound": "verify_receipt(base, strict=True)" in combined
        and "unresolved_collision_candidates" in combined,
        "protocol numbers are recomputed": "minimum_effect" in combined
        and "legal_range" in combined and "math.isfinite" in combined,
        "final test cannot select directions": set(contract.get("allowed_data_roles", [])) == {"pilot", "validation", "synthetic"},
        "method revision invalidates both evidence classes and choice set": set(contract.get("method_revision_invalidates", [])) == {
            "positive_coarse_test_evidence", "collision_search_evidence", "active_five-choice_set",
        },
        "literature remains clickable": "credential-free clickable HTTPS URL" in combined
        and "literature_links" in combined,
        "positive signal claim stays bounded": "local coarse signal" in combined
        and "not confirmatory evidence" in combined,
    }
    architecture_candidates = [
        {"candidate": "prompt-only direction brainstorming", "decision": "REJECT"},
        {"candidate": "second novelty engine or generic command executor", "decision": "REJECT"},
        {"candidate": "automatic best-direction score", "decision": "REJECT"},
        {"candidate": "GPU-first endless optimization loop", "decision": "REJECT"},
        {"candidate": "receipt-bound coordinator with exact-five user choice", "decision": "ADMIT"},
    ]
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "architecture_candidates": architecture_candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated direction-exploration SkillOpt gates")
    parser.add_argument("--rounds", type=int, default=4, choices=(3, 4, 5))
    arguments = parser.parse_args()
    require_start_headroom()
    require_orchestrator_budget()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    run_root = EVIDENCE / dt.datetime.now(dt.timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    run_root.mkdir(parents=True, exist_ok=False)
    rounds: list[dict[str, Any]] = []
    for index in range(1, arguments.rounds + 1):
        static = _static_contract()
        try:
            completed = run_managed(
                [sys.executable, "-X", "utf8", "-m", "unittest", "tests.test_direction_exploration", "-v"],
                cwd=PLUGIN,
                timeout=300,
            )
            record = {
                "round": index,
                "status": "PASS" if completed.returncode == 0 and static["status"] == "PASS" else "FAIL",
                "static_contract": static,
                "test_returncode": completed.returncode,
                "test_output_sha256": hashlib.sha256(
                    ((completed.stdout or "") + (completed.stderr or "")).encode("utf-8")
                ).hexdigest(),
                "test_stdout_tail": (completed.stdout or "")[-10000:],
                "test_stderr_tail": (completed.stderr or "")[-10000:],
                "resource_usage": completed.resource_usage,
            }
        except ResourceGuardError as exc:
            record = {
                "round": index,
                "status": "FAIL",
                "static_contract": static,
                "test_returncode": None,
                "test_output_sha256": None,
                "test_stdout_tail": "",
                "test_stderr_tail": "",
                "resource_usage": None,
                "resource_guard_error": str(exc),
            }
        (run_root / f"round-{index:02d}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
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
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    (run_root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
