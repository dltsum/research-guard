from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from intent_router_core import route_prompt
from paper_audit_core import plan_paper_audit
from resource_guard import require_orchestrator_budget, require_start_headroom, run_managed


PLUGIN = Path(__file__).resolve().parents[1]
CONFIG = PLUGIN / "assets" / "p13-skillopt-config.json"
EVIDENCE = PLUGIN / "evals" / "p13-skillopt"
CASES = [
    ("Prove every theorem with Lean and check units with Pint", "formula_verification", "formal_math_lean"),
    ("Use SymPy for algebraic equivalence and Z3 for parameter constraints", "formula_verification", "formal_math_lean"),
    ("Numerically test equation limits, overflow, and boundary cases", "formula_verification", "formal_math_lean"),
    ("Calibrate the paper audit against public OpenReview reviews", "paper_audit", "openreview_calibration"),
    ("Audit scientific image integrity and duplicate image regions", "academic_figure", "scientific_image_integrity"),
    ("Check equations, OpenReview calibration, and scientific image integrity", "formula_verification", "formal_math_lean"),
]
NEGATIVE = ["Check Z3 compression in this game", "Review my restaurant photos", "Plan a weekend picnic"]


def _score(priorities: dict[str, int]) -> tuple[float, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    total = 0.0
    for prompt, module, role in CASES:
        routed = route_prompt(prompt, priority_overrides=priorities)
        with __import__("tempfile").TemporaryDirectory() as temporary:
            plan = plan_paper_audit(temporary, prompt)
        passed = module in routed["selected_modules"] and role in plan["selected_roles"] and len(routed["selected_modules"]) <= 3 and len(plan["selected_roles"]) <= 3
        primary = routed["primary_module"] == module
        score = float(passed) + 0.25 * float(primary)
        total += score
        rows.append({"prompt": prompt, "module": module, "role": role, "selected_modules": routed["selected_modules"], "selected_roles": plan["selected_roles"], "passed": passed, "primary": primary})
    negatives = []
    for prompt in NEGATIVE:
        routed = route_prompt(prompt, priority_overrides=priorities)
        false_positive = any(module in routed["selected_modules"] for module in ("formula_verification", "academic_figure", "paper_audit"))
        total -= float(false_positive)
        negatives.append({"prompt": prompt, "selected": routed["selected_modules"], "passed": not false_positive})
    return total / len(CASES), rows + negatives


def _worker(round_index: int, baseline: float, output: Path) -> int:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=20260814 + round_index))

    def objective(trial: Any) -> float:
        value, _ = _score({
            "formula_verification": trial.suggest_int("formula_verification", 91, 102),
            "academic_figure": trial.suggest_int("academic_figure", 84, 96),
            "paper_audit": trial.suggest_int("paper_audit", 80, 92),
        })
        return value

    study.optimize(objective, n_trials=12, show_progress_bar=False)
    priorities = {key: int(value) for key, value in study.best_params.items()}
    score, cases = _score(priorities)
    record = {
        "round": round_index, "optimizer": "optuna.tpe", "trials": len(study.trials),
        "input_baseline": baseline, "objective": score, "priorities": priorities,
        "cases": cases, "hard_gates_optimized": False,
        "accepted": score >= baseline and all(row["passed"] for row in cases),
        "trial_evidence": [{"number": trial.number, "parameters": trial.params, "objective": trial.value, "selected": trial.number == study.best_trial.number} for trial in study.trials],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=4, choices=(3, 4, 5))
    parser.add_argument("--worker-round", type=int)
    parser.add_argument("--baseline", type=float)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.worker_round is not None:
        return _worker(arguments.worker_round, float(arguments.baseline), arguments.output)
    require_start_headroom()
    require_orchestrator_budget()
    current = json.loads(CONFIG.read_text(encoding="utf-8"))
    priorities = dict(current["routing_priorities"])
    baseline, baseline_cases = _score(priorities)
    rounds = []
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for index in range(1, arguments.rounds + 1):
        output = EVIDENCE / f"round-{index:02d}.json"
        completed = run_managed(
            [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--worker-round", str(index), "--baseline", repr(baseline), "--output", str(output)],
            cwd=PLUGIN, timeout=300,
        )
        if completed.returncode != 0 or not output.is_file():
            raise RuntimeError(f"P13 SkillOpt round {index} failed: {(completed.stderr or completed.stdout)[-2000:]}")
        record = json.loads(output.read_text(encoding="utf-8"))
        record["resource_usage"] = completed.resource_usage
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rounds.append(record)
        if record["accepted"] and record["objective"] >= baseline:
            priorities, baseline = record["priorities"], record["objective"]
    final = {**current, "routing_priorities": priorities}
    CONFIG.write_text(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {
        "status": "PASS" if len(rounds) == arguments.rounds and all(record["accepted"] for record in rounds) else "FAIL",
        "round_count": len(rounds), "initial_objective": _score(current["routing_priorities"])[0],
        "final_objective": baseline, "baseline_cases": baseline_cases, "selected_config": final,
        "rounds": [{"round": item["round"], "objective": item["objective"], "accepted": item["accepted"], "trials": item["trials"]} for item in rounds],
    }
    report["report_sha256"] = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (EVIDENCE / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
