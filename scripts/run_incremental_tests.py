from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resource_guard import (
    LEAN_ORCHESTRATOR_RESERVE_BYTES, LEAN_TRIM_TRIGGER_BYTES, LEAN_WORKER_LIMIT_BYTES,
    ORCHESTRATOR_RESERVE_BYTES, WORKER_JOB_LIMIT_BYTES,
    require_orchestrator_budget, require_start_headroom, run_managed,
)


PLUGIN = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT_ROOT = PLUGIN / "evals" / "incremental-tests"
LEAN_TEST_FILE = "test_p1_round3_lean.py"


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _safe_suite_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_-]+", "-", value.casefold()).strip("-")
    if not normalized:
        raise ValueError("suite name is empty")
    return normalized


def _diagnostic_tail(value: str, limit: int = 4000) -> str:
    """Keep a short, non-secret failure hint in the CI summary.

    Test output is normally retained in the per-file receipt, but a failed
    CI job stops before receipts can be uploaded.  The diagnostic is bounded
    and redacts common token-shaped values so a public workflow log remains
    useful without becoming a dump of the child process environment.
    """
    text = str(value or "")[-limit:]
    text = re.sub(r"(?i)(gh[pousr]_[A-Za-z0-9_\-]{12,}|github_pat_[A-Za-z0-9_\-]{12,})", "<redacted-token>", text)
    text = re.sub(r"(?i)(authorization\s*[:=]\s*(?:bearer|token)\s+)[^\s]+", r"\1<redacted>", text)
    return text


def _test_execution_order(path: Path) -> tuple[int, str]:
    """Run the tight-orchestrator Lean profile before the long-lived process grows."""
    return (0 if path.name == LEAN_TEST_FILE else 1, path.as_posix())


def run(
    patterns: list[str], suite: str, *, resume: bool = True,
    env: dict[str, str] | None = None, extra_contract: dict[str, str] | None = None,
) -> dict[str, Any]:
    # Old resume/extra_contract arguments remain accepted; requested tests
    # always run and their actual output is recorded. No source digest scan.
    # Normalize at call time too: temporary or injected roots may use an OS
    # path alias, while the discovered test files resolve to its target.
    plugin_root = PLUGIN.resolve()
    require_start_headroom()
    require_orchestrator_budget()
    tests: list[Path] = []
    for pattern in patterns:
        tests.extend(plugin_root.joinpath("tests").glob(pattern))
    tests = sorted(
        {path.resolve() for path in tests if path.is_file()},
        key=_test_execution_order,
    )
    if not tests:
        raise RuntimeError(f"no tests match: {patterns}")
    receipt_root = DEFAULT_RECEIPT_ROOT.resolve() / _safe_suite_name(suite)
    results: list[dict[str, Any]] = []
    for test_file in tests:
        require_orchestrator_budget()
        receipt_path = receipt_root / f"{test_file.stem}.json"
        module = f"tests.{test_file.stem}"
        lean_profile = LEAN_TEST_FILE == test_file.name
        completed = run_managed(
            [
                sys.executable, "-X", "utf8", "-m", "unittest", "discover",
                "-s", "tests", "-p", test_file.name, "-v",
            ],
            cwd=plugin_root, env=env, timeout=600,
            maximum_job_bytes=LEAN_WORKER_LIMIT_BYTES if lean_profile else WORKER_JOB_LIMIT_BYTES,
            maximum_orchestrator_bytes=(
                LEAN_ORCHESTRATOR_RESERVE_BYTES if lean_profile else ORCHESTRATOR_RESERVE_BYTES
            ),
            trim_trigger_bytes=LEAN_TRIM_TRIGGER_BYTES if lean_profile else None,
        )
        record = {
            "schema_version": 1,
            "test_file": test_file.relative_to(plugin_root).as_posix(),
            "module": module,
            "resource_profile": "lean" if lean_profile else "standard",
            "resource_usage": getattr(completed, "resource_usage", {}),
            "returncode": completed.returncode,
            "status": "PASS" if completed.returncode == 0 else "FAIL",
            "stdout_tail": completed.stdout[-50000:],
            "stderr_tail": completed.stderr[-50000:],
            "resumed": False,
        }
        _atomic_json(receipt_path, record)
        results.append(record)
        if completed.returncode != 0:
            # The full tails remain in the local receipt.  This compact hint
            # is printed only for the failing file so hosted CI can explain
            # why later build/install steps were not admitted.
            print(json.dumps({
                "failed_test_file": record["test_file"],
                "returncode": record["returncode"],
                "stderr_tail": _diagnostic_tail(record["stderr_tail"]),
                "stdout_tail": _diagnostic_tail(record["stdout_tail"]),
            }, ensure_ascii=False, indent=2))
            break
    summary = {
        "schema_version": 1, "suite": suite, "patterns": patterns,
        "test_files": len(tests), "completed_files": len(results),
        "passed_files": sum(item["status"] == "PASS" for item in results),
        "resumed_files": sum(bool(item.get("resumed")) for item in results),
        "status": "PASS" if len(results) == len(tests) and all(item["status"] == "PASS" for item in results) else "FAIL",
        "results": [{key: item[key] for key in ("test_file", "status", "returncode", "resumed")} for item in results],
    }
    _atomic_json(receipt_root / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run requested test files serially in bounded workers")
    parser.add_argument("--pattern", action="append", required=True, help="tests/ glob; repeat for multiple groups")
    parser.add_argument("--suite", required=True)
    parser.add_argument("--no-resume", action="store_true")
    arguments = parser.parse_args()
    summary = run(arguments.pattern, arguments.suite, resume=not arguments.no_resume)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
