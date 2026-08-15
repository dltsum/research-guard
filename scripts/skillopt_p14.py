from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from intent_router_core import route_prompt
from resource_guard import require_orchestrator_budget, require_start_headroom, run_managed


PLUGIN = Path(__file__).resolve().parents[1]
CONFIG = PLUGIN / "assets" / "p14-skillopt-config.json"
EVIDENCE = PLUGIN / "evals" / "p14-skillopt"
CASES = [
    {
        "prompt": "Analyze a historical studies research method before the literature search",
        "required": ["discipline_profile"], "primary": "discipline_profile",
    },
    {
        "prompt": "Initialize field knowledge for an unregistered academic discipline",
        "required": ["discipline_profile"], "primary": "discipline_profile",
    },
    {
        "prompt": "我想深入研究历史学，先分析学科支持再查文献",
        "required": ["discipline_profile", "citation_literature"], "primary": "citation_literature",
    },
    {
        "prompt": "Search current literature for a philosophy research paper",
        "required": ["discipline_profile", "citation_literature"], "primary": "citation_literature",
    },
    {
        "prompt": "Deep dive into a specialized neural compression research method",
        "required": ["domain_skill"], "primary": "domain_skill",
    },
    {
        "prompt": "Design an experiment for an unregistered discipline and assess its literature",
        "required": ["discipline_profile", "citation_literature", "research_strategy"], "primary": "citation_literature",
    },
]
NEGATIVE = [
    "I like history games",
    "Write a family history story",
    "Initialize domain knowledge for a database service",
    "Plan a weekend museum visit",
    "历史游戏里哪个角色最好",
]


def _score(priorities: dict[str, int]) -> tuple[float, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    total = 0.0
    for case in CASES:
        routed = route_prompt(case["prompt"], priority_overrides=priorities)
        selected = routed["selected_modules"]
        required = case["required"]
        passed = all(module in selected for module in required) and len(selected) <= 3
        primary = routed["primary_module"] == case["primary"]
        total += float(passed) + 0.25 * float(primary)
        rows.append({
            **case, "selected_modules": selected, "passed": passed, "primary_passed": primary,
            "suppressed": routed["suppressed"],
        })
    for prompt in NEGATIVE:
        routed = route_prompt(prompt, priority_overrides=priorities)
        false_positive = "discipline_profile" in routed["selected_modules"]
        total -= float(false_positive)
        rows.append({"prompt": prompt, "selected_modules": routed["selected_modules"], "passed": not false_positive})
    return total / len(CASES), rows


def _worker(round_index: int, baseline: float, current_priorities: dict[str, int], output: Path) -> int:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        direction="maximize", sampler=optuna.samplers.TPESampler(seed=20260815 + round_index),
    )
    study.enqueue_trial(current_priorities)

    def objective(trial: Any) -> float:
        value, _ = _score({
            "citation_literature": trial.suggest_int("citation_literature", 76, 84),
            "discipline_profile": trial.suggest_int("discipline_profile", 76, 90),
            "domain_skill": trial.suggest_int("domain_skill", 70, 78),
            "research_strategy": trial.suggest_int("research_strategy", 66, 74),
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
        "trial_evidence": [
            {
                "number": trial.number, "parameters": trial.params, "objective": trial.value,
                "selected": trial.number == study.best_trial.number,
            }
            for trial in study.trials
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=4, choices=(3, 4, 5))
    parser.add_argument("--worker-round", type=int)
    parser.add_argument("--baseline", type=float)
    parser.add_argument("--current-priorities", type=json.loads)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.worker_round is not None:
        return _worker(
            arguments.worker_round, float(arguments.baseline),
            {str(key): int(value) for key, value in arguments.current_priorities.items()}, arguments.output,
        )
    require_start_headroom()
    require_orchestrator_budget()
    current = json.loads(CONFIG.read_text(encoding="utf-8"))
    priorities = dict(current["routing_priorities"])
    initial_objective, baseline_cases = _score(priorities)
    baseline = initial_objective
    rounds = []
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for index in range(1, arguments.rounds + 1):
        output = EVIDENCE / f"round-{index:02d}.json"
        completed = run_managed(
            [
                sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
                "--worker-round", str(index), "--baseline", repr(baseline),
                "--current-priorities", json.dumps(priorities, separators=(",", ":")),
                "--output", str(output),
            ],
            cwd=PLUGIN, timeout=300,
        )
        if completed.returncode != 0 or not output.is_file():
            raise RuntimeError(f"P14 SkillOpt round {index} failed: {(completed.stderr or completed.stdout)[-2000:]}")
        record = json.loads(output.read_text(encoding="utf-8"))
        record["resource_usage"] = completed.resource_usage
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rounds.append(record)
        if record["accepted"] and record["objective"] >= baseline:
            priorities, baseline = record["priorities"], record["objective"]
    selected = {**current, "routing_priorities": priorities}
    CONFIG.write_text(json.dumps(selected, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {
        "status": "PASS" if len(rounds) == arguments.rounds and all(item["accepted"] for item in rounds) else "FAIL",
        "round_count": len(rounds), "initial_objective": initial_objective,
        "final_objective": baseline, "baseline_cases": baseline_cases, "selected_config": selected,
        "rounds": [
            {"round": item["round"], "objective": item["objective"], "accepted": item["accepted"], "trials": item["trials"]}
            for item in rounds
        ],
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
