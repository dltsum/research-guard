from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import sys
import unittest
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--pattern", default="test_*.py")
    args = parser.parse_args()
    plugin = Path(__file__).resolve().parents[1]
    suite = unittest.defaultTestLoader.discover(str(plugin / "tests"), pattern=args.pattern)
    stream = io.StringIO()
    started = dt.datetime.now(dt.timezone.utc)
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    ended = dt.datetime.now(dt.timezone.utc)
    output = stream.getvalue()
    evidence = plugin / "evals" / f"iteration-{args.iteration:02d}"
    evidence.mkdir(parents=True, exist_ok=True)
    attempts = sorted(evidence.glob("attempt-*"))
    attempt = evidence / f"attempt-{len(attempts) + 1:02d}"
    attempt.mkdir()
    (attempt / "unittest.txt").write_text(output, encoding="utf-8")
    summary = {
        "iteration": args.iteration,
        "attempt": len(attempts) + 1,
        "pattern": args.pattern,
        "started_at": started.replace(microsecond=0).isoformat(),
        "ended_at": ended.replace(microsecond=0).isoformat(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "successful": result.wasSuccessful(),
    }
    (attempt / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (plugin / "evals" / "work-log.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(summary, sort_keys=True) + "\n")
    sys.stdout.write(output)
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
