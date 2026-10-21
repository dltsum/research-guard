"""Smoke imports must match the dependencies actually shipped per platform."""
import re
import unittest
from pathlib import Path


class CoreInstallSmokeTests(unittest.TestCase):
    def test_core_install_and_verifier_smokes_cover_all_requirements(self):
        root = Path(__file__).resolve().parents[1]
        module_names = {"pillow": "PIL", "pyyaml": "yaml", "z3-solver": "z3"}
        expected = set()
        for line in (root / "requirements-core.txt").read_text(encoding="utf8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            package = re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].strip().lower()
            expected.add(module_names.get(package, package.replace("-", "_")))
        self.assertIn("psutil", expected)
        for source in ["scripts/install.ps1", "scripts/install_posix.py"]:
            with self.subTest(source=source):
                text = (root / source).read_text(encoding="utf8")
                imports = [set(names.split(",")) for names in re.findall(r"import ([A-Za-z0-9_,]+)", text)]
                shipped = expected - {"psutil", "yaml"} if source.endswith(".ps1") else expected
                # The pinned Windows payload uses native resource telemetry
                # and does not ship psutil/PyYAML; POSIX installs both.
                self.assertTrue(any(shipped <= names for names in imports),
                                f"{source} lacks the platform import smoke: {sorted(shipped)}")
    def test_selected_core_diagnostic_uses_its_actual_dependencies(self):
        import tempfile
        import sys
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "scripts"))
        from component_install import install_components
        from verify_isolated_install import verify
        with tempfile.TemporaryDirectory() as temporary:
            user_root = Path(temporary)
            install_components(root, user_root / "plugins/research-guard", ["core"])
            result = verify(user_root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["installation_diagnostic"]["runtime_check"], "NOT_REQUIRED_STDLIB")
        self.assertGreater(result["mcp_tools"], 0)



if __name__ == "__main__":
    unittest.main()
