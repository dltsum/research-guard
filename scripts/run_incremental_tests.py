from __future__ import annotations

import argparse
import ast
import hashlib
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_local_module(module: str) -> Path | None:
    parts = module.split(".")
    candidates = [
        PLUGIN.joinpath(*parts).with_suffix(".py"),
        PLUGIN.joinpath(*parts, "__init__.py"),
        PLUGIN.joinpath("scripts", parts[-1]).with_suffix(".py"),
        PLUGIN.joinpath("tests", parts[-1]).with_suffix(".py"),
    ]
    return next((path.resolve() for path in candidates if path.is_file()), None)


def _literal_project_path(node: ast.AST) -> Path | None:
    if isinstance(node, ast.Name) and node.id in {"PLUGIN", "ROOT", "PLUGIN_ROOT"}:
        return PLUGIN
    if (
        isinstance(node, ast.BinOp)
        and isinstance(node.op, ast.Div)
        and isinstance(node.right, ast.Constant)
        and isinstance(node.right.value, str)
    ):
        parent = _literal_project_path(node.left)
        if parent is not None:
            return parent / node.right.value
    return None


def _local_dependency_files(test_file: Path) -> list[Path]:
    queue = [test_file.resolve()]
    found: set[Path] = set()
    known_python = {
        path.name: path.resolve()
        for root in (PLUGIN / "scripts", PLUGIN / "tests")
        for path in root.glob("*.py")
    }
    while queue:
        path = queue.pop()
        if path in found:
            continue
        found.add(path)
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
        discovered: set[Path] = set()
        for node in ast.walk(tree):
            literal_path = _literal_project_path(node)
            if literal_path is not None and literal_path.is_file():
                discovered.add(literal_path.resolve())
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            for module in modules:
                resolved = _resolve_local_module(module)
                if resolved:
                    discovered.add(resolved)
        for name, candidate in known_python.items():
            if name in text:
                discovered.add(candidate)
        queue.extend(sorted(discovered - found))
    return sorted(found)


def _contract_hash(test_file: Path, extra_contract: dict[str, str] | None = None) -> str:
    dependencies = _local_dependency_files(test_file)
    records = [(path.relative_to(PLUGIN).as_posix(), _sha256(path)) for path in dependencies]
    dependency_names = {path.name for path in dependencies}
    shared_contracts = [
        "assets/resource-policy.json",
        "scripts/run_incremental_tests.py",
        "scripts/resource_guard.py",
    ]
    if dependency_names & {"intent_router_core.py", "research_integrity_core.py"}:
        shared_contracts.append("assets/p12-skillopt-config.json")
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in dependencies)
    for relative in (".codex-plugin/plugin.json", ".mcp.json"):
        if Path(relative).name in source_text:
            shared_contracts.append(relative)
    for relative in shared_contracts:
        path = PLUGIN / relative
        if path.is_file():
            records.append((relative, _sha256(path)))
    for name, digest in sorted((extra_contract or {}).items()):
        records.append((f"external:{name}", digest))
    return hashlib.sha256(json.dumps(records, separators=(",", ":")).encode("utf-8")).hexdigest()


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


def run(
    patterns: list[str], suite: str, *, resume: bool = True,
    env: dict[str, str] | None = None, extra_contract: dict[str, str] | None = None,
) -> dict[str, Any]:
    require_start_headroom()
    require_orchestrator_budget()
    tests: list[Path] = []
    for pattern in patterns:
        tests.extend(PLUGIN.joinpath("tests").glob(pattern))
    tests = sorted({path.resolve() for path in tests if path.is_file()})
    if not tests:
        raise RuntimeError(f"no tests match: {patterns}")
    receipt_root = DEFAULT_RECEIPT_ROOT / _safe_suite_name(suite)
    results: list[dict[str, Any]] = []
    for test_file in tests:
        require_orchestrator_budget()
        contract_hash = _contract_hash(test_file, extra_contract)
        receipt_path = receipt_root / f"{test_file.stem}.json"
        if resume and receipt_path.is_file():
            try:
                existing = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = {}
            if existing.get("status") == "PASS" and existing.get("contract_hash") == contract_hash:
                results.append({**existing, "resumed": True})
                continue
        module = f"tests.{test_file.stem}"
        dependency_files = _local_dependency_files(test_file)
        lean_profile = "test_p1_round3_lean.py" == test_file.name
        completed = run_managed(
            [
                sys.executable, "-X", "utf8", "-m", "unittest", "discover",
                "-s", "tests", "-p", test_file.name, "-v",
            ],
            cwd=PLUGIN, env=env, timeout=600,
            maximum_job_bytes=LEAN_WORKER_LIMIT_BYTES if lean_profile else WORKER_JOB_LIMIT_BYTES,
            maximum_orchestrator_bytes=(
                LEAN_ORCHESTRATOR_RESERVE_BYTES if lean_profile else ORCHESTRATOR_RESERVE_BYTES
            ),
            trim_trigger_bytes=LEAN_TRIM_TRIGGER_BYTES if lean_profile else None,
        )
        record = {
            "schema_version": 1,
            "test_file": test_file.relative_to(PLUGIN).as_posix(),
            "module": module,
            "contract_hash": contract_hash,
            "dependency_files": [path.relative_to(PLUGIN).as_posix() for path in dependency_files],
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
            break
    summary = {
        "schema_version": 1, "suite": suite, "patterns": patterns,
        "test_files": len(tests), "completed_files": len(results),
        "passed_files": sum(item["status"] == "PASS" for item in results),
        "resumed_files": sum(bool(item.get("resumed")) for item in results),
        "status": "PASS" if len(results) == len(tests) and all(item["status"] == "PASS" for item in results) else "FAIL",
        "results": [{key: item[key] for key in ("test_file", "status", "returncode", "contract_hash", "resumed")} for item in results],
    }
    _atomic_json(receipt_root / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run test files serially in <=384 MiB workers with resumable receipts")
    parser.add_argument("--pattern", action="append", required=True, help="tests/ glob; repeat for multiple groups")
    parser.add_argument("--suite", required=True)
    parser.add_argument("--no-resume", action="store_true")
    arguments = parser.parse_args()
    summary = run(arguments.pattern, arguments.suite, resume=not arguments.no_resume)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
