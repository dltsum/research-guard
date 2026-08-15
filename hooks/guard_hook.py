from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from research_guard_core import (  # noqa: E402
    GuardError,
    declare_method_change,
    detect_source_mentions,
    load_state,
    sync_discipline_profile_files,
    sync_manual_evidence_files,
    sync_tracked_method_files,
)
from paper_audit_core import AuditError, get_paper_audit_status  # noqa: E402
from dependency_manager import (  # noqa: E402
    DependencyError,
    component_need as dependency_need,
    inventory as dependency_inventory,
)


if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


PROTECTED_TERMS = re.compile(
    r"(?:^|[\\/\s\"'])(?:paper|manuscript|proposal|abstract|introduction|related[_ -]?work|results?|论文|方法|实验)"
    r"[^\s\"']*|\.tex(?:\s|$)|\.docx(?:\s|$)",
    re.IGNORECASE,
)
WRITE_TERMS = re.compile(
    r"apply_patch|set-content|add-content|out-file|writealltext|write_text|>>|(?<![<>=])>(?![>=])|"
    r"\b(?:cp|copy|mv|move|tee|sed)\b",
    re.IGNORECASE,
)
EVIDENCE_SUPPLY_TERMS = re.compile(
    r"https?://|附件|截图|导出|检索结果|搜索结果|文件|路径|哈希|sha-?256|"
    r"attached|screenshot|export|result|capture|\.csv\b|\.ris\b|\.bib\b|\.json\b|\.pdf\b|\.png\b|\.jpe?g\b",
    re.IGNORECASE,
)
def emit(value: dict[str, Any]) -> int:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    return 0


def find_project(cwd: str) -> Path | None:
    current = Path(cwd).expanduser().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".research-guard" / "state.json").is_file():
            return candidate
    return None


def find_audit_project(cwd: str) -> Path | None:
    current = Path(cwd).expanduser().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".research-guard" / "paper-audit-state.json").is_file():
            return candidate
    return None


def context(event: str, message: str) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}


def deny(reason: str) -> dict[str, Any]:
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason,
    }}


def dependency_context(component_id: str) -> str:
    guidance = dependency_need(component_id)
    if guidance["status"] == "AVAILABLE":
        return ""
    if guidance["status"] == "DEGRADED":
        return (
            f"Optional component {component_id} was declined. Continue only with this recorded degradation: "
            f"{guidance.get('degradation')} Do not report the omitted capability as PASS."
        )
    if guidance["status"] == "INSTALL_INCOMPLETE":
        return f"Optional component {component_id} was selected but installation is incomplete; stop that capability and expose the failed/incomplete state."
    choices = "; ".join(
        f"{item['id']} => {item['command']}" for item in guidance.get("choices", [])
    )
    prerequisite = guidance.get("prerequisite")
    prerequisite_text = f" Prerequisite: {prerequisite}." if prerequisite else ""
    return (
        f"The requested capability needs optional component {component_id}. Ask the user before any installation. "
        f"Download estimate={guidance['download_bytes_min'] / 1048576:.1f}-"
        f"{guidance['download_bytes_max'] / 1048576:.1f} MiB; installed estimate="
        f"{guidance['installed_bytes_min'] / 1073741824:.2f}-"
        f"{guidance['installed_bytes_max'] / 1073741824:.2f} GiB. Choices: {choices}."
        f"{prerequisite_text} If the user chooses not_now, use only the named degradation and label omitted checks NOT_RUN."
    )


