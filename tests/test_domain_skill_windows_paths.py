"""Local I/O regression; Git responses below are explicit unit-test fixtures."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import domain_skill_core as core
from evidence_kernel import io_path


class DomainSkillPathTests(unittest.TestCase):
    def test_long_project_stages_scans_and_detects_changed_content(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / ("project-" + "x" * 110) / ("nested-" + "y" * 55)
            commit = "a" * 40
            checkout_paths = []

            def fixture_git(repository, *args, **kwargs):
                if args[0] == "clone":
                    clone = Path(args[-1])
                    checkout_paths.append(clone)
                    (clone / "skills" / "local-science").mkdir(parents=True)
                    (clone / "skills" / "local-science" / "SKILL.md").write_text(
                        "---\nname: local-science\ndescription: unit fixture\nlicense: MIT\n---\nLocal science notes.\n", encoding="utf8")
                    return ""
                if "rev-parse" in args:
                    return commit
                if "ls-tree" in args:
                    return "skills/local-science/SKILL.md\n"
                return ""

            with patch.object(core, "_remote_head", return_value=commit), patch.object(core, "_git", side_effect=fixture_git):
                staged = core.stage_domain_skill(str(project), "fixture/repository", "local-science")
            self.assertEqual(staged["scan"]["status"], "PASS")
            base = io_path(project / core.STATE_DIR / "quarantine" / "local-science" / commit)
            self.assertGreater(len(str(base / "manifest.json")), 260)
            self.assertTrue((base / "manifest.json").is_file())
            self.assertFalse(checkout_paths[0].exists())
            self.assertNotIn(str(project), str(checkout_paths[0]))
            self.assertFalse(core.domain_skill_status(str(project))["admitted"])
            with self.assertRaisesRegex(core.DomainSkillError, "optimization rounds"):
                core.admit_domain_skill(str(project), "local-science", "domain_only", "domain_skill")
            (base / "content" / "SKILL.md").write_text("changed", encoding="utf8")
            with self.assertRaisesRegex(core.DomainSkillError, "changed after"):
                core.scan_domain_skill(str(project), "local-science", commit)
            project.resolve().relative_to(Path(directory).resolve())
            shutil.rmtree(io_path(project))

    def test_temporary_checkout_removed_after_operation_failure(self):
        checkout = None
        with self.assertRaisesRegex(RuntimeError, "fixture failure"):
            with core._temporary_checkout() as checkout:
                checkout.mkdir()
                (checkout / "file.txt").write_text("fixture", encoding="utf8")
                raise RuntimeError("fixture failure")
        self.assertFalse(checkout.exists())


if __name__ == "__main__":
    unittest.main()
