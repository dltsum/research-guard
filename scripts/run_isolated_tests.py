"""Run test modules serially in separate interpreters, preserving production limits."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


def _write(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")
    temporary.replace(path)


def run_modules(test_dir: Path, output: Path, *, python: str = sys.executable,
                pattern: str = "test_*.py", timeout: float = 600) -> dict:
    test_dir, output = test_dir.resolve(), output.resolve()
    modules = sorted(path for path in test_dir.glob(pattern) if path.is_file() and path.suffix == ".py")
    if not modules:
        raise ValueError(f"No test modules matched {test_dir / pattern}")
    output.mkdir(parents=True, exist_ok=True)
    summary = {"status": "RUNNING", "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
               "mode": "one fresh subprocess per test module; concurrency=1; production resource limits unchanged",
               "test_dir": str(test_dir), "python": str(Path(python).resolve()), "pattern": pattern,
               "module_count": len(modules), "modules": [], "counts": {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}}
    manifest = output / "isolated-suite.json"
    _write(manifest, summary)
    for index, module in enumerate(modules, 1):
        command = [summary["python"], "-X", "utf8", "-m", "unittest", "discover", "-s", str(test_dir), "-p", module.name, "-v"]
        started = time.monotonic()
        record = {"module": module.name, "command": command, "cwd": str(test_dir.parent), "status": "RUNNING"}
        environment = {**os.environ, "PYTHONUTF8": "1"}
        try:
            run = subprocess.run(command, cwd=test_dir.parent, env=environment, capture_output=True,
                                 text=True, encoding="utf8", errors="replace", timeout=timeout)
            stdout, stderr, returncode = run.stdout, run.stderr, run.returncode
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout or ""
            stderr = error.stderr or ""
            stdout = stdout.decode("utf8", "replace") if isinstance(stdout, bytes) else stdout
            stderr = stderr.decode("utf8", "replace") if isinstance(stderr, bytes) else stderr
            returncode = None
        combined = stdout + "\n" + stderr
        match = re.search(r"Ran (\d+) tests? in ([\d.]+)s", combined)
        counts = {"tests": int(match.group(1)) if match else 0,
                  **{name: int(re.search(rf"\b{name}=(\d+)", combined).group(1))
                     if re.search(rf"\b{name}=(\d+)", combined) else 0 for name in ["failures", "errors", "skipped"]}}
        stdout_path, stderr_path = output / f"{module.stem}.stdout.txt", output / f"{module.stem}.stderr.txt"
        stdout_path.write_text(stdout, encoding="utf8")
        stderr_path.write_text(stderr, encoding="utf8")
        status = "TIMEOUT" if returncode is None else "PASS" if returncode == 0 and match else "FAIL"
        record.update(status=status, returncode=returncode, duration_seconds=round(time.monotonic() - started, 4),
                      counts=counts, stdout_file=str(stdout_path), stderr_file=str(stderr_path))
        summary["modules"].append(record)
        for name, value in counts.items():
            summary["counts"][name] += value
        _write(output / f"{module.stem}.json", record)
        _write(manifest, summary)
        print(f"[{index}/{len(modules)}] {module.name}: {status} ({counts['tests']} tests)", flush=True)
    summary["status"] = "PASS" if all(item["status"] == "PASS" for item in summary["modules"]) else "FAIL"
    summary["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    _write(manifest, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-dir", type=Path, default=Path("tests"))
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()
    result = run_modules(args.test_dir, args.output, python=args.python, pattern=args.pattern, timeout=args.timeout)
    print(json.dumps({key: result[key] for key in ["status", "module_count", "counts"]}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
