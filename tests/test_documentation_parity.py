from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from documentation_parity import (  # noqa: E402
    DocumentationParityError,
    refresh_hashes,
    validate_documentation,
)


ZERO_SHA256 = "0" * 64


def _write_minimal_contract(root: Path) -> None:
    (root / "assets").mkdir(parents=True)
    source = (
        "<!-- research-guard-doc-pair: guide | revision: r1 -->\n"
        "# Guide\n\n"
        "## Start\n\n"
        "Shared token.\n\n"
        "## Finish\n\n"
        "Reviewed source.\n"
    )
    translation = (
        "<!-- research-guard-doc-pair: guide | revision: r1 -->\n"
        "# 指南\n\n"
        "## 开始\n\n"
        "Shared token.\n\n"
        "## 完成\n\n"
        "已审阅译文。\n"
    )
    (root / "guide.md").write_text(source, encoding="utf-8", newline="\n")
    (root / "guide.zh-CN.md").write_text(translation, encoding="utf-8", newline="\n")
    manifest = {
        "schema_version": 1,
        "contract_id": "test-bilingual-docs-v1",
        "translation_suffix": ".zh-CN.md",
        "all_translation_files_must_be_registered": True,
        "normalized_newlines": "LF",
        "pairs": [
            {
                "id": "guide",
                "source_language": "en",
                "translation_language": "zh-CN",
                "source_path": "guide.md",
                "translation_path": "guide.zh-CN.md",
                "revision": "r1",
                "source_sha256": ZERO_SHA256,
                "translation_sha256": ZERO_SHA256,
                "pair_sha256": ZERO_SHA256,
                "sections": [
                    {"id": "start", "source_heading": "Start", "translation_heading": "开始"},
                    {"id": "finish", "source_heading": "Finish", "translation_heading": "完成"},
                ],
                "common_tokens": ["Shared token"],
                "source_tokens": ["Reviewed source"],
                "translation_tokens": ["已审阅译文"],
                "required_images": [],
            }
        ],
    }
    (root / "assets" / "documentation-parity.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


class DocumentationParityTests(unittest.TestCase):
    def test_repository_contract_passes_and_audits_shared_image(self) -> None:
        report = validate_documentation(PLUGIN)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["pair_count"], 9)
        self.assertEqual(report["translation_files"], 9)
        self.assertIn("instruction-and-numerical", {item["id"] for item in report["pairs"]})
        self.assertIn("research-console-ui", {item["id"] for item in report["pairs"]})
        self.assertIn("frontier-skill-research", {item["id"] for item in report["pairs"]})
        self.assertIn("skill-portability", {item["id"] for item in report["pairs"]})
        self.assertIn("p25-skill-portability", {item["id"] for item in report["pairs"]})
        self.assertIn("skill-composition", {item["id"] for item in report["pairs"]})
        self.assertIn("p26-skill-composition", {item["id"] for item in report["pairs"]})
        readme = next(item for item in report["pairs"] if item["id"] == "readme")
        self.assertEqual(len(readme["images"]), 1)
        self.assertEqual(readme["images"][0]["width"], 2172)
        self.assertEqual(readme["images"][0]["height"], 724)
        self.assertLessEqual(readme["images"][0]["bytes"], 2 * 1024 * 1024)

    def test_hash_refresh_is_explicit_and_produces_a_valid_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_minimal_contract(root)
            report = refresh_hashes(root)
            self.assertTrue(report["hashes_refreshed"])
            manifest = json.loads((root / "assets" / "documentation-parity.json").read_text(encoding="utf-8"))
            pair = manifest["pairs"][0]
            self.assertNotEqual(pair["source_sha256"], ZERO_SHA256)
            self.assertNotEqual(pair["translation_sha256"], ZERO_SHA256)
            self.assertNotEqual(pair["pair_sha256"], ZERO_SHA256)
            self.assertEqual(validate_documentation(root)["status"], "PASS")

    def test_unregistered_translation_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_minimal_contract(root)
            refresh_hashes(root)
            (root / "orphan.zh-CN.md").write_text("# 未登记\n", encoding="utf-8")
            with self.assertRaisesRegex(DocumentationParityError, "unregistered"):
                validate_documentation(root)

    def test_missing_pair_member_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_minimal_contract(root)
            (root / "guide.zh-CN.md").unlink()
            with self.assertRaisesRegex(DocumentationParityError, "incomplete"):
                validate_documentation(root, check_hashes=False)

    def test_section_drift_fails_before_hash_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_minimal_contract(root)
            translation = root / "guide.zh-CN.md"
            translation.write_text(
                translation.read_text(encoding="utf-8") + "\n## 未登记章节\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(DocumentationParityError, "section skeleton drifted"):
                refresh_hashes(root)

    def test_link_target_drift_fails_before_hash_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_minimal_contract(root)
            (root / "one.md").write_text("one\n", encoding="utf-8")
            (root / "two.md").write_text("two\n", encoding="utf-8")
            source = root / "guide.md"
            translation = root / "guide.zh-CN.md"
            source.write_text(source.read_text(encoding="utf-8") + "\n[Target](one.md)\n", encoding="utf-8")
            translation.write_text(
                translation.read_text(encoding="utf-8") + "\n[目标](two.md)\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(DocumentationParityError, "link target parity drift"):
                refresh_hashes(root)

    def test_content_change_without_hash_refresh_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_minimal_contract(root)
            refresh_hashes(root)
            source = root / "guide.md"
            source.write_text(source.read_text(encoding="utf-8") + "\nNew reviewed detail.\n", encoding="utf-8")
            with self.assertRaisesRegex(DocumentationParityError, "source_sha256 drifted"):
                validate_documentation(root)

    def test_copied_unregistered_pair_is_not_accidentally_admitted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_minimal_contract(root)
            refresh_hashes(root)
            shutil.copyfile(root / "guide.zh-CN.md", root / "copy.zh-CN.md")
            with self.assertRaisesRegex(DocumentationParityError, "registry coverage drift"):
                validate_documentation(root)


if __name__ == "__main__":
    unittest.main()
