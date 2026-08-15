from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]


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
                    "research-guard/.gitignore", "research-guard/.gitattributes",
                    "research-guard/.editorconfig", "research-guard/requirements-dev.txt",
                    "research-guard/REQUIREMENTS.md",
                    "research-guard/.github/workflows/ci.yml",
                    "research-guard/.github/workflows/release.yml",
                    "research-guard/assets/discipline-registry.json",
                    "research-guard/scripts/discipline_profile_core.py",
                    "research-guard/tests/test_p14_cross_discipline.py",
                ):
                    self.assertIn(required, names)
                self.assertFalse(any(name.casefold().endswith((".pdf", ".html", ".pyc")) for name in names))
                self.assertFalse(any("/evals/" in name or "/.research-guard/" in name or "/__pycache__/" in name for name in names))
                manifest = json.loads(archive.read("research-guard/RELEASE_MANIFEST.json"))
                self.assertFalse(manifest["third_party_binary_assets_included"])
                for item in manifest["files"]:
                    digest = hashlib.sha256()
                    with archive.open("research-guard/" + item["path"]) as handle:
                        for block in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(block)
                    self.assertEqual(digest.hexdigest(), item["sha256"])

                archive.extractall(temporary)
            root = Path(temporary) / "research-guard"
            env = os.environ.copy()
            env["PYTHONPATH"] = str(root / "scripts")
            check = subprocess.run(
                [sys.executable, "-X", "utf8", "-c",
                 "from mcp_server import TOOLS; from ccf_catalog_core import load_catalog; c=load_catalog(); print(len(TOOLS),len(c['entries']),c['counts'])"],
                cwd=root, env=env, text=True, capture_output=True, encoding="utf-8", check=True,
            )
            self.assertIn("15 183 {'A': 58, 'B': 125}", check.stdout)

    def test_public_docs_and_notices_exist(self):
        for relative in (
            "README.md", "REQUIREMENTS.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "requirements-dev.txt",
            ".gitignore", ".gitattributes", ".editorconfig", ".github/workflows/ci.yml",
            ".github/workflows/release.yml", "GOVERNANCE.md", "SUPPORT.md",
            "docs/ARCHITECTURE.md", "docs/DISCIPLINE_SUPPORT.md", "docs/UPSTREAM_AUDIT.md",
        ):
            self.assertTrue((PLUGIN / relative).is_file(), relative)

    def test_readme_first_screen_has_one_copy_paste_install_path(self):
        readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
        first_screen = "\n".join(readme.splitlines()[:80])
        self.assertIn("直接复制给 Agent 安装", first_screen)
        self.assertIn("research-guard-windows-x64-modular.zip", first_screen)
        self.assertIn("SHA256SUMS.txt", first_screen)
        self.assertIn("not_now", first_screen)
        self.assertIn("303,582,309", first_screen)
        self.assertIn("REQUIREMENTS.md", first_screen)
        self.assertNotIn("minimal package", first_screen.casefold())
        requirements = (PLUGIN / "REQUIREMENTS.md").read_text(encoding="utf-8")
        for dependency in ("Python 3.14.3", "Pint", "SymPy", "z3-solver", "Lean", "MiKTeX", "MCP"):
            self.assertIn(dependency, requirements)
        self.assertIn("There is no\nseparate minimal/full package", requirements)


if __name__ == "__main__":
    unittest.main()
