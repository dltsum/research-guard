from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from resource_guard import require_orchestrator_budget, require_start_headroom, run_managed


PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / "p16-skillopt"
RUNTIME_FILES = (
    "hooks/guard_hook.py",
    "scripts/intent_router_core.py",
    "scripts/discipline_profile_core.py",
    "scripts/paper_audit_core.py",
    "scripts/research_guard_core.py",
    "scripts/mcp_server.py",
)


def _static_contract() -> dict[str, Any]:
    texts = {
        relative: (PLUGIN / relative).read_text(encoding="utf-8")
        for relative in RUNTIME_FILES
    }
    combined = "\n".join(texts.values())
    forbidden_runtime_markers = {
        "disabled automatic implementations": "def _disabled_",
        "legacy prompt keyword classifier": "RESEARCH_TERMS = re.compile",
        "legacy method-change keyword classifier": "METHOD_CHANGE_TERMS = re.compile",
    }
    absent = {
        label: marker not in combined
        for label, marker in forbidden_runtime_markers.items()
    }
    from mcp_server import TOOLS

    tools = TOOLS
    schemas_have_no_generic_timeout = all(
        "timeout" not in item["inputSchema"].get("properties", {})
        for item in tools
    )
    novelty = next(item for item in tools if item["name"] == "run_novelty_search")
    properties = novelty["inputSchema"]["properties"]
    checks = {
        **absent,
        "all MCP tools avoid ambiguous generic timeout": schemas_have_no_generic_timeout,
        "novelty has per-attempt timeout": "attempt_timeout_seconds" in properties,
        "novelty exposes persisted scheduling slices": "work_units_per_call" in properties,
        "novelty exposes explicit retry": "retry_unit_ids" in properties,
        "novelty exposes explicit factual-blocker decision": "blocker_decision" in properties,
        "hook requires main-agent selection": "main agent must call list_research_modules" in texts["hooks/guard_hook.py"],
        "hook forbids timer-based research stopping": "timeouts never constitute a research deadline" in texts["hooks/guard_hook.py"],
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated P16 main-agent-selection and continuation SkillOpt gates")
    parser.add_argument("--rounds", type=int, default=4, choices=(3, 4, 5))
    arguments = parser.parse_args()
    require_start_headroom()
    require_orchestrator_budget()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rounds = []
    for index in range(1, arguments.rounds + 1):
        static = _static_contract()
        completed = run_managed(
            [
                sys.executable, "-X", "utf8", "-m", "unittest", "discover",
                "-s", "tests", "-p", "test_p16_*.py", "-v",
            ],
            cwd=PLUGIN,
            timeout=900,
        )
        record = {
            "round": index,
            "status": "PASS" if completed.returncode == 0 and static["status"] == "PASS" else "FAIL",
            "semantic_selector_optimized": False,
            "optimization_target": "explicit-selection validation, durable progress, and stop-policy enforcement",
            "static_contract": static,
            "test_returncode": completed.returncode,
            "test_output_sha256": hashlib.sha256(
                ((completed.stdout or "") + (completed.stderr or "")).encode("utf-8")
            ).hexdigest(),
            "resource_usage": completed.resource_usage,
        }
        (EVIDENCE / f"round-{index:02d}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
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
        "research_deadline": None,
        "rounds": rounds,
    }
    report["report_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    (EVIDENCE / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
