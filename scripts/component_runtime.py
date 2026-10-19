"""Selected-component capability checks and deferred imports (standard library only).

An installed receipt is the authority. A source checkout without a receipt keeps
the complete development API, while never importing optional modules at startup.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


class ComponentError(ValueError):
    code = "COMPONENT_NOT_INSTALLED"

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        if code is not None:
            self.code = code


def lazy_function(module: str, symbol: str):
    def call(*args, **kwargs):
        try:
            function = getattr(importlib.import_module(module), symbol)
        except ModuleNotFoundError as exc:
            raise ComponentError(
                f"DEPENDENCY_MISSING: {module} requires {exc.name}. Install the selected "
                "group with --install-python-deps into a fresh target; no automatic download occurred.",
                code="DEPENDENCY_MISSING",
            ) from exc
        return function(*args, **kwargs)
    call.__name__ = symbol
    return call


def installed_components(root: Path | None = None) -> set[str] | None:
    path = (root or ROOT) / "COMPONENT_INSTALL.json"
    if not path.is_file():
        return None  # Full source checkout / legacy release.
    try:
        receipt = json.loads(path.read_text(encoding="utf-8-sig"))
        stable = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
        actual = hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False,
                                          separators=(",", ":")).encode()).hexdigest()
        selected = receipt["resolved_components"]
        if actual != receipt["receipt_sha256"] or not isinstance(selected, list) or "core" not in selected:
            raise ValueError("invalid component receipt")
        return set(selected)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ComponentError(f"COMPONENT_RECEIPT_INVALID: {exc}", code="COMPONENT_RECEIPT_INVALID") from exc


FAMILIES = {
    "research_design": {
        "instruction_action": "core", "delegation_action": "core", "dependency_action": "core",
        "maintenance_action": "core", "metrics_action": "experiments", "resource_plan_action": "experiments",
        "direction_action": "experiments", "discipline_action": "literature", "artifact_action": "literature",
        "integrity_action": "experiments", "knowledge_action": "citespace", "frontier_analysis_action": "citespace",
        "domain_skill_action": "skill-lab", "frontier_skill_action": "skill-lab",
        "skill_portability_action": "skill-lab", "skill_composition_action": "skill-lab", "evolution_action": "skill-lab",
    },
    "paper_audit": {
        "figure_action": "figures", "image_action": "figures", "numerical_action": "formal",
        "verification_action": "formal", "citation_action": "literature", "integrity_action": "literature",
        "tex_action": "writing", "review_action": "writing",
    },
}
TOOL_GROUPS = {
    "select_research_modules": "core", "list_research_modules": "core", "register_method": "core",
    "get_gate_status": "core", "get_collision_report": "core", "research_design": "core",
    "language_assist": "writing",
}
MODULE_GROUPS = {
    "venue_evidence": "writing", "formula_verification": "formal", "academic_figure": "figures",
    "structured_evidence": "literature", "research_integrity": "experiments", "research_artifact": "literature",
    "paper_audit": "writing", "citation_literature": "literature", "self_evolution": "skill-lab",
    "domain_skill": "skill-lab", "discipline_profile": "literature", "research_strategy": "research",
    "resource_planning": "experiments", "academic_language": "writing", "research_novelty": "literature",
}


def require_component(group: str, selected: set[str] | None = None) -> None:
    selected = installed_components() if selected is None else selected
    if selected is not None and group not in selected:
        raise ComponentError(
            f"COMPONENT_NOT_INSTALLED: {group}. Installed: {', '.join(sorted(selected))}. "
            f"Use scripts/component_install.py --components {group} --target <fresh-directory> "
            "and explicitly add --install-python-deps if required."
        )


def check_call(name: str, arguments: dict[str, Any]) -> None:
    selected = installed_components()
    if selected is None:
        return
    if name in FAMILIES:
        found = False
        for key, group in FAMILIES[name].items():
            if arguments.get(key):
                require_component(group, selected)
                found = True
        if not found:
            group = "research" if name == "research_design" else (
                "formal" if arguments.get("action") == "lean_check" else
                next((item for item in ("writing", "formal", "figures") if item in selected), "writing"))
            require_component(group, selected)
    else:
        require_component(TOOL_GROUPS.get(name, "literature"), selected)
    if name == "select_research_modules":
        for module in arguments.get("selected_modules", []):
            if module in MODULE_GROUPS:
                require_component(MODULE_GROUPS[module], selected)


def filter_modules(value: dict[str, Any]) -> dict[str, Any]:
    selected = installed_components()
    if selected is None:
        return value
    result = dict(value)
    result["modules"] = [item for item in value["modules"] if MODULE_GROUPS.get(item["id"]) in selected]
    result["installed_components"] = sorted(selected)
    return result


def available_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = installed_components()
    if selected is None:
        return tools
    result = []
    for original in tools:
        name = original["name"]
        if name not in FAMILIES and TOOL_GROUPS.get(name, "literature") not in selected:
            continue
        if name == "paper_audit" and not selected.intersection({"writing", "formal", "figures", "literature"}):
            continue
        tool = copy.deepcopy(original)
        properties = tool["inputSchema"]["properties"]
        for key, group in FAMILIES.get(name, {}).items():
            if group not in selected:
                properties.pop(key, None)
        if name in FAMILIES:
            base_group = "research" if name == "research_design" else "writing"
            if name == "paper_audit" and selected.intersection({"formal", "figures"}):
                properties["action"]["enum"] = ["plan", "submit", "status", "verify"] + (
                    ["lean_check"] if "formal" in selected else [])
            elif base_group not in selected:
                properties["action"]["enum"] = ["status"] + (
                    ["lean_check"] if name == "paper_audit" and "formal" in selected else [])
                properties["action"]["description"] = (
                    "Compatibility envelope: status requires one installed sub-action. "
                    "Default workflow is not installed.")
        if name == "paper_audit" and "formal" not in selected:
            properties["action"]["enum"] = [item for item in properties["action"]["enum"] if item != "lean_check"]
        result.append(tool)
    return result


def validate_action_arguments(tools: list[dict[str, Any]], name: str, arguments: dict[str, Any]) -> None:
    tool = next((item for item in tools if item["name"] == name), None)
    if tool is None:
        return
    properties = tool["inputSchema"]["properties"]
    for key, value in arguments.items():
        if key == "action" or key.endswith("_action"):
            allowed = properties.get(key, {}).get("enum")
            if allowed is not None and value not in allowed:
                raise ComponentError(f"INVALID_ACTION: {name}.{key}={value!r}; allowed: {allowed}", code="INVALID_ACTION")


def component_inventory() -> dict[str, Any]:
    selected = installed_components()
    return {
        "installation_mode": "selected-components" if selected is not None else "full-source-or-legacy",
        "installed_components": sorted(selected) if selected is not None else None,
        "first_load_pending": False,
        "optional_selection_mode": "explicit-component-installation",
        "receipt": str(ROOT / "COMPONENT_INSTALL.json") if selected is not None else None,
        "citespace_engine_status": "NOT_VERIFIED_BY_COMPONENT_INSTALLATION",
        "note": "A copied group is not proof that its external engine, credentials, or online sources work.",
    }


def selected_component_python(group: str, root: Path | None = None) -> Path | None:
    """Return only a selected installation's bound private Python, or legacy None.

    A selected receipt is authoritative: a missing dependency or invalid binding
    cannot fall back to a host/global legacy core-runtime receipt.
    """
    import os

    package = (root or ROOT).resolve()
    path = package / "COMPONENT_INSTALL.json"
    if not path.is_file():
        return None
    selected = installed_components(package)
    if group not in selected:
        raise ComponentError(f"COMPONENT_NOT_INSTALLED: {group}")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8-sig"))
        stable = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        digest = hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False,
                                          separators=(",", ":")).encode()).hexdigest()
        if digest != receipt.get("receipt_sha256") or receipt.get("status") != "INSTALLED":
            raise ValueError("installation receipt changed or is incomplete")
        if receipt.get("python_dependency_status") != "INSTALLED":
            raise ValueError("selected Python dependencies are not INSTALLED; explicitly install the selected group with --install-python-deps")
        interpreter = Path(receipt["interpreter"])
        expected = package / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not interpreter.is_file() or not expected.is_file() or not os.path.samefile(interpreter, expected):
            raise ValueError("interpreter is not the package's bound .venv Python")
        with interpreter.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != receipt.get("interpreter_sha256"):
                raise ValueError("bound interpreter SHA256 differs")
        configuration = (package / ".venv" / "pyvenv.cfg").read_text(encoding="utf8")
        if not any(line.strip().casefold() == "include-system-site-packages = false" for line in configuration.splitlines()):
            raise ValueError("bound venv must disable system site-packages")
        return interpreter
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ComponentError(f"COMPONENT_RUNTIME_INVALID: {exc}") from exc
