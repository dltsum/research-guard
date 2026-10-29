"""Release-boundary regressions, not aesthetic or multi-platform evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_public_package import _include
from component_install import install_components
from mcp_server import handle


class FigureReleaseTests(unittest.TestCase):
    def test_release_versions_match_mcp(self):
        versions = [json.loads((ROOT / path).read_text("utf-8"))["version"]
                    for path in (".codex-plugin/plugin.json",
                                 ".claude-plugin/plugin.json", "kimi.plugin.json")]
        self.assertEqual(len(set(versions)), 1)
        mcp = handle({"id": 1, "method": "initialize", "params": {}})
        self.assertEqual(versions[0].split("+")[0], mcp["result"]["serverInfo"]["version"])
        citation = yaml.safe_load((ROOT / "CITATION.cff").read_text("utf-8"))
        self.assertEqual(citation["version"], mcp["result"]["serverInfo"]["version"])

    def test_public_package_keeps_install_and_figure_reproduction(self):
        for path in ("INSTALL_PROMPT.md", ".claude-plugin/plugin.json", "kimi.plugin.json",
                     "tests/test_reference_figure_contract.py", "tests/test_figure_connector_turns.py",
                     "tests/test_p31_flat_fill_evidence.py", "tests/test_figure_release.py",
                     "docs/FIGURE_WORKFLOW_RELEASE.md", "docs/FIGURE_WORKFLOW_RELEASE.zh-CN.md",
                     "skills/academic-figure-guard/references/repair-and-layout-playbook.md",
                     "skills/academic-figure-guard/references/task-faithful-repair.md"):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())
                self.assertTrue(_include(Path(path)))

    def test_selected_figures_install_retains_revision_guidance(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "installed"
            receipt = install_components(ROOT, target, ["figures"])
            self.assertEqual(receipt["network_operations"], 0)
            for path in ("docs/FIGURE_WORKFLOW_RELEASE.md", "docs/FIGURE_WORKFLOW_RELEASE.zh-CN.md",
                         "skills/academic-figure-guard/references/repair-and-layout-playbook.md",
                         "skills/academic-figure-guard/references/task-faithful-repair.md"):
                self.assertTrue((target / path).is_file(), path)
                self.assertEqual((target / path).read_bytes(), (ROOT / path).read_bytes())


if __name__ == "__main__":
    unittest.main()
