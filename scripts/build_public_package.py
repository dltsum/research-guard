from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resource_guard import (
    RUN_MIN_FREE_BYTES, ResourceGuardError, memory_snapshot,
    require_orchestrator_budget, require_start_headroom, run_managed,
)


# Build behavior history (keep the two most recent behaviors beside the code):
# - v0.8-dev (2026-08-26): ``mode=development`` inspects the current source
#   tree in place and returns a small receipt.  It does not clone a version,
#   pin source/material components, or calculate sensitive source hashes.
# - v0.7-release (2026-08-23): ``mode=release`` emits the public ZIP and its
#   artifact manifest, retaining the checks needed for a distributable archive.


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BUILD_MODES = ("release", "development")
ROOT_FILES = {
    ".mcp.json", ".editorconfig", ".gitattributes", ".gitignore",
    "README.md", "README.zh-CN.md", "LICENSE", "SKILL.md", "THIRD_PARTY_NOTICES.md",
    "CONTRIBUTING.md", "SECURITY.md", "GOVERNANCE.md", "SUPPORT.md",
    "CODE_OF_CONDUCT.md", "CITATION.cff", "CHANGELOG.md",
    "requirements-core.txt", "requirements-dev.txt", "REQUIREMENTS.md",
}
ROOT_DIRECTORIES = {".codex-plugin", ".github", "agents", "hooks", "references", "skills", "scripts", "docs", "tests", "assets"}
INTERNAL_REPORT_PREFIXES = tuple(f"P{index}_" for index in range(15))
PUBLIC_PROVENANCE_REPORTS = {
    "docs/provenance/P12_COMPONENT_REGISTRY.json",
    "docs/provenance/P12_OVERLAP_AUDIT.md",
    "docs/provenance/P12_SKILLOPT_REPORT.md",
    "docs/provenance/P13_RELEASE_VERIFICATION.md",
    "docs/provenance/P14_DISCIPLINE_AND_RELEASE.md",
    "docs/provenance/P16_AGENT_SELECTION_AND_CONTINUATION.md",
    "docs/provenance/P17_PAPER_WRITING_AI_REVIEWER_AND_FIGURES.md",
    "docs/provenance/P18_ACTIVE_AI_REVIEWER_OPTIMIZATION.md",
    "docs/provenance/P19_RESOURCE_AWARE_TASK_PLANNING.md",
    "docs/provenance/P20_DIRECTION_EXPLORATION.md",
    "docs/provenance/P21_CI_MIGRATION_ASSURANCE.md",
    "docs/provenance/P22_INSTRUCTION_AND_CONSTRUCTIVE_NUMERICAL.md",
    "docs/provenance/P23_RESEARCH_CONSOLE_UI.md",
    "docs/provenance/P24_FRONTIER_SKILL_RESEARCH.md",
    "docs/provenance/P25_SKILL_PORTABILITY.md",
    "docs/provenance/P25_SKILL_PORTABILITY.zh-CN.md",
    "docs/provenance/P26_SKILL_COMPOSITION.md",
    "docs/provenance/P26_SKILL_COMPOSITION.zh-CN.md",
    "docs/provenance/P27_MACRO_PAPER_SPINE.md",
}
EXCLUDED_SUFFIXES = {".dll", ".exe", ".html", ".pdf", ".pyd", ".pyc", ".pyo", ".whl", ".zip"}
EXCLUDED_PARTS = {"__pycache__", ".git", ".research-guard", "admitted", "development", "evals", "payloads", "quarantine", "snapshots"}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _include(relative: Path) -> bool:
    if not relative.parts:
        return False
    if relative.name in ROOT_FILES and len(relative.parts) == 1:
        return True
    if relative.as_posix() in PUBLIC_PROVENANCE_REPORTS:
        return True
    if relative.parts[0] not in ROOT_DIRECTORIES:
        return False
    if relative.parts[0] == "tests" and not relative.name.startswith(("test_p10_", "test_p11_", "test_p12_", "test_p13_", "test_p14_", "test_p16_", "test_p17_", "test_p18_", "test_p21_", "test_p22_", "test_p24_", "test_p25_", "test_p26_", "test_p27_", "test_build_development_mode", "test_install_clean", "test_experiment_metrics", "test_education_profiles", "test_cross_platform", "test_subagent_delegation", "test_resource_task_planning", "test_direction_exploration", "test_documentation_parity")):
        return False
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if relative.suffix.casefold() in EXCLUDED_SUFFIXES:
        return False
    return relative.as_posix() in PUBLIC_PROVENANCE_REPORTS or not relative.name.startswith(INTERNAL_REPORT_PREFIXES)


