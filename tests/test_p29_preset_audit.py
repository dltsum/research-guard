from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "scripts"))

from preset_audit import audit_repository  # noqa: E402


def _minimal_policy_root(root: Path) -> None:
    (root / "assets").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    required = (
        "assets/resource-policy.json", "assets/llm-delegation-policy.json", "scripts/network_config_core.py",
        "scripts/resource_guard.py", "scripts/mcp_launcher.py", "scripts/research_guard_core.py", "scripts/install_posix.py",
        "scripts/install_lean_mathlib.ps1", "scripts/audit_research_upstreams.py",
        "scripts/academic_figure_core.py", "addons/research-console/research_console/static/styles.css",
    )
    for relative in required:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)


class PresetAuditTests(unittest.TestCase):
    def test_complete_checkout_has_no_unapproved_host_preset(self) -> None:
        report = audit_repository(ROOT)
        self.assertEqual(report["status"], "PASS", report["violations"][:10])
        self.assertGreater(report["scan"]["files_scanned"], 100)
        self.assertGreater(report["scan"]["binary_or_non_utf8_files_skipped"], 0)
        self.assertGreaterEqual(report["scan"]["archive_text_bytes_scanned"], 1)
        self.assertTrue(report["policy_bindings"])

        inventory = {item["category"]: item for item in report["mechanism_inventory"]}
        expected = {
            "path_resolution", "platform_detection", "locale_timezone", "font_selection",
            "environment_override", "network_client", "network_route_control",
            "package_index_control", "credential_input", "subprocess_launch",
            "resource_control", "archive_lifecycle", "provenance_receipt",
        }
        self.assertTrue(expected <= set(inventory))
        self.assertTrue(all(item["occurrences"] > 0 for item in inventory.values()))
        self.assertTrue(all("snippet" not in example and "match" not in example for item in inventory.values() for example in item["examples"]))

    def test_concrete_path_is_a_violation_but_explicit_fixture_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _minimal_policy_root(root)
            bad_path = "C:" + "\\Users\\someone\\cache"
            (root / "bad.py").write_text(f"CACHE = {bad_path!r}\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "fixture.py").write_text(
                'PROXY = "http://127.0.0.1:7897"\n', encoding="utf-8"
            )
            report = audit_repository(root, policy_path=ROOT / "assets/preset-audit-policy.json")
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(item["category"] == "literal_user_path" for item in report["violations"]))
        self.assertTrue(any(item["category"] == "fixed_local_endpoint" for item in report["allowed_findings"]))

    def test_absolute_path_is_reported_separately_from_user_home(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _minimal_policy_root(root)
            (root / "bad.py").write_text("CACHE = 'C:/Program Files/Research Guard/cache'\n", encoding="utf-8")
            report = audit_repository(root, policy_path=ROOT / "assets/preset-audit-policy.json")
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(item["category"] == "literal_absolute_path" for item in report["violations"]))

    def test_runtime_preset_categories_cover_locale_fonts_and_ambient_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _minimal_policy_root(root)
            (root / "bad.py").write_text(
                "import locale, os\n"
                "HOST_LOCALE = locale.getlocale()\n"
                "STYLE = {'font-family': 'Arial'}\n"
                "INDEX = os.environ.get('PIP_INDEX_URL')\n"
                "CHILD_ENV = dict(os.environ)\n",
                encoding="utf-8",
            )
            report = audit_repository(root, policy_path=ROOT / "assets/preset-audit-policy.json")
        self.assertEqual(report["status"], "FAIL")
        categories = {item["category"] for item in report["violations"]}
        self.assertTrue({"host_locale_inference", "host_font_preset", "ambient_package_index_read", "ambient_environment_inheritance"} <= categories)

    def test_optional_credential_reads_are_visible_and_documented(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _minimal_policy_root(root)
            with (root / "scripts" / "research_guard_core.py").open("a", encoding="utf-8") as handle:
                handle.write('KEY = os.environ.get("OPENALEX_API_KEY")\n')
            report = audit_repository(root, policy_path=ROOT / "assets/preset-audit-policy.json")
        self.assertEqual(report["status"], "PASS", report["violations"])
        self.assertTrue(any(item["category"] == "ambient_credential_read" for item in report["allowed_findings"]))

    def test_zip_members_are_scanned_with_visible_limits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _minimal_policy_root(root)
            with zipfile.ZipFile(root / "bundle.zip", "w") as archive:
                archive.writestr("config.py", "CACHE = 'C:/Program Files/Research Guard/cache'\n")
            report = audit_repository(root, policy_path=ROOT / "assets/preset-audit-policy.json")
        self.assertEqual(report["status"], "FAIL")
        self.assertGreaterEqual(report["scan"]["archives_inspected"], 1)
        self.assertGreaterEqual(report["scan"]["archive_entries_scanned"], 1)
        self.assertTrue(any("bundle.zip::config.py" in item["path"] for item in report["violations"]))

    def test_tar_members_are_scanned_with_visible_limits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _minimal_policy_root(root)
            payload = root / "config.py"
            payload.write_text("CACHE = 'C:/Program Files/Research Guard/cache'\n", encoding="utf-8")
            with tarfile.open(root / "bundle.tar.gz", "w:gz") as archive:
                archive.add(payload, arcname="config.py")
            payload.unlink()
            report = audit_repository(root, policy_path=ROOT / "assets/preset-audit-policy.json")
        self.assertEqual(report["status"], "FAIL")
        self.assertGreaterEqual(report["scan"]["archives_inspected"], 1)
        self.assertGreaterEqual(report["scan"]["archive_entries_scanned"], 1)
        self.assertTrue(any("bundle.tar.gz::config.py" in item["path"] for item in report["violations"]))

    def test_symlink_entries_are_visible_and_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _minimal_policy_root(root)
            target = root / "outside.py"
            target.write_text("CACHE = 'C:/Program Files/Research Guard/cache'\n", encoding="utf-8")
            link = root / "linked.py"
            try:
                os.symlink(target, link)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            report = audit_repository(root, policy_path=ROOT / "assets/preset-audit-policy.json")
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["scan"]["symlink_entries_skipped"], 1)
        self.assertTrue(any(item["path"] == "linked.py" and item["reason"] == "symlink-not-followed" for item in report["skipped_files"]))
        self.assertFalse(any(item.get("path") == "linked.py" for item in report["violations"]))

    def test_utf8_sample_boundary_does_not_hide_valid_multibyte_text(self) -> None:
        # The scanner samples bytes before opening the full text file. Place a
        # three-byte character across that boundary to catch false skips.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _minimal_policy_root(root)
            path = root / "boundary.md"
            path.write_text("a" * 8191 + "汉" + "\n", encoding="utf-8")
            report = audit_repository(root, policy_path=ROOT / "assets/preset-audit-policy.json")
        self.assertEqual(report["status"], "PASS", report["violations"])
        self.assertNotIn("boundary.md", {item["path"] for item in report["skipped_files"]})

    def test_generated_audit_receipt_is_skipped_without_recursive_growth(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _minimal_policy_root(root)
            state = root / ".research-guard"
            state.mkdir()
            (state / "preset-audit.json").write_text(
                '{"old_host_path": "C:/Program Files/old"}\n', encoding="utf-8"
            )
            report = audit_repository(root, policy_path=ROOT / "assets/preset-audit-policy.json")
        self.assertEqual(report["status"], "PASS", report["violations"])
        self.assertEqual(report["scan"]["generated_audit_receipts_skipped"], 1)

    def test_mcp_maintenance_route_delegates_to_the_same_audit(self) -> None:
        import mcp_server

        with patch.object(mcp_server, "audit_repository", return_value={"status": "PASS"}) as audit:
            result = mcp_server.dispatch(
                "research_design",
                {
                    "action": "status",
                    "project_root": "project",
                    "maintenance_action": "preset-audit",
                    "maintenance_project_root": "project",
                    "maintenance_policy": "policy.json",
                    "maintenance_include_ignored": True,
                },
            )
        self.assertEqual(result, {"status": "PASS"})
        audit.assert_called_once_with(
            "project", policy_path="policy.json", include_ignored=True,
        )

    def test_no_ignored_option_really_excludes_generated_development_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _minimal_policy_root(root)
            development = root / "docs" / "development"
            development.mkdir(parents=True)
            historical_path = "C:" + "\\Users\\historical\\path"
            (development / "history.md").write_text(f"OLD = {historical_path!r}\n", encoding="utf-8")
            report = audit_repository(root, policy_path=ROOT / "assets/preset-audit-policy.json", include_ignored=False)
        self.assertEqual(report["status"], "PASS", report["violations"])
        self.assertIn("excluding .git and repository-generated ignored paths", report["scope"])


if __name__ == "__main__":
    unittest.main()
