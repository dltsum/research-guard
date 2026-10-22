from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from research_integrity_core import _score_review_candidates
from network_config_core import network_environment
from skillopt_runner import create_run_root, run_command, run_regression, write_report


PLUGIN = Path(__file__).resolve().parents[1]
CONFIG_PATH = PLUGIN / "assets" / "p12-skillopt-config.json"
EVIDENCE_ROOT = PLUGIN / "evals" / "p12-skillopt"

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


def _review_score(cases: list[dict[str, Any]], smoothing: float, prior_weight: float) -> tuple[float, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    total = 0.0
    for case in cases:
        ranking = _score_review_candidates(case["records"], smoothing=smoothing, prior_weight=prior_weight)
        probabilities = {item["record_id"]: float(item["priority_probability"]) for item in ranking}
        labels = case["labels"]
        positive = [probabilities[key] for key, value in labels.items() if value == 1.0]
        negative = [probabilities[key] for key, value in labels.items() if value == 0.0]
        pair_correct = bool(positive and negative and min(positive) > max(negative))
        brier = sum((probabilities[key] - expected) ** 2 for key, expected in labels.items()) / len(labels)
        score = 0.5 * float(pair_correct) + 0.5 * (1.0 - brier)
        total += score
        rows.append({"probabilities": probabilities, "pair_correct": pair_correct, "brier": brier, "score": score})
    return total / max(1, len(cases)), rows


def _objective(active_review: dict[str, float]) -> tuple[float, dict[str, float]]:
    train, _ = _review_score(REVIEW_TRAIN, **active_review)
    validation, _ = _review_score(REVIEW_VALIDATION, **active_review)
    return 0.5 * train + 0.5 * validation, {"train_review": train, "validation_review": validation}


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _worker(round_index: int, baseline: float, output: Path) -> int:
    optuna = importlib.import_module("optuna")
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        direction="maximize", sampler=optuna.samplers.TPESampler(seed=20260813 + round_index),
    )

    def objective(trial: Any) -> float:
        value, _ = _objective({
            "smoothing": trial.suggest_float("smoothing", 0.25, 3.0, log=True),
            "prior_weight": trial.suggest_float("prior_weight", 0.0, 2.0),
        })
        return value

    study.optimize(objective, n_trials=18, show_progress_bar=False)
    active_review = {key: float(value) for key, value in study.best_params.items()}
    heldout_score, heldout = _review_score(REVIEW_HELDOUT, **active_review)
    record = {
        "round": round_index,
        "optimizer": "optuna.tpe",
        "trials": len(study.trials),
        "input_baseline": baseline,
        "objective": float(study.best_value),
        "configuration": {"active_review": active_review},
        "review_heldout_score": heldout_score,
        "review_heldout": heldout,
        "candidate_gate_passed": float(study.best_value) >= baseline - 1e-12 and all(row["pair_correct"] for row in heldout),
        "automatic_semantic_routing": False,
    }
    _atomic_json(output, record)
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
        and all(all(case["pair_correct"] for case in item["review_heldout"]) for item in rounds)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Optimize human-only systematic-review prioritization; never semantic routing")
    parser.add_argument("--rounds", type=int, default=1, help="Actual optimization rounds; default: 1")
    parser.add_argument("--output-root", type=Path, default=EVIDENCE_ROOT)
    parser.add_argument("--apply-config", action="store_true", help="Write an accepted configuration back after the real regression passes")
    parser.add_argument("--worker-round", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--baseline", type=float, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--no-resume", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds must be positive")
    if args.worker_round is not None:
        if args.baseline is None or args.output is None:
            parser.error("--worker-round requires --baseline and --output")
        return _worker(args.worker_round, args.baseline, args.output)
    current = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    chosen = {key: float(value) for key, value in current["active_review"].items()}
    baseline, baseline_metrics = _objective(chosen)
    best = baseline
    rounds = []
    run_root = create_run_root(args.output_root)
    for index in range(1, args.rounds + 1):
        worker_path = run_root / f".round-{index:02d}-worker.json"
        optimizer = run_command([
            sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
            "--worker-round", str(index), "--baseline", repr(best), "--output", str(worker_path),
        ], cwd=PLUGIN, run_root=run_root, prefix=f"round-{index:02d}-optimizer", timeout=600)
        if optimizer["status"] != "PASS" or not worker_path.is_file():
            rounds.append({"round": index, "optimizer_execution": optimizer, "accepted": False,
                           "candidate_gate_passed": False, "review_heldout": [],
                           "regression": {"status": "NOT_RUN"}})
            break
        record = json.loads(worker_path.read_text(encoding="utf-8"))
        worker_path.unlink()
        candidate = {**current, "active_review": record["configuration"]["active_review"]}
        candidate_path = run_root / f"candidate-config-{index:02d}.json"
        _atomic_json(candidate_path, candidate)
        child_environment = network_environment()
        child_environment["RESEARCH_GUARD_SKILLOPT_CONFIG"] = str(candidate_path)
        record["regression"] = run_regression(
            ["discover", "-s", "tests", "-p", "test_p12_*.py"],
            cwd=PLUGIN, run_root=run_root, prefix=f"round-{index:02d}-regression",
            timeout=900, env=child_environment,
        )
        record["accepted"] = bool(record["candidate_gate_passed"] and record["regression"]["status"] == "PASS")
        record["optimizer_execution"] = optimizer
        record["candidate_config"] = str(candidate_path)
        rounds.append(record)
        if record["regression"]["status"] != "PASS":
            break
        if record["accepted"]:
            best = record["objective"]
            chosen = record["configuration"]["active_review"]
    report = {
        "schema_version": 3,
        "status": "PASS" if _rounds_pass_gate(rounds, args.rounds, best, baseline) else "FAIL",
        "round_count": len(rounds),
        "requested_rounds": args.rounds,
        "baseline_objective": baseline,
        "baseline_metrics": baseline_metrics,
        "selected_active_review": chosen,
        "automatic_semantic_routing": False,
        "evidence_scope": "Synthetic review-prioritization fixtures; no live literature decisions or scientific-efficacy claim.",
        "rounds": rounds,
    }
    report["configuration_applied"] = bool(args.apply_config and report["status"] == "PASS")
    if report["configuration_applied"]:
        current["active_review"] = chosen
        _atomic_json(CONFIG_PATH, current)
    return write_report(report, run_root)


if __name__ == "__main__":
    raise SystemExit(main())
