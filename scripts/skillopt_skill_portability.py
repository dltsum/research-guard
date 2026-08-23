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
EVIDENCE = PLUGIN / "evals" / "p25-skill-portability-skillopt"
CONTRACT_FILES = (
    "assets/research-repositories/registry.json",
    "assets/resource-policy.json",
    "scripts/frontier_skill_research_core.py",
    "scripts/skill_portability_core.py",
    "scripts/mcp_server.py",
    "skills/research-design-guard/SKILL.md",
    "skills/research-design-guard/references/extended-research-contracts.md",
    "docs/ARCHITECTURE.md",
    "docs/SKILL_PORTABILITY.md",
    "docs/SKILL_PORTABILITY.zh-CN.md",
    "README.md",
    "README.zh-CN.md",
    "tests/test_p25_skill_portability.py",
)


def _static_contract() -> dict[str, Any]:
    texts = {name: (PLUGIN / name).read_text(encoding="utf-8") for name in CONTRACT_FILES}
    combined = "\n".join(texts.values())
    core = texts["scripts/skill_portability_core.py"]
    frontier = texts["scripts/frontier_skill_research_core.py"]
    registry = json.loads(texts["assets/research-repositories/registry.json"])
    resource = json.loads(texts["assets/resource-policy.json"])
    documentation = validate_documentation(PLUGIN)
    pair_ids = {item["id"] for item in documentation["pairs"]}
    repository_ids = {item["id"] for item in registry["repositories"]}
    from mcp_server import TOOLS

    design = next(item for item in TOOLS if item["name"] == "research_design")
    properties = design["inputSchema"]["properties"]
    classifications = {
        "POSITIVE_TRANSFER", "NO_MEASURED_GAIN", "NEGATIVE_TRANSFER", "SAFETY_REGRESSION",
    }
    checks = {
        "canonical research-design owner preserves 17 tools":
        len(TOOLS) == 17
        and properties.get("skill_portability_action", {}).get("enum")
        == ["plan", "record_source", "record_trial", "finalize", "status", "verify"],
        "exact finalized P24 artifact and owner handoff":
        "get_frontier_skill_portability_binding" in frontier
        and "source_binding must contain the exact P24 admission identity" in core
        and "frontier finalization hash changed" in core,
        "source splits cannot leak into portability cases":
        "portability cases overlap the source protocol train, validation, or heldout cases" in core
        and "occupied_case_ids_sha256" in core,
        "matrix count replication and actual variation are frozen":
        "replicates must be exactly 2 or 3" in core
        and "cells must be an array with 2..12 entries" in core
        and "portability cells must vary by model, harness, or task scope" in core,
        "coupled executions cannot masquerade as independent":
        "cells sharing a model family or executor group must share one evidence family" in core
        and '"executor_group": cell["executor_group"]' in core
        and '"executor_group": item["executor_group"]' in core
        and "scoped_claim_allowed and evidence_family_count >= 2" in core,
        "all four target-cell outcomes remain explicit":
        all(label in core for label in classifications)
        and "no cross-cell score average" in core,
        "no pre-final outcome leakage or universal claim":
        'summary["status"] = "RECORDED_NOT_EXPOSED"' in core
        and '"universal_claim_allowed": False' in core
        and "do not generalize beyond recorded cells" in core,
        "clickable primary and immutable repository sources are mandatory":
        "Skill portability sources require a clickable HTTPS URL" in core
        and "repository sources require an immutable 40-character commit" in core
        and "portability protocol lacks a primary-paper source" in core,
        "artifacts state ordering and replay are fail closed":
        "SKILL_PORTABILITY_STATE_INTEGRITY_FAILURE" in core
        and "Skill portability run hashes must be unique" in core
        and "Skill portability execution receipt hashes must be unique" in core
        and "Skill portability trials must follow frozen replicate order" in core,
        "the core records evidence but cannot execute apply or admit":
        '"execution_allowed_by_core": False' in core
        and '"apply_route_exposed": False' in core
        and "admission_effect" in core,
        "current portability implementations are pinned":
        {"skillopt", "skilllens", "workflow-localized-mechanism-learning"} <= repository_ids,
        "bilingual operator contract is registered and current":
        documentation["status"] == "PASS" and "skill-portability" in pair_ids,
        "resource contract remains serial CPU and at most 512 MiB":
        resource.get("owned_task_budget_bytes") == 512 * 1024 * 1024
        and resource.get("maximum_parallel_workers") == 1
        and resource.get("gpu_allowed") is False,
    }
    candidates = [
        {"candidate": "infer transfer from one target or repository popularity", "decision": "REJECT"},
        {"candidate": "pool target scores and hide one negative-transfer cell", "decision": "REJECT"},
        {"candidate": "label same-family or same-executor results independent", "decision": "REJECT"},
        {"candidate": "rerun or install third-party Skill code inside the portability core", "decision": "REJECT"},
        {
            "candidate": "exact P24 handoff plus disjoint per-cell paired artifacts and scoped claim boundary",
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
    parser = argparse.ArgumentParser(description="Run repeated Skill portability SkillOpt gates")
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
