from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from mcp_server import TOOLS, handle  # noqa: E402
from paper_spine_core import (  # noqa: E402
    PaperSpineError,
    bind_paper_spine_collision,
    get_paper_spine_status,
    plan_paper_spine,
    register_paper_spine,
    verify_paper_spine,
)


class MacroPaperSpineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.plan = plan_paper_spine(
            self.root,
            spine_id="qxy-spine",
            request_text="Build a macro paper line from a small language variety observation",
            local_observation="Qinxiang shows a small set of documented alternations across recorded speakers.",
            domain_scope="historical and comparative linguistics",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def spine(self, *, method_hash: str = "a" * 64) -> dict:
        return {
            "method_hash": method_hash,
            "local_observation": "Qinxiang shows a small set of documented alternations across recorded speakers.",
            "macro_problem": "How can structured language variation become evidence for contact, typological organization, and change across communities?",
            "unifying_method": "A comparative mechanism maps local forms to a cross-context evidence graph and tests the same explanatory invariant across varieties and historical records.",
            "mechanism": "The method separates observed form, social or historical context, and predicted change, then compares the linked mechanism instead of cataloguing one local feature.",
            "central_claim": "A local variety can serve as a discriminating case for a general account of how patterned variation records interaction and change when the same predictions travel across contexts.",
            "generality_target": "Comparable language varieties and time-indexed records with enough evidence to test the same mechanism.",
            "abstraction_move": {
                "from_local_case": "Start from Qinxiang alternations without treating the inventory as the contribution.",
                "to_macro_question": "Ask what general mechanism makes patterned variation informative about contact and change.",
                "unifying_invariant": "The relation among form, context, and predicted change remains testable across cases.",
                "why_general": "The mechanism can be tested in neighboring varieties and historical records rather than only one dialect.",
                "anti_overclaim": "The study does not claim all variation has one cause or that this case proves a universal law.",
            },
            "cross_context_predictions": [
                {
                    "context": "neighboring language varieties",
                    "prediction": "The proposed relation predicts which alternations should co-vary with contact structure.",
                    "test": "Compare matched forms and contact histories under the registered coding scheme.",
                    "failure_condition": "The relation disappears after the prespecified comparison and controls.",
                },
                {
                    "context": "historical records",
                    "prediction": "The mechanism predicts a time-ordered shift in the same form-context relation.",
                    "test": "Evaluate dated texts or archival records with the same operational definitions.",
                    "failure_condition": "The predicted ordering is absent or cannot be distinguished from an alternative.",
                },
            ],
            "falsifiers": [
                "The cross-context invariant fails in a preregistered matched comparison.",
                "An alternative mechanism explains all observations with fewer unsupported assumptions.",
            ],
            "scope_boundary": [
                "The evidence concerns the registered varieties, records, and operational definitions.",
                "The paper does not infer a universal law for every language or historical setting.",
            ],
            "evidence_plan": [
                {
                    "evidence_id": "ev1",
                    "claim": "The comparative framing has a documented literature base and explicit source boundary.",
                    "evidence_type": "primary literature",
                    "test": "Read and locate the cited works before drafting the related-work comparison.",
                    "source_links": [
                        {"title": "Comparative historical linguistics record", "url": "https://doi.org/10.1000/qxy-comparison"},
                    ],
                },
                {
                    "evidence_id": "ev2",
                    "claim": "The local forms and historical records can be coded with reproducible definitions.",
                    "evidence_type": "corpus and archive protocol",
                    "test": "Bind the coding sheet and source locators before interpreting the cross-context result.",
                    "source_links": [
                        {"title": "Open archival record", "url": "https://example.org/qxy-archive"},
                    ],
                },
            ],
            "title_candidates": [
                {
                    "title_id": "ttl1",
                    "title": "Variation as Evidence: A General Method for Linking Form, Context, and Change",
                    "level": "macro",
                    "rationale": "Names the transferable problem and method without hiding the evidence boundary.",
                    "claim_scope": "A comparative method, not a universal causal law.",
                },
                {
                    "title_id": "ttl2",
                    "title": "From Local Forms to General Mechanisms of Language Change",
                    "level": "macro",
                    "rationale": "Places the local case inside a broader account of change.",
                    "claim_scope": "Mechanism tested in the registered contexts.",
                },
                {
                    "title_id": "ttl3",
                    "title": "A Cross-Context Evidence Graph for Contact-Induced Variation",
                    "level": "meso",
                    "rationale": "Highlights the concrete unifying representation and comparison.",
                    "claim_scope": "Contact-linked variation in the studied records.",
                },
                {
                    "title_id": "ttl4",
                    "title": "Testing Form–Context Relations Across Varieties and Historical Records",
                    "level": "meso",
                    "rationale": "Makes the falsifiable comparison visible to adjacent fields.",
                    "claim_scope": "The operationalized cross-context test.",
                },
                {
                    "title_id": "ttl5",
                    "title": "Qinxiang Alternations as a Test Case for Comparative Change",
                    "level": "local",
                    "rationale": "Retains a precise local title for a venue that needs the case named.",
                    "claim_scope": "Qinxiang evidence only; no universal inference.",
                },
            ],
            "collision": {"status": "PENDING", "note": "Search after this exact method revision is registered."},
        }

    def test_plan_exposes_macro_generation_contract_without_domain_inference(self) -> None:
        self.assertEqual(self.plan["status"], "READY_FOR_MACRO_DRAFT")
        contract = self.plan["plan"]["generation_contract"]
        self.assertEqual(contract["required_layers"], ["local_observation", "macro_problem", "unifying_method", "cross_context_evidence"])
        self.assertTrue(any("Lift" in step for step in contract["sequence"]))
        self.assertFalse(self.plan["plan"]["automatic_domain_inference"])

    def test_register_keeps_macro_spine_and_five_unranked_title_levels(self) -> None:
        result = register_paper_spine(
            self.root, spine_id="qxy-spine", plan_hash=self.plan["plan"]["plan_hash"], spine=self.spine(),
        )
        self.assertEqual(result["status"], "COLLISION_SEARCH_REQUIRED")
        self.assertTrue(result["automatic_title_selection"] is False)
        self.assertTrue(result["user_title_selection_required"])
        current = result["spine"]
        self.assertIn("macro_problem", current)
        self.assertIn("unifying_method", current)
        self.assertEqual(len(current["title_candidates"]), 5)
        self.assertEqual({item["level"] for item in current["title_candidates"]}, {"macro", "meso", "local"})
        self.assertTrue(all(link["url"].startswith("https://") for item in current["evidence_plan"] for link in item["source_links"]))

    def test_narrow_title_set_is_rejected_instead_of_silently_shrinking_the_problem(self) -> None:
        candidate = self.spine()
        for item in candidate["title_candidates"]:
            item["level"] = "local"
        with self.assertRaisesRegex(PaperSpineError, "at least two macro titles"):
            register_paper_spine(
                self.root, spine_id="qxy-spine", plan_hash=self.plan["plan"]["plan_hash"], spine=candidate,
            )

    def test_collision_pass_can_only_be_bound_by_canonical_receipt(self) -> None:
        candidate = self.spine()
        candidate["collision"] = {"status": "PASS"}
        with self.assertRaisesRegex(PaperSpineError, "only be attached by bind_collision"):
            register_paper_spine(
                self.root, spine_id="qxy-spine", plan_hash=self.plan["plan"]["plan_hash"], spine=candidate,
            )

    def test_method_revision_archives_prior_spine_and_resets_collision(self) -> None:
        first = register_paper_spine(
            self.root, spine_id="qxy-spine", plan_hash=self.plan["plan"]["plan_hash"], spine=self.spine(),
        )
        self.assertEqual(first["spine"]["revision"], 1)
        second_spine = copy.deepcopy(self.spine(method_hash="b" * 64))
        second_spine["central_claim"] = "The revised mechanism tests whether form-context relations remain informative under a different registered comparison design."
        second = register_paper_spine(
            self.root, spine_id="qxy-spine", plan_hash=self.plan["plan"]["plan_hash"], spine=second_spine,
        )
        self.assertEqual(second["spine"]["revision"], 2)
        self.assertEqual(second["status"], "COLLISION_SEARCH_REQUIRED")
        self.assertEqual(len(get_paper_spine_status(self.root)["macro_spine"]["collision"]["literature_links"]), 0)
        self.assertEqual(len(json.loads((self.root / ".research-guard" / "paper-spine-state.json").read_text(encoding="utf-8"))["history"]), 1)

    def test_bind_collision_requires_current_strict_novelty_receipt_and_preserves_links(self) -> None:
        register_paper_spine(
            self.root, spine_id="qxy-spine", plan_hash=self.plan["plan"]["plan_hash"], spine=self.spine(),
        )
        receipt = self.root / ".research-guard" / "receipts" / "current.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text("{}\n", encoding="utf-8")
        report = {
            "gate_status": "PASS", "method_hash": "a" * 64,
            "report_hash": "c" * 64, "query_plan_hash": "d" * 64,
            "works": [{"title": "Linked comparison", "citation_links": [{"url": "https://doi.org/10.1000/linked"}]}],
        }
        gate = {"method_hash": "a" * 64, "current_receipt": " .research-guard/receipts/current.json".strip()}
        with patch("research_guard_core.verify_receipt", return_value={"valid": True}), \
             patch("research_guard_core.get_gate_status", return_value=gate), \
             patch("research_guard_core.get_collision_report", return_value=report):
            result = bind_paper_spine_collision(self.root, spine_id="qxy-spine")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["literature_links"][0]["url"], "https://doi.org/10.1000/linked")
            verified = verify_paper_spine(self.root, spine_id="qxy-spine")
        self.assertEqual(verified["status"], "PASS")
        self.assertTrue(verified["valid"])
        self.assertEqual(verified["macro_spine"]["collision"]["receipt_sha256"], hashlib.sha256(receipt.read_bytes()).hexdigest())

    def test_same_method_framing_revision_carries_collision_receipt_without_research_restart(self) -> None:
        register_paper_spine(
            self.root, spine_id="qxy-spine", plan_hash=self.plan["plan"]["plan_hash"], spine=self.spine(),
        )
        receipt = self.root / ".research-guard" / "receipts" / "current.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text("{}\n", encoding="utf-8")
        report = {
            "gate_status": "PASS", "method_hash": "a" * 64,
            "report_hash": "c" * 64, "query_plan_hash": "d" * 64, "works": [],
        }
        gate = {"method_hash": "a" * 64, "current_receipt": ".research-guard/receipts/current.json"}
        with patch("research_guard_core.verify_receipt", return_value={"valid": True}), \
             patch("research_guard_core.get_gate_status", return_value=gate), \
             patch("research_guard_core.get_collision_report", return_value=report):
            bind_paper_spine_collision(self.root, spine_id="qxy-spine")
        revised = self.spine()
        revised.pop("collision")
        revised["central_claim"] = "The same registered method is now framed as a cross-context account while preserving its exact evidence and falsifiers."
        result = register_paper_spine(
            self.root, spine_id="qxy-spine", plan_hash=self.plan["plan"]["plan_hash"], spine=revised,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["spine"]["collision"]["report_hash"], "c" * 64)

    def test_changed_method_after_pass_requires_a_fresh_collision_search(self) -> None:
        register_paper_spine(
            self.root, spine_id="qxy-spine", plan_hash=self.plan["plan"]["plan_hash"], spine=self.spine(),
        )
        receipt = self.root / ".research-guard" / "receipts" / "current.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text("{}\n", encoding="utf-8")
        report = {
            "gate_status": "PASS", "method_hash": "a" * 64,
            "report_hash": "c" * 64, "query_plan_hash": "d" * 64, "works": [],
        }
        gate = {"method_hash": "a" * 64, "current_receipt": ".research-guard/receipts/current.json"}
        with patch("research_guard_core.verify_receipt", return_value={"valid": True}), \
             patch("research_guard_core.get_gate_status", return_value=gate), \
             patch("research_guard_core.get_collision_report", return_value=report):
            bind_paper_spine_collision(self.root, spine_id="qxy-spine")
        changed = copy.deepcopy(self.spine(method_hash="b" * 64))
        registered = register_paper_spine(
            self.root, spine_id="qxy-spine", plan_hash=self.plan["plan"]["plan_hash"], spine=changed,
        )
        self.assertEqual(registered["status"], "COLLISION_SEARCH_REQUIRED")
        self.assertEqual(registered["spine"]["collision"]["status"], "PENDING")
        self.assertEqual(registered["spine"]["collision"]["method_hash"], "b" * 64)

    def test_mcp_exposes_spine_subroute_without_adding_top_level_tool(self) -> None:
        self.assertEqual(len(TOOLS), 17)
        language = next(item for item in TOOLS if item["name"] == "language_assist")
        self.assertIn("spine_action", language["inputSchema"]["properties"])
        mcp_root = self.root / "mcp"
        mcp_root.mkdir()
        response = handle({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "language_assist", "arguments": {
                "action": "status", "spine_action": "plan", "project_root": str(mcp_root),
                "request_text": "Build a macro paper line from a small language variety observation",
                "spine_id": "mcp-spine", "spine_observation": "A small language variety has patterned alternations.",
                "spine_domain_scope": "comparative linguistics",
            }},
        })
        self.assertFalse(response["result"]["isError"])
        self.assertEqual(response["result"]["structuredContent"]["status"], "READY_FOR_MACRO_DRAFT")


if __name__ == "__main__":
    unittest.main()
