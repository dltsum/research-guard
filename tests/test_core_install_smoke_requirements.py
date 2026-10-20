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
        verifier = (root / "scripts/verify_isolated_install.py").read_text(encoding="utf8")
        probes = re.search(r'probe_modules = "([A-Za-z0-9_,]+)" if os.name == "nt" else "([A-Za-z0-9_,]+)"', verifier)
        self.assertIsNotNone(probes, "Verifier must explicitly select the platform bundle")
        self.assertEqual(set(probes.group(1).split(',')), expected - {"psutil", "yaml"})
        self.assertEqual(set(probes.group(2).split(',')), expected)
        self.assertIn('f"import json,{probe_modules};', verifier)


if __name__ == "__main__":
    unittest.main()
