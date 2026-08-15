from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from intent_router_core import route_prompt
from research_integrity_core import _score_review_candidates
from resource_guard import require_orchestrator_budget, require_start_headroom, run_managed
from run_incremental_tests import run as run_incremental_tests


PLUGIN = Path(__file__).resolve().parents[1]
CONFIG_PATH = PLUGIN / "assets" / "p12-skillopt-config.json"
EVIDENCE_ROOT = PLUGIN / "evals" / "p12-skillopt"

TRAIN = [
    ("Parse this PDF into structured sections and formulas", "structured_evidence"),
    ("Build a claim-evidence graph with support and refutation", "structured_evidence"),
    ("Parse this paper into a claim-evidence graph and audit statistical consistency", "structured_evidence"),
    ("Preregister this analysis and freeze the stopping rule", "research_integrity"),
    ("Recompute the reported p-values for statistical consistency", "research_integrity"),
    ("Run a resource-bounded computational reproducibility check", "research_integrity"),
    ("Audit statistical consistency and then review the manuscript", "research_integrity"),
    ("Prioritize this active-learning systematic review ledger", "research_artifact"),
]
VALIDATION = [
    ("Ingest the manuscript and audit its claim evidence", "structured_evidence"),
    ("Extract exact paper locators and monitor its DOI for retraction", "structured_evidence"),
    ("Monitor this DOI for a retraction or expression of concern", "research_integrity"),
    ("Check computational reproducibility and review the paper", "research_integrity"),
    ("Audit this manuscript and references", "paper_audit"),
    ("Develop a research hypothesis and experiment design", "research_strategy"),
]
HELDOUT = [
    ("Extract this paper with exact page locators", "structured_evidence"),
    ("Build a support/refute evidence graph and recompute every p-value", "structured_evidence"),
    ("Record a preregistration deviation and rerun the experiment", "research_integrity"),
    ("Monitor retractions while auditing the manuscript", "research_integrity"),
    ("Create a statistical research plot", "academic_figure"),
    ("Write an ordinary product announcement", None),
]

REVIEW_TRAIN = [{
    "records": [
        {"record_id": "i1", "title": "Randomized treatment improves survival", "abstract": "causal treatment survival", "decision": "include"},
        {"record_id": "i2", "title": "Causal intervention benefit", "abstract": "randomized treatment effect", "decision": "include"},
        {"record_id": "e1", "title": "Historical policy essay", "abstract": "qualitative archival narrative", "decision": "exclude"},
        {"record_id": "e2", "title": "Editorial history", "abstract": "archival qualitative commentary", "decision": "exclude"},
        {"record_id": "p", "title": "Randomized survival intervention", "abstract": "causal treatment benefit"},
        {"record_id": "n", "title": "Historical editorial narrative", "abstract": "qualitative archival essay"},
    ],
    "labels": {"p": 1.0, "n": 0.0},
}]
REVIEW_VALIDATION = [{
    "records": [
        {"record_id": "i1", "title": "Graph neural model", "abstract": "message passing benchmark", "decision": "include"},
        {"record_id": "e1", "title": "Rule based index", "abstract": "manual heuristic taxonomy", "decision": "exclude"},
        {"record_id": "e2", "title": "Manual classification", "abstract": "rule based heuristic", "decision": "exclude"},
        {"record_id": "p", "title": "Neural message passing", "abstract": "graph benchmark model"},
        {"record_id": "n", "title": "Manual rule taxonomy", "abstract": "heuristic classification"},
    ],
    "labels": {"p": 1.0, "n": 0.0},
}]
REVIEW_HELDOUT = [{
    "records": [
        {"record_id": "i1", "title": "Prospective clinical trial", "abstract": "registered intervention outcome", "decision": "include"},
        {"record_id": "e1", "title": "Opinion article", "abstract": "unregistered commentary", "decision": "exclude"},
        {"record_id": "p", "title": "Registered prospective intervention", "abstract": "clinical trial outcome"},
        {"record_id": "n", "title": "Unregistered opinion commentary", "abstract": "editorial article"},
    ],
    "labels": {"p": 1.0, "n": 0.0},
}]


