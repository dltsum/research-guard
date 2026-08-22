from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resource_guard import (
    RUN_MIN_FREE_BYTES, ResourceGuardError, memory_snapshot,
    require_orchestrator_budget, require_start_headroom, run_managed,
)
from hydrate_release_payloads import PayloadHydrationError, validate_payload_directory


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".mcp.json", ".editorconfig", ".gitattributes", ".gitignore",
    "SKILL.md", "README.md", "README.zh-CN.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
    "CONTRIBUTING.md", "SECURITY.md", "GOVERNANCE.md", "SUPPORT.md",
    "CODE_OF_CONDUCT.md", "CITATION.cff", "CHANGELOG.md",
    "requirements-core.txt", "requirements-dev.txt", "REQUIREMENTS.md",
}
ROOT_DIRECTORIES = {".codex-plugin", ".github", "agents", "hooks", "skills", "scripts", "docs", "references", "tests", "assets"}
EXCLUDED_PARTS = {"__pycache__", ".git", ".research-guard", "development", "evals", "snapshots", "quarantine", "admitted"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
UNLICENSED_CACHED_SUFFIXES = {".pdf", ".html"}
PRIVATE_PATH = re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s\"'<>]+", re.I)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _include(relative: Path) -> bool:
    if not relative.parts:
        return False
    if len(relative.parts) == 1:
        return relative.name in ROOT_FILES
    if relative.parts[0] not in ROOT_DIRECTORIES or any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if relative.suffix.casefold() in EXCLUDED_SUFFIXES:
        return False
    if relative.parts[:2] == ("assets", "venue-evidence"):
        if relative.suffix.casefold() in UNLICENSED_CACHED_SUFFIXES:
            return False
        if "templates" in relative.parts and relative.suffix.casefold() == ".zip":
            return False
    if relative.parts[0] == "scripts" and relative.name == "build_public_package.py":
        return False
    return True


def _check_text(path: Path, relative: Path) -> None:
    if path.suffix.casefold() not in {".py", ".md", ".json", ".yaml", ".yml", ".txt", ".ps1", ".cmd", ".sh"} and path.name not in {"LICENSE", ".mcp.json"}:
        return
    text = path.read_text(encoding="utf-8", errors="strict")
    if PRIVATE_PATH.search(text):
        raise RuntimeError(f"private absolute path found in release file: {relative.as_posix()}")


