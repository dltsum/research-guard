from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(PLUGIN / "scripts"))


class P10CycleEPublicPackageTests(unittest.TestCase):
    def test_public_package_excludes_third_party_binary_assets_and_verifies(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "research-guard.zip"
            run = subprocess.run(
                [sys.executable, str(PLUGIN / "scripts" / "build_public_package.py"), "--output", str(output)],
                text=True, capture_output=True, encoding="utf-8", check=True,
            )
            receipt = json.loads(run.stdout)
            self.assertEqual(receipt["status"], "PASS")
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertIn("research-guard/RELEASE_MANIFEST.json", names)
                for required in (
                    "research-guard/INSTALL_PROMPT.md",
                    "research-guard/companions/README.md",
                    "research-guard/companions/README.zh-CN.md",
                    "research-guard/companions/citespace-mcp/server.py",
                    "research-guard/companions/citespace-mcp/.mcp.json",
                    "research-guard/companions/citespace-mcp/bridge/startup-agent.jar",
                    "research-guard/.claude-plugin/plugin.json",
                    "research-guard/kimi.plugin.json",
                    "research-guard/tests/test_p31_flat_fill_evidence.py",
                    "research-guard/tests/test_reference_figure_contract.py",
                    "research-guard/tests/test_figure_connector_turns.py",
                    "research-guard/skills/academic-figure-guard/references/repair-and-layout-playbook.md",
                    "research-guard/.gitignore", "research-guard/.gitattributes",
                    "research-guard/.editorconfig", "research-guard/requirements-dev.txt",
                    "research-guard/REQUIREMENTS.md",
                    "research-guard/.github/workflows/ci.yml",
                    "research-guard/.github/workflows/release.yml",
                    "research-guard/assets/discipline-registry.json",
                    "research-guard/assets/documentation-parity.json",
                    "research-guard/assets/readme/research-guard-evidence-lifecycle.png",
                    "research-guard/assets/readme/asset-provenance.json",
                    "research-guard/docs/DOCUMENTATION_POLICY.md",
                    "research-guard/docs/DOCUMENTATION_POLICY.zh-CN.md",
                    "research-guard/docs/RESEARCH_CONSOLE_UI.md",
                    "research-guard/docs/RESEARCH_CONSOLE_UI.zh-CN.md",
                    "research-guard/docs/provenance/P23_RESEARCH_CONSOLE_UI.md",
                    "research-guard/docs/provenance/P28_NETWORK_CHANNEL.md",
                    "research-guard/docs/FRONTIER_SKILL_RESEARCH.md",
                    "research-guard/docs/FRONTIER_SKILL_RESEARCH.zh-CN.md",
                    "research-guard/docs/provenance/P24_FRONTIER_SKILL_RESEARCH.md",
                    "research-guard/scripts/frontier_skill_research_core.py",
                    "research-guard/scripts/skillopt_frontier_skill_research.py",
                    "research-guard/tests/test_p24_frontier_skill_research.py",
                    "research-guard/tests/test_p28_network_channel.py",
                    "research-guard/tests/test_network_route_fallback.py",
                    "research-guard/docs/SKILL_PORTABILITY.md",
                    "research-guard/docs/SKILL_PORTABILITY.zh-CN.md",
                    "research-guard/docs/provenance/P25_SKILL_PORTABILITY.md",
                    "research-guard/docs/provenance/P25_SKILL_PORTABILITY.zh-CN.md",
                    "research-guard/scripts/skill_portability_core.py",
                    "research-guard/scripts/skillopt_skill_portability.py",
                    "research-guard/tests/test_p25_skill_portability.py",
                    "research-guard/scripts/documentation_parity.py",
                    "research-guard/tests/test_documentation_parity.py",
                    "research-guard/scripts/discipline_profile_core.py",
                    "research-guard/tests/test_p14_cross_discipline.py",
                ):
                    self.assertIn(required, names)
                self.assertFalse(any(name.casefold().endswith((".pdf", ".html", ".pyc")) for name in names))
                self.assertFalse(any("/evals/" in name or "/.research-guard/" in name or "/__pycache__/" in name for name in names))
                self.assertFalse(any("/addons/" in name or "/research_console/" in name for name in names))
                manifest = json.loads(archive.read("research-guard/RELEASE_MANIFEST.json"))
                self.assertFalse(manifest["third_party_binary_assets_included"])
                self.assertEqual(manifest["optional_addons_included"], [])
                self.assertIn("optional UI add-ons", manifest["excluded_classes"])
                self.assertIsNone(archive.testzip())
                for item in manifest["files"]:
                    self.assertIn("research-guard/" + item["path"], names)
                    self.assertNotIn("sha256", item)
                archive.extractall(temporary)
            root = Path(temporary) / "research-guard"
            env = os.environ.copy()
            env["PYTHONPATH"] = str(root / "scripts")
            check = subprocess.run(
                [sys.executable, "-X", "utf8", "-c",
                 "from mcp_server import TOOLS; from ccf_catalog_core import load_catalog; c=load_catalog(); print(len(TOOLS),len(c['entries']),c['counts'])"],
                cwd=root, env=env, text=True, capture_output=True, encoding="utf-8", check=True,
            )
            self.assertIn("17 183 {'A': 58, 'B': 125}", check.stdout)

    def test_public_docs_and_notices_exist(self):
        for relative in (
            "README.md", "README.zh-CN.md", "REQUIREMENTS.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
            "requirements-core.txt", "requirements-dev.txt",
            ".gitignore", ".gitattributes", ".editorconfig", ".github/workflows/ci.yml",
            ".github/workflows/release.yml", "GOVERNANCE.md", "SUPPORT.md",
            "docs/ARCHITECTURE.md", "docs/DISCIPLINE_SUPPORT.md", "docs/EDUCATION_SUPPORT.md", "docs/UPSTREAM_AUDIT.md",
            "docs/DOCUMENTATION_POLICY.md", "docs/DOCUMENTATION_POLICY.zh-CN.md",
            "docs/RESEARCH_CONSOLE_UI.md", "docs/RESEARCH_CONSOLE_UI.zh-CN.md",
            "docs/SKILL_PORTABILITY.md", "docs/SKILL_PORTABILITY.zh-CN.md",
            "assets/documentation-parity.json", "assets/readme/research-guard-evidence-lifecycle.png",
        ):
            self.assertTrue((PLUGIN / relative).is_file(), relative)

    def test_readme_first_screen_has_one_copy_paste_install_path(self):
        readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
        first_screen = "\n".join(readme.splitlines()[:80])
        for token in ("scripts/component_install.py", "--components literature", "--verify", "INSTALL_PROMPT.md", "--install-python-deps"):
            self.assertIn(token, first_screen)
        self.assertNotIn("fresh-absolute-directory", first_screen)
        requirements = (PLUGIN / "REQUIREMENTS.md").read_text(encoding="utf-8")
        for dependency in ("Python 3.11", "Pint", "SymPy", "Lean", "TeX", "MCP"):
            self.assertIn(dependency, requirements)


if __name__ == "__main__":
    unittest.main()
