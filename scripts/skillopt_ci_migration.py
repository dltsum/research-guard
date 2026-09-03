from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from resource_guard import ResourceGuardError, require_orchestrator_budget, require_start_headroom, run_managed


PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / "p21-ci-migration-skillopt"
CONTRACT_FILES = (
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "scripts/test_isolated_install.py",
    "scripts/verify_isolated_install.py",
    "scripts/hydrate_release_payloads.py",
    "assets/payload-bootstrap.json",
    "scripts/validate_repository.py",
    "scripts/build_modular_package.py",
    "tests/test_p21_ci_migration_assurance.py",
    "docs/provenance/P21_CI_MIGRATION_ASSURANCE.md",
    "README.md",
    "README.zh-CN.md",
)


def _static_contract() -> dict[str, Any]:
    texts = {name: (PLUGIN / name).read_text(encoding="utf-8") for name in CONTRACT_FILES}
    ci = texts[".github/workflows/ci.yml"]
    release = texts[".github/workflows/release.yml"]
    runner = texts["scripts/test_isolated_install.py"]
    verifier = texts["scripts/verify_isolated_install.py"]
    hydrator = texts["scripts/hydrate_release_payloads.py"]
    builder = texts["scripts/build_modular_package.py"]
    combined = "\n".join(texts.values())
    checks = {
        "archive extraction is bounded and traversal-safe": all(token in runner for token in (
            "MAX_ARCHIVE_MEMBERS", "MAX_UNCOMPRESSED_BYTES", "PurePosixPath", "stat.S_ISLNK",
        )),
        "installer and verifier use the aggregate memory guard": runner.count("run_managed_install") >= 2,
        "Windows and POSIX runtime layouts are admitted": all(token in verifier for token in (
            'runtime / "python.exe"', 'runtime / "Scripts" / "python.exe"', 'runtime / "bin" / "python"',
        )),
        "CI Windows payload hydration precedes build": ci.index("Hydrate audited Windows release payloads")
        < ci.index("Build platform migration archive")
        and "if: runner.os == 'Windows'" in ci,
        "CI order is build then clean install then retention": ci.index("Build platform migration archive")
        < ci.index("Verify isolated platform installation") < ci.index("Retain verified migration archive"),
        "bootstrap archive and payloads are independently hash bound": all(token in hydrator for token in (
            "asset_sha256", "payload_manifest_sha256", "release_manifest", "release_record",
            "payload content integrity mismatch",
        )),
        "Windows builder fails closed before enumerating package files": builder.index("validate_payload_directory(")
        < builder.index('PLUGIN_ROOT.rglob("*")')
        and "WINDOWS_PAYLOAD_PREFLIGHT_FAILED" in builder,
        "development mode reads the source tree without release copying": all(token in builder for token in (
            'BUILD_MODES = ("release", "development")', 'if mode == "development"',
            '"archive_created": False', '"hashes": "omitted_in_development_mode"',
        )),
        "exact ZIP is retained for three days": all(token in ci for token in (
            "actions/upload-artifact@v7", "archive: false", "retention-days: 3", "if-no-files-found: error",
        )),
        "release verifies Linux before publishing": release.index("Build POSIX migration archives")
        < release.index("Verify isolated Linux release archive") < release.index("Publish GitHub release metadata"),
        "release verifies Windows modular asset on a native runner": all(token in release for token in (
            "release-windows:", "Hydrate audited Windows release payloads",
            "Build Windows x64 modular archive", "Verify isolated Windows release archive",
            "Write Windows checksum", "Upload Windows release assets",
            "research-guard-windows-x64-modular.zip", "SHA256SUMS.txt",
        )) and release.index("Hydrate audited Windows release payloads", release.index("release-windows:"))
        < release.index("Build Windows x64 modular archive", release.index("release-windows:"))
        < release.index("Verify isolated Windows release archive", release.index("release-windows:")),
        "P21 regression is present in CI and release": ci.count('test_p21_*.py') == 1
        and release.count('test_p21_*.py') == 1,
        "P26 behavior regression is present in CI and release": ci.count('test_p26_*.py') == 1
        and release.count('test_p26_*.py') == 1,
        "repository and package validators require P21": all(token in combined for token in (
            "docs/provenance/P21_CI_MIGRATION_ASSURANCE.md", "tests/test_p21_ci_migration_assurance.py",
            "scripts/skillopt_ci_migration.py",
        )),
        "bilingual public contract states short CI retention": "3-day verified CI archive" in texts["README.md"]
        and "3 天已验证 CI 归档" in texts["README.zh-CN.md"],
        "official action provenance is linked": "https://github.com/actions/upload-artifact" in combined,
        "MCP surface remains unchanged": "17 top-level MCP tools" in texts["README.md"],
    }
    candidates = [
        {"candidate": "trust archive creation without installation", "decision": "REJECT"},
        {"candidate": "add a second installer per platform", "decision": "REJECT"},
        {"candidate": "retain every CI archive indefinitely", "decision": "REJECT"},
        {"candidate": "commit 300 MB payloads into Git history", "decision": "REJECT"},
        {"candidate": "download current upstream binaries without archive pinning for a release", "decision": "REJECT"},
        {"candidate": "inspect the current source tree directly for development without payload pinning", "decision": "ADMIT"},
        {"candidate": "merge dependency upgrades without rebuilding the bundled runtime", "decision": "DEFER"},
        {"candidate": "hydrate from one SHA-pinned prior release, cross-check payload manifests, then clean-install", "decision": "ADMIT"},
    ]
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "architecture_candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated P21 CI-migration SkillOpt gates")
    parser.add_argument("--rounds", type=int, default=4, choices=(3, 4, 5))
    arguments = parser.parse_args()
    require_start_headroom()
    require_orchestrator_budget()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    run_root = EVIDENCE / dt.datetime.now(dt.timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    run_root.mkdir(parents=True, exist_ok=False)
    rounds: list[dict[str, Any]] = []
    test_modules = (
        "tests.test_p21_ci_migration_assurance",
        "tests.test_cross_platform",
        "tests.test_p10_cycle_e_public_package",
        "tests.test_p11_resource_and_selection",
    )
    for index in range(1, arguments.rounds + 1):
        static = _static_contract()
        try:
            completed = run_managed(
                [sys.executable, "-X", "utf8", "-m", "unittest", *test_modules, "-v"],
                cwd=PLUGIN, timeout=900,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            record = {
                "round": index,
                "status": "PASS" if completed.returncode == 0 and static["status"] == "PASS" else "FAIL",
                "static_contract": static,
                "test_returncode": completed.returncode,
                "test_output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
                "test_stdout_tail": (completed.stdout or "")[-10_000:],
                "test_stderr_tail": (completed.stderr or "")[-10_000:],
                "resource_usage": completed.resource_usage,
            }
        except ResourceGuardError as exc:
            record = {
                "round": index,
                "status": "FAIL",
                "static_contract": static,
                "test_returncode": None,
                "test_output_sha256": None,
                "test_stdout_tail": "",
                "test_stderr_tail": "",
                "resource_usage": None,
                "resource_guard_error": str(exc),
            }
        (run_root / f"round-{index:02d}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        rounds.append(record)
        if record["status"] != "PASS":
            break
    report = {
        "schema_version": 1,
        "status": "PASS" if len(rounds) == arguments.rounds and all(item["status"] == "PASS" for item in rounds) else "FAIL",
        "requested_rounds": arguments.rounds,
        "round_count": len(rounds),
        "run_root": str(run_root.relative_to(PLUGIN).as_posix()),
        "rounds": rounds,
    }
    report["report_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (run_root / "report.json").write_text(rendered, encoding="utf-8")
    (EVIDENCE / "report.json").write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
