from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from research_guard_core import register_method  # noqa: E402
from research_integrity_core import (  # noqa: E402
    IntegrityError,
    document_status,
    ingest_document,
    register_claim_evidence,
    integrity_status,
)


METHOD = {"title": "Evidence test", "problem": "ground claims", "mechanism": "hash-bound evidence"}


class P12CycleAIngestionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "paper.md").write_text(
            "# Method\n\nThe intervention changed the outcome [@doe2026].\n\nSecond paragraph.\n\n$$y=x+1$$\n",
            encoding="utf-8",
        )
        register_method(self.root, METHOD)

    def tearDown(self):
        self.temp.cleanup()

    def test_text_ingestion_is_idempotent_and_source_bound(self):
        first = ingest_document(self.root, "paper.md", "paper-v1")
        second = ingest_document(self.root, "paper.md", "paper-v1")
        self.assertEqual(first["document_hash"], second["document_hash"])
        self.assertEqual(first["source"]["sha256"], hashlib.sha256((self.root / "paper.md").read_bytes()).hexdigest())
        self.assertEqual(first["method_version"], 1)
        self.assertTrue(first["method_hash"])
        self.assertTrue(first["parsed"]["citations"])
        self.assertTrue(first["parsed"]["formulas"])
        self.assertNotEqual(first["parsed"]["blocks"][0]["locator"], first["parsed"]["blocks"][1]["locator"])
        self.assertIn("start_line", first["parsed"]["formulas"][0]["locator"])
        self.assertIn("start_line", first["parsed"]["citations"][0]["locator"])
        (self.root / "paper.md").write_text("changed", encoding="utf-8")
        self.assertEqual(document_status(self.root, "paper-v1")["status"], "INVALIDATED")
        self.assertEqual(document_status(self.root, "paper-v1")["status"], "INVALIDATED")

    def test_external_parser_requires_locator_provenance(self):
        (self.root / "bad.json").write_text('{"sections": [], "blocks": [{"text": "x"}]}', encoding="utf-8")
        with self.assertRaises(IntegrityError):
            ingest_document(self.root, "paper.md", "external-v1", parser_backend="docling", parser_output_path="bad.json")
        (self.root / "bad-formula.json").write_text(
            '{"sections": [], "blocks": [{"text": "x", "locator": {"page": 1}}], "formulas": [{"text": "x"}]}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(IntegrityError, "formulas item 0"):
            ingest_document(self.root, "paper.md", "external-v2", parser_backend="docling", parser_output_path="bad-formula.json")
        (self.root / "bad-section.json").write_text(
            '{"sections": [{"heading": "Method"}], "blocks": [{"text": "x", "locator": {"page": 1}}]}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(IntegrityError, "section 0"):
            ingest_document(self.root, "paper.md", "external-v3", parser_backend="docling", parser_output_path="bad-section.json")
        (self.root / "fake-locator.json").write_text(
            '{"sections": [{"locator": {"note": "page one"}}], '
            '"blocks": [{"text": "x", "locator": {"note": "somewhere"}}]}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(IntegrityError, "locator needs"):
            ingest_document(self.root, "paper.md", "external-fake", parser_backend="docling", parser_output_path="fake-locator.json")
        (self.root / "normalized.json").write_text(
            '{"parser_version": "test", "sections": [{"heading": "Method", "locator": {"page": 1}}], '
            '"blocks": [{"text": "located block", "locator": {"page": 1, "bbox": [0, 0, 1, 1]}}], '
            '"tables": [{"locator": {"page": 1, "bbox": [0, 0, 1, 1]}}], '
            '"figures": [], "formulas": [], "citations": []}',
            encoding="utf-8",
        )
        accepted = ingest_document(
            self.root, "paper.md", "external-v4", parser_backend="docling",
            parser_output_path="normalized.json",
        )
        self.assertEqual(accepted["status"], "PASS")
        self.assertEqual(accepted["parsed"]["sections"][0]["locator"]["page"], 1)
        self.assertEqual(accepted["parsed"]["sections"][0]["section_id"], "section-0001")
        self.assertEqual(accepted["parsed"]["blocks"][0]["block_id"], "blk-000001")
        (self.root / "duplicate-block.json").write_text(
            '{"sections": [], "blocks": ['
            '{"block_id": "same", "text": "a", "locator": {"page": 1}},'
            '{"block_id": "same", "text": "b", "locator": {"page": 1}}]}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(IntegrityError, "duplicates block_id"):
            ingest_document(
                self.root, "paper.md", "external-duplicate", parser_backend="docling",
                parser_output_path="duplicate-block.json",
            )

    def test_claim_evidence_requires_hash_url_and_user_selection(self):
        ingestion = ingest_document(self.root, "paper.md", "paper-v1")
        source_hash = hashlib.sha256((self.root / "paper.md").read_bytes()).hexdigest()
        claims = [{"claim_id": "c1", "text": "The intervention changes the outcome."}]
        evidence = [{
            "evidence_id": "e1", "kind": "literature", "source_sha256": source_hash,
            "document_id": "paper-v1", "primary_record_url": "https://doi.org/10.1000/test",
            "locator": {**ingestion["parsed"]["blocks"][0]["locator"], "block_id": ingestion["parsed"]["blocks"][0]["block_id"]},
            "excerpt": "The intervention changed the outcome",
        }]
        edges = [{"claim_id": "c1", "evidence_id": "e1", "relation": "supports", "rationale": "The cited result directly measures the claim outcome."}]
        graph = register_claim_evidence(self.root, "graph-v1", claims, evidence, edges, selected_by="user")
        self.assertEqual(graph["status"], "PASS")
        self.assertEqual(graph["evidence"][0]["primary_record_url"], "https://doi.org/10.1000/test")
        incomplete_locator = [{**evidence[0], "locator": {"block_id": ingestion["parsed"]["blocks"][0]["block_id"]}}]
        with self.assertRaisesRegex(IntegrityError, "locator does not identify"):
            register_claim_evidence(
                self.root, "graph-incomplete-locator", claims, incomplete_locator, edges, selected_by="user",
            )
        insufficient = register_claim_evidence(
            self.root, "graph-insufficient", claims, evidence,
            [{**edges[0], "relation": "insufficient"}], selected_by="user",
        )
        self.assertEqual(insufficient["status"], "EVIDENCE_INSUFFICIENT")
        self.assertEqual(insufficient["insufficient_claim_ids"], ["c1"])
        refuted = register_claim_evidence(
            self.root, "graph-refuted", claims, evidence,
            [{**edges[0], "relation": "refutes"}], selected_by="user",
        )
        self.assertEqual(refuted["status"], "CLAIMS_REFUTED")
        self.assertEqual(refuted["refuted_claim_ids"], ["c1"])
        (self.root / "paper.md").write_text("changed after graph", encoding="utf-8")
        document_status(self.root, "paper-v1")
        self.assertEqual(integrity_status(self.root, "evidence_graphs", "graph-v1")["status"], "INVALIDATED")
        (self.root / "paper.md").write_text(
            "# Method\n\nThe intervention changed the outcome [@doe2026].\n\nSecond paragraph.\n\n$$y=x+1$$\n",
            encoding="utf-8",
        )
        with self.assertRaises(IntegrityError):
            register_claim_evidence(self.root, "graph-v2", claims, evidence, edges, selected_by="agent")
        forged = [dict(evidence[0], source_sha256="0" * 64)]
        with self.assertRaises(IntegrityError):
            register_claim_evidence(self.root, "graph-v3", claims, forged, edges, selected_by="user")
        registry_path = self.root / "registry.json"
        registry_path.write_text('{"id":"trial-1"}', encoding="utf-8")
        registry_evidence = [{
            "evidence_id": "registry-1", "kind": "registry",
            "source_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
            "source_path": "registry.json", "locator": {"json_pointer": "/id"},
            "excerpt": "trial-1",
        }]
        with self.assertRaisesRegex(IntegrityError, "clickable HTTPS"):
            register_claim_evidence(self.root, "graph-registry", claims, registry_evidence, [{
                "claim_id": "c1", "evidence_id": "registry-1", "relation": "supports",
                "rationale": "The official registry record directly reports the claimed trial.",
            }], selected_by="user")
        fabricated = [{**registry_evidence[0], "primary_record_url": "https://example.org/trial-1", "excerpt": "not in source"}]
        with self.assertRaisesRegex(IntegrityError, "absent from the located source"):
            register_claim_evidence(self.root, "graph-fabricated", claims, fabricated, [{
                "claim_id": "c1", "evidence_id": "registry-1", "relation": "supports",
                "rationale": "The registry export is claimed to contain this result directly.",
            }], selected_by="user")
        unresolved = [{
            **registry_evidence[0], "primary_record_url": "https://example.org/trial-1",
            "locator": {"json_pointer": "/missing"},
        }]
        with self.assertRaisesRegex(IntegrityError, "json_pointer does not resolve"):
            register_claim_evidence(self.root, "graph-unresolved", claims, unresolved, [{
                "claim_id": "c1", "evidence_id": "registry-1", "relation": "supports",
                "rationale": "The registry field is claimed to support this result directly.",
            }], selected_by="user")


if __name__ == "__main__":
    unittest.main()
