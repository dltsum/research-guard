from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from mcp_server import handle  # noqa: E402
import dependency_manager  # noqa: E402
from research_guard_core import (  # noqa: E402
    GuardError,
    detect_source_mentions,
    get_gate_status,
    load_state,
    register_manual_evidence,
    register_method,
    request_manual_evidence,
    run_novelty_search,
)


def social_method(**changes):
    value = {
        "title": "Adaptive evidence framing in education policy communication",
        "problem": "Education policy communication affects social governance outcomes",
        "mechanism": "A staged evidence framing intervention changes public interpretation",
        "contributions": "version-bound communication intervention",
        "required_sources": ["CSSCI"],
    }
    value.update(changes)
    return value


class ManualEvidenceDialogRoundFiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.key = Path(self.temp.name) / "key.bin"
        self.old_key = os.environ.get("RESEARCH_GUARD_KEY_FILE")
        os.environ["RESEARCH_GUARD_KEY_FILE"] = str(self.key)

    def tearDown(self):
        if self.old_key is None:
            os.environ.pop("RESEARCH_GUARD_KEY_FILE", None)
        else:
            os.environ["RESEARCH_GUARD_KEY_FILE"] = self.old_key
        self.temp.cleanup()

    def write_capture(self, name="cssci.txt", text="official CSSCI query capture"):
        path = self.root / "evidence" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def required_fixtures_without(self, source):
        plan = load_state(self.root)["search_plan"]
        return {item: [] for item in plan["required_sources"] if item != source}

    def query_ids(self):
        return [item["query_id"] for item in load_state(self.root)["search_plan"]["query_specs"]]

    def hook(self, prompt):
        completed = subprocess.run(
            [sys.executable, str(PLUGIN / "hooks" / "guard_hook.py")],
            input=json.dumps({"hook_event_name": "UserPromptSubmit", "cwd": str(self.root), "prompt": prompt}),
            text=True, encoding="utf-8", capture_output=True, timeout=10,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_detects_named_manual_sources_without_sci_substring_false_positive(self):
        self.assertEqual(
            detect_source_mentions("请查 SCI、SSCI、CCF、IEEE、CSSCI、C刊、知网和万方"),
            ["wos_ssci", "wos_sci", "ccf", "cssci", "c_journal", "ieee", "cnki", "wanfang"],
        )
        self.assertNotIn("wos_sci", detect_source_mentions("scientific method"))

    def test_request_returns_exact_questions_and_official_url(self):
        register_method(self.root, social_method())
        request = request_manual_evidence(self.root)
        self.assertTrue(request["needs_user_input"])
        cssci = next(item for item in request["requests"] if item["source"] == "cssci")
        self.assertEqual(cssci["purpose"], "index_membership")
        self.assertTrue(cssci["search_url"].startswith("https://cssrac.nju.edu.cn/"))
        self.assertEqual(len(cssci["questions"]), 4)

    def test_mcp_manual_request_returns_structured_questions(self):
        register_method(self.root, social_method())
        dependency_home = Path(self.temp.name) / "dependency-home"
        previous_home = os.environ.get("RESEARCH_GUARD_HOME")
        try:
            os.environ["RESEARCH_GUARD_HOME"] = str(dependency_home)
            dependency_manager.decide([], [])
            response = handle({
                "jsonrpc": "2.0", "id": 9, "method": "tools/call",
                "params": {
                    "name": "request_manual_evidence",
                    "arguments": {"project_root": str(self.root), "sources": ["CSSCI"]},
                },
            })
        finally:
            if previous_home is None:
                os.environ.pop("RESEARCH_GUARD_HOME", None)
            else:
                os.environ["RESEARCH_GUARD_HOME"] = previous_home
        result = response["result"]
        self.assertFalse(result["isError"])
        self.assertTrue(result["structuredContent"]["needs_user_input"])
        self.assertEqual(result["structuredContent"]["requests"][0]["source"], "cssci")

    def test_register_index_capture_satisfies_required_manual_source(self):
        register_method(self.root, social_method())
        capture = self.write_capture()
        registered = register_manual_evidence(
            self.root,
            source="CSSCI",
            purpose="index_membership",
            query="教育学 / 示例期刊",
            status="index_not_listed",
            identifier="示例期刊",
            evidence_path=str(capture.relative_to(self.root)),
            evidence_url="https://cssrac.nju.edu.cn/cpzx/zwshkxywsy/index.html",
        )
        self.assertTrue(registered["registered"])
        result = run_novelty_search(
            self.root, fixture_sources=self.required_fixtures_without("cssci")
        )["report"]
        self.assertEqual(result["gate_status"], "PASS")
        self.assertEqual(result["coverage"]["cssci"]["evidence_mode"], "registered_manual_evidence")
        self.assertEqual(result["index_checks"]["cssci"]["status"], "index_not_listed")

    def test_hits_present_requires_records_and_imported_hit_is_collision_scored(self):
        method = social_method(required_sources=["CNKI"])
        register_method(self.root, method)
        capture = self.write_capture("cnki.csv", "title,doi\ncollision,10.1000/collision")
        with self.assertRaisesRegex(GuardError, "requires at least one"):
            register_manual_evidence(
                self.root, source="CNKI", purpose="literature_search", query=method["title"],
                status="hits_present", evidence_path=str(capture.relative_to(self.root)),
                evidence_url="https://kns.cnki.net/kns8s/AdvSearch",
                query_ids=self.query_ids(),
            )
        register_manual_evidence(
            self.root, source="CNKI", purpose="literature_search", query=method["title"],
            status="hits_present", evidence_path=str(capture.relative_to(self.root)),
            evidence_url="https://kns.cnki.net/kns8s/AdvSearch",
            records=[{"title": method["title"], "doi": "10.1000/collision", "year": 2026}],
            query_ids=self.query_ids(),
        )
        report = run_novelty_search(
            self.root, fixture_sources=self.required_fixtures_without("cnki")
        )["report"]
        self.assertEqual(report["gate_status"], "COLLISION_REVIEW_REQUIRED")
        self.assertEqual(report["collision_candidates"][0]["collision_score"], 1.0)

    def test_unofficial_url_and_path_escape_are_rejected(self):
        register_method(self.root, social_method())
        capture = self.write_capture()
        with self.assertRaisesRegex(GuardError, "not an official host"):
            register_manual_evidence(
                self.root, source="CSSCI", purpose="index_membership", query="示例期刊",
                status="index_verified", identifier="示例期刊",
                evidence_path=str(capture.relative_to(self.root)), evidence_url="https://example.com/result",
            )
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("capture", encoding="utf-8")
        with self.assertRaisesRegex(GuardError, "escapes project root"):
            register_manual_evidence(
                self.root, source="CSSCI", purpose="index_membership", query="示例期刊",
                status="index_verified", identifier="示例期刊", evidence_path="../outside.txt",
                evidence_url="https://cssrac.nju.edu.cn/",
            )

    def test_capture_change_invalidates_receipt_and_method_change_drops_registration(self):
        register_method(self.root, social_method())
        capture = self.write_capture()
        register_manual_evidence(
            self.root, source="CSSCI", purpose="index_membership", query="示例期刊",
            status="index_verified", identifier="示例期刊",
            evidence_path=str(capture.relative_to(self.root)), evidence_url="https://cssrac.nju.edu.cn/",
        )
        run_novelty_search(self.root, fixture_sources=self.required_fixtures_without("cssci"))
        self.assertEqual(get_gate_status(self.root)["gate"]["status"], "PASS")
        capture.write_text("changed capture", encoding="utf-8")
        invalid = get_gate_status(self.root)
        self.assertEqual(invalid["gate"]["status"], "NOVELTY_CHECK_REQUIRED")
        self.assertIsNone(invalid["current_receipt"])
        register_method(self.root, social_method(mechanism="A causal framing intervention changes interpretation"))
        self.assertEqual(load_state(self.root)["manual_evidence"], {})

    def test_hook_tells_agent_to_ask_then_register_supplied_evidence(self):
        first = self.hook("请补查 CSSCI 和 CCF")
        first_text = first["hookSpecificOutput"]["additionalContext"]
        self.assertIn("request_manual_evidence", first_text)
        self.assertIn("required_sources", first_text)
        second = self.hook(
            "CSSCI 截图已保存到 evidence/cssci.png，结果页 https://cssrac.nju.edu.cn/"
        )
        second_text = second["hookSpecificOutput"]["additionalContext"]
        self.assertIn("register_manual_evidence", second_text)
        self.assertIn("chat text alone", second_text)


if __name__ == "__main__":
    unittest.main()
