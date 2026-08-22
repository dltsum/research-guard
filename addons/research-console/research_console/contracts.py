from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MAX_REQUEST_BYTES = 256 * 1024
MAX_MESSAGE_CHARACTERS = 50_000
MAX_SELECTED_FOCUS = 3
SANDBOXES = {"read-only", "workspace-write"}
LOCALES = {"en", "zh-CN"}

FOCUS_OPTIONS: tuple[dict[str, str], ...] = (
    {
        "id": "auto",
        "label_en": "Let Codex choose",
        "label_zh": "由 Codex 判断",
        "description_en": "The main Codex reads the complete request and selects only the necessary Research Guard modules.",
        "description_zh": "主 Codex 阅读完整请求，只选择真正需要的 Research Guard 模块。",
    },
    {
        "id": "ideas-novelty",
        "label_en": "Ideas & novelty",
        "label_zh": "Idea 与撞车检索",
        "description_en": "Idea exploration, explicit field choice, literature coverage, and method-change collision gates.",
        "description_zh": "Idea 探索、显式领域选择、文献覆盖和方法修改后的撞车门禁。",
    },
    {
        "id": "literature-citations",
        "label_en": "Literature & citations",
        "label_zh": "文献与引用",
        "description_en": "Linked source discovery, claim-evidence mapping, citation verification, and Related Work.",
        "description_zh": "带链接来源发现、主张—证据映射、引用核验和 Related Work。",
    },
    {
        "id": "study-experiments",
        "label_en": "Study & experiments",
        "label_zh": "研究与实验",
        "description_en": "Study design, preregistration, metrics, protocol legality, code, and reproducibility.",
        "description_zh": "研究设计、预注册、指标、协议合法性、代码和可复现性。",
    },
    {
        "id": "writing-review",
        "label_en": "Writing & review",
        "label_zh": "写作与审稿",
        "description_en": "Venue-grounded writing, language revision, manuscript audit, rebuttal, and reviewer modes.",
        "description_zh": "基于 venue 证据的写作、语言修改、论文审计、rebuttal 和审稿模式。",
    },
    {
        "id": "formulas-numbers",
        "label_en": "Formulas & numbers",
        "label_zh": "公式与数值",
        "description_en": "Lean, Pint, SymPy, Z3, protocol checks, legal intervals, and jointly feasible anchors.",
        "description_zh": "Lean、Pint、SymPy、Z3、协议检查、合法区间和联合可行锚点。",
    },
    {
        "id": "figures-images",
        "label_en": "Figures & images",
        "label_zh": "科研作图与图像",
        "description_en": "Statistical/vector figures, venue style, final-size layout, and scientific-image integrity.",
        "description_zh": "统计图/向量图、刊物风格、最终尺寸布局和科研图像完整性。",
    },
    {
        "id": "resources-directions",
        "label_en": "Resources & directions",
        "label_zh": "资源与方向探索",
        "description_en": "Resource-aware task DAGs and explicitly authorized five-direction exploration.",
        "description_zh": "资源感知任务 DAG 和经显式授权的五方向探索。",
    },
    {
        "id": "domain-initialization",
        "label_en": "Field initialization",
        "label_zh": "领域初始化",
        "description_en": "Main-agent field selection and evidence-backed initialization for an unregistered discipline.",
        "description_zh": "主智能体选择领域，并为未登记学科进行证据化初始化。",
    },
)
FOCUS_IDS = {item["id"] for item in FOCUS_OPTIONS}
THREAD_ID = re.compile(r"^[0-9a-fA-F-]{36}$")


class ContractError(ValueError):
    def __init__(self, code: str, message: str, *, http_status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True, slots=True)
class ChatRequest:
    message: str
    workspace: Path
    sandbox: str
    focus: tuple[str, ...]
    locale: str
    thread_id: str | None


def public_focus_options() -> list[dict[str, str]]:
    return [dict(item) for item in FOCUS_OPTIONS]