def tool_text(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        return json.dumps(tool_input, ensure_ascii=False, sort_keys=True)
    return str(tool_input or "")


def touches_tracked(text: str, state: dict[str, Any]) -> bool:
    lowered = text.replace("\\", "/").lower()
    files = state.get("active_method", {}).get("payload", {}).get("method_files", [])
    return any(item.replace("\\", "/").lower() in lowered for item in files)


def protected_write(payload: dict[str, Any], text: str) -> bool:
    tool = str(payload.get("tool_name", ""))
    is_write = tool == "apply_patch" or bool(WRITE_TERMS.search(text))
    return is_write and bool(PROTECTED_TERMS.search(text))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError) as exc:
        return emit({"systemMessage": f"Research Guard hook received invalid input: {exc}"})
    event = str(payload.get("hook_event_name", ""))
    try:
        dependency_state = dependency_inventory()
    except DependencyError as exc:
        return emit({
            "continue": False,
            "stopReason": f"Research Guard dependency state is invalid: {exc.code}",
            "systemMessage": str(exc),
        })
    dependency_message = ""
    if dependency_state["first_load_pending"]:
        component_lines = []
        for item in dependency_state["components"]:
            download_min = item.get("download_bytes_min", item.get("download_bytes", 0))
            download_max = item.get("download_bytes_max", item.get("download_bytes", 0))
            component_lines.append(
                f"{item['id']}: bundled={item['bundled_bytes'] / 1048576:.1f} MiB, "
                f"download={download_min / 1048576:.1f}-{download_max / 1048576:.1f} MiB, "
                f"installed={item.get('installed_bytes_min', 0) / 1073741824:.2f}-"
                f"{item.get('installed_bytes_max', 0) / 1073741824:.2f} GiB; "
                f"features={', '.join(item.get('features', []))}"
            )
        dependency_message = (
            "Research Guard core work is ready; optional dependencies are selected on demand. Core features: "
            + "; ".join(dependency_state["core_features"])
            + ". Components: " + " | ".join(component_lines)
            + f". Actionable component IDs: {', '.join(dependency_state.get('actionable_component_ids', []))}. "
            + f"Inventory-only external adapters: {', '.join(dependency_state.get('informational_component_ids', []))}. "
            + "Do not ask the user to choose everything now. When a requested capability needs one component, call research_design dependency_action=need, show reuse/install/not_now with exact sizes, and wait for the user's decision. Never download automatically."
        )
        if event == "SessionStart":
            return emit(context(event, dependency_message))
    project = find_project(str(payload.get("cwd") or "."))
    audit_project = find_audit_project(str(payload.get("cwd") or "."))
    prompt = str(payload.get("prompt") or "")

    if event == "UserPromptSubmit":
        messages = [
            "Research Guard does not run keyword domain classifiers, automatic module routers, or automatic reviewer-role selectors. "
            "If this request involves research, the main agent must call list_research_modules, then select_research_modules with 1-3 explicit modules, selected_by=main_agent, a rationale, and method_change=true exactly when its semantic judgment says the research method changed. "
            "Register the method first, then register an explicit domain selection before collision search. Paper audits likewise require 2-3 roles and explicit audit_features chosen by the main agent. "
            "A novelty-search response with status=IN_PROGRESS is a durable stage result, not a stopping condition: report its factual linked results to the user and continue from the checkpoint. ACTION_REQUIRED means the main agent must retry explicit failed units, register admissible manual evidence, or submit a factual blocker_decision covering every failed required unit. Per-attempt transport or child-process timeouts never constitute a research deadline; stop only after the coverage contract completes, that blocker is preserved, or the user explicitly sets a budget/time/stop constraint."
        ]
        mentioned_sources = detect_source_mentions(prompt)
        if mentioned_sources:
            source_text = ", ".join(mentioned_sources)
            if EVIDENCE_SUPPLY_TERMS.search(prompt):
                messages.append(
                    f"The user explicitly mentioned evidence for {source_text}. Preserve it inside the project and register its official HTTPS provenance before claiming coverage."
                )
            else:
                messages.append(
                    f"The user explicitly named {source_text}; the main agent must include it in its source plan and return clickable HTTPS evidence."
                )
        return emit(context(event, " ".join(messages)))

    if audit_project is not None:
        try:
            audit_status = get_paper_audit_status(audit_project)
        except AuditError as exc:
            if event == "Stop":
                return emit({"decision": "block", "reason": f"Repair invalid paper audit state before stopping: {exc}"})
            return emit({"systemMessage": f"Paper Audit Guard state error: {exc}"})
        if event == "Stop" and audit_status["status"] != "PASS":
            reason = f"Paper audit gate is {audit_status['status']}: {audit_status['reason']}"
            if payload.get("stop_hook_active"):
                return emit({"continue": False, "stopReason": reason, "systemMessage": reason})
            return emit({"decision": "block", "reason": reason})
        if project is None and event == "SessionStart":
            return emit(context(event, f"Paper Audit Guard active: {audit_status['status']}. Literature outputs require clickable https:// links."))
        if project is None and event == "PostToolUse" and audit_status["status"] != "PASS":
            return emit(context(event, f"Paper audit remains {audit_status['status']}: {audit_status['reason']}"))

    if project is None:
        return 0

    try:
        if event == "PostToolUse":
            sync = {"changed": False}
            manual_sync = {"changed": False, "invalid_sources": []}
            discipline_sync = {"changed": False, "errors": []}
            state = load_state(project)
        else:
            sync = sync_tracked_method_files(project)
            discipline_sync = sync_discipline_profile_files(project)
            manual_sync = sync_manual_evidence_files(project)
            state = load_state(project)
    except GuardError as exc:
        if event == "PreToolUse" and protected_write(payload, tool_text(payload)):
            return emit(deny(f"Research Guard state is invalid: {exc}"))
        if event == "Stop":
            return emit({"decision": "block", "reason": f"Repair invalid Research Guard state before stopping: {exc}"})
        return emit({"systemMessage": f"Research Guard state error: {exc}"})

    gate = state["gate"]
    if event == "SessionStart":
        changed = " A tracked method file changed, so the receipt was invalidated." if sync.get("changed") else ""
        discipline_changed = " A bound discipline profile changed, so the search plan and receipt must be rebuilt." if discipline_sync.get("errors") else ""
        manual_changed = " A registered manual evidence capture changed, so it must be imported again." if manual_sync.get("changed") else ""
        return emit(context(event, f"Research Guard active: method v{state['active_method']['version']}, gate {gate['status']}.{changed}{discipline_changed}{manual_changed}"))

    if event == "PreToolUse":
        text = tool_text(payload)
        if protected_write(payload, text) and gate["status"] != "PASS":
            if touches_tracked(text, state) and not re.search(r"\.tex|paper|manuscript|proposal|论文", text, re.IGNORECASE):
                return emit(context(event, "Allow the method edit, then re-register the full method and rerun novelty search before protected outputs."))
            return emit(deny(f"Novelty gate is {gate['status']}: {gate['reason']}"))
        if touches_tracked(text, state):
            return emit(context(event, "This tool touches a tracked method file. Its receipt will be invalidated after the tool finishes."))
        return 0

    if event == "PostToolUse":
        after = sync_tracked_method_files(project)
        discipline_after = sync_discipline_profile_files(project)
        manual_after = sync_manual_evidence_files(project)
        if after.get("changed"):
            return emit(context(event, "Tracked method content changed. The old novelty receipt is invalid; register and search the adjusted method now."))
        if manual_after.get("changed"):
            return emit(context(event, "A registered manual evidence capture changed. The old receipt is invalid; call request_manual_evidence and register_manual_evidence again."))
        if discipline_after.get("errors"):
            return emit(context(event, "The bound discipline registry or live profile changed. The old receipt is invalid; rebuild the field-aware search plan and rerun the complete collision search."))
        return 0

    if event == "Stop" and gate["status"] != "PASS":
        reason = f"Research acceptance gate is {gate['status']}: {gate['reason']}"
        if payload.get("stop_hook_active"):
            return emit({"continue": False, "stopReason": reason, "systemMessage": reason})
        return emit({"decision": "block", "reason": reason})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
