"""Selection-state regression; component registration is a local unit fixture."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dependency_manager as d


class DependencySelectionSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {"RESEARCH_GUARD_HOME": self.temp.name})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def test_partial_reuse_does_not_decline_unmentioned_components(self):
        with patch.object(d, "register_existing", return_value={"component": "tex-basic"}):
            result = d.decide([], ["tex-basic"])
        self.assertEqual(result["decision"]["selected"], ["tex-basic"])
        self.assertEqual(result["decision"]["declined"], [])
        self.assertEqual(d.component_need("lean-mathlib")["status"], "USER_DECISION_REQUIRED")
        with self.assertRaises(d.DependencyError) as caught:
            d.require("lean-mathlib")
        self.assertEqual(caught.exception.code, "DEPENDENCY_USER_DECISION_REQUIRED")

    def test_empty_choice_does_not_equal_decline_all(self):
        result = d.decide([], [])
        self.assertEqual(result["decision"]["declined"], [])
        for component in d.OPTIONAL_IDS:
            self.assertEqual(d.component_need(component)["status"], "USER_DECISION_REQUIRED")

    def test_prior_explicit_decline_persists_but_reselection_clears_it(self):
        d.decline_all()
        with patch.object(d, "register_existing", return_value={}):
            result = d.decide([], ["tex-basic"])
        self.assertEqual(result["decision"]["declined"], ["lean-mathlib", "portable-git"])
        self.assertEqual(d.component_need("lean-mathlib")["status"], "DEGRADED")

    def test_failed_selection_does_not_create_refusals(self):
        d.decline("lean-mathlib")
        with patch.object(d, "install", side_effect=d.DependencyError("FIXTURE_FAILURE", "unit fixture")):
            with self.assertRaises(d.DependencyError):
                d.decide(["tex-basic"], [])
        saved = d._decision()
        self.assertEqual(saved["status"], "INSTALL_FAILED")
        self.assertEqual(saved["declined"], ["lean-mathlib"])
        self.assertEqual(d.component_need("portable-git")["status"], "USER_DECISION_REQUIRED")

    def test_empty_interrupted_resume_preserves_only_explicit_declines(self):
        d._atomic_json(d.dependency_root() / "selection.json", {"status": "INTERRUPTED", "selected": [], "declined": ["portable-git"]})
        result = d.resume_install()
        self.assertEqual(result["decision"]["declined"], ["portable-git"])
        self.assertEqual(d.component_need("lean-mathlib")["status"], "USER_DECISION_REQUIRED")

    def test_explicit_decline_and_decline_all_remain_degraded(self):
        self.assertEqual(d.decline("lean-mathlib")["status"], "DEGRADED")
        result = d.decline_all()
        self.assertEqual(set(result["decision"]["declined"]), d.OPTIONAL_IDS)
        for component in d.OPTIONAL_IDS:
            self.assertEqual(d.component_need(component)["status"], "DEGRADED")


if __name__ == "__main__":
    unittest.main()
