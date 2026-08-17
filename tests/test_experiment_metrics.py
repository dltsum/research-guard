from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))
sys.path.insert(0, str(PLUGIN / "tests"))

from experiment_metrics_core import (  # noqa: E402
    ExperimentMetricsError,
    analyze_metrics,
    metric_status,
    optimize_metrics,
    register_metric_plan,
)
from research_design_core import (  # noqa: E402
    commit_candidate,
    plan_ideation,
    register_candidates,
    register_experiment,
    register_hypothesis,
)
from test_p3_round4_experiment_integration import candidate, experiment, hypothesis  # noqa: E402


def metric_plan() -> dict:
    return {
        "metric_plan_id": "M1",
        "data_level": "independent_run",
        "configuration_column": "configuration",
        "split_column": "split",
        "replicate_column": "seed",
        "optimization_split": "validation",
        "final_test_split": "test",
        "candidate_budget": 3,
        "selection_boundary": "Only validation aggregates may rank observed candidates; test remains sealed.",
        "metrics": [
            {
                "metric_id": "delta_loss", "column": "delta_loss", "role": "primary",
                "direction": "minimize", "unit": "loss units",
                "estimand": "Mean loss change across independent seeded runs", "aggregation": "mean",
                "missing_policy": "fail", "optimization_allowed": True,
                "legal_min": -10, "legal_max": 10,
            },
            {
                "metric_id": "runtime", "column": "runtime", "role": "safety",
                "direction": "minimize", "unit": "seconds",
                "estimand": "Median runtime across independent seeded runs", "aggregation": "median",
                "missing_policy": "fail", "optimization_allowed": True,
                "legal_min": 0, "legal_max": 1000,
            },
        ],
    }


class ExperimentMetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        plan = plan_ideation(self.root, request_text="Design a bounded experiment", problem="Boundary adaptation is confounded.")
        item = candidate()
        register_candidates(self.root, plan_hash=plan["plan_hash"], candidates=[item])
        commit_candidate(
            self.root, candidate_id="I1", selected_by="user",
            method={key: item[key] for key in ("title", "problem", "mechanism")},
        )
        register_hypothesis(self.root, hypothesis())
        register_experiment(self.root, experiment())

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_data(self, *, illegal: bool = False) -> Path:
        path = self.root / "metrics.csv"
        value = "11" if illegal else "0.8"
        path.write_text(
            "configuration,split,seed,delta_loss,runtime\n"
            f"baseline,validation,1,{value},100\n"
            "baseline,validation,2,1.0,102\n"
            "candidate,validation,1,0.4,110\n"
            "candidate,validation,2,0.5,108\n",
            encoding="utf-8",
        )
        return path

    def test_plan_analysis_and_pareto_optimization_are_hash_bound(self) -> None:
        plan = register_metric_plan(self.root, metric_plan(), selected_by="main_agent")
        self.assertTrue(plan["metric_plan_hash"])
        self.write_data()
        analysis = analyze_metrics(
            self.root, data_path="metrics.csv", analysis_id="A1",
            baseline_configuration="baseline",
        )
        optimized = optimize_metrics(
            self.root, analysis_id="A1", optimization_id="O1",
            objectives=["delta_loss", "runtime"], constraints=[{"metric_id": "runtime", "operator": "<=", "value": 120}],
        )
        self.assertEqual(optimized["selection_split"], "validation")
        self.assertFalse(optimized["final_test_split_touched"])
        self.assertEqual(optimized["decision_status"], "USER_SELECTION_REQUIRED")
        self.assertEqual(set(optimized["pareto_front"]), {"baseline", "candidate"})
        self.assertTrue(analysis["analysis_hash"])
        self.assertEqual(metric_status(self.root, verify=True)["status"], "PASS")

    def test_final_test_rows_are_rejected_before_metric_parsing(self) -> None:
        register_metric_plan(self.root, metric_plan(), selected_by="main_agent")
        path = self.write_data()
        with path.open("a", encoding="utf-8") as handle:
            handle.write("candidate,test,1,not-even-a-number,109\n")
        with self.assertRaisesRegex(ExperimentMetricsError, "FINAL_TEST_SEALED"):
            analyze_metrics(self.root, data_path="metrics.csv", analysis_id="A1")

    def test_illegal_metric_value_and_non_independent_data_fail_closed(self) -> None:
        register_metric_plan(self.root, metric_plan(), selected_by="main_agent")
        self.write_data(illegal=True)
        with self.assertRaisesRegex(ExperimentMetricsError, "ILLEGAL_METRIC_VALUE"):
            analyze_metrics(self.root, data_path="metrics.csv", analysis_id="A1")
        clustered = metric_plan(); clustered["data_level"] = "student"
        with self.assertRaisesRegex(ExperimentMetricsError, "SPECIALIST_ANALYSIS_REQUIRED"):
            register_metric_plan(self.root, clustered, selected_by="main_agent")

    def test_weighted_ranking_requires_user_owned_weights_and_scales(self) -> None:
        register_metric_plan(self.root, metric_plan(), selected_by="main_agent")
        self.write_data()
        analyze_metrics(self.root, data_path="metrics.csv", analysis_id="A1")
        kwargs = {
            "analysis_id": "A1", "optimization_id": "O1", "objectives": ["delta_loss", "runtime"],
            "weights": {"delta_loss": 0.8, "runtime": 0.2},
            "reference_scales": {"delta_loss": {"low": 0, "high": 2}, "runtime": {"low": 50, "high": 150}},
        }
        with self.assertRaisesRegex(ExperimentMetricsError, "User-selected"):
            optimize_metrics(self.root, **kwargs)
        result = optimize_metrics(self.root, selected_by="user", **kwargs)
        self.assertEqual(result["ranking"][0]["configuration"], "candidate")

    def test_state_tampering_is_detected(self) -> None:
        register_metric_plan(self.root, metric_plan(), selected_by="main_agent")
        path = self.root / ".research-guard" / "experiment-metrics.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["metric_plan"]["metric_plan"]["candidate_budget"] = 999
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ExperimentMetricsError, "INTEGRITY"):
            metric_status(self.root, verify=True)

    def test_metric_plan_selector_tampering_is_detected(self) -> None:
        register_metric_plan(self.root, metric_plan(), selected_by="main_agent")
        path = self.root / ".research-guard" / "experiment-metrics.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["metric_plan"]["selected_by"] = "user"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ExperimentMetricsError, "INTEGRITY"):
            metric_status(self.root, verify=True)

    def test_mcp_keeps_one_research_design_owner(self) -> None:
        import mcp_server

        tools = [item for item in mcp_server.TOOLS if item["name"] == "research_design"]
        self.assertEqual(len(tools), 1)
        properties = tools[0]["inputSchema"]["properties"]
        self.assertEqual(properties["metrics_action"]["enum"], ["plan", "analyze", "optimize", "status", "verify"])


if __name__ == "__main__":
    unittest.main()
