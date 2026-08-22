from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from mcp_server import TOOLS  # noqa: E402
from paper_audit_core import AuditError, plan_paper_audit  # noqa: E402
from research_design_core import DesignError, plan_ideation, register_candidates  # noqa: E402
from research_guard_core import (  # noqa: E402
    _normalize_work,
    classify_domain,
    GuardError,
    make_search_plan,
    request_manual_evidence,
    register_method,
    refresh_domain,
)


class P4CycleACanonicalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_latin_domain_terms_use_word_boundaries(self):
        with self.assertRaisesRegex(GuardError, "selected_by=main_agent"):
            classify_domain(
                primary_domain="natural_science", secondary_domains=[], selected_by="classifier",
                selection_rationale="A forbidden keyword classifier attempted this selection.",
            )
        profile = classify_domain(
            primary_domain="natural_science", secondary_domains=[], selected_by="main_agent",
            selection_rationale="The main agent selected natural science for the reagent calibration protocol.",
        )
        self.assertNotIn("computer_science", [profile["primary"], *profile["secondary"]])
        social = classify_domain(
            primary_domain="social_science", secondary_domains=[], selected_by="main_agent",
            selection_rationale="The main agent selected social science for management policy and governance.",
        )
        self.assertEqual(social["primary"], "social_science")
        self.assertNotIn("computer_science", social["secondary"])

    def test_multilingual_cross_domain_profile_is_preserved(self):
        profile = classify_domain(
            primary_domain="computer_science", secondary_domains=["medicine_life_science"],
            selected_by="main_agent",
            selection_rationale="The main agent selected computing and medicine for clinical transformer imaging.",
        )
        domains = {profile["primary"], *profile["secondary"]}
        self.assertTrue({"computer_science", "medicine_life_science"} <= domains)
        self.assertIn("arxiv", profile["required_sources"])
        self.assertIn("pubmed", profile["required_sources"])

    def test_query_compiler_keeps_aliases_components_and_named_indices(self):
        method = {
            "title": "Boundary-Aware Clinical Transformer",
            "problem": "distribution shift in clinical diagnosis",
            "mechanism": "uncertainty calibrated transformer routing",
            "contributions": ["boundary detector", "calibrated abstention"],
            "datasets": ["site A", "site B"],
            "evaluation": "calibration and diagnostic accuracy",
            "aliases": ["selective prediction", "risk controlled routing"],
            "required_sources": "SCI; IEEE, CCF",
        }
        profile = classify_domain(
            primary_domain="computer_science", secondary_domains=["medicine_life_science"],
            selected_by="main_agent",
            selection_rationale="The main agent selected computing and medicine for this clinical transformer method.",
        )
        plan = make_search_plan(method, profile)
        self.assertEqual(len(plan["query_specs"]), len({item["query_id"] for item in plan["query_specs"]}))
        self.assertTrue({"wos_sci", "ieee", "ccf"} <= set(plan["required_sources"]))
        kinds = {item["kind"] for item in plan["query_specs"]}
        self.assertTrue({"exact_title", "exact_mechanism", "problem_mechanism", "aliases"} <= kinds)

    def test_work_source_string_is_normalized_and_links_are_https(self):
        work = _normalize_work(
            {"title": "Linked record", "sources": "crossref", "url": "http://example.org/work"},
            "manual",
        )
        self.assertEqual(work["sources"], ["crossref", "manual"])
        self.assertTrue(all(link["url"].startswith("https://") for link in work["citation_links"]))

    def test_every_catalog_output_url_is_https(self):
        catalog = json.loads(
            (PLUGIN / "skills" / "research-novelty-guard" / "references" / "source-catalog.json").read_text(
                encoding="utf-8"
            )
        )
        for source in catalog:
            for field in ("search_url", "api_url", "docs_url"):
                value = source.get(field)
                if value:
                    self.assertTrue(value.startswith("https://"), f"{source['id']}.{field}={value}")

    def test_manual_request_returns_https_official_route_and_exact_questions(self):
        register_method(
            self.root,
            {"title": "Index study", "problem": "software reliability", "mechanism": "graph analysis", "required_sources": ["CCF"]},
        )
        refresh_domain(
            self.root,
            primary_domain="computer_science",
            secondary_domains=[],
            selected_by="main_agent",
            selection_rationale=(
                "The main agent selected computer science because this indexed study concerns "
                "software reliability and graph analysis."
            ),
        )
        result = request_manual_evidence(self.root, ["ccf"])
        self.assertTrue(result["needs_user_input"])
        request = result["requests"][0]
        self.assertTrue(request["search_url"].startswith("https://"))
        self.assertEqual(len(request["questions"]), 4)
        self.assertIn("完整检索式", request["questions"][0])

    def test_mixed_paper_request_keeps_three_mandatory_roles_and_high_cap(self):
        plan = plan_paper_audit(
            self.root,
            "请审计全文公式、文献引用以及代码实验结果",
            selected_roles=["formal_math_lean", "code_experiment_integrity", "domain_literature"],
            audit_features={"formula": True, "experiment": True, "literature": True},
            selected_by="main_agent",
            selection_rationale="The main agent selected the three mandatory roles for formulas, literature, and experiments.",
            effort="high",
        )
        self.assertEqual(
            plan["selected_roles"],
            ["formal_math_lean", "code_experiment_integrity", "domain_literature"],
        )
        self.assertEqual(plan["effort"], "high")
        self.assertTrue(all(role["numeric_checks"] for role in plan["role_templates"]))

    def test_paper_effort_above_high_is_rejected(self):
        with self.assertRaisesRegex(AuditError, "forbidden"):
            plan_paper_audit(self.root, "audit manuscript", effort="xhigh")

    def test_multilingual_design_lenses_are_deterministic_and_bounded(self):
        first = plan_ideation(
            self.root,
            request_text="探索数据有限条件下的跨领域类比和失效边界",
            problem="预算有限且分布变化",
            constraints=["算力有限"],
        )
        second = plan_ideation(
            self.root,
            request_text="探索数据有限条件下的跨领域类比和失效边界",
            problem="预算有限且分布变化",
            constraints=["算力有限"],
        )
        self.assertEqual(first["plan_hash"], second["plan_hash"])
        self.assertGreaterEqual(len(first["selected_lenses"]), 2)
        self.assertLessEqual(len(first["selected_lenses"]), 3)
        self.assertEqual(first["effort_cap"], "high")

    def test_design_literature_never_accepts_unlinked_prior_work(self):
        plan = plan_ideation(self.root, request_text="brainstorm a boundary idea", problem="model failure")
        lens = plan["selected_lens_ids"][0]
        candidate = {
            "candidate_id": "c1",
            "title": "Boundary model",
            "problem": "model failure",
            "mechanism": "boundary detector",
            "falsifier": "no boundary effect",
            "minimum_viable_experiment": "two-regime comparison",
            "differentiator": "explicit failure boundary",
            "feasibility": "small public dataset",
            "lens_id": lens,
            "prior_work": [{"title": "Prior work", "url": "http://example.org/paper"}],
        }
        with self.assertRaisesRegex(DesignError, "HTTPS"):
            register_candidates(self.root, plan_hash=plan["plan_hash"], candidates=[candidate])

    def test_unified_tool_surface_remains_exactly_seventeen(self):
        names = [item["name"] for item in TOOLS]
        self.assertEqual(len(names), 17)
        self.assertEqual(names.count("paper_audit"), 1)
        self.assertEqual(names.count("research_design"), 1)


if __name__ == "__main__":
    unittest.main()
