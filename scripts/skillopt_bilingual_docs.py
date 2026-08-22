from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from documentation_parity import validate_documentation
from resource_guard import ResourceGuardError, require_orchestrator_budget, require_start_headroom, run_managed


PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / "bilingual-documentation-skillopt"
CONTRACT_FILES = (
    "assets/documentation-parity.json",
    "assets/readme/asset-provenance.json",
    "README.md",
    "README.zh-CN.md",
    "docs/DOCUMENTATION_POLICY.md",
    "docs/DOCUMENTATION_POLICY.zh-CN.md",
    "scripts/documentation_parity.py",
    "scripts/validate_repository.py",
    "scripts/build_modular_package.py",
    "scripts/build_public_package.py",
    "tests/test_documentation_parity.py",
    "tests/test_p10_cycle_e_public_package.py",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "CONTRIBUTING.md",
)


def _static_contract() -> dict[str, Any]:
    texts = {name: (PLUGIN / name).read_text(encoding="utf-8") for name in CONTRACT_FILES}
    report = validate_documentation(PLUGIN)
    readme_first_screen = "\n".join(texts["README.md"].splitlines()[:80])
    chinese_first_screen = "\n".join(texts["README.zh-CN.md"].splitlines()[:80])
    ci = texts[".github/workflows/ci.yml"]
    release = texts[".github/workflows/release.yml"]
    validator = texts["scripts/validate_repository.py"]
    builder = texts["scripts/build_modular_package.py"]
    public_builder = texts["scripts/build_public_package.py"]
    parity = texts["scripts/documentation_parity.py"]
    image_report = next(item for item in report["pairs"] if item["id"] == "readme")["images"][0]
    checks = {
        "all declared bilingual pairs pass the executable contract": report["status"] == "PASS"
        and report["pair_count"] == 2 and report["translation_files"] == 2,
        "orphan translations fail closed": "translation registry coverage drift" in parity
        and "all_translation_files_must_be_registered" in parity,
        "structure links images and hashes are separate checks": all(token in parity for token in (
            "section skeleton drifted", "link target parity drift", "image target parity drift",
            "source_sha256", "translation_sha256", "pair_sha256", "PNG CRC mismatch",
        )),
        "human semantic review remains explicit": "human bilingual review" in texts["docs/DOCUMENTATION_POLICY.md"]
        and "人工双语审阅" in texts["docs/DOCUMENTATION_POLICY.zh-CN.md"]
        and "does not claim that a machine proved translation quality" in texts["README.md"],
        "first screen has one complete agent path": all(token in readme_first_screen for token in (
            "Give this to an agent", "research-guard-windows-x64-modular.zip",
            "research-guard-linux-x64.zip", "research-guard-macos-arm64.zip",
            "SHA256SUMS.txt", "not_now", "about 300 MB", "REQUIREMENTS.md",
        )) and all(token in chinese_first_screen for token in (
            "直接复制给 Agent 安装", "research-guard-windows-x64-modular.zip",
            "research-guard-linux-x64.zip", "research-guard-macos-arm64.zip",
            "SHA256SUMS.txt", "not_now", "约 300 MB", "REQUIREMENTS.md",
        )),
        "shared banner is bounded and provenance bound": image_report["width"] == 2172
        and image_report["height"] == 724 and image_report["aspect_ratio"] == 3.0
        and image_report["bytes"] <= 2 * 1024 * 1024,
        "repository validation owns documentation admission": "validate_documentation(ROOT)" in validator
        and "bilingual_document_pairs" in validator,
        "package requires the full documentation contract": all(token in builder for token in (
            "assets/documentation-parity.json", "assets/readme/research-guard-evidence-lifecycle.png",
            "docs/DOCUMENTATION_POLICY.zh-CN.md", "tests/test_documentation_parity.py",
        )) and all(token in public_builder for token in (
            "assets/documentation-parity.json", "assets/readme/research-guard-evidence-lifecycle.png",
            "docs/DOCUMENTATION_POLICY.zh-CN.md", "tests/test_documentation_parity.py",
        )),
        "four-platform CI and release include focused regression": ci.count('test_documentation_parity.py') == 1
        and release.count('test_documentation_parity.py') == 1,
        "README contract preserves the 17-tool surface": "17 top-level MCP tools" in texts["README.md"]
        and "17 个顶层 MCP 工具" in texts["README.zh-CN.md"],
    }
    candidates = [
        {"candidate": "prompt-only reminder to update both READMEs", "decision": "REJECT"},
        {"candidate": "publish automatic machine translation without review", "decision": "REJECT"},
        {"candidate": "token-presence parity without structure or hashes", "decision": "REJECT"},
        {"candidate": "README banner with generated formulas or code glyphs", "decision": "REJECT"},
        {"candidate": "duplicate language-specific image binaries", "decision": "REJECT"},
        {
            "candidate": "registered pairs plus structure, links, shared image audit, hashes, CI, and human review",
            "decision": "ADMIT",
        },
    ]
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "architecture_candidates": candidates,
        "documentation_report": report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated bilingual-documentation SkillOpt gates")
    parser.add_argument("--rounds", type=int, default=4, choices=(3, 4, 5))
    arguments = parser.parse_args()
    require_start_headroom()
    require_orchestrator_budget()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    run_root = EVIDENCE / dt.datetime.now(dt.timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    run_root.mkdir(parents=True, exist_ok=False)
    rounds: list[dict[str, Any]] = []
    test_modules = (
        "tests.test_documentation_parity",
        "tests.test_p10_cycle_e_public_package",
    )
    for index in range(1, arguments.rounds + 1):
        static = _static_contract()
        try:
            completed = run_managed(
                [sys.executable, "-X", "utf8", "-m", "unittest", *test_modules, "-v"],
                cwd=PLUGIN,
                timeout=600,
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
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        rounds.append(record)
        if record["status"] != "PASS":
            break
    report = {
        "schema_version": 1,
        "status": "PASS" if len(rounds) == arguments.rounds and all(item["status"] == "PASS" for item in rounds) else "FAIL",
        "requested_rounds": arguments.rounds,
        "round_count": len(rounds),
        "run_root": run_root.relative_to(PLUGIN).as_posix(),
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