def _routing_score(cases: list[tuple[str, str | None]], priorities: dict[str, int]) -> tuple[float, list[dict[str, Any]]]:
    results = []
    total = 0.0
    for prompt, expected in cases:
        routed = route_prompt(prompt, priority_overrides=priorities)
        selected = routed["selected_modules"]
        passed = (expected in selected) if expected else routed["status"] == "NO_RESEARCH_MODULE"
        primary = routed["primary_module"] == expected if expected else passed
        budget = len(selected) <= 3
        instruction_chars = sum(len(value) for value in routed["instructions"])
        value = (1.0 if passed else 0.0) + (0.5 if primary else 0.0) + (0.25 if budget else -5.0)
        total += value
        results.append({
            "prompt": prompt, "expected": expected, "selected": selected,
            "primary": routed["primary_module"], "passed": passed and primary and budget,
            "estimated_instruction_tokens": (instruction_chars + 3) // 4,
        })
    return total / max(1, len(cases)), results


def _review_score(cases: list[dict[str, Any]], smoothing: float, prior_weight: float) -> tuple[float, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    total = 0.0
    for case in cases:
        ranking = _score_review_candidates(case["records"], smoothing=smoothing, prior_weight=prior_weight)
        probabilities = {item["record_id"]: float(item["priority_probability"]) for item in ranking}
        labels = case["labels"]
        positive = [probabilities[key] for key, value in labels.items() if value == 1.0]
        negative = [probabilities[key] for key, value in labels.items() if value == 0.0]
        pair_correct = bool(positive and negative and min(positive) > max(negative))
        brier = sum((probabilities[key] - expected) ** 2 for key, expected in labels.items()) / len(labels)
        case_score = 0.5 * float(pair_correct) + 0.5 * (1.0 - brier)
        total += case_score
        results.append({"probabilities": probabilities, "pair_correct": pair_correct, "brier": brier, "score": case_score})
    return total / max(1, len(cases)), results


def _objective_value(priorities: dict[str, int], active_review: dict[str, float]) -> tuple[float, dict[str, float]]:
    train_routing, train_results = _routing_score(TRAIN, priorities)
    validation_routing, validation_results = _routing_score(VALIDATION, priorities)
    train_review, _ = _review_score(REVIEW_TRAIN, **active_review)
    validation_review, _ = _review_score(REVIEW_VALIDATION, **active_review)
    instruction_tokens = sum(
        item["estimated_instruction_tokens"] for item in train_results + validation_results
    ) / max(1, len(train_results) + len(validation_results))
    prompt_cost = instruction_tokens / 10_000
    objective = 0.5 * train_routing + 0.3 * validation_routing + 0.1 * train_review + 0.1 * validation_review - prompt_cost
    return objective, {
        "train_routing": train_routing, "validation_routing": validation_routing,
        "train_review": train_review, "validation_review": validation_review,
        "mean_estimated_instruction_tokens": instruction_tokens, "prompt_cost": prompt_cost,
    }


def _optimize_round(round_index: int, baseline: float, optuna: Any) -> dict[str, Any]:
    sampler = optuna.samplers.TPESampler(seed=20260813 + round_index)
    study = optuna.create_study(direction="maximize", sampler=sampler)

    def objective(trial: Any) -> float:
        priorities = {
            "structured_evidence": trial.suggest_int("structured_evidence_priority", 86, 100),
            "research_integrity": trial.suggest_int("research_integrity_priority", 82, 98),
        }
        active_review = {
            "smoothing": trial.suggest_float("active_review_smoothing", 0.25, 3.0, log=True),
            "prior_weight": trial.suggest_float("active_review_prior_weight", 0.0, 2.0),
        }
        value, _ = _objective_value(priorities, active_review)
        return value

    study.optimize(objective, n_trials=18, show_progress_bar=False)
    priorities = {
        "structured_evidence": int(study.best_params["structured_evidence_priority"]),
        "research_integrity": int(study.best_params["research_integrity_priority"]),
    }
    active_review = {
        "smoothing": float(study.best_params["active_review_smoothing"]),
        "prior_weight": float(study.best_params["active_review_prior_weight"]),
    }
    train_score, train_results = _routing_score(TRAIN, priorities)
    validation_score, validation_results = _routing_score(VALIDATION, priorities)
    heldout_score, heldout_results = _routing_score(HELDOUT, priorities)
    review_train_score, review_train = _review_score(REVIEW_TRAIN, **active_review)
    review_validation_score, review_validation = _review_score(REVIEW_VALIDATION, **active_review)
    review_heldout_score, review_heldout = _review_score(REVIEW_HELDOUT, **active_review)
    all_train = all(item["passed"] for item in train_results)
    all_validation = all(item["passed"] for item in validation_results)
    all_heldout = all(item["passed"] for item in heldout_results)
    candidate_gate_passed = (
        float(study.best_value) >= baseline - 1e-12
        and all_train and all_validation and all_heldout
        and all(item["pair_correct"] for item in review_heldout)
    )
    trial_evidence = []
    for trial in study.trials:
        selected = trial.number == study.best_trial.number
        if selected:
            reason = "round objective winner"
        elif trial.value is None:
            reason = "trial did not produce an objective value"
        elif float(trial.value) < float(study.best_value):
            reason = "objective below the round winner"
        else:
            reason = "objective tied the round winner; deterministic study order selected another trial"
        trial_evidence.append({
            "trial_number": trial.number, "state": trial.state.name,
            "parameters": trial.params, "objective": trial.value,
            "decision": "selected_for_heldout" if selected else "rejected",
            "reason": reason,
        })
    return {
        "round": round_index, "optimizer": "optuna.tpe", "trials": len(study.trials),
        "configuration": {"routing_priorities": priorities, "active_review": active_review}, "objective": float(study.best_value),
        "train_score": train_score, "validation_score": validation_score, "heldout_score": heldout_score,
        "train": train_results, "validation": validation_results, "heldout": heldout_results,
        "review_scores": {"train": review_train_score, "validation": review_validation_score, "heldout": review_heldout_score},
        "review_train": review_train, "review_validation": review_validation, "review_heldout": review_heldout,
        "candidate_gate_passed": candidate_gate_passed,
        "candidate_decision": (
            "pending incremental regression" if candidate_gate_passed
            else "rejected: baseline, train, validation, held-out, or active-review gate failed"
        ),
        "trials_evidence": trial_evidence,
        "rejected_trials": sum(trial.number != study.best_trial.number for trial in study.trials),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _contract_hash() -> str:
    records = []
    for relative in (
        "scripts/skillopt_p12.py", "scripts/intent_router_core.py",
        "scripts/research_integrity_core.py", "scripts/resource_guard.py",
        "scripts/run_incremental_tests.py", "assets/resource-policy.json",
        "assets/p12-skillopt-config.json",
    ):
        path = PLUGIN / relative
        records.append((relative, _sha256(path)))
    for path in sorted((PLUGIN / "tests").glob("test_p12_*.py")):
        records.append((path.relative_to(PLUGIN).as_posix(), _sha256(path)))
    return hashlib.sha256(json.dumps(records, separators=(",", ":")).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _worker(round_index: int, baseline: float, output: Path) -> int:
    require_start_headroom()
    optuna = importlib.import_module("optuna")
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    record = _optimize_round(round_index, baseline, optuna)
    record["contract_hash"] = _contract_hash()
    record["input_baseline"] = baseline
    _atomic_json(output, record)
    print(json.dumps({"status": "ROUND_CANDIDATE_READY", "round": round_index, "output": str(output)}))
    return 0


def _rounds_pass_gate(rounds: list[dict[str, Any]], expected_rounds: int, best: float, baseline: float) -> bool:
    return bool(
        len(rounds) == expected_rounds
        and best >= baseline - 1e-12
        and all(item.get("regression", {}).get("status") == "PASS" for item in rounds)
        and all(
            bool(item.get("accepted"))
            == bool(item.get("candidate_gate_passed") and item.get("regression", {}).get("status") == "PASS")
            for item in rounds
        )
        and all(all(case["passed"] for case in item["train"]) for item in rounds)
        and all(all(case["passed"] for case in item["validation"]) for item in rounds)
        and all(all(case["passed"] for case in item["heldout"]) for item in rounds)
        and all(all(case["pair_correct"] for case in item["review_heldout"]) for item in rounds)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=4, choices=(3, 4, 5))
    parser.add_argument("--worker-round", type=int)
    parser.add_argument("--baseline", type=float)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    if args.worker_round is not None:
        if args.baseline is None or args.output is None:
            parser.error("--worker-round requires --baseline and --output")
        return _worker(args.worker_round, args.baseline, args.output)
    require_start_headroom()
    require_orchestrator_budget()
    current = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    baseline_priorities = dict(current["routing_priorities"])
    baseline_active_review = {key: float(value) for key, value in current["active_review"].items()}
    baseline, baseline_metrics = _objective_value(baseline_priorities, baseline_active_review)
    rounds = []
    best = baseline
    chosen_priorities = baseline_priorities
    chosen_active_review = baseline_active_review
    contract_hash = _contract_hash()
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    for round_index in range(1, args.rounds + 1):
        require_orchestrator_budget()
        round_path = EVIDENCE_ROOT / f"round-{round_index:02d}.json"
        record = None
        if not args.no_resume and round_path.is_file():
            try:
                existing = json.loads(round_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = {}
            if (
                existing.get("contract_hash") == contract_hash
                and abs(float(existing.get("input_baseline", float("nan"))) - best) <= 1e-12
                and existing.get("regression", {}).get("status") == "PASS"
            ):
                record = existing
        if record is None:
            worker_output = EVIDENCE_ROOT / f".round-{round_index:02d}-worker.json"
            try:
                completed = run_managed(
                    [
                        sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
                        "--worker-round", str(round_index), "--baseline", repr(best),
                        "--output", str(worker_output),
                    ],
                    cwd=PLUGIN, timeout=600,
                )
                if completed.returncode != 0 or not worker_output.is_file():
                    raise RuntimeError(
                        f"SkillOpt round {round_index} worker failed: "
                        + (completed.stderr or completed.stdout)[-4000:]
                    )
                record = json.loads(worker_output.read_text(encoding="utf-8"))
            finally:
                if worker_output.exists():
                    worker_output.unlink()
            candidate_path = EVIDENCE_ROOT / f"candidate-config-{round_index:02d}.json"
            candidate_config = {
                **current,
                "routing_priorities": record["configuration"]["routing_priorities"],
                "active_review": record["configuration"]["active_review"],
            }
            _atomic_json(candidate_path, candidate_config)
            candidate_hash = _sha256(candidate_path)
            regression = run_incremental_tests(
                ["test_p12_*.py"], f"p12-skillopt-round-{round_index}",
                resume=not args.no_resume,
                env={
                    **os.environ,
                    "RESEARCH_GUARD_SKILLOPT_CONFIG": str(candidate_path),
                    "RESEARCH_GUARD_SKILLOPT_CONFIG_SHA256": candidate_hash,
                },
                extra_contract={"candidate_config": candidate_hash},
            )
            record["candidate_config"] = {
                "path": candidate_path.relative_to(PLUGIN).as_posix(),
                "sha256": candidate_hash,
            }
            record["regression"] = regression
            record["accepted"] = bool(record["candidate_gate_passed"] and regression["status"] == "PASS")
            record["candidate_decision"] = (
                "accepted" if record["accepted"]
                else "rejected: candidate or incremental regression gate failed"
            )
            _atomic_json(round_path, record)
        rounds.append(record)
        if record["accepted"]:
            best = record["objective"]
            chosen_priorities = record["configuration"]["routing_priorities"]
            chosen_active_review = record["configuration"]["active_review"]
    report = {
        "schema_version": 1, "round_count": args.rounds, "trials_per_round": 18,
        "baseline_objective": baseline, "baseline_metrics": baseline_metrics,
        "rounds": rounds, "selected_routing_priorities": chosen_priorities,
        "selected_active_review": chosen_active_review,
        "hard_constraints_unchanged": current["hard_constraints"],
        "status": "PASS" if _rounds_pass_gate(rounds, args.rounds, best, baseline) else "FAIL",
    }
    report_path = EVIDENCE_ROOT / "report.json"
    _atomic_json(report_path, report)
    if report["status"] == "PASS":
        current["routing_priorities"] = chosen_priorities
        current["active_review"] = chosen_active_review
        _atomic_json(CONFIG_PATH, current)
    print(json.dumps({
        "status": report["status"], "report": str(report_path),
        "selected_routing": chosen_priorities, "selected_active_review": chosen_active_review,
    }, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
