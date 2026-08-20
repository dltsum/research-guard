from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from resource_guard import require_orchestrator_budget, require_start_headroom, run_managed


PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / "resource-task-planning-skillopt"
CONTRACT_FILES = (
    "assets/resource-policy.json", "assets/task-resource-profiles.json",
    "scripts/resource_guard.py", "scripts/resource_task_planner_core.py",
    "scripts/research_integrity_core.py", "scripts/mcp_server.py", "hooks/guard_hook.py", "SKILL.md",
    "docs/RESOURCE_AWARE_TASK_PLANNING.md", "README.md", "README.zh-CN.md",
    "docs/provenance/P19_RESOURCE_AWARE_TASK_PLANNING.md",
)


def _static_contract() -> dict[str, Any]:
    texts = {name: (PLUGIN / name).read_text(encoding="utf-8") for name in CONTRACT_FILES}
    policy = json.loads(texts["assets/resource-policy.json"])
    profiles = json.loads(texts["assets/task-resource-profiles.json"])
    from mcp_server import TOOLS

    design = next(item for item in TOOLS if item["name"] == "research_design")
    properties = design["inputSchema"]["properties"]
    combined = "\n".join(texts.values())
    checks = {
        "one canonical owner and 17-tool surface": len(TOOLS) == 17
        and "resource_plan_action" in properties
        and "execute" in properties["resource_plan_action"]["enum"],
        "512 MiB policy remains exact": policy.get("owned_task_budget_bytes") == 512 * 1024 * 1024,
        "serial CPU and GPU-off remain exact": policy.get("maximum_parallel_workers") == 1
        and policy.get("gpu_allowed") is False,
        "profiles map to executable resource guard": profiles["profiles"]["managed_standard"]["execution_route"] == "resource_guard.run_managed"
        and profiles["profiles"]["managed_install"]["execution_route"] == "resource_guard.run_managed_install"
        and profiles["profiles"]["managed_lean"]["execution_route"] == "resource_guard.run_managed_lean",
        "unknown completion requires inspection": "RECEIPT_INSPECTION_REQUIRED" in combined
        and profiles["global_contract"]["unknown_completion_requires_receipt_inspection"] is True,
        "whole-task deadlines are user-owned": profiles["global_contract"]["whole_task_deadline_without_user_budget"] is None
        and "budget_selected_by=user" in combined,
        "host inventory is not entitlement": "inventory" in combined.casefold() and "entitlement" in combined.casefold(),
        "resource plans and artifacts are hash bound": "plan_hash" in combined and "state_sha256" in combined
        and "ARTIFACT_HASH_MISMATCH" in combined,
        "semantic selection remains with main agent": "resource_selected_by=main_agent" in combined,
        "managed execution reuses the frozen reproducibility owner": "execute_reproducibility" in combined
        and "reproducibility_run_id" in combined
        and "research_integrity.execute_reproducibility" in combined,
        "linked completion rejects caller telemetry": "MANAGED_REPRODUCIBILITY_EXECUTION_REQUIRED" in combined
        and "caller-reported telemetry" in combined,
        "managed receipt binds resource duration plan execution and outputs": "duration_seconds" in combined
        and "execution_hash" in combined and "reproducibility_plan_hash" in combined
        and "peak_owned_bytes" in combined,
        "unmeasured network and disk claims fail closed": "MANAGED_NETWORK_ISOLATION_UNAVAILABLE" in combined
        and "MANAGED_DISK_TELEMETRY_UNAVAILABLE" in combined,
        "nonfinite child timeout is rejected": "RESOURCE_TASK_TIMEOUT_INVALID" in combined
        and "math.isfinite" in combined,
        "interrupted managed execution reconciles but never auto-replays":
        "reconciled_existing_receipt" in combined
        and "receipt_inspected" in combined
        and "replay is forbidden" in combined,
    }
    candidates = [
        {"candidate": "prompt-only task advice", "decision": "REJECT"},
        {"candidate": "new distributed scheduler or top-level MCP tool", "decision": "REJECT"},
        {"candidate": "second generic command executor inside the resource planner", "decision": "REJECT"},
        {"candidate": "caller-reported telemetry for a linked managed task", "decision": "REJECT"},
        {"candidate": "automatic replay after interrupted managed execution", "decision": "REJECT"},
        {"candidate": "automatic memory escalation after failure", "decision": "REJECT"},
        {"candidate": "typed DAG plus canonical reproducibility and process-guard receipts", "decision": "ADMIT"},
    ]
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "architecture_candidates": candidates}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated resource-aware task-planning SkillOpt gates")
    parser.add_argument("--rounds", type=int, default=4, choices=(3, 4, 5))
    arguments = parser.parse_args()
    require_start_headroom()
    require_orchestrator_budget()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rounds: list[dict[str, Any]] = []
    for index in range(1, arguments.rounds + 1):
        static = _static_contract()
        completed = run_managed(
            [sys.executable, "-X", "utf8", "-m", "unittest", "tests.test_resource_task_planning", "-v"],
            cwd=PLUGIN, timeout=600,
        )
        record = {
            "round": index,
            "status": "PASS" if completed.returncode == 0 and static["status"] == "PASS" else "FAIL",
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
        "requested_rounds": arguments.rounds,
        "round_count": len(rounds),
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
