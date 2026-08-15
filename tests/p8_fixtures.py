from __future__ import annotations

import csv
import sys
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))


def write_training_csv(root: Path, *, missing: bool = False) -> Path:
    path = root / "data" / "training.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ["step", "method", "seed", "score"],
        [1, "Baseline", 1, 0.51], [1, "Baseline", 2, 0.53],
        [2, "Baseline", 1, 0.57], [2, "Baseline", 2, 0.56],
        [1, "Method A", 1, 0.55], [1, "Method A", 2, 0.56],
        [2, "Method A", 1, 0.63], [2, "Method A", 2, "" if missing else 0.64],
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    return path


def statistical_spec(*, missing_policy: str = "error") -> dict:
    return {
        "kind": "statistical",
        "chart_type": "line",
        "data_file": "data/training.csv",
        "x": "step",
        "y": "score",
        "series": "method",
        "x_label": "Training step",
        "y_label": "Accuracy (fraction)",
        "claim": "Accuracy over the two registered training steps.",
        "alt_text": "Line plot of accuracy by training step for Baseline and Method A.",
        "missing_policy": missing_policy,
        "summary": {
            "estimator": "mean",
            "uncertainty": "sd",
            "replicate_unit": "independent seed",
            "seed": 20260812
        },
        "style": {"palette": "okabe_ito_on_white"}
    }


def diagram_spec() -> dict:
    return {
        "kind": "diagram",
        "claim": "A verifier returns failed results to the planner.",
        "alt_text": "Planner sends a task to Executor, which sends results to Verifier; failed verification returns to Planner.",
        "nodes": [
            {"id": "planner", "label": "Planner", "x": 0.18, "y": 0.5, "shape": "rounded"},
            {"id": "executor", "label": "Executor", "x": 0.50, "y": 0.5, "shape": "rounded"},
            {"id": "verifier", "label": "Verifier", "x": 0.82, "y": 0.5, "shape": "rounded"}
        ],
        "edges": [
            {"from": "planner", "to": "executor", "label": "task", "style": "solid"},
            {"from": "executor", "to": "verifier", "label": "result", "style": "solid"},
            {"from": "verifier", "to": "planner", "label": "revise", "style": "dashed", "curve": True}
        ],
        "style": {"palette": "okabe_ito_on_white"}
    }


def plan_statistical(root: Path) -> dict:
    from academic_figure_core import plan_academic_figure

    write_training_csv(root)
    return plan_academic_figure(
        root,
        figure_id="training",
        request_text="Create a publication line plot with uncertainty from raw seeded results.",
        figure_kind="statistical",
        source_files=["data/training.csv"],
        width_mm=89,
        height_mm=62,
        formats=["svg", "pdf", "png"],
        effort="medium",
    )
