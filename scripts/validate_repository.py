from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from hydrate_release_payloads import validate_bootstrap_contract


ROOT = Path(__file__).resolve().parents[1]
MIB = 1024 ** 2
REQUIRED_ROOT = {
    ".codex-plugin/plugin.json", ".editorconfig", ".gitattributes", ".gitignore",
    ".github/workflows/ci.yml", ".github/workflows/release.yml",
    ".github/PULL_REQUEST_TEMPLATE.md", ".github/CODEOWNERS", ".github/dependabot.yml",
    "CHANGELOG.md", "CITATION.cff", "CODE_OF_CONDUCT.md", "CONTRIBUTING.md",
    "GOVERNANCE.md", "LICENSE", "README.md", "README.zh-CN.md", "SECURITY.md", "SKILL.md", "SUPPORT.md",
    "THIRD_PARTY_NOTICES.md", "docs/DISCIPLINE_SUPPORT.md", "docs/EDUCATION_SUPPORT.md",
    "docs/TIME_AND_CONTINUATION_POLICY.md", "docs/SUBAGENT_DELEGATION.md",
    "docs/RESOURCE_AWARE_TASK_PLANNING.md", "docs/DIRECTION_EXPLORATION.md",
    "docs/provenance/P20_DIRECTION_EXPLORATION.md",
    "docs/provenance/P21_CI_MIGRATION_ASSURANCE.md",
    "docs/provenance/SUBAGENT_DELEGATION_VERIFICATION.md",
    "requirements-core.txt", "requirements-dev.txt", "REQUIREMENTS.md",
    "scripts/install.ps1", "scripts/install.sh", "scripts/install_posix.py",
    "scripts/mcp_launcher.py", "scripts/mcp.sh", "scripts/experiment_metrics_core.py",
    "scripts/llm_delegation_core.py", "scripts/skillopt_subagent_delegation.py",
    "scripts/resource_task_planner_core.py", "scripts/skillopt_resource_task_planning.py",
    "scripts/direction_exploration_core.py", "scripts/skillopt_direction_exploration.py",
    "scripts/test_isolated_install.py", "scripts/verify_isolated_install.py",
    "scripts/hydrate_release_payloads.py", "assets/payload-bootstrap.json",
    "scripts/skillopt_ci_migration.py", "tests/test_p21_ci_migration_assurance.py",
    "tests/test_resource_task_planning.py", "assets/llm-delegation-policy.json",
    "tests/test_direction_exploration.py", "assets/task-resource-profiles.json",
    "assets/direction-exploration-contract.json",
}
PRIVATE_PATH = re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s\"'<>]+", re.I)
TEXT_SUFFIXES = {".cff", ".cmd", ".json", ".md", ".ps1", ".py", ".sh", ".txt", ".yaml", ".yml"}
TEXT_NAMES = {"LICENSE", ".editorconfig", ".gitattributes", ".gitignore", ".mcp.json"}


def _load_yaml(relative: str) -> Any:
    return yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))


def _git_excluded(relative: Path) -> bool:
    parts = relative.parts
    if not parts:
        return False
    if parts[0] in {"evals", "dist", "build"}:
        return True
    if parts[:2] == ("docs", "development"):
        return True
    if parts[:2] == ("assets", "payloads"):
        return True
    if parts[:2] == ("assets", "venue-evidence") and relative.suffix.casefold() in {".html", ".pdf", ".zip"}:
        return True
    if "__pycache__" in parts or relative.suffix.casefold() in {".pyc", ".pyo"}:
        return True
    return False