def _normalize_thread_id(value: Any) -> str | None:
    if value in (None, ""):
        return None
    candidate = str(value).strip()
    if not THREAD_ID.fullmatch(candidate):
        raise ContractError("THREAD_ID_INVALID", "A resumed Codex thread must use the UUID returned by Codex.")
    try:
        return str(uuid.UUID(candidate))
    except ValueError as exc:
        raise ContractError("THREAD_ID_INVALID", "The Codex thread UUID is invalid.") from exc


def normalize_chat_request(value: Any, default_workspace: Path) -> ChatRequest:
    if not isinstance(value, dict):
        raise ContractError("REQUEST_INVALID", "The chat request must be a JSON object.")
    allowed = {"message", "workspace", "sandbox", "focus", "locale", "thread_id"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ContractError("REQUEST_FIELDS_UNKNOWN", f"Unknown request fields: {', '.join(unknown)}")

    message = str(value.get("message") or "").strip()
    if not message:
        raise ContractError("MESSAGE_REQUIRED", "Enter a research request before starting Codex.")
    if len(message) > MAX_MESSAGE_CHARACTERS:
        raise ContractError(
            "MESSAGE_TOO_LARGE",
            f"The message exceeds the {MAX_MESSAGE_CHARACTERS:,}-character UI limit; reference a workspace file instead.",
        )

    workspace_value = str(value.get("workspace") or "").strip()
    workspace = Path(workspace_value).expanduser() if workspace_value else default_workspace
    try:
        workspace = workspace.resolve(strict=True)
    except OSError as exc:
        raise ContractError("WORKSPACE_MISSING", "The selected workspace does not exist or cannot be resolved.") from exc
    if not workspace.is_dir():
        raise ContractError("WORKSPACE_NOT_DIRECTORY", "The selected workspace must be a directory.")

    sandbox = str(value.get("sandbox") or "workspace-write").strip()
    if sandbox not in SANDBOXES:
        raise ContractError("SANDBOX_INVALID", "Choose read-only or workspace-write; unsafe bypass is not exposed by the UI.")

    raw_focus = value.get("focus", ["auto"])
    if not isinstance(raw_focus, list) or not raw_focus:
        raise ContractError("FOCUS_REQUIRED", "Select automatic main-agent judgment or one to three explicit focus areas.")
    focus = tuple(str(item).strip() for item in raw_focus)
    if len(focus) != len(set(focus)) or any(item not in FOCUS_IDS for item in focus):
        raise ContractError("FOCUS_INVALID", "The Research Guard focus selection is invalid or duplicated.")
    if "auto" in focus and len(focus) != 1:
        raise ContractError("FOCUS_AUTO_EXCLUSIVE", "Automatic main-agent judgment cannot be mixed with explicit focus areas.")
    if len(focus) > MAX_SELECTED_FOCUS:
        raise ContractError("FOCUS_LIMIT", f"Select at most {MAX_SELECTED_FOCUS} focus areas to avoid trigger overload.")

    locale = str(value.get("locale") or "zh-CN").strip()
    if locale not in LOCALES:
        raise ContractError("LOCALE_INVALID", "The UI locale must be en or zh-CN.")

    return ChatRequest(
        message=message,
        workspace=workspace,
        sandbox=sandbox,
        focus=focus,
        locale=locale,
        thread_id=_normalize_thread_id(value.get("thread_id")),
    )


def compose_codex_prompt(request: ChatRequest, plugin_skill: Path) -> str:
    focus = "main-agent semantic selection" if request.focus == ("auto",) else ", ".join(request.focus)
    context = (
        "Research Guard UI context (visible, not a hidden instruction):\n"
        f"- Read the installed Research Guard instructions at {plugin_skill} before acting.\n"
        f"- User-selected focus: {focus}. Treat this as an explicit preference, not keyword classification.\n"
        "- Select only the necessary Research Guard modules and at most 2-3 audit roles; do not activate every module.\n"
        "- Keep linked evidence, gate states, and factual progress visible. Do not use an external LLM API automatically.\n"
        "\nUser request:\n"
    )
    return context + request.message
