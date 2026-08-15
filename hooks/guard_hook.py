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
from paper_audit_core import AuditError, get_paper_audit_status, plan_paper_audit  # noqa: E402
from intent_router_core import route_prompt  # noqa: E402
from dependency_manager import DependencyError, inventory as dependency_inventory  # noqa: E402


if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


RESEARCH_TERMS = re.compile(
    r"novelty|prior work|related work|research idea|method|mechanism|experiment|paper|manuscript|"
    r"architecture|loss(?: function)?|objective|dataset|training|evaluation|contribution|"
    r"创新|查新|查重|已有工作|相关工作|研究想法|方法|机制|架构|结构|目标函数|损失函数|损失|"
    r"数据集|数据|训练|评测|评价|贡献|实验|论文",
    re.IGNORECASE,
)
METHOD_CHANGE_TERMS = re.compile(
    r"\b(?:change|changed|changing|adjust|adjusted|adjusting|revision|revise|revised|revising|"
    r"replace|replaced|replacing|switch|switched|switching|redesign|redesigned|redesigning|"
    r"add|added|adding|remove|removed|removing|modify|modified|modifying)\b|"
    r"改|调整|修改|替换|增加|新增|引入|删除|移除|换成|改为",
    re.IGNORECASE,
)
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
PAPER_AUDIT_TERMS = re.compile(
    r"\b(?:academic writing|write|writing|citation|reference|literature|related work|"
    r"audit|review|formula|equation|theorem|proof)\b|"
    r"学术写作|写作|撰写|引用|参考文献|文献|相关工作|审计|审稿|评审|公式|方程|定理|证明",
    re.IGNORECASE,
)
PAPER_CONTEXT_TERMS = re.compile(r"\b(?:paper|manuscript|code|experiment|results?)\b|论文|稿件|代码|实验|结果", re.IGNORECASE)
AUDIT_ACTION_TERMS = re.compile(r"\b(?:audit|review|check|verify|validate|complete|finalize|submit)\b|审计|审稿|评审|检查|核验|完成|定稿|投稿", re.IGNORECASE)
LANGUAGE_ASSIST_TERMS = re.compile(
    r"\b(?:academic\s+writing|write|writing|rewrite|revise|revision|polish|polishing|edit|editing|"
    r"translate|translation|conference\s+(?:paper|writing|manuscript)|argument|prose|wording|"
    r"defensive\s+writing|hedging|manuscript\s+(?:audit|review))\b|"
    r"学术写作|写作协助|撰写|改写|修改|润色|翻译|译文|会议(?:论文|写作|稿件)|论述|措辞|防御性写作|论文审计|审稿",
    re.IGNORECASE,
)
VENUE_WRITING_TERMS = re.compile(
    r"\b(?:NeurIPS|ICML|ICLR|CVPR|ACL|AAAI|KDD|SIGMOD|CHI|ICSE|conference)\b.*"
    r"\b(?:paper|manuscript|outline|section|chapter|structure|layout|format|narrative|writing|write|draft)\b|"
    r"\b(?:paper|manuscript|outline|section|chapter|structure|layout|format|narrative|writing|write|draft)\b.*"
    r"\b(?:NeurIPS|ICML|ICLR|CVPR|ACL|AAAI|KDD|SIGMOD|CHI|ICSE|conference)\b|"
    r"顶会|会议论文|章节名|分章|排版|叙事风格",
    re.IGNORECASE,
)
STRATEGY_TERMS = re.compile(
    r"\b(?:problem selection|research strategy|project strategy|risk assessment|assumption registry|"
    r"decision tree|go/no-go|fixed parameter|floating parameter|adversity planning|problem inversion|"
    r"stuck project|next research step)\b|"
    r"选题|开题|研究策略|项目策略|风险评估|假设清单|决策树|关卡|固定参数|浮动参数|"
    r"逆境规划|问题反转|项目卡住|下一步怎么走",
    re.IGNORECASE,
)
ACADEMIC_FIGURE_TERMS = re.compile(
    r"\b(?:academic|scientific|publication|paper|research)\s+(?:figure|plot|chart|diagram|visuali[sz]ation)\b|"
    r"\b(?:vector\s+(?:figure|diagram)|statistical\s+(?:plot|chart)|architecture\s+diagram|workflow\s+diagram)\b|"
    r"科研(?:图|绘图|作图|配图|可视化)|学术(?:图|绘图|作图|配图|可视化)|论文(?:图|绘图|作图|配图)|"
    r"统计图|向量图|架构图|流程图|可视化",
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
            "Research Guard first-load dependency selection is required. Core features: "
            + "; ".join(dependency_state["core_features"])
            + ". Components: " + " | ".join(component_lines)
            + f". Actionable component IDs: {', '.join(dependency_state.get('actionable_component_ids', []))}. "
            + f"Inventory-only external adapters: {', '.join(dependency_state.get('informational_component_ids', []))}. "
            + "Ask the user which actionable optional component IDs to install or reuse. External adapters require a separate reviewed environment and cannot be selected here. Do not choose or download for them. "
            "Use dependency_manager.py select --existing ID to reuse a detected environment, "
            "select --install ID for a bundled/fixed install, or acknowledge-none."
        )
        if event == "SessionStart":
            return emit(context(event, dependency_message))
    project = find_project(str(payload.get("cwd") or "."))
    audit_project = find_audit_project(str(payload.get("cwd") or "."))
    prompt = str(payload.get("prompt") or "")

    if event == "UserPromptSubmit":
        messages: list[str] = []
        routed = route_prompt(prompt)
        selected_modules = set(routed["selected_modules"])
        if routed["method_change_overlay"]:
            if project is not None:
                try:
                    declaration = declare_method_change(project, prompt)
                except (GuardError, OSError) as exc:
                    return emit({
                        "continue": False,
                        "stopReason": f"Research Guard could not invalidate the prior receipt: {exc}",
                        "systemMessage": f"Research Guard failed closed while declaring a method change: {exc}",
                    })
                action = "invalidated" if declaration["changed"] else "remains invalid"
                messages.append(
                    f"Research method adjustment detected. The prior novelty receipt is {action}. "
                    "Call research-guard register_method with the complete adjusted method, then rerun the full collision search (rerun the novelty search)."
                )
            else:
                messages.append(
                    "Research method adjustment detected. Call research-guard register_method with the complete adjusted method, then rerun the full collision search (rerun the novelty search); the prior receipt must not be reused."
                )
        if dependency_message:
            messages.append(dependency_message)
        if "paper_audit" in selected_modules or "formula_verification" in selected_modules:
            audit_root = audit_project or project or Path(str(payload.get("cwd") or ".")).expanduser().resolve()
            try:
                audit_plan = plan_paper_audit(audit_root, prompt)
            except (AuditError, OSError) as exc:
                return emit({
                    "continue": False,
                    "stopReason": f"Paper Audit Guard could not register the audit: {exc}",
                    "systemMessage": f"Paper Audit Guard failed closed: {exc}",
                })
            audit_project = audit_root
            roles = ", ".join(audit_plan["selected_roles"])
            lean_note = " Run paper_audit action=lean_check on exactly one full-formula Lean file, then verification_action=cross_verify for separate Pint dimensional, SymPy algebraic, Z3 satisfiability, and protocol-admitted numerical boundary/limit/overflow results before submit." if audit_plan["requirements"]["lean_required"] else ""
            messages.append(
                f"Paper audit triggered with roles [{roles}] at effort={audit_plan['effort']}. Use the research-guard paper_audit tool to complete and submit the selected audits.{lean_note} "
                "Every literature item in collision checks, citation/writing help, or literature analysis must be returned with a clickable https:// hyperlink; missing links fail the audit."
            )
        if "structured_evidence" in selected_modules:
            messages.append(
                "Structured evidence support triggered. Use research-guard paper_audit with integrity_action=ingest or claim_evidence. Bind source and parser-output hashes, require exact block/page/section locators, and preserve parser limitations. Literature or registry evidence needs a clickable https:// primary record; metadata alone cannot support or refute a claim."
            )
        if "research_integrity" in selected_modules:
            messages.append(
                "Research integrity support triggered. Use paper_audit.integrity_action for statistics or record_health, and research_design.integrity_action for preregistration, resource-bounded reproducibility, or active-review ranking. Only the user may freeze/deviate a protocol or decide review inclusion; exit code alone cannot establish reproducibility."
            )
        if "academic_language" in selected_modules:
            messages.append(
                "Academic language review triggered. Use research-guard language_assist to hash-bind the manuscript or translation source/draft, preserve evidence-required uncertainty, run translation or official-venue contracts when applicable, and analyze high-precision wording signals. Present every limitation and potential ethics omission as a user decision checklist; only the user's explicit choice may close it. Resolve other blockers and verify the receipt before paper submission."
            )
        if "venue_evidence" in selected_modules:
            messages.append(
                "Venue writing evidence gate triggered. Before proposing chapter names, order, layout, formatting, or narrative, call research-guard language_assist with venue_action=resolve for the exact venue/year/track/stage. Official policy/template evidence owns hard format rules; award-paper observations are descriptive only. If it returns ONLINE_ACQUISITION_REQUIRED, search and download the exact sources first (official discovery: https://www.google.com/search?q=official+conference+author+guidelines+template ; open records: https://api.openalex.org/works), then venue_action=register. You must not invent or silently borrow a nearby venue/year structure, and every paper/source must be output with a clickable https:// link."
            )
        if "research_strategy" in selected_modules:
            messages.append(
                "Research strategy support triggered. After the user selects and commits a candidate, call research_design plan_strategy, use only its 2-3 modules, then register an evidence-bounded strategy. Attribute priorities and likelihoods to the user, require clickable https:// links for literature evidence, and present every required decision branch for explicit user choice. A method-changing branch must call decide_strategy_branch so the old novelty receipt is invalidated before the adjusted method is registered and searched again."
            )
        if "academic_figure" in selected_modules:
            messages.append(
                "Academic figure support triggered. Use research-guard paper_audit with its figure_action subroute (plan, render, audit, visual_review, verify): bind the claim, raw sources, final physical size, and SVG/PDF/PNG outputs; inspect the current PNG at final size before PASS. Never use image generation for quantitative evidence or exact formal diagrams, silently exclude data, auto-highlight Ours, or claim that automation certifies scientific correctness, accessibility, or venue acceptance."
            )
        if audit_plan.get("requirements", {}).get("openreview_calibration_required") if 'audit_plan' in locals() else False:
            messages.append(
                "OpenReview calibration is required. Use paper_audit review_action=calibrate with official public API v2 forum IDs; preserve clickable forum URLs and review schemas. This only calibrates issue coverage and must never predict acceptance."
            )
        if audit_plan.get("requirements", {}).get("scientific_image_integrity_required") if 'audit_plan' in locals() else False:
            messages.append(
                "Scientific-image integrity audit is required. Use paper_audit image_action=audit to hash-bind originals, processed images, and transformations. Duplicate, metadata, and pixel signals require expert review and must not be reported as findings of fraud."
            )
        if "research_artifact" in selected_modules:
            messages.append(
                "Structured research artifact support triggered. Use research-guard research_design with artifact_action=plan, then submit and verify: paper cards require exactly Sections 01-16 with locators; systematic-review screening decisions remain selected_by=user; experiment logs separate immutable raw measurements from interpretation; reviewer responses require an issue-complete evidence board."
            )
        if "citation_literature" in selected_modules and "paper_audit" not in selected_modules:
            messages.append(
                "Citation and literature support triggered. Search current primary scholarly sources and output one clickable https:// DOI or primary-record link for every item. For APA, MLA, IEEE, or Harvard rendering, call research-guard paper_audit with citation_action=verify_format so Crossref metadata is verified before deterministic formatting; formatting does not prove claim support."
            )
        if "discipline_profile" in selected_modules:
            messages.append(
                "Cross-discipline profile support triggered. Tell the user that the first field-knowledge build queries several official public sources and may take several minutes. Call research-guard research_design with action=status and discipline_action=analyze, passing the complete request_text and any explicit discipline. An unregistered field must be initialized automatically before deep analysis; after initialization, rebuild the novelty plan and rerun the complete collision search. Return every discovered journal, book, catalog, or primary-source record with its clickable https:// evidence URL. Journal candidates are discovery leads, never quality rankings or index-membership claims."
            )
        if "domain_skill" in selected_modules:
            messages.append(
                "In-depth domain support triggered. Call research-guard research_design with domain_skill_action=discover, select one narrow GitHub/SkillsHub candidate, then stage, scan, optimize for exactly 2-3 rounds, and admit after overlap review. Quarantined third-party Skills must not be globally installed or executed automatically."
            )
        if "self_evolution" in selected_modules:
            messages.append(
                "Research Guard evolution support triggered. Use research_design evolution_action=record for evidence-bearing observations and evolution_action=propose only after at least five observations. The mechanism intentionally exposes no apply route: corpus, hook, MCP, marketplace, and knowledge changes still require separate human-reviewed SkillOpt and regression gates."
            )
        mentioned_sources = detect_source_mentions(prompt)
        if mentioned_sources:
            source_text = ", ".join(mentioned_sources)
            if EVIDENCE_SUPPLY_TERMS.search(prompt):
                messages.append(
                    f"User-supplied manual evidence detected for {source_text}. Locate or save the supplied official export/capture inside the project, call request_manual_evidence if fields are missing, then call register_manual_evidence. Do not treat the chat text alone as registered evidence."
                )
            else:
                messages.append(
                    f"Named source requirement detected: {source_text}. Include these values in the method required_sources, call request_manual_evidence after the automated search, and ask the returned questions before claiming coverage."
                )
            if project is None:
                messages.append("No active Research Guard project state was found; call register_method before requesting or importing manual evidence.")
        if RESEARCH_TERMS.search(prompt) or selected_modules:
            if project is None:
                messages.append("Research work detected. Initialize the evidence gate by calling research-guard register_method before novelty or paper claims.")
        if messages:
            return emit(context(event, " ".join(messages)))
        return 0

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
