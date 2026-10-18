"""The runtime smoke must cover every top-level core dependency, including psutil."""
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
        for source in ["scripts/install.ps1", "scripts/install_posix.py", "scripts/verify_isolated_install.py"]:
            with self.subTest(source=source):
                text = (root / source).read_text(encoding="utf8")
                imports = [set(names.split(",")) for names in re.findall(r"import ([A-Za-z0-9_,]+)", text)]
                # One real child import smoke must cover the full core set;
                # unrelated imports elsewhere in an installer do not count.
                self.assertTrue(any(expected <= names for names in imports),
                                f"{source} lacks a complete core import smoke: {sorted(expected)}")


if __name__ == "__main__":
    unittest.main()
