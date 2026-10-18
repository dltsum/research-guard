"""Regression for the long-path failure observed during real MCP acceptance."""
import sys
import tempfile
import shutil
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from evidence_kernel import EvidenceRecorder, EvidencePersistenceError, evidence_scope, io_path, verify_evidence_manifest
from research_guard_core import _request, _atomic_json
from discipline_profile_core import _atomic_json as discipline_atomic, _sha256


class EvidencePathTests(unittest.TestCase):
    def test_long_project_records_resumes_and_verifies_raw_response(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / ("project-" + "x" * 115) / ("nested-" + "y" * 60)
            io_path(root).mkdir(parents=True)
            recorder = EvidenceRecorder(root, "v0001-20261018T181403Z-1fe87d4e")
            recorder.record_fixture(source="crossref", query_id="q-exact-mechanism", query="residual learning", payload={"actual": "local regression only"})
            relative, manifest = recorder.finalize(method_version=1, method_hash="method", query_plan_hash="plan", query_runs=[])
            self.assertGreater(len(str(root / manifest["attempts"][0]["raw_path"])), 260)
            self.assertEqual(verify_evidence_manifest(root, relative), [])
            self.assertEqual(len(EvidenceRecorder(root, recorder.run_id, resume=True).attempts), 1)
            _atomic_json(root / ".research-guard" / "search-progress" / ("progress-" + "z" * 45 + ".json"), {"saved": True})
            profile_evidence = root / ".research-guard" / "discipline-profiles" / ("field-" + "a" * 35) / "evidence" / "openalex-4485715981ac3b0e.json"
            discipline_atomic(profile_evidence, {"records": []})
            self.assertEqual(len(_sha256(profile_evidence)), 64)
            # Scope cleanup to this test-owned, verified temporary child.
            root.resolve().relative_to(Path(directory).resolve())
            shutil.rmtree(io_path(root))

    def test_local_write_failure_is_not_transport_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = EvidenceRecorder(directory, "write-failure")
            response = BytesIO(b'{"message": {}}')
            response.status = 200
            response.headers = None
            opener = Mock()
            opener.open.return_value = response
            with patch("research_guard_core.urllib.request.build_opener", return_value=opener), patch("evidence_kernel._atomic_bytes", side_effect=OSError("disk unavailable")), evidence_scope(recorder, source="crossref", query_id="q1", query="residual"):
                with self.assertRaisesRegex(EvidencePersistenceError, "local evidence"):
                    _request("https://api.crossref.org/works", timeout=1)
            self.assertEqual(opener.open.call_count, 1)


if __name__ == "__main__":
    unittest.main()