def validate() -> dict[str, Any]:
    missing = sorted(item for item in REQUIRED_ROOT if not (ROOT / item).is_file())
    if missing:
        raise RuntimeError(f"required GitHub files are missing: {missing}")
    root_internal = sorted(path.name for path in ROOT.glob("P[0-9]*_*") if path.is_file())
    if root_internal:
        raise RuntimeError(f"development phase files remain at repository root: {root_internal}")

    plugin = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    if plugin.get("name") != "research-guard" or plugin.get("skills") != "./skills/":
        raise RuntimeError("plugin manifest name or Skills boundary is invalid")
    if plugin.get("author", {}).get("name") != "Research Guard contributors":
        raise RuntimeError("plugin author metadata is not publication-ready")
    if "hooks" in plugin:
        raise RuntimeError("unsupported hooks field is present in plugin manifest")
    base_version = str(plugin.get("version", "")).split("+", 1)[0]
    citation = _load_yaml("CITATION.cff")
    if base_version != str(citation.get("version")):
        raise RuntimeError("plugin and citation versions do not match")

    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    if not skill.startswith("---\n") or "name: research-guard" not in skill:
        raise RuntimeError("traditional Skill frontmatter is invalid")
    if len(skill.splitlines()) > 500:
        raise RuntimeError("SKILL.md exceeds the progressive-disclosure line budget")
    openai = _load_yaml("agents/openai.yaml")
    if openai.get("interface", {}).get("display_name") != "Research Guard":
        raise RuntimeError("agents/openai.yaml does not match the Skill")

    registry = json.loads((ROOT / "assets" / "discipline-registry.json").read_text(encoding="utf-8"))
    profiles = registry.get("disciplines") or []
    if len(profiles) < 22 or len({item.get("id") for item in profiles}) != len(profiles):
        raise RuntimeError("discipline registry is incomplete or has duplicate ids")
    required_profiles = {
        "computer_science", "engineering", "mathematics_statistics", "natural_science",
        "medicine_life_science", "social_science", "humanities", "history",
        "education", "educational_technology",
    }
    if not required_profiles <= {item.get("id") for item in profiles}:
        raise RuntimeError("discipline registry is missing a required broad/history profile")
    catalogs = registry.get("public_catalogs") or {}
    if not catalogs or any(not str(item.get("url", "")).startswith("https://") for item in catalogs.values()):
        raise RuntimeError("discipline public catalogs must have HTTPS URLs")
    for resource_group in ("venue_resources", "method_resources", "data_resources"):
        resources = registry.get(resource_group) or {}
        if not resources or any(not str(item.get("url", "")).startswith("https://") for item in resources.values()):
            raise RuntimeError(f"discipline {resource_group} must have HTTPS URLs")

    english_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    parity_tokens = (
        "research-guard-windows-x64-modular.zip", "research-guard-linux-x64.zip",
        "research-guard-macos-x64.zip", "research-guard-macos-arm64.zip",
        "metrics_action=plan", "educational technology", "512 MiB", "17 top-level MCP tools",
        "Native-subagent-first LLM delegation",
        "Resource-aware task planning", "resource_plan_action=inventory", "resource_plan_action=execute",
        "Authorized local-resource direction exploration", "direction_action", "exactly five",
        "3-day verified CI archive",
    )
    if any(token not in english_readme for token in parity_tokens):
        raise RuntimeError("English README is missing a required cross-platform/capability token")
    chinese_tokens = (
        "research-guard-windows-x64-modular.zip", "research-guard-linux-x64.zip",
        "research-guard-macos-x64.zip", "research-guard-macos-arm64.zip",
        "metrics_action=plan", "教育技术学", "512 MiB", "17 个顶层 MCP 工具",
        "原生 subagent 优先的 LLM 委派",
        "资源感知任务规划", "resource_plan_action=inventory", "resource_plan_action=execute",
        "经授权的本地资源科研方向探索", "direction_action", "恰好五个",
        "3 天已验证 CI 归档",
    )
    if any(token not in chinese_readme for token in chinese_tokens):
        raise RuntimeError("Chinese README is missing a required cross-platform/capability token")

    mcp = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    server = mcp.get("mcpServers", {}).get("research-guard", {})
    if server.get("command") != "python" or not any("mcp_launcher.py" in value for value in server.get("args", [])):
        raise RuntimeError("source MCP entrypoint is not platform-neutral")

    bootstrap = validate_bootstrap_contract(
        ROOT / "assets" / "payload-bootstrap.json",
        ROOT / "assets" / "payload-manifest.json",
    )

    policy = json.loads((ROOT / "assets" / "resource-policy.json").read_text(encoding="utf-8"))
    expected = {
        "owned_task_budget_bytes": 512 * MIB,
        "worker_job_limit_bytes": 384 * MIB,
        "orchestrator_reserve_bytes": 128 * MIB,
        "install_worker_limit_bytes": 448 * MIB,
        "install_orchestrator_reserve_bytes": 64 * MIB,
        "lean_worker_limit_bytes": 464 * MIB,
        "lean_orchestrator_reserve_bytes": 48 * MIB,
        "lean_trim_trigger_bytes": 384 * MIB,
        "start_min_free_bytes": 768 * MIB,
        "run_min_free_bytes": 512 * MIB,
        "maximum_parallel_workers": 1,
        "gpu_allowed": False,
        "execution_mode": "incremental_serial",
        "memory_metric": "aggregate_working_set",
        "sampling_interval_seconds": 0.01,
    }
    for key, value in expected.items():
        if policy.get(key) != value:
            raise RuntimeError(f"resource policy drift: {key}={policy.get(key)!r}")
    if policy["worker_job_limit_bytes"] + policy["orchestrator_reserve_bytes"] > policy["owned_task_budget_bytes"]:
        raise RuntimeError("resource worker plus orchestrator exceeds total budget")
    if policy["install_worker_limit_bytes"] + policy["install_orchestrator_reserve_bytes"] > policy["owned_task_budget_bytes"]:
        raise RuntimeError("installer worker plus orchestrator exceeds total budget")
    if policy["lean_worker_limit_bytes"] + policy["lean_orchestrator_reserve_bytes"] > policy["owned_task_budget_bytes"]:
        raise RuntimeError("Lean worker plus orchestrator exceeds total budget")
    task_profiles = json.loads((ROOT / "assets" / "task-resource-profiles.json").read_text(encoding="utf-8"))
    task_profile_map = task_profiles.get("profiles") or {}
    if set(task_profile_map) != {"inline_light", "managed_standard", "managed_install", "managed_lean", "llm_assistance", "external_wait"}:
        raise RuntimeError("resource task profile set is invalid")
    if task_profile_map["managed_standard"].get("worker_limit_bytes") != policy["worker_job_limit_bytes"]:
        raise RuntimeError("standard task profile does not match resource policy")
    if task_profile_map["managed_install"].get("worker_limit_bytes") != policy["install_worker_limit_bytes"]:
        raise RuntimeError("installer task profile does not match resource policy")
    if task_profile_map["managed_lean"].get("worker_limit_bytes") != policy["lean_worker_limit_bytes"]:
        raise RuntimeError("Lean task profile does not match resource policy")
    if task_profiles.get("global_contract", {}).get("maximum_parallel_tasks") != 1:
        raise RuntimeError("resource task planner must remain serial")
    if task_profiles.get("global_contract", {}).get("gpu_allowed") is not False:
        raise RuntimeError("resource task planner must remain GPU-off")

    _load_yaml(".github/workflows/ci.yml")
    _load_yaml(".github/workflows/release.yml")
    _load_yaml(".github/dependabot.yml")
    for relative in (
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/ISSUE_TEMPLATE/bug.yml",
        ".github/ISSUE_TEMPLATE/feature.yml",
    ):
        _load_yaml(relative)

    text_files = 0
    source_bytes = 0
    excluded_bytes = 0
    oversized: list[str] = []
    private_hits: list[str] = []
    for path in sorted(item for item in ROOT.rglob("*") if item.is_file()):
        relative = path.relative_to(ROOT)
        excluded = _git_excluded(relative)
        if excluded:
            excluded_bytes += path.stat().st_size
        else:
            source_bytes += path.stat().st_size
            if path.stat().st_size > 95 * MIB:
                oversized.append(relative.as_posix())
            if (relative.suffix.casefold() in TEXT_SUFFIXES or relative.name in TEXT_NAMES):
                text_files += 1
                value = path.read_text(encoding="utf-8", errors="strict")
                if PRIVATE_PATH.search(value):
                    private_hits.append(relative.as_posix())
                if ("Local" + " developer") in value:
                    private_hits.append(f"{relative.as_posix()}: placeholder author")
    if oversized:
        raise RuntimeError(f"GitHub source contains oversized files: {oversized}")
    if private_hits:
        raise RuntimeError(f"public text contains private paths/placeholders: {private_hits}")

    return {
        "status": "PASS",
        "required_files": len(REQUIRED_ROOT),
        "validated_text_files": text_files,
        "github_source_bytes": source_bytes,
        "locally_excluded_bytes": excluded_bytes,
        "resource_budget_bytes": policy["owned_task_budget_bytes"],
        "plugin": plugin["name"],
        "version": base_version,
        "discipline_profiles": len(profiles),
        "discipline_catalogs": len(catalogs),
        "payload_bootstrap_release": bootstrap["release_tag"],
    }


def main() -> int:
    try:
        report = validate()
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
