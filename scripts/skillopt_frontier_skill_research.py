from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from documentation_parity import validate_documentation
from resource_guard import (
    ResourceGuardError,
    require_orchestrator_budget,
    require_start_headroom,
    run_managed,
)


PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / "p24-frontier-skillopt"
CONTRACT_FILES = (
    "assets/research-repositories/registry.json",
    "assets/resource-policy.json",
    "scripts/domain_skill_core.py",
    "scripts/frontier_skill_research_core.py",
    "scripts/mcp_server.py",
    "skills/research-design-guard/SKILL.md",
    "skills/research-design-guard/references/extended-research-contracts.md",
    "docs/ARCHITECTURE.md",
    "docs/FRONTIER_SKILL_RESEARCH.md",
    "docs/FRONTIER_SKILL_RESEARCH.zh-CN.md",
    "README.md",
    "README.zh-CN.md",
    "tests/test_p24_frontier_skill_research.py",
    "tests/test_p10_cycle_b_domain_graph_evolution.py",
)


def _static_contract() -> dict[str, Any]:
    texts = {name: (PLUGIN / name).read_text(encoding="utf-8") for name in CONTRACT_FILES}
    combined = "\n".join(texts.values())
    registry = json.loads(texts["assets/research-repositories/registry.json"])
    resource = json.loads(texts["assets/resource-policy.json"])
    repository_ids = {item["id"] for item in registry["repositories"]}
    documentation = validate_documentation(PLUGIN)
    pair_ids = {item["id"] for item in documentation["pairs"]}
    from mcp_server import TOOLS

    design = next(item for item in TOOLS if item["name"] == "research_design")
    properties = design["inputSchema"]["properties"]
    checks = {
        "canonical research-design owner preserves 17 tools":
        len(TOOLS) == 17 and "frontier_skill_action" in properties,
        "main agent selects target and no classifier is added":
        "frontier_selected_by=main_agent is required" in combined
        and "no keyword classifier or small routing model" in combined,
        "frozen disjoint splits and exact validation count":
        "train, validation, and heldout case ids must be disjoint" in combined
        and "validation_rounds must be exactly 2 or 3" in combined,
        "heldout is locked and used once":
        "heldout evaluation is locked until all validation rounds pass" in combined
        and "heldout evaluation is a single final round" in combined,
        "validation evidence is ordered and run ids are unique":
        "validation trials must be appended in frozen round order" in combined
        and "frontier trial run_id must be unique within the protocol" in combined,
        "target utility and safety are recomputed from artifacts":
        "utility_improved" in texts["scripts/frontier_skill_research_core.py"]
        and "safety_pass" in texts["scripts/frontier_skill_research_core.py"]
        and "caller-supplied PASS labels are not accepted" in combined,
        "sources and candidate ownership are immutable and clickable":
        "primary-paper source" in combined
        and "implementation/specification source" in combined
        and "frontier evidence does not bind this artifact, owner, and overlap decision" in combined,
        "failed branches persist without automatic apply":
        "rejected_or_reference_branches" in combined
        and '"apply_route_exposed": False' in texts["scripts/frontier_skill_research_core.py"],
        "quarantine findings fail closed across markdown and files":
        '"status": "PASS" if manifest.get("license_allowed") and not findings else "BLOCKED"'
        in texts["scripts/domain_skill_core.py"]
        and "cross_file_sensitive_exfiltration" in combined
        and "hidden_unicode_control" in combined,
        "proxy optimization cannot become final performance evidence":
        "trigger/file-selection proxy only" in combined
        and "artifact-backed target-agent frontier protocol is still required" in combined,
        "current primary implementations are pinned":
        {"skillopt", "skilllens", "arbor", "skill-inject", "skillweaver"} <= repository_ids,
        "bilingual operator contract is registered and current":
        documentation["status"] == "PASS" and "frontier-skill-research" in pair_ids,
        "resource contract remains serial CPU and at most 512 MiB":
        resource.get("owned_task_budget_bytes") == 512 * 1024 * 1024
        and resource.get("maximum_parallel_workers") == 1
        and resource.get("gpu_allowed") is False,
    }
    architecture_candidates = [
        {"candidate": "popularity or token overlap as sufficient admission evidence", "decision": "REJECT"},
        {"candidate": "automatic executable Skill synthesis and immediate installation", "decision": "REJECT"},
        {"candidate": "static regex scan represented as a proof of safety", "decision": "REJECT"},
        {"candidate": "discard failed trials and expose heldout during optimization", "decision": "REJECT"},
        {
            "candidate": "fail-closed quarantine plus source-bound hypothesis tree and target-harness validation/heldout receipts",
            "decision": "ADMIT",
        },
    ]
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "architecture_candidates": architecture_candidates,
        "documentation": {
            "status": documentation["status"],
            "pair_count": documentation["pair_count"],
            "translation_files": documentation["translation_files"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated frontier Skill research SkillOpt gates")
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
                [
                    sys.executable, "-X", "utf8", "-m", "unittest",
                    "tests.test_p24_frontier_skill_research",
                    "tests.test_p10_cycle_b_domain_graph_evolution",
                    "-v",
                ],
                cwd=PLUGIN,
                timeout=600,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            record = {
                "round": index,
                "status": "PASS" if completed.returncode == 0 and static["status"] == "PASS" else "FAIL",
                "static_contract": static,
                "test_returncode": completed.returncode,
                "test_output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
                "test_stdout_tail": (completed.stdout or "")[-10_000:],
                "test_stderr_tail": (completed.stderr or "")[-10_000:],
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
        "status": "PASS" if len(rounds) == arguments.rounds and all(
            item["status"] == "PASS" for item in rounds
        ) else "FAIL",
        "requested_rounds": arguments.rounds,
        "round_count": len(rounds),
        "run_root": run_root.relative_to(PLUGIN).as_posix(),
        "rounds": rounds,
    }
    report["report_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (run_root / "report.json").write_text(rendered, encoding="utf-8")
    (EVIDENCE / "report.json").write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
