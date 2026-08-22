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
EVIDENCE = PLUGIN / "evals" / "instruction-numerical-skillopt"
CONTRACT_FILES = (
    "assets/instruction-adherence-policy.json",
    "assets/resource-policy.json",
    "scripts/instruction_adherence_core.py",
    "scripts/constructive_numerical_core.py",
    "scripts/constructive_numerical_worker.py",
    "scripts/paper_audit_core.py",
    "scripts/mcp_server.py",
    "hooks/guard_hook.py",
    "SKILL.md",
    "docs/ARCHITECTURE.md",
    "docs/INSTRUCTION_AND_NUMERICAL_CONTRACT.md",
    "docs/INSTRUCTION_AND_NUMERICAL_CONTRACT.zh-CN.md",
    "tests/test_p22_instruction_adherence.py",
    "tests/test_p22_constructive_numerical.py",
)


def _static_contract() -> dict[str, Any]:
    texts = {name: (PLUGIN / name).read_text(encoding="utf-8") for name in CONTRACT_FILES}
    policy = json.loads(texts["assets/instruction-adherence-policy.json"])
    resource = json.loads(texts["assets/resource-policy.json"])
    from mcp_server import TOOLS

    design = next(item for item in TOOLS if item["name"] == "research_design")
    audit = next(item for item in TOOLS if item["name"] == "paper_audit")
    design_properties = design["inputSchema"]["properties"]
    audit_properties = audit["inputSchema"]["properties"]
    combined = "\n".join(texts.values())
    documentation = validate_documentation(PLUGIN)
    pair_ids = {item["id"] for item in documentation["pairs"]}
    checks = {
        "canonical subroutes preserve the 17-tool surface": len(TOOLS) == 17
        and "instruction_action" in design_properties
        and "numerical_action" in audit_properties,
        "main-agent semantic intake replaces automatic classification":
        policy.get("activation") == "main_agent_semantic_multistep_selection"
        and "instruction_selected_by" in design_properties
        and "selection_rationale" in combined,
        "atomic requirements bind acceptance dependencies evidence and substitutions":
        all(token in texts["scripts/instruction_adherence_core.py"] for token in (
            "acceptance_criteria", "depends_on", "required_evidence_kinds",
            "forbidden_substitutions", "request_sha256",
        )),
        "completion and stop are fail closed": all(
            token in combined for token in (
                "completion_claim_allowed", "ACTION_REQUIRED",
                "USER_DECISION_REQUIRED", "blocked_handoff_only",
            )
        ) and "instruction_adherence_status" in texts["hooks/guard_hook.py"],
        "waivers are user selected and evidence drift is rechecked":
        "selected_by != \"user\"" in texts["scripts/instruction_adherence_core.py"]
        and "evidence_invalid" in texts["scripts/instruction_adherence_core.py"],
        "constructive audit uses Pint SymPy Z3 and exact rational recheck": all(
            token in texts["scripts/constructive_numerical_worker.py"] for token in (
                "pint", "sympy", "z3", "Fraction", "exact_rational_anchor_recheck",
                "marginal_projection_subject_to_all_registered_constraints",
                "joint_anchors",
            )
        ),
        "unsupported nonlinear and affine paths fail explicitly": all(
            token in texts["scripts/constructive_numerical_worker.py"] for token in (
                "unsupported", "offset", "zero coefficient", "unused",
            )
        ),
        "joint anchors are complete and not Cartesian interval claims":
        "complete assignment" in combined
        and "not a Cartesian-product guarantee" in combined
        and "binary64" in combined,
        "paper audit owns role coverage and receipt drift":
        "constructive_numerical" in texts["scripts/paper_audit_core.py"]
        and "methodology_statistics" in texts["scripts/paper_audit_core.py"]
        and "constructive numerical receipt" in texts["scripts/paper_audit_core.py"].casefold(),
        "resource contract stays serial CPU and below or equal to 512 MiB":
        resource.get("owned_task_budget_bytes") == 512 * 1024 * 1024
        and resource.get("maximum_parallel_workers") == 1
        and resource.get("gpu_allowed") is False,
        "bilingual operator contract is registered and current":
        documentation["status"] == "PASS"
        and "instruction-and-numerical" in pair_ids,
    }
    candidates = [
        {"candidate": "prompt-only reminders for agent obedience", "decision": "REJECT"},
        {"candidate": "automatic keyword or small-model instruction intake", "decision": "REJECT"},
        {"candidate": "a second top-level MCP tool for each feature", "decision": "REJECT"},
        {"candidate": "floating-point heuristic feasibility and clipping", "decision": "REJECT"},
        {"candidate": "Cartesian products of marginal ranges as anchors", "decision": "REJECT"},
        {"candidate": "claim nonlinear systems are certified by a linear core", "decision": "REJECT"},
        {
            "candidate": "typed append-only instruction ledger plus exact unit-aware linear construction under canonical owners",
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
    parser = argparse.ArgumentParser(
        description="Run repeated instruction-adherence and constructive-numerical SkillOpt gates"
    )
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
                    sys.executable, "-X", "utf8", "-m", "unittest", "discover",
                    "-s", "tests", "-p", "test_p22_*.py", "-v",
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
