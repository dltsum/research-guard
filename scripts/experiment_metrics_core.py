from __future__ import annotations

import csv
import math
import os
import statistics
import tempfile
from pathlib import Path
from typing import Any

from research_guard_core import GuardError, digest, project_root
from research_design_core import _load_design, _require_current_commit, utc_now


METRICS_SCHEMA_VERSION = 1
METRICS_STATE_NAME = "experiment-metrics.json"


class ExperimentMetricsError(GuardError):
    pass


def _state_path(root: str | os.PathLike[str]) -> Path:
    return project_root(root) / ".research-guard" / METRICS_STATE_NAME


def _atomic_json(path: Path, value: Any) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _text(value: Any, field: str) -> str:
    result = " ".join(str(value or "").split())
    if not result:
        raise ExperimentMetricsError(f"{field} is required")
    return result


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ExperimentMetricsError(f"{field} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ExperimentMetricsError(f"{field} must be a finite number") from exc
    if not math.isfinite(result):
        raise ExperimentMetricsError(f"{field} must be a finite number")
    return result


def _current_design(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    design = _load_design(root)
    committed, _ = _require_current_commit(root, design)
    experiment = design.get("experiment")
    if not isinstance(experiment, dict):
        raise ExperimentMetricsError("A current registered experiment is required before metric work")
    if experiment.get("method_hash") != committed.get("method_hash"):
        raise ExperimentMetricsError("STALE_EXPERIMENT: register the experiment for the current method")
    return design, committed, experiment


def _load_state(root: Path, *, required: bool = True) -> dict[str, Any] | None:
    import json

    path = _state_path(root)
    if not path.exists():
        if required:
            raise ExperimentMetricsError("No metric plan; call metrics_action=plan first")
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperimentMetricsError(f"Unreadable experiment-metrics state: {exc}") from exc
    if state.get("schema_version") != METRICS_SCHEMA_VERSION:
        raise ExperimentMetricsError("Unsupported experiment-metrics schema")
    plan_record = state.get("metric_plan") or {}
    expected = digest({
        "method_hash": plan_record.get("method_hash"),
        "experiment_hash": plan_record.get("experiment_hash"),
        "selected_by": plan_record.get("selected_by"),
        "metric_plan": plan_record.get("metric_plan"),
    })
    if expected != plan_record.get("metric_plan_hash"):
        raise ExperimentMetricsError("METRIC_PLAN_INTEGRITY_FAILURE")
    for analysis in state.get("analyses", []):
        stable = {key: analysis.get(key) for key in (
            "metric_plan_hash", "data_sha256", "data_path", "analysis_id", "baseline_configuration",
            "summaries", "comparisons",
        )}
        if digest(stable) != analysis.get("analysis_hash"):
            raise ExperimentMetricsError("METRIC_ANALYSIS_INTEGRITY_FAILURE")
    for optimization in state.get("optimizations", []):
        stable = {key: optimization.get(key) for key in (
            "metric_plan_hash", "analysis_hash", "optimization_id", "objectives", "constraints",
            "weights", "reference_scales", "selected_by", "feasible_configurations", "pareto_front", "ranking",
        )}
        if digest(stable) != optimization.get("optimization_hash"):
            raise ExperimentMetricsError("METRIC_OPTIMIZATION_INTEGRITY_FAILURE")
    return state


def _require_current(root: Path, state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    _, committed, experiment = _current_design(root)
    plan = state["metric_plan"]
    if plan.get("method_hash") != committed.get("method_hash"):
        raise ExperimentMetricsError("STALE_METRIC_PLAN: the method changed; freeze a new metric plan")
    if plan.get("experiment_hash") != experiment.get("experiment_hash"):
        raise ExperimentMetricsError("STALE_METRIC_PLAN: the experiment changed; freeze a new metric plan")
    return plan, experiment


def _normalize_metric(item: Any, index: int, primary_outcomes: set[str]) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ExperimentMetricsError(f"metric_plan.metrics[{index}] must be an object")
    role = _text(item.get("role"), f"metric_plan.metrics[{index}].role").lower()
    if role not in {"primary", "secondary", "diagnostic", "safety"}:
        raise ExperimentMetricsError(f"metric_plan.metrics[{index}].role is unsupported")
    direction = _text(item.get("direction"), f"metric_plan.metrics[{index}].direction").lower()
    if direction not in {"maximize", "minimize", "target"}:
        raise ExperimentMetricsError(f"metric_plan.metrics[{index}].direction is unsupported")
    aggregation = _text(item.get("aggregation"), f"metric_plan.metrics[{index}].aggregation").lower()
    if aggregation not in {"mean", "median"}:
        raise ExperimentMetricsError("Core metric aggregation must be mean or median")
    missing_policy = _text(item.get("missing_policy"), f"metric_plan.metrics[{index}].missing_policy").lower()
    if missing_policy != "fail":
        raise ExperimentMetricsError("Core metric analysis supports only missing_policy=fail; use a specialist model otherwise")
    record: dict[str, Any] = {
        "metric_id": _text(item.get("metric_id"), f"metric_plan.metrics[{index}].metric_id"),
        "column": _text(item.get("column"), f"metric_plan.metrics[{index}].column"),
        "role": role,
        "direction": direction,
        "unit": _text(item.get("unit"), f"metric_plan.metrics[{index}].unit"),
        "estimand": _text(item.get("estimand"), f"metric_plan.metrics[{index}].estimand"),
        "aggregation": aggregation,
        "missing_policy": missing_policy,
        "optimization_allowed": item.get("optimization_allowed") is True,
    }
    if role == "primary" and record["metric_id"] not in primary_outcomes and record["column"] not in primary_outcomes:
        raise ExperimentMetricsError(
            f"Primary metric {record['metric_id']} is not a registered experiment.primary_outcome"
        )
    for bound in ("legal_min", "legal_max"):
        if item.get(bound) is not None:
            record[bound] = _number(item.get(bound), f"metric_plan.metrics[{index}].{bound}")
    if "legal_min" in record and "legal_max" in record and record["legal_min"] >= record["legal_max"]:
        raise ExperimentMetricsError("metric legal_min must be below legal_max")
    if direction == "target":
        record["target"] = _number(item.get("target"), f"metric_plan.metrics[{index}].target")
    return record


def register_metric_plan(
    root: str | os.PathLike[str], metric_plan: dict[str, Any], *, selected_by: str,
) -> dict[str, Any]:
    base = project_root(root)
    _, committed, experiment = _current_design(base)
    if selected_by not in {"user", "main_agent"}:
        raise ExperimentMetricsError("metrics_selected_by must be user or main_agent")
    if not isinstance(metric_plan, dict):
        raise ExperimentMetricsError("metric_plan must be an object")
    data_level = _text(metric_plan.get("data_level"), "metric_plan.data_level").lower()
    if data_level != "independent_run":
        raise ExperimentMetricsError(
            "SPECIALIST_ANALYSIS_REQUIRED: clustered, participant-level, longitudinal, weighted, IRT, and qualitative data "
            "must not be flattened into the independent-run core engine"
        )
    items = metric_plan.get("metrics")
    if not isinstance(items, list) or not items:
        raise ExperimentMetricsError("metric_plan.metrics requires at least one metric")
    primary_outcomes = set(experiment["experiment"]["primary_outcomes"])
    metrics = [_normalize_metric(item, index, primary_outcomes) for index, item in enumerate(items)]
    ids = [item["metric_id"] for item in metrics]
    columns = [item["column"] for item in metrics]
    if len(ids) != len(set(ids)) or len(columns) != len(set(columns)):
        raise ExperimentMetricsError("Metric IDs and columns must be unique")
    if not any(item["role"] == "primary" for item in metrics):
        raise ExperimentMetricsError("At least one primary metric is required")
    optimization_split = _text(metric_plan.get("optimization_split"), "metric_plan.optimization_split")
    final_test_split = _text(metric_plan.get("final_test_split"), "metric_plan.final_test_split")
    if optimization_split == final_test_split:
        raise ExperimentMetricsError("Optimization and final-test splits must be distinct")
    candidate_budget = metric_plan.get("candidate_budget")
    if isinstance(candidate_budget, bool) or not isinstance(candidate_budget, int) or candidate_budget < 1:
        raise ExperimentMetricsError("metric_plan.candidate_budget must be a positive integer")
    normalized = {
        "metric_plan_id": _text(metric_plan.get("metric_plan_id"), "metric_plan.metric_plan_id"),
        "data_level": data_level,
        "configuration_column": _text(metric_plan.get("configuration_column"), "metric_plan.configuration_column"),
        "split_column": _text(metric_plan.get("split_column"), "metric_plan.split_column"),
        "replicate_column": _text(metric_plan.get("replicate_column"), "metric_plan.replicate_column"),
        "optimization_split": optimization_split,
        "final_test_split": final_test_split,
        "candidate_budget": candidate_budget,
        "metrics": metrics,
        "selection_boundary": _text(metric_plan.get("selection_boundary"), "metric_plan.selection_boundary"),
    }
    plan_hash = digest({
        "method_hash": committed["method_hash"],
        "experiment_hash": experiment["experiment_hash"],
        "selected_by": selected_by,
        "metric_plan": normalized,
    })
    record = {
        "method_hash": committed["method_hash"], "experiment_hash": experiment["experiment_hash"],
        "metric_plan_hash": plan_hash, "registered_at": utc_now(), "selected_by": selected_by,
        "metric_plan": normalized,
    }
    previous = _load_state(base, required=False)
    changed = not previous or previous.get("metric_plan", {}).get("metric_plan_hash") != plan_hash
    _atomic_json(_state_path(base), {
        "schema_version": METRICS_SCHEMA_VERSION, "metric_plan": record, "analyses": [], "optimizations": [],
    })
    return {"changed": changed, **record}


def _safe_data_path(base: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError as exc:
        raise ExperimentMetricsError("metrics_data_path must stay inside project_root") from exc
    if not path.is_file():
        raise ExperimentMetricsError(f"Metrics data file does not exist: {path}")
    return path


def _summary(values: list[float], aggregation: str) -> dict[str, Any]:
    center = statistics.mean(values) if aggregation == "mean" else statistics.median(values)
    sd = statistics.stdev(values) if len(values) > 1 else None
    return {
        "n": len(values), "center": center, "mean": statistics.mean(values),
        "median": statistics.median(values), "sd": sd, "minimum": min(values), "maximum": max(values),
        "inference_status": "DESCRIPTIVE_ONLY",
    }


def analyze_metrics(
    root: str | os.PathLike[str], *, data_path: str, analysis_id: str, baseline_configuration: str | None = None,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base)
    plan_record, _ = _require_current(base, state)
    plan = plan_record["metric_plan"]
    path = _safe_data_path(base, data_path)
    raw = path.read_bytes()
    import hashlib

    data_sha256 = hashlib.sha256(raw).hexdigest()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {plan["configuration_column"], plan["split_column"], plan["replicate_column"]}
        required.update(item["column"] for item in plan["metrics"])
        missing_columns = sorted(required - set(reader.fieldnames or []))
        if missing_columns:
            raise ExperimentMetricsError(f"Metrics CSV lacks columns: {', '.join(missing_columns)}")
        grouped: dict[tuple[str, str, str], list[float]] = {}
        seen: set[tuple[str, str, str]] = set()
        configurations: set[str] = set()
        for row_index, row in enumerate(reader, start=2):
            configuration = _text(row.get(plan["configuration_column"]), f"row {row_index} configuration")
            split = _text(row.get(plan["split_column"]), f"row {row_index} split")
            replicate = _text(row.get(plan["replicate_column"]), f"row {row_index} replicate")
            row_key = (configuration, split, replicate)
            if row_key in seen:
                raise ExperimentMetricsError(f"Duplicate configuration/split/replicate row at line {row_index}")
            seen.add(row_key)
            if split == plan["final_test_split"]:
                raise ExperimentMetricsError(
                    "FINAL_TEST_SEALED: optimization analysis must not receive final-test rows; "
                    "keep final-test data in a separate sealed artifact"
                )
            configurations.add(configuration)
            for metric in plan["metrics"]:
                value = _number(row.get(metric["column"]), f"row {row_index} metric {metric['metric_id']}")
                if "legal_min" in metric and value < metric["legal_min"]:
                    raise ExperimentMetricsError(f"ILLEGAL_METRIC_VALUE: {metric['metric_id']} below legal_min at row {row_index}")
                if "legal_max" in metric and value > metric["legal_max"]:
                    raise ExperimentMetricsError(f"ILLEGAL_METRIC_VALUE: {metric['metric_id']} above legal_max at row {row_index}")
                grouped.setdefault((configuration, split, metric["metric_id"]), []).append(value)
    if not seen:
        raise ExperimentMetricsError("Metrics CSV contains no data rows")
    if len(configurations) > plan["candidate_budget"]:
        raise ExperimentMetricsError("CANDIDATE_BUDGET_EXCEEDED")
    summaries: list[dict[str, Any]] = []
    metric_by_id = {item["metric_id"]: item for item in plan["metrics"]}
    for (configuration, split, metric_id), values in sorted(grouped.items()):
        summaries.append({
            "configuration": configuration, "split": split, "metric_id": metric_id,
            **_summary(values, metric_by_id[metric_id]["aggregation"]),
        })
    baseline = " ".join(str(baseline_configuration or "").split()) or None
    comparisons: list[dict[str, Any]] = []
    if baseline:
        lookup = {(item["configuration"], item["split"], item["metric_id"]): item for item in summaries}
        if baseline not in configurations:
            raise ExperimentMetricsError("baseline_configuration is absent from the data")
        for item in summaries:
            if item["configuration"] == baseline:
                continue
            reference = lookup.get((baseline, item["split"], item["metric_id"]))
            if reference:
                comparisons.append({
                    "configuration": item["configuration"], "baseline": baseline, "split": item["split"],
                    "metric_id": item["metric_id"], "center_difference": item["center"] - reference["center"],
                    "inference_boundary": "descriptive aggregate-run comparison; not a causal or significance claim",
                })
    stable = {
        "metric_plan_hash": plan_record["metric_plan_hash"], "data_sha256": data_sha256,
        "data_path": str(path.relative_to(base)), "analysis_id": _text(analysis_id, "analysis_id"),
        "baseline_configuration": baseline, "summaries": summaries, "comparisons": comparisons,
    }
    record = {**stable, "analysis_hash": digest(stable), "analyzed_at": utc_now()}
    state["analyses"] = [item for item in state.get("analyses", []) if item.get("analysis_id") != stable["analysis_id"]]
    state["analyses"].append(record)
    state["optimizations"] = []
    _atomic_json(_state_path(base), state)
    return record


def _objective_value(center: float, metric: dict[str, Any]) -> float:
    if metric["direction"] == "maximize":
        return center
    if metric["direction"] == "minimize":
        return -center
    return -abs(center - metric["target"])


def optimize_metrics(
    root: str | os.PathLike[str], *, analysis_id: str, optimization_id: str,
    objectives: list[str], constraints: list[dict[str, Any]] | None = None,
    weights: dict[str, Any] | None = None, reference_scales: dict[str, Any] | None = None,
    selected_by: str | None = None,
) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base)
    plan_record, _ = _require_current(base, state)
    plan = plan_record["metric_plan"]
    analyses = [item for item in state.get("analyses", []) if item.get("analysis_id") == analysis_id]
    if len(analyses) != 1:
        raise ExperimentMetricsError("A unique current analysis_id is required")
    analysis = analyses[0]
    metric_by_id = {item["metric_id"]: item for item in plan["metrics"]}
    objective_ids = [_text(item, "objectives[]") for item in objectives or []]
    if not objective_ids or len(objective_ids) != len(set(objective_ids)):
        raise ExperimentMetricsError("objectives must contain unique metric IDs")
    for metric_id in objective_ids:
        if metric_id not in metric_by_id or not metric_by_id[metric_id]["optimization_allowed"]:
            raise ExperimentMetricsError(f"Metric {metric_id} is undeclared or not allowed for optimization")
    constraint_records: list[dict[str, Any]] = []
    for index, item in enumerate(constraints or []):
        if not isinstance(item, dict):
            raise ExperimentMetricsError(f"constraints[{index}] must be an object")
        metric_id = _text(item.get("metric_id"), f"constraints[{index}].metric_id")
        operator = _text(item.get("operator"), f"constraints[{index}].operator")
        if metric_id not in metric_by_id or operator not in {"<=", ">="}:
            raise ExperimentMetricsError(f"constraints[{index}] is unsupported")
        constraint_records.append({"metric_id": metric_id, "operator": operator, "value": _number(item.get("value"), f"constraints[{index}].value")})
    optimization_rows = [item for item in analysis["summaries"] if item["split"] == plan["optimization_split"]]
    if not optimization_rows:
        raise ExperimentMetricsError("No rows exist for the frozen optimization split")
    values: dict[str, dict[str, float]] = {}
    for item in optimization_rows:
        values.setdefault(item["configuration"], {})[item["metric_id"]] = item["center"]
    required_ids = set(objective_ids) | {item["metric_id"] for item in constraint_records}
    feasible: list[str] = []
    for configuration, metrics in sorted(values.items()):
        if not required_ids <= metrics.keys():
            raise ExperimentMetricsError(f"Configuration {configuration} lacks an objective or constraint metric")
        if all(
            (metrics[item["metric_id"]] <= item["value"] if item["operator"] == "<=" else metrics[item["metric_id"]] >= item["value"])
            for item in constraint_records
        ):
            feasible.append(configuration)
    if not feasible:
        raise ExperimentMetricsError("INFEASIBLE_CONSTRAINTS: no configuration satisfies the frozen constraints")
    transformed = {
        configuration: {metric_id: _objective_value(values[configuration][metric_id], metric_by_id[metric_id]) for metric_id in objective_ids}
        for configuration in feasible
    }
    pareto: list[str] = []
    for candidate in feasible:
        dominated = any(
            other != candidate
            and all(transformed[other][metric_id] >= transformed[candidate][metric_id] for metric_id in objective_ids)
            and any(transformed[other][metric_id] > transformed[candidate][metric_id] for metric_id in objective_ids)
            for other in feasible
        )
        if not dominated:
            pareto.append(candidate)
    normalized_weights: dict[str, float] | None = None
    normalized_scales: dict[str, dict[str, float]] | None = None
    ranking: list[dict[str, Any]] | None = None
    if weights is not None or reference_scales is not None:
        if selected_by != "user" or not isinstance(weights, dict) or not isinstance(reference_scales, dict):
            raise ExperimentMetricsError("User-selected weights and reference_scales must be supplied together")
        if set(weights) != set(objective_ids) or set(reference_scales) != set(objective_ids):
            raise ExperimentMetricsError("Weights and reference scales must cover every objective exactly")
        normalized_weights = {metric_id: _number(weights[metric_id], f"weights.{metric_id}") for metric_id in objective_ids}
        if any(value < 0 for value in normalized_weights.values()) or sum(normalized_weights.values()) <= 0:
            raise ExperimentMetricsError("Objective weights must be nonnegative with a positive sum")
        total = sum(normalized_weights.values())
        normalized_weights = {key: value / total for key, value in normalized_weights.items()}
        normalized_scales = {}
        for metric_id in objective_ids:
            raw_scale = reference_scales[metric_id]
            if not isinstance(raw_scale, dict):
                raise ExperimentMetricsError(f"reference_scales.{metric_id} must be an object")
            low = _number(raw_scale.get("low"), f"reference_scales.{metric_id}.low")
            high = _number(raw_scale.get("high"), f"reference_scales.{metric_id}.high")
            if low >= high:
                raise ExperimentMetricsError("Each reference scale low must be below high")
            normalized_scales[metric_id] = {"low": low, "high": high}
        ranking = []
        for configuration in feasible:
            score = 0.0
            for metric_id in objective_ids:
                scale = normalized_scales[metric_id]
                metric = metric_by_id[metric_id]
                raw_value = values[configuration][metric_id]
                if metric["direction"] == "maximize":
                    utility = (raw_value - scale["low"]) / (scale["high"] - scale["low"])
                elif metric["direction"] == "minimize":
                    utility = (scale["high"] - raw_value) / (scale["high"] - scale["low"])
                else:
                    utility = 1.0 - abs(raw_value - metric["target"]) / (scale["high"] - scale["low"])
                score += normalized_weights[metric_id] * utility
            ranking.append({"configuration": configuration, "score": score})
        ranking.sort(key=lambda item: (-item["score"], item["configuration"]))
    stable = {
        "metric_plan_hash": plan_record["metric_plan_hash"], "analysis_hash": analysis["analysis_hash"],
        "optimization_id": _text(optimization_id, "optimization_id"), "objectives": objective_ids,
        "constraints": constraint_records, "weights": normalized_weights, "reference_scales": normalized_scales,
        "selected_by": selected_by,
        "feasible_configurations": feasible, "pareto_front": pareto, "ranking": ranking,
    }
    record = {
        **stable, "optimization_hash": digest(stable), "optimized_at": utc_now(),
        "selection_split": plan["optimization_split"], "final_test_split_touched": False,
        "decision_status": "USER_SELECTION_REQUIRED",
        "inference_boundary": "Validation-only observed-candidate comparison; no experiment execution or final-test claim.",
    }
    state["optimizations"] = [item for item in state.get("optimizations", []) if item.get("optimization_id") != stable["optimization_id"]]
    state["optimizations"].append(record)
    _atomic_json(_state_path(base), state)
    return record


def metric_status(root: str | os.PathLike[str], *, verify: bool = False) -> dict[str, Any]:
    base = project_root(root)
    state = _load_state(base, required=False)
    if not state:
        return {"status": "METRIC_PLAN_REQUIRED", "ready": False}
    try:
        plan, _ = _require_current(base, state)
    except ExperimentMetricsError as exc:
        return {"status": "STALE_METRIC_PLAN", "ready": False, "error": str(exc)}
    result = {
        "status": "PASS" if verify else "CURRENT", "ready": True,
        "metric_plan_hash": plan["metric_plan_hash"], "analysis_count": len(state.get("analyses", [])),
        "optimization_count": len(state.get("optimizations", [])),
    }
    if verify:
        result["integrity_verified"] = True
    return result