def _check_text(path: Path, relative: Path) -> None:
    if path.suffix.casefold() not in {".py", ".md", ".json", ".yaml", ".yml", ".txt", ".ps1", ".cmd", ".sh"} and path.name not in {"LICENSE", ".mcp.json"}:
        return
    text = path.read_text(encoding="utf-8", errors="strict")
    patterns = (
        re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s\"'<>]+", re.I),
        re.compile(r"research-guard-p\d+-upstreams", re.I),
        re.compile(r"\.codex[\\/]plugins[\\/]cache", re.I),
    )
    hit = next((pattern.pattern for pattern in patterns if pattern.search(text)), None)
    if hit:
        raise RuntimeError(f"private absolute path found in public file {relative}: {hit}")


def _development_receipt(files: list[tuple[Path, Path]]) -> dict[str, object]:
    """Return an in-place source inspection receipt, never a source copy."""
    return {
        "status": "PASS",
        "mode": "development",
        "source_tree": True,
        "archive_created": False,
        "third_party_binary_assets_included": False,
        "files": len(files),
        "source_bytes": sum(path.stat().st_size for path, _ in files),
        "hashes": "omitted_in_development_mode",
        "message": "Source tree was inspected in place; edit it directly and rerun.",
    }


def build(output: Path | None, *, mode: str = "release") -> dict[str, object]:
    if mode not in BUILD_MODES:
        raise RuntimeError(f"unsupported build mode: {mode!r}")
    try:
        headroom = require_start_headroom()
    except ResourceGuardError as exc:
        raise RuntimeError(str(exc)) from exc
    if mode == "release":
        if output is None:
            raise RuntimeError("output is required for release mode")
        output = output.resolve()
        if output.suffix.casefold() != ".zip":
            raise RuntimeError("public package output must be a .zip file")
    files = []
    for path in sorted((item for item in PLUGIN_ROOT.rglob("*") if item.is_file())):
        relative = path.relative_to(PLUGIN_ROOT)
        if _include(relative):
            if mode == "release":
                _check_text(path, relative)
            files.append((path, relative))
    if mode == "development":
        receipt = _development_receipt(files)
        receipt["start_memory"] = headroom
        return receipt
    required = {Path(name) for name in ROOT_FILES | PUBLIC_PROVENANCE_REPORTS} | {
        Path("scripts/research_integrity_core.py"), Path("assets/p12-skillopt-config.json"),
        Path("scripts/math_verification_worker.py"), Path("scripts/openreview_calibration_core.py"),
        Path("scripts/discipline_profile_core.py"), Path("assets/discipline-registry.json"),
        Path("scripts/experiment_metrics_core.py"), Path("docs/EDUCATION_SUPPORT.md"),
        Path("scripts/install.sh"), Path("scripts/install_posix.py"), Path("scripts/network_config_core.py"), Path("scripts/mcp_launcher.py"),
        Path("scripts/skillopt_p16.py"), Path("docs/TIME_AND_CONTINUATION_POLICY.md"),
        Path("scripts/skillopt_p17.py"), Path("scripts/ai_reviewer_robustness_core.py"),
        Path("scripts/skillopt_p18.py"),
        Path("scripts/resource_task_planner_core.py"), Path("scripts/skillopt_resource_task_planning.py"),
        Path("assets/task-resource-profiles.json"), Path("docs/RESOURCE_AWARE_TASK_PLANNING.md"),
        Path("docs/provenance/P19_RESOURCE_AWARE_TASK_PLANNING.md"),
        Path("tests/test_resource_task_planning.py"),
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
        Path("scripts/paper_spine_core.py"),
        Path("scripts/skillopt_p27_macro_paper_spine.py"),
        Path("scripts/skillopt_instruction_numerical.py"),
        Path("tests/test_p22_instruction_adherence.py"),
        Path("tests/test_p22_constructive_numerical.py"),
        Path("tests/test_p27_macro_paper_spine.py"),
        Path("docs/INSTRUCTION_AND_NUMERICAL_CONTRACT.md"),
        Path("docs/INSTRUCTION_AND_NUMERICAL_CONTRACT.zh-CN.md"),
        Path("docs/provenance/P22_INSTRUCTION_AND_CONSTRUCTIVE_NUMERICAL.md"),
        Path("docs/RESEARCH_CONSOLE_UI.md"),
        Path("docs/RESEARCH_CONSOLE_UI.zh-CN.md"),
        Path("docs/provenance/P23_RESEARCH_CONSOLE_UI.md"),
        Path("assets/review-evidence/ai-reviewer-evidence.json"),
        Path("docs/PAPER_WRITING_CAPABILITIES.md"),
        Path("references/research-progression-contract.md"),
        Path("skills/academic-figure-guard/references/visual-quality-contract.md"),
        Path("skills/paper-audit-guard/references/ai-reviewer-optimization.md"),
        Path("skills/academic-language-guard/references/paper-spine-contract.md"),
        Path("scripts/frontier_skill_research_core.py"),
        Path("scripts/skillopt_frontier_skill_research.py"),
        Path("tests/test_p24_frontier_skill_research.py"),
        Path("docs/FRONTIER_SKILL_RESEARCH.md"),
        Path("docs/FRONTIER_SKILL_RESEARCH.zh-CN.md"),
        Path("docs/provenance/P24_FRONTIER_SKILL_RESEARCH.md"),
        Path("scripts/skill_portability_core.py"),
        Path("scripts/skillopt_skill_portability.py"),
        Path("tests/test_p25_skill_portability.py"),
        Path("docs/SKILL_PORTABILITY.md"),
        Path("docs/SKILL_PORTABILITY.zh-CN.md"),
        Path("docs/provenance/P25_SKILL_PORTABILITY.md"),
        Path("docs/provenance/P25_SKILL_PORTABILITY.zh-CN.md"),
        Path("scripts/skill_composition_core.py"),
        Path("scripts/skillopt_skill_composition.py"),
        Path("tests/test_p26_skill_composition.py"),
        Path("docs/SKILL_COMPOSITION.md"),
        Path("docs/SKILL_COMPOSITION.zh-CN.md"),
        Path("docs/provenance/P26_SKILL_COMPOSITION.md"),
        Path("docs/provenance/P26_SKILL_COMPOSITION.zh-CN.md"),
        Path("docs/provenance/P27_MACRO_PAPER_SPINE.md"),
    }
    found = {relative for _, relative in files}
    if not required.issubset(found):
        raise RuntimeError(f"public package is missing root files: {sorted(str(item) for item in required - found)}")
    manifest_files = [
        {"path": relative.as_posix(), "bytes": source.stat().st_size, "sha256": _sha(source)}
        for source, relative in files
    ]
    manifest = {
        "schema_version": 1, "package": "research-guard",
        "third_party_binary_assets_included": False,
        "optional_addons_included": [],
        "excluded_classes": ["binary dependency payloads", "optional UI add-ons", "paper PDFs", "cached HTML", "venue template ZIPs", "Python caches", "evaluation logs", "project state", "quarantined/admitted domain Skills"],
        "files": manifest_files,
    }
    manifest["manifest_sha256"] = hashlib.sha256(
        json.dumps(manifest_files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_zip = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(temporary_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for source, relative in files:
                available = int(memory_snapshot()["available_physical_bytes"])
                if available < RUN_MIN_FREE_BYTES:
                    raise RuntimeError(
                        f"RESOURCE_LOW_WATER_ABORT: available RAM is {available / 1024 ** 2:.0f} MiB during packaging"
                    )
                archive.write(source, Path("research-guard") / relative)
            archive.writestr(
                "research-guard/RELEASE_MANIFEST.json",
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            )
        os.replace(temporary_zip, output)
    finally:
        if temporary_zip.exists():
            temporary_zip.unlink()
    return {
        "status": "PASS", "path": str(output), "files": len(files) + 1,
        "bytes": output.stat().st_size, "sha256": _sha(output), "start_memory": headroom,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or inspect a Research Guard public package.")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--mode", choices=BUILD_MODES, default="release",
        help="release creates a ZIP; development inspects the current source tree in place",
    )
    parser.add_argument("--bounded-worker", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.mode == "release" and arguments.output is None:
        parser.error("--output is required in release mode")
    if arguments.bounded_worker or os.environ.get("RESEARCH_GUARD_MANAGED_WORKER") == "1":
        print(json.dumps(build(arguments.output, mode=arguments.mode), indent=2))
        return 0
    require_orchestrator_budget()
    command = [
        sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
        "--mode", arguments.mode, "--bounded-worker",
    ]
    if arguments.output is not None:
        command.extend(("--output", str(arguments.output)))
    completed = run_managed(
        command, cwd=PLUGIN_ROOT,
        timeout=300 if arguments.mode == "development" else 900,
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