def build(output: Path, platform_target: str) -> dict[str, object]:
    try:
        headroom = require_start_headroom()
    except ResourceGuardError as exc:
        raise RuntimeError(str(exc)) from exc
    output = output.resolve()
    if output.suffix.casefold() != ".zip":
        raise RuntimeError("output must be a .zip file")
    if platform_target == "windows-x64":
        try:
            validate_payload_directory(
                PLUGIN_ROOT / "assets" / "payload-manifest.json",
                PLUGIN_ROOT / "assets" / "payloads",
            )
        except PayloadHydrationError as exc:
            raise RuntimeError(
                "WINDOWS_PAYLOAD_PREFLIGHT_FAILED: run scripts/hydrate_release_payloads.py; " + str(exc)
            ) from exc
    files: list[tuple[Path, Path]] = []
    for path in sorted(item for item in PLUGIN_ROOT.rglob("*") if item.is_file()):
        relative = path.relative_to(PLUGIN_ROOT)
        if _include(relative):
            if platform_target != "windows-x64" and relative.parts[:2] == ("assets", "payloads"):
                continue
            _check_text(path, relative)
            files.append((path, relative))
    found = {relative for _, relative in files}
    required = {Path(name) for name in ROOT_FILES} | {
        Path("agents/openai.yaml"), Path("references/dependencies.md"),
        Path("assets/dependency-catalog.json"), Path("assets/payload-manifest.json"),
        Path("assets/payload-bootstrap.json"), Path("scripts/hydrate_release_payloads.py"),
        Path("scripts/install.ps1"), Path("scripts/install.sh"), Path("scripts/install_posix.py"),
        Path("scripts/mcp_launcher.py"), Path("scripts/mcp.sh"), Path("scripts/dependency_manager.py"),
        Path("scripts/experiment_metrics_core.py"),
        Path("scripts/llm_delegation_core.py"), Path("scripts/skillopt_subagent_delegation.py"),
        Path("assets/llm-delegation-policy.json"), Path("docs/SUBAGENT_DELEGATION.md"),
        Path("docs/provenance/SUBAGENT_DELEGATION_VERIFICATION.md"),
        Path("scripts/research_integrity_core.py"), Path("scripts/skillopt_p12.py"),
        Path("assets/p12-skillopt-config.json"),
        Path("scripts/math_verification_worker.py"), Path("scripts/openreview_calibration_core.py"),
        Path("scripts/discipline_profile_core.py"), Path("assets/discipline-registry.json"),
        Path("scripts/skillopt_p16.py"), Path("docs/TIME_AND_CONTINUATION_POLICY.md"),
        Path("docs/provenance/P16_AGENT_SELECTION_AND_CONTINUATION.md"),
        Path("scripts/skillopt_p17.py"), Path("scripts/ai_reviewer_robustness_core.py"),
        Path("scripts/skillopt_p18.py"),
        Path("scripts/resource_task_planner_core.py"), Path("scripts/skillopt_resource_task_planning.py"),
        Path("assets/task-resource-profiles.json"), Path("docs/RESOURCE_AWARE_TASK_PLANNING.md"),
        Path("docs/provenance/P19_RESOURCE_AWARE_TASK_PLANNING.md"),
        Path("tests/test_resource_task_planning.py"),
        Path("scripts/direction_exploration_core.py"), Path("scripts/skillopt_direction_exploration.py"),
        Path("assets/direction-exploration-contract.json"), Path("docs/DIRECTION_EXPLORATION.md"),
        Path("docs/provenance/P20_DIRECTION_EXPLORATION.md"),
        Path("tests/test_direction_exploration.py"),
        Path("skills/research-design-guard/references/direction-exploration-contract.md"),
        Path("scripts/test_isolated_install.py"), Path("scripts/verify_isolated_install.py"),
        Path("scripts/skillopt_ci_migration.py"),
        Path("docs/provenance/P21_CI_MIGRATION_ASSURANCE.md"),
        Path("tests/test_p21_ci_migration_assurance.py"),
        Path("assets/documentation-parity.json"),
        Path("assets/readme/research-guard-evidence-lifecycle.png"),
        Path("assets/readme/asset-provenance.json"),
        Path("docs/DOCUMENTATION_POLICY.md"),
        Path("docs/DOCUMENTATION_POLICY.zh-CN.md"),
        Path("docs/provenance/BILINGUAL_DOCUMENTATION_AND_README.md"),
        Path("scripts/documentation_parity.py"),
        Path("scripts/skillopt_bilingual_docs.py"),
        Path("tests/test_documentation_parity.py"),
        Path("assets/instruction-adherence-policy.json"),
        Path("scripts/instruction_adherence_core.py"),
        Path("scripts/constructive_numerical_core.py"),
        Path("scripts/constructive_numerical_worker.py"),
        Path("scripts/skillopt_instruction_numerical.py"),
        Path("tests/test_p22_instruction_adherence.py"),
        Path("tests/test_p22_constructive_numerical.py"),
        Path("docs/INSTRUCTION_AND_NUMERICAL_CONTRACT.md"),
        Path("docs/INSTRUCTION_AND_NUMERICAL_CONTRACT.zh-CN.md"),
        Path("docs/provenance/P22_INSTRUCTION_AND_CONSTRUCTIVE_NUMERICAL.md"),
        Path("docs/RESEARCH_CONSOLE_UI.md"),
        Path("docs/RESEARCH_CONSOLE_UI.zh-CN.md"),
        Path("docs/provenance/P23_RESEARCH_CONSOLE_UI.md"),
        Path("assets/review-evidence/ai-reviewer-evidence.json"),
        Path("docs/PAPER_WRITING_CAPABILITIES.md"),
        Path("docs/provenance/P17_PAPER_WRITING_AI_REVIEWER_AND_FIGURES.md"),
        Path("docs/provenance/P18_ACTIVE_AI_REVIEWER_OPTIMIZATION.md"),
        Path("references/research-progression-contract.md"),
        Path("skills/academic-figure-guard/references/visual-quality-contract.md"),
        Path("skills/paper-audit-guard/references/ai-reviewer-optimization.md"),
        Path("docs/provenance/P12_COMPONENT_REGISTRY.json"),
        Path("docs/provenance/P12_OVERLAP_AUDIT.md"),
        Path("docs/provenance/P12_SKILLOPT_REPORT.md"),
        Path("docs/provenance/P13_RELEASE_VERIFICATION.md"),
        Path("docs/provenance/P14_DISCIPLINE_AND_RELEASE.md"),
        Path("skills/paper-audit-guard/references/research-integrity-contracts.md"),
        Path("skills/research-design-guard/references/research-integrity-contracts.md"),
    }
    missing = sorted(str(path) for path in required - found)
    if missing:
        raise RuntimeError(f"release is missing required files: {missing}")
    manifest_files = [
        {"path": relative.as_posix(), "bytes": source.stat().st_size, "sha256": _sha256(source)}
        for source, relative in files
    ]
    manifest = {
        "schema_version": 1,
        "package": "research-guard",
        "variant": "windows-x64-modular" if platform_target == "windows-x64" else f"{platform_target}-venv",
        "platform": platform_target,
        "runtime_delivery": "bundled-python" if platform_target == "windows-x64" else "system-python-venv",
        "optional_downloads_require_user_selection": True,
        "optional_addons_included": [],
        "files": manifest_files,
    }
    manifest["files_sha256"] = hashlib.sha256(
        json.dumps(manifest_files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for source, relative in files:
                available = int(memory_snapshot()["available_physical_bytes"])
                if available < RUN_MIN_FREE_BYTES:
                    raise RuntimeError(
                        f"RESOURCE_LOW_WATER_ABORT: available RAM is {available / 1024 ** 2:.0f} MiB during packaging"
                    )
                already_compressed = source.suffix.casefold() in {".zip", ".exe", ".png", ".jpg", ".jpeg", ".pdf"}
                archive.write(
                    source, Path("research-guard") / relative,
                    compress_type=zipfile.ZIP_STORED if already_compressed else zipfile.ZIP_DEFLATED,
                    compresslevel=None if already_compressed else 6,
                )
            archive.writestr(
                "research-guard/RELEASE_MANIFEST.json",
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )
        if temporary.stat().st_size > 1024 ** 3:
            raise RuntimeError(f"modular archive exceeds the 1 GiB cap: {temporary.stat().st_size} bytes")
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {
        "status": "PASS", "path": str(output), "platform": platform_target,
        "runtime_delivery": manifest["runtime_delivery"], "files": len(files) + 1,
        "bytes": output.stat().st_size, "sha256": _sha256(output), "start_memory": headroom,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the <=1 GiB Research Guard modular migration Skill")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--platform", dest="platform_target", required=True,
        choices=("windows-x64", "linux-x64", "macos-x64", "macos-arm64"),
    )
    parser.add_argument("--bounded-worker", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.bounded_worker or os.environ.get("RESEARCH_GUARD_MANAGED_WORKER") == "1":
        print(json.dumps(build(arguments.output, arguments.platform_target), ensure_ascii=False, indent=2))
        return 0
    require_orchestrator_budget()
    completed = run_managed(
        [
            sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
            "--output", str(arguments.output), "--platform", arguments.platform_target, "--bounded-worker",
        ],
        cwd=PLUGIN_ROOT, timeout=1800,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.returncode != 0:
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
