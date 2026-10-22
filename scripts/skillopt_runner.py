"""Shared execution and logs for SkillOpt experiments, without static scoring."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

from resource_guard import ResourceGuardError, run_managed


def create_run_root(output_root: Path) -> Path:
    run_root = output_root.expanduser().resolve() / dt.datetime.now(dt.timezone.utc).strftime("run-%Y%m%dT%H%M%S%fZ")
    run_root.mkdir(parents=True)
    return run_root


def run_command(
    command: list[str], *, cwd: Path, run_root: Path, prefix: str,
    timeout: float = 900, env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute once and retain actual output; requested repeats stay explicit."""
    try:
        completed = run_managed(command, cwd=cwd, env=env, timeout=timeout)
        stdout, stderr = completed.stdout or "", completed.stderr or ""
        record = {
            "status": "PASS" if completed.returncode == 0 else "FAIL",
            "returncode": completed.returncode,
            "resource_usage": completed.resource_usage,
        }
    except ResourceGuardError as exc:
        stdout, stderr = "", str(exc) + "\n"
        record = {"status": "FAIL", "returncode": None, "execution_error": str(exc)}
    stdout_path = run_root / f"{prefix}.stdout.log"
    stderr_path = run_root / f"{prefix}.stderr.log"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    match = re.search(r"Ran (\d+) tests?", stderr)
    skipped = re.search(r"skipped=(\d+)", stderr)
    record.update({
        "command": command,
        "stdout_log": str(stdout_path), "stderr_log": str(stderr_path),
        "stdout_tail": stdout[-10_000:], "stderr_tail": stderr[-10_000:],
        "test_count": int(match.group(1)) if match else 0,
        "skipped_tests": int(skipped.group(1)) if skipped else 0,
    })
    return record


def run_regression(
    test_arguments: list[str], *, cwd: Path, run_root: Path, prefix: str,
    timeout: float = 900, env: dict[str, str] | None = None,
) -> dict[str, Any]:
    command = [sys.executable, "-X", "utf8", "-m", "unittest", *test_arguments, "-v"]
    record = run_command(command, cwd=cwd, run_root=run_root, prefix=prefix, timeout=timeout, env=env)
    if not record["test_count"]:
        record.update(status="FAIL", execution_error=record.get("execution_error", "no completed unittest execution was reported"))
    return record


def write_report(report: dict[str, Any], run_root: Path) -> int:
    report["run_root"] = str(run_root)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    (run_root / "report.json").write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "PASS" else 1


def run_experiment(
    description: str, test_arguments: list[str], *, output_root: Path,
    timeout: float = 900,
) -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--rounds", type=int, default=1, help="Actual suite executions; default: 1")
    parser.add_argument("--output-root", type=Path, default=output_root, help="Directory for a run report and complete test logs")
    arguments = parser.parse_args()
    if arguments.rounds < 1:
        parser.error("--rounds must be positive")
    run_root = create_run_root(arguments.output_root)
    rounds = []
    for index in range(1, arguments.rounds + 1):
        record = run_regression(
            test_arguments, cwd=Path(__file__).resolve().parents[1],
            run_root=run_root, prefix=f"round-{index:02d}", timeout=timeout,
        )
        rounds.append({"round": index, **record})
        if record["status"] != "PASS":
            break
    report = {
        "schema_version": 3,
        "experiment": description,
        "status": "PASS" if len(rounds) == arguments.rounds and all(item["status"] == "PASS" for item in rounds) else "FAIL",
        "requested_rounds": arguments.rounds, "round_count": len(rounds), "rounds": rounds,
        "evidence_scope": "Actual local regressions; repeated executions are not independent scientific replication.",
    }
    return write_report(report, run_root)
