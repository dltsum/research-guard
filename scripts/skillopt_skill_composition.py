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
EVIDENCE = PLUGIN / "evals" / "p26-skill-composition-skillopt"
CONTRACT_FILES = (
    "assets/research-repositories/registry.json",
    "assets/resource-policy.json",
    "scripts/frontier_skill_research_core.py",
    "scripts/skill_composition_core.py",
    "scripts/mcp_server.py",
    "skills/research-design-guard/SKILL.md",
    "skills/research-design-guard/references/extended-research-contracts.md",
    "docs/ARCHITECTURE.md",
    "docs/SKILL_COMPOSITION.md",
    "docs/SKILL_COMPOSITION.zh-CN.md",
    "README.md",
    "README.zh-CN.md",
    "tests/test_p26_skill_composition.py",
)


def _static_contract() -> dict[str, Any]:
    texts = {name: (PLUGIN / name).read_text(encoding="utf-8") for name in CONTRACT_FILES}
    core = texts["scripts/skill_composition_core.py"]
    frontier = texts["scripts/frontier_skill_research_core.py"]
    registry = json.loads(texts["assets/research-repositories/registry.json"])
    resource = json.loads(texts["assets/resource-policy.json"])
    documentation = validate_documentation(PLUGIN)
    pair_ids = {item["id"] for item in documentation["pairs"]}
    repository_ids = {item["id"] for item in registry["repositories"]}

    from mcp_server import TOOLS

    design = next(item for item in TOOLS if item["name"] == "research_design")
    properties = design["inputSchema"]["properties"]
    outcomes = {
        "POSITIVE_COMPOSITION_GAIN",
        "NO_COMPOSITION_GAIN",
        "INTERFERENCE",
        "SAFETY_REGRESSION",
    }
    checks = {
        "canonical research-design owner preserves 17 tools":
        len(TOOLS) == 17
        and properties.get("skill_composition_action", {}).get("enum")
        == ["plan", "record_source", "record_trial", "finalize", "status", "verify"],
        "main agent selects exactly two or three exact P24 artifacts":
        "selected_by != \"main_agent\"" in core
        and "components must contain exactly two or three main-agent-selected Skills" in core
        and "get_frontier_skill_portability_binding" in frontier
        and "must contain the exact P24 admission identity" in core,
        "composition cases cannot reuse any component P24 split":
        "composition cases overlap a component P24 train, validation, or heldout split" in core
        and "frontier_case_ids_sha256" in core,
        "no-Skill singles target and control are mandatory":
        "trial conditions must contain no-Skill, every single Skill, ordered, and control order" in core
        and "control_order must differ from the target component order" in core
        and "replicates must be exactly 2 or 3" in core,
        "all four outcomes and every order effect remain explicit":
        all(label in core for label in outcomes)
        and "no score average" in core
        and "order_effect" in core,
        "safety dominates and broad claims stay forbidden":
        'if "SAFETY_REGRESSION" in classifications' in core
        and '"universal_claim_allowed": False' in core
        and '"order_invariant_claim_allowed": False' in core
        and '"safety_claim_allowed": False' in core,
        "declared cross-Skill capability paths are order scoped":
        "TARGET_ORDER_PATH_REVIEW_REQUIRED" in core
        and "CONTROL_ORDER_PATH_REVIEW_REQUIRED" in core
        and "len(used_skills) >= 2" in core
        and '"attack_synthesis_performed": False' in core,
        "sources and execution artifacts fail closed":
        "Skill composition sources require a clickable HTTPS URL" in core
        and "repository sources require an immutable 40-character commit" in core
        and "SKILL_COMPOSITION_STATE_INTEGRITY_FAILURE" in core
        and "execution receipt hashes must be unique across replicates" in core,
        "the route records evidence but cannot execute apply optimize or admit":
        '"execution_allowed_by_core": False' in core
        and '"apply_route_exposed": False' in core
        and "admission_effect" in core,
        "current composition implementations are pinned":
        {"skillsbench", "sr-agents", "polyskill", "composkill"} <= repository_ids,
        "bilingual operator contract is registered and current":
        documentation["status"] == "PASS" and "skill-composition" in pair_ids,
        "resource contract remains serial CPU and at most 512 MiB":
        resource.get("owned_task_budget_bytes") == 512 * 1024 * 1024
        and resource.get("maximum_parallel_workers") == 1
        and resource.get("gpu_allowed") is False,
    }
    candidates = [
        {
            "candidate": "activate every locally available research Skill and infer synergy from coverage",
            "decision": "REJECT",
        },
        {
            "candidate": "test only the composed condition without no-Skill and single-Skill controls",
            "decision": "REJECT",
        },
        {
            "candidate": "pool replicates or orders and allow gains to erase one safety regression",
            "decision": "REJECT",
        },
        {
            "candidate": "treat a declared static capability graph as a complete safety proof",
            "decision": "REJECT",
        },
        {
            "candidate": "exact P24 bindings plus fresh controlled replicates and order-scoped path review",
            "decision": "ADMIT",
        },
    ]
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "architecture_candidates": candidates,
        "documentation": {
            "status": documentation["status"],
            "pair_count": documentation["pair_count"],
            "translation_files": documentation["translation_files"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated Skill composition SkillOpt gates")
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
                    sys.executable,
                    "-X",
                    "utf8",
                    "-m",
                    "unittest",
                    "tests.test_p26_skill_composition",
                    "tests.test_p25_skill_portability",
                    "tests.test_p24_frontier_skill_research",
                    "tests.test_p10_cycle_d_router_mcp",
                    "-v",
                ],
                cwd=PLUGIN,
                timeout=900,
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
