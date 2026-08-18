from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from resource_guard import require_orchestrator_budget, require_start_headroom, run_managed


PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / "subagent-delegation-skillopt"
CONTRACT_FILES = (
    "assets/llm-delegation-policy.json", "scripts/llm_delegation_core.py",
    "scripts/mcp_server.py", "hooks/guard_hook.py", "SKILL.md",
    "docs/SUBAGENT_DELEGATION.md", "README.md", "README.zh-CN.md",
)


def _static_contract() -> dict[str, Any]:
    texts = {name: (PLUGIN / name).read_text(encoding="utf-8") for name in CONTRACT_FILES}
    policy = json.loads(texts["assets/llm-delegation-policy.json"])
    from mcp_server import TOOLS

    research_design = next(item for item in TOOLS if item["name"] == "research_design")
    props = research_design["inputSchema"]["properties"]
    combined = "\n".join(texts.values())
    checks = {
        "one canonical owner and 17-tool surface": len(TOOLS) == 17 and "delegation_action" in props,
        "native subagent is default": policy.get("default_execution_mode") == "native_subagent",
        "one serial lowest-capable worker": policy.get("default_subagent_count") == 1
        and policy.get("maximum_parallel_subagents") == 1,
        "low reasoning is default and medium is the cap": policy.get("default_reasoning_effort") == "low"
        and policy.get("maximum_reasoning_effort") == "medium",
        "silent external fallback is forbidden": policy.get("external_api_default_allowed") is False
        and policy.get("fallback_without_subagent") == "main_agent_local",
        "external exceptions require user provenance": "EXTERNAL_API_USER_DECISION_REQUIRED" in combined
        and "external_selected_by=user" in combined,
        "artifact receipts are hash bound": "artifact_sha256" in combined and "receipt_sha256" in combined,
        "independence boundary is explicit": "not independent" in combined.casefold()
        and "NOT_CROSS_PROVIDER" in combined,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
        "architecture_candidates": [
            {"candidate": "unrecorded external API fallback", "decision": "REJECT"},
            {"candidate": "prompt-only subagent preference", "decision": "REJECT"},
            {"candidate": "new top-level delegation tool", "decision": "REJECT"},
            {"candidate": "research_design typed route with native-first plan and hash receipt", "decision": "ADMIT"},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated native-subagent delegation SkillOpt gates")
    parser.add_argument("--rounds", type=int, default=4, choices=(3, 4, 5))
    arguments = parser.parse_args()
    require_start_headroom()
    require_orchestrator_budget()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rounds: list[dict[str, Any]] = []
    for index in range(1, arguments.rounds + 1):
        static = _static_contract()
        completed = run_managed(
            [sys.executable, "-X", "utf8", "-m", "unittest", "tests.test_subagent_delegation", "-v"],
            cwd=PLUGIN, timeout=600,
        )
        record = {
            "round": index,
            "status": "PASS" if completed.returncode == 0 and static["status"] == "PASS" else "FAIL",
            "static_contract": static, "test_returncode": completed.returncode,
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
        "requested_rounds": arguments.rounds, "round_count": len(rounds), "rounds": rounds,
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
