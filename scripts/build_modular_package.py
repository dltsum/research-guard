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


# Build behavior history (keep the two most recent behaviors here, close to the
# implementation that owns them):
# - v0.8-dev (2026-08-26): ``mode=development`` reads the current source tree
#   in place and emits a small receipt only.  It deliberately omits payload
#   hydration, release pinning, and per-file hashes; edit the source and rerun.
# - v0.7-release (2026-08-23): ``mode=release`` builds the migration ZIP with
#   the existing payload preflight and artifact manifest used by CI/releases.
#   Release checks are kept separate from exploratory source-tree work.


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BUILD_MODES = ("release", "development")
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


def _development_receipt(
    files: list[tuple[Path, Path]], platform_target: str,
) -> dict[str, object]:
    """Describe the source tree without copying it or pinning its contents.

    Development builds are intentionally not release artifacts.  In
    particular, no digest is calculated for source files: developers should
    edit the one checked-out tree and rerun the operation.  Release mode below
    remains the only path that emits a ZIP and a file-level manifest.
    """
    return {
        "status": "PASS",
        "mode": "development",
        "platform": platform_target,
        "source_tree": True,
        "archive_created": False,
        "third_party_assets_included": False,
        "files": len(files),
        "source_bytes": sum(path.stat().st_size for path, _ in files),
        "hashes": "omitted_in_development_mode",
        "message": "Source tree was inspected in place; edit it directly and rerun.",
    }


def build(
    output: Path | None, platform_target: str, *, mode: str = "release",
) -> dict[str, object]:
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
            raise RuntimeError("output must be a .zip file")
    if mode == "release" and platform_target == "windows-x64":
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
            # Exploratory builds never copy third-party payloads.  The release
            # Windows path includes them only after its explicit preflight.
            if (
                (mode == "development" or platform_target != "windows-x64")
                and relative.parts[:2] == ("assets", "payloads")
            ):
                continue
            if mode == "release":
                _check_text(path, relative)
            files.append((path, relative))
    if mode == "development":
        receipt = _development_receipt(files, platform_target)
        receipt["start_memory"] = headroom
        return receipt
    found = {relative for _, relative in files}
    required = {Path(name) for name in ROOT_FILES} | {
        Path("agents/openai.yaml"), Path("references/dependencies.md"),
        Path("assets/dependency-catalog.json"), Path("assets/payload-manifest.json"),
        Path("assets/payload-bootstrap.json"), Path("scripts/hydrate_release_payloads.py"),
        Path("scripts/install.ps1"), Path("scripts/install.sh"), Path("scripts/install_posix.py"), Path("scripts/network_config_core.py"),
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
        Path("docs/provenance/P17_PAPER_WRITING_AI_REVIEWER_AND_FIGURES.md"),
        Path("docs/provenance/P18_ACTIVE_AI_REVIEWER_OPTIMIZATION.md"),
        Path("references/research-progression-contract.md"),
        Path("skills/academic-figure-guard/references/visual-quality-contract.md"),
        Path("skills/paper-audit-guard/references/ai-reviewer-optimization.md"),
        Path("skills/academic-language-guard/references/paper-spine-contract.md"),
        Path("docs/provenance/P12_COMPONENT_REGISTRY.json"),
        Path("docs/provenance/P12_OVERLAP_AUDIT.md"),
        Path("docs/provenance/P12_SKILLOPT_REPORT.md"),
        Path("docs/provenance/P13_RELEASE_VERIFICATION.md"),
        Path("docs/provenance/P14_DISCIPLINE_AND_RELEASE.md"),
        Path("skills/paper-audit-guard/references/research-integrity-contracts.md"),
        Path("skills/research-design-guard/references/research-integrity-contracts.md"),
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
    parser = argparse.ArgumentParser(description="Build or inspect the Research Guard modular migration Skill")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--platform", dest="platform_target", required=True,
        choices=("windows-x64", "linux-x64", "macos-x64", "macos-arm64"),
    )
    parser.add_argument(
        "--mode", choices=BUILD_MODES, default="release",
        help="release creates a ZIP; development inspects the current source tree in place",
    )
    parser.add_argument("--bounded-worker", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.mode == "release" and arguments.output is None:
        parser.error("--output is required in release mode")
    if arguments.bounded_worker or os.environ.get("RESEARCH_GUARD_MANAGED_WORKER") == "1":
        print(json.dumps(
            build(arguments.output, arguments.platform_target, mode=arguments.mode),
            ensure_ascii=False, indent=2,
        ))
        return 0
    require_orchestrator_budget()
    command = [
        sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
        "--platform", arguments.platform_target, "--mode", arguments.mode, "--bounded-worker",
    ]
    if arguments.output is not None:
        command.extend(("--output", str(arguments.output)))
    completed = run_managed(
        command, cwd=PLUGIN_ROOT,
        timeout=300 if arguments.mode == "development" else 1800,
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
