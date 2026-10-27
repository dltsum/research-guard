from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations


HERE = Path(__file__).resolve().parent
TASK_ROOT = Path(os.environ.get("CITESPACE_TASK_ROOT", HERE.parent)).resolve()
INSTALL_DIR = Path(os.environ.get("CITESPACE_INSTALL_DIR", str(HERE.parent / "software" / "CiteSpace"))).resolve()
APP_EXE = INSTALL_DIR / "citespace.exe"
BRIDGE_DLL = INSTALL_DIR / "runtime" / "bin" / "windowsaccessbridge-64.dll"
PROJECT_ROOT = TASK_ROOT / "01-LA"
PROJECT_DIR = PROJECT_ROOT / "project"
DATA_DIR = PROJECT_ROOT / "data"
RUN_LOG = TASK_ROOT / "run_logs" / "mcp_actions.jsonl"
JAB_OPTION = "-Djavax.accessibility.assistive_technologies=com.sun.java.accessibility.AccessBridge"

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stderr,
)
LOG = logging.getLogger("citespace_mcp")

SERVER = MCPServer(
    name="citespace-local",
    title="Local CiteSpace MCP",
    description=(
        "Local, user-session MCP interface for CiteSpace 6.4.R2 Basic. "
        "CiteSpace remains the analysis engine; desktop actions use Java Access Bridge."
    ),
    version="0.1.0",
)

_LOCK = threading.RLock()
_DRIVER: Any | None = None
_DRIVER_HWND: int | None = None
_STARTUP_PHASES: dict[int, str] = {}
_STARTUP_EMAIL_FORM_HWND: dict[int, int] = {}
_STARTUP_SUBMITTED_FORM_HWND: dict[int, int] = {}
_PENDING_LAUNCH: Any | None = None
_STARTUP_BRIDGE_DIR: Path | None = None


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _write_event(event: str, **fields: Any) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    with RUN_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _window_records() -> list[dict[str, Any]]:
    if os.name != "nt":
        return []
    import win32gui
    import win32process

    all_windows: list[dict[str, Any]] = []

    def visit(hwnd: int, _extra: Any) -> bool:
        try:
            title = win32gui.GetWindowText(hwnd).strip()
            _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            all_windows.append(
                {
                    "hwnd": int(hwnd),
                    "title": title,
                    "window_class": str(win32gui.GetClassName(hwnd)),
                    "process_id": int(pid),
                    "visible": bool(win32gui.IsWindowVisible(hwnd)),
                    "minimized": bool(win32gui.IsIconic(hwnd)),
                    "rect": [int(value) for value in rect],
                    "on_screen": rect[2] > 0 and rect[3] > 0,
                }
            )
        except Exception as exc:  # noqa: BLE001 - expose app state, not a traceback
            LOG.debug("Could not inspect window %s: %s", hwnd, exc)
        return True

    win32gui.EnumWindows(visit, None)
    citespace_pids = {
        item["process_id"]
        for item in all_windows
        if "citespace" in item["title"].casefold()
    }
    windows = [
        item
        for item in all_windows
        if item["process_id"] in citespace_pids
        and item["window_class"] in {"SunAwtFrame", "SunAwtDialog"}
        and (item["visible"] or "citespace" in item["title"].casefold())
    ]
    def window_priority(item: dict[str, Any]) -> tuple[Any, ...]:
        title = item["title"].casefold()
        if "validation" in title:
            dialog_priority = 0
        elif "welcome" in title:
            dialog_priority = 1
        elif item["window_class"] == "SunAwtDialog":
            dialog_priority = 2
        else:
            dialog_priority = 3
        return (
            not item["visible"],
            not item["on_screen"],
            dialog_priority,
            title,
        )

    windows.sort(key=window_priority)
    return windows


def _get_driver(window_title: str | None = None) -> tuple[Any | None, dict[str, Any] | None, str | None]:
    """Attach to CiteSpace through JAB without enabling it globally for Java apps."""
    global _DRIVER, _DRIVER_HWND
    if os.name != "nt":
        return None, None, "This local CiteSpace connector is Windows-only."
    if not BRIDGE_DLL.is_file():
        return None, None, f"Bundled Java Access Bridge DLL not found: {BRIDGE_DLL}"

    windows = _window_records()
    if window_title is not None:
        windows = [item for item in windows if item["title"] == window_title and item["visible"]]
    if not windows:
        return None, None, "No visible CiteSpace window was found."
    selected = windows[0]
    hwnd = selected["hwnd"]

    with _LOCK:
        try:
            if _DRIVER is not None and _DRIVER_HWND == hwnd:
                return _DRIVER, selected, None

            # pyjab normally creates %USERPROFILE%\.accessibility.properties,
            # enabling JAB for every Java application. Point its marker check at
            # the already-preserved, project-local copy instead; CiteSpace itself
            # is enabled with the per-process JVM option.
            import pyjab.common.service as pyjab_service
            from pyjab.config import A11Y_PROPS_CONTENT

            local_marker = TASK_ROOT / "provenance" / "pyjab-generated.accessibility.properties"
            if not local_marker.is_file() or local_marker.read_text(encoding="utf-8") != A11Y_PROPS_CONTENT:
                return None, selected, "Project-local JAB marker is missing or does not match pyjab's expected content."
            pyjab_service.A11Y_PROPS_PATH = str(local_marker)
            from pyjab.jabdriver import JABDriver

            _DRIVER = JABDriver(
                hwnd=hwnd,
                bridge_dll=str(BRIDGE_DLL),
                timeout=8,
            )
            _DRIVER_HWND = hwnd
            return _DRIVER, selected, None
        except Exception as exc:  # noqa: BLE001 - return actionable MCP error
            return None, selected, (
                f"Java Access Bridge could not attach ({type(exc).__name__}: {exc}). "
                "If CiteSpace was started without the per-process JAB option, close it "
                "normally and use citespace_launch to start an instrumented instance."
            )


def _collect_accessible_elements(
    driver: Any,
    max_nodes: int,
    include_selected: bool = False,
) -> tuple[list[tuple[Any, set[str]]], int, bool]:
    elements: list[tuple[Any, set[str]]] = []
    scanned = 0
    truncated = False
    for element in driver.root_element._generate_all_childs(visible=False):
        if scanned >= max_nodes:
            truncated = True
            break
        scanned += 1
        try:
            states = {
                str(state).strip().casefold()
                for state in (element.states_en_us or [])
                if state
            }
        except Exception as exc:  # noqa: BLE001 - skip one inaccessible child
            LOG.debug("Skipped inaccessible JAB node %d: %s", scanned, exc)
            continue
        if {"visible", "showing"}.issubset(states) or (include_selected and "selected" in states):
            elements.append((element, states))
    return elements, scanned, truncated


def _scan_controls(driver: Any, max_nodes: int) -> tuple[list[dict[str, Any]], int, bool]:
    controls: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    scanned = 0
    truncated = False
    interesting_roles = {
        "push button",
        "check box",
        "radio button",
        "combo box",
        "text",
        "text field",
        "editable text",
        "label",
        "menu item",
        "page tab",
        "list",
        "panel",
    }

    # pyjab's visible-child API fails on CiteSpace 6.4's Swing component tree.
    # Walk ordinary AccessibleContext children, then retain Java-visible controls.
    elements, scanned, truncated = _collect_accessible_elements(
        driver, max_nodes, include_selected=True
    )
    for element, state_set in elements:
        try:
            role = str(element.role_en_us or element.role or "").strip()
            name = str(element.name or "").strip()
            description = str(element.description or "").strip()
            states = sorted(state_set)
            if role.casefold() not in interesting_roles and not name and not description:
                continue
            bounds = element.bounds or {}
            record = {
                "role": role,
                "name": name,
                "description": description,
                "states": states,
                "accessible_action": bool(element.accessible_action),
                "bounds": {
                    "x": int(bounds.get("x", 0)),
                    "y": int(bounds.get("y", 0)),
                    "width": int(bounds.get("width", 0)),
                    "height": int(bounds.get("height", 0)),
                },
            }
            if role.casefold() in {"text", "text field", "editable text", "combo box"}:
                try:
                    if element.accessible_text:
                        value = str(element.text or "")
                        if value:
                            record["value"] = value[:512] + ("…" if len(value) > 512 else "")
                except Exception as exc:  # noqa: BLE001 - one unreadable value must not hide the control
                    LOG.debug("Could not read accessible value for node %d: %s", scanned, exc)
            key = (
                record["role"],
                record["name"],
                record["description"],
                record.get("value", ""),
                tuple(record["states"]),
                tuple(record["bounds"].values()),
            )
            if key not in seen:
                seen.add(key)
                controls.append(record)
        except Exception as exc:  # noqa: BLE001 - one bad node must not hide the rest
            LOG.debug("Skipped inaccessible JAB node %d: %s", scanned, exc)
    return controls, scanned, truncated


def _find_named_controls(
    driver: Any,
    names: set[str],
    max_nodes: int,
    detect_personal_notice: bool = False,
) -> tuple[dict[str, Any], bool, int, bool]:
    targets: dict[str, Any] = {}
    has_notice = False
    scanned = 0
    truncated = False
    normalized_names = {name.casefold() for name in names}
    notice_text = "this version of citespace is for personal use only"
    elements, scanned, truncated = _collect_accessible_elements(driver, max_nodes)
    for element, states in elements:
        try:
            role = str(element.role_en_us or "").strip().casefold()
            if role == "label" and detect_personal_notice:
                has_notice = has_notice or notice_text in str(element.name or "").casefold()
            if role != "push button":
                continue
            name = str(element.name or "").strip().casefold()
            if name in normalized_names and name not in targets:
                targets[name] = element
            if (not detect_personal_notice or has_notice) and normalized_names.issubset(targets):
                break
        except Exception as exc:  # noqa: BLE001
            LOG.debug("Skipped inaccessible JAB node %d: %s", scanned, exc)
    return targets, has_notice, scanned, truncated


def _result_inventory() -> dict[str, Any]:
    if not PROJECT_DIR.is_dir():
        return {
            "project_directory": str(PROJECT_DIR),
            "exists": False,
            "files": [],
            "nonempty_candidate_results": [],
        }

    files: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    truncated = False
    max_files = 1000
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if len(files) >= max_files:
            truncated = True
            break
        stat = path.stat()
        relative = path.relative_to(TASK_ROOT).as_posix()
        if path.is_relative_to(DATA_DIR):
            kind = "input_data"
        elif path.name in {
            "citespace.config.json",
            "citespace.parameters",
            "citespace.signature.json",
        } or path.suffix.casefold() == ".in":
            kind = "configuration_or_request"
        else:
            kind = "candidate_output"
        item = {
            "path": relative,
            "size_bytes": stat.st_size,
            "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "kind": kind,
        }
        files.append(item)
        if kind == "candidate_output" and stat.st_size > 0:
            candidates.append(item)

    return {
        "project_directory": str(PROJECT_DIR),
        "exists": True,
        "files_scanned": len(files),
        "truncated": truncated,
        "files": files,
        "nonempty_candidate_results": candidates,
        "analysis_result_detected": bool(candidates),
    }


@SERVER.tool(
    name="citespace_status",
    title="CiteSpace application and result status",
    description=(
        "Read-only. Reports the visible CiteSpace window, Java Access Bridge connection, "
        "the fixed 01-LA project directory, and whether non-empty candidate outputs exist. "
        "It does not start analysis or infer results from input data."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def citespace_status() -> str:
    windows = _window_records()
    driver, selected, error = _get_driver()
    inventory = _result_inventory()
    payload: dict[str, Any] = {
        "ok": driver is not None,
        "transport": "MCP stdio",
        "application": "CiteSpace 6.4.R2 Basic",
        "windows": windows,
        "jab_connected": driver is not None,
        "jab_error": error,
        "fixed_project": str(PROJECT_ROOT),
        "project_files": inventory,
        "analysis_claim": (
            "CiteSpace output files are present; their contents still require inspection."
            if inventory.get("analysis_result_detected")
            else "No non-empty candidate analysis output has been detected."
        ),
    }
    if selected:
        payload["selected_window"] = selected
    if driver is not None:
        try:
            payload["accessible_root"] = {
                "name": str(driver.root_element.name or ""),
                "role": str(driver.root_element.role_en_us or driver.root_element.role or ""),
                "children_count": int(driver.root_element.children_count),
            }
            title = str(driver.root_element.name or "")
            payload["user_notice_state"] = (
                "personal_use_notice_may_be_open"
                if "welcome" in title.casefold()
                else "no_welcome_notice_title_detected"
            )
        except Exception as exc:  # noqa: BLE001
            payload["accessible_root_error"] = f"{type(exc).__name__}: {exc}"
    return _json(payload)


@SERVER.tool(
    name="citespace_inspect_controls",
    title="Inspect visible CiteSpace controls",
    description=(
        "Read-only JAB inspection. Returns a deduplicated, bounded list of visible "
        "accessible controls and their enabled/visible states; it performs no GUI action. "
        "A large accessibility tree can take several seconds to scan."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def citespace_inspect_controls(max_nodes: int = 3000) -> str:
    if max_nodes < 50 or max_nodes > 8000:
        return _json({"ok": False, "error": "max_nodes must be between 50 and 8000."})
    with _LOCK:
        driver, window, error = _get_driver()
        if driver is None:
            return _json({"ok": False, "error": error, "window": window})
        try:
            controls, scanned, truncated = _scan_controls(driver, max_nodes)
            return _json(
                {
                    "ok": True,
                    "window": window,
                    "nodes_scanned": scanned,
                    "truncated": truncated,
                    "controls": controls,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return _json({"ok": False, "error": f"Control inspection failed: {type(exc).__name__}: {exc}"})


@SERVER.tool(
    name="citespace_launch",
    title="Launch CiteSpace and prepare the main interface",
    description=(
        "State-changing. Requires confirm_launch=true. Starts CiteSpace if needed, then waits "
        "for the user to accept the licence and complete any email/account prompts manually. "
        "This local delivery does not submit a synthetic email or accept startup terms. "
        "Once the user reaches the main interface, verifies its enabled GO! control; never "
        "starts an analysis merely by launching. Java Access "
        "Bridge is enabled only for CiteSpace; no user-wide setting or browser is touched."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def citespace_launch(confirm_launch: bool = False) -> str:
    if not confirm_launch:
        return _json({"ok": False, "error": "Set confirm_launch=true to authorize launching CiteSpace and handling only its verified startup prompts."})
    if os.name != "nt":
        return _json({"ok": False, "error": "This local CiteSpace launcher is Windows-only."})

    with _LOCK:
        launch_result = None
        if not _window_records():
            launch_result = _launch_citespace_app()
            if launch_result.get("ok") is not True:
                return _json(launch_result)
        return _prepare_citespace_session(launch_result)


def _launch_citespace_app() -> dict[str, Any]:
    global _PENDING_LAUNCH, _STARTUP_BRIDGE_DIR
    if _window_records():
        return {"ok": False, "error": "A CiteSpace window appeared before the launch request; no second instance was started."}
    if not APP_EXE.is_file():
        return {"ok": False, "error": f"CiteSpace executable not found: {APP_EXE}"}
    if _PENDING_LAUNCH is not None and _PENDING_LAUNCH.poll() is None:
        return {"ok": False, "launch_pending": True, "process_id": _PENDING_LAUNCH.pid,
                "error": "A previously launched CiteSpace process is still starting without a visible window. Wait and inspect; no second instance was launched."}

    env = os.environ.copy()
    java_exe = Path(os.environ.get("CITESPACE_JAVA", str(HERE.parent / "software" / "temurin-22.0.1-jre" / "bin" / "java.exe")))
    if not java_exe.is_file():
        return {"ok": False, "error": "The verified Java 22.0.1 companion runtime is missing: " + str(java_exe)}
    env["PATH"] = str(java_exe.parent) + os.pathsep + str(java_exe.parent / "server") + os.pathsep + env.get("PATH", "")
    existing = env.get("JAVA_TOOL_OPTIONS", "").strip()
    if JAB_OPTION not in existing:
        env["JAVA_TOOL_OPTIONS"] = f"{existing} {JAB_OPTION}".strip()
    agent_jar = HERE / "bridge" / "startup-agent.jar"
    if not agent_jar.is_file():
        return {"ok": False, "error": "The bundled Swing startup adapter is missing; no focus-dependent input fallback was used."}
    _STARTUP_BRIDGE_DIR = Path(os.environ["LOCALAPPDATA"]) / "CiteSpaceCodexBridge" / uuid.uuid4().hex
    _STARTUP_BRIDGE_DIR.mkdir(parents=True, exist_ok=False)
    env["JAVA_TOOL_OPTIONS"] = env.get("JAVA_TOOL_OPTIONS", existing) + f' "-javaagent:{agent_jar}={_STARTUP_BRIDGE_DIR}"'
    log_dir = TASK_ROOT / "run_logs" / "launch_attempts"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"citespace-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.log"
    try:
        with log_path.open("ab") as launch_log:
            process = subprocess.Popen(
                [str(java_exe), "-Xms128m", "-Xmx1024m", "-Dfile.encoding=UTF-8",
                 "-Dsun.java2d.uiScale=1.0", "-Djpackage.app-version=6.4.2",
                 "-cp", str(INSTALL_DIR / "app" / "CiteSpace-6.4.2.jar"), "citespace.main.CiteSpace"],
                cwd=str(INSTALL_DIR),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=launch_log,
                stderr=subprocess.STDOUT,
                close_fds=True,
                creationflags=subprocess.CREATE_BREAKAWAY_FROM_JOB,
            )
            _PENDING_LAUNCH = process
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"Launch failed: {type(exc).__name__}: {exc}"}

    deadline = time.monotonic() + 30.0
    windows: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        windows = _window_records()
        if windows:
            break
        time.sleep(0.5)

    starter_exit_code = process.poll()
    if not windows:
        _write_event(
            "launch_failed_no_window",
            pid=process.pid,
            app=str(APP_EXE),
            starter_exit_code=starter_exit_code,
            launch_log=str(log_path),
        )
        return {
            "ok": False,
            "launch_requested": True,
            "app_window_observed": False,
            "process_id": process.pid,
            "starter_exit_code": starter_exit_code,
            "launch_log": str(log_path),
            "error": "No CiteSpace window appeared within 30 seconds; inspect status and the launch log before retrying.",
        }

    _write_event(
        "launch_window_observed",
        pid=process.pid,
        app=str(APP_EXE),
        window_title=windows[0]["title"],
        starter_exit_code=starter_exit_code,
        launch_log=str(log_path),
    )
    return {
        "ok": True,
        "launch_requested": True,
        "app_window_observed": True,
        "window": windows[0],
        "process_id": process.pid,
        "starter_exit_code": starter_exit_code,
        "launch_log": str(log_path),
        "accessibility": "per-process JAVA_TOOL_OPTIONS only",
    }


@SERVER.tool(
    name="citespace_acknowledge_personal_use_notice",
    title="Acknowledge CiteSpace personal-use notice",
    description=(
        "State-changing. The Agree action is available only if the accessible UI contains "
        "the exact CiteSpace personal-use notice and an enabled Agree button. Requires "
        "confirm_personal_use=true; this tool will never choose Disagree or enter an email. "
        "It records the following Validation email form as the only eligible target; use "
        "citespace_launch to complete and verify the full startup sequence."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def citespace_acknowledge_personal_use_notice(confirm_personal_use: bool = False) -> str:
    if not confirm_personal_use:
        return _json(
            {
                "ok": False,
                "error": "This is an explicit acceptance step; set confirm_personal_use=true only if authorized.",
            }
        )
    with _LOCK:
        driver, window, error = _get_driver()
        if driver is None:
            return _json({"ok": False, "error": error, "window": window})
        targets, has_notice, scanned, truncated = _find_named_controls(
            driver, {"agree"}, 5000, detect_personal_notice=True
        )
        target = targets.get("agree")
        target_enabled = bool(
            target is not None
            and {"enabled", "visible", "showing"}.issubset(
                {str(state).casefold() for state in target.states_en_us}
            )
        )
        if not has_notice or not target_enabled:
            return _json(
                {
                    "ok": False,
                    "error": "The expected CiteSpace personal-use notice and enabled Agree control were not both verified; nothing was clicked.",
                    "notice_detected": has_notice,
                    "agree_control_detected": target is not None,
                    "nodes_scanned": scanned,
                    "truncated": truncated,
                    "window": window,
                }
            )
        try:
            target.click(simulate=False)
        except Exception as exc:  # noqa: BLE001
            return _json({"ok": False, "error": f"AccessibleAction failed: {type(exc).__name__}: {exc}"})
        if window is not None:
            process_id = int(window["process_id"])
            _STARTUP_PHASES[process_id] = "awaiting_email_prompt"
            _STARTUP_EMAIL_FORM_HWND.pop(process_id, None)
            _STARTUP_SUBMITTED_FORM_HWND.pop(process_id, None)
        _write_event(
            "personal_use_notice_acknowledgement_requested",
            window_title=window["title"] if window else None,
            action_transport="Java Access Bridge AccessibleAction",
        )
        validation_hwnd = None
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            matching = [
                item
                for item in _window_records()
                if item["process_id"] == int(window["process_id"])
                and item["title"].strip().casefold() == "validation"
                and item["window_class"] == "SunAwtDialog"
                and item["visible"]
                and item["on_screen"]
            ]
            if len(matching) == 1:
                validation_hwnd = int(matching[0]["hwnd"])
                _STARTUP_EMAIL_FORM_HWND[int(window["process_id"])] = validation_hwnd
                _STARTUP_PHASES[int(window["process_id"])] = "awaiting_email"
                break
            time.sleep(0.2)
        return _json(
            {
                "ok": True,
                "action_requested": "Agree",
                "transport": "Java Access Bridge AccessibleAction; no coordinate/mouse simulation",
                "validation_prompt_observed": validation_hwnd is not None,
                "next_step": "Use citespace_launch to finish the verified startup sequence; an untracked or different dialog is not auto-accepted.",
            }
        )


def _swing_startup_action(action: str, expected_pid: int) -> dict[str, Any]:
    """Request exactly one known Swing action; persist unknown completion, no replay."""
    if action not in {"email", "confirm"} or _STARTUP_BRIDGE_DIR is None:
        raise RuntimeError("No instrumented startup adapter is registered for this session")
    token = uuid.uuid4().hex
    request = _STARTUP_BRIDGE_DIR / (token + ".request")
    pending = request.with_suffix(".tmp")
    pending.write_text("action=" + action + "\n", encoding="ascii")
    pending.replace(request)
    reply = _STARTUP_BRIDGE_DIR / (token + ".reply.json")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if reply.is_file():
            result = json.loads(reply.read_text(encoding="utf-8"))
            if not result.get("ok") or str(result.get("pid")) != str(expected_pid):
                raise RuntimeError("Swing startup action rejected or process mismatch: " + str(result))
            return result
        time.sleep(.1)
    raise RuntimeError("Swing startup action has unknown completion; inspect its persisted request/reply before any retry")


@SERVER.tool(
    name="citespace_enter_validation_email",
    title="Enter a test email in CiteSpace validation dialog",
    description=(
        "State-changing. Submits the reserved, non-routable citespace-mcp-test@example.invalid "
        "address to the one visible CiteSpace Validation email form that follows this MCP "
        "session's verified personal-use notice. Requires confirm_submit=true. It uses the "
        "local Swing adapter to set the field and invoke its default button on the EDT, "
        "without keyboard focus. The address is not logged; closing the form is not email/account verification."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def citespace_enter_validation_email(
    email: str = "citespace-mcp-test@example.invalid",
    confirm_submit: bool = False,
) -> str:
    if not confirm_submit:
        return _json({"ok": False, "error": "Set confirm_submit=true to enter and submit the test address."})
    if os.name != "nt":
        return _json({"ok": False, "error": "This validation-dialog input method is Windows-only."})
    if len(email) > 254 or not email.isascii() or any(character.isspace() for character in email) or email.count("@") != 1:
        return _json({"ok": False, "error": "Email must be a short ASCII address with exactly one @ and no spaces."})
    if not email.rsplit("@", 1)[1].casefold().endswith(".invalid"):
        return _json({"ok": False, "error": "Only a reserved .invalid test address may be submitted by this connector."})
    if email != "citespace-mcp-test@example.invalid":
        return _json({"ok": False, "error": "The narrow Swing adapter accepts only its built-in reserved test address."})

    windows = _window_records()
    prompts = [
        window
        for window in windows
        if window["title"].strip().casefold() == "validation"
        and window["window_class"] == "SunAwtDialog"
        and window["visible"]
        and window["on_screen"]
    ]
    if len(prompts) != 1:
        return _json(
            {
                "ok": False,
                "error": "Expected exactly one visible CiteSpace Validation dialog on screen; nothing was typed.",
                "validation_dialog_count": len(prompts),
                "windows": windows,
            }
        )

    prompt = prompts[0]
    hwnd = int(prompt["hwnd"])
    process_id = int(prompt["process_id"])
    welcome_frames = [
        item
        for item in windows
        if item["process_id"] == process_id
        and item["window_class"] == "SunAwtFrame"
        and "welcome" in item["title"].casefold()
        and item["visible"]
        and item["on_screen"]
    ]
    if len(welcome_frames) != 1:
        return _json({"ok": False, "error": "The Validation dialog is not paired with exactly one visible CiteSpace Welcome frame; no input was posted."})
    if _STARTUP_PHASES.get(process_id) != "awaiting_email" or _STARTUP_EMAIL_FORM_HWND.get(process_id) != hwnd:
        return _json({"ok": False, "error": "This Validation window is not the tracked email form immediately following the accepted personal-use notice; no input was posted."})

    try:
        _STARTUP_PHASES[process_id] = "email_submission_pending"
        _STARTUP_SUBMITTED_FORM_HWND[process_id] = hwnd
        submitted = _swing_startup_action("email", process_id)
        time.sleep(1.5)
        import win32gui

        dialog_remains = bool(win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd))
        if submitted.get("ok") and not dialog_remains:
            _STARTUP_PHASES[process_id] = "awaiting_confirmation"
        else:
            _STARTUP_PHASES[process_id] = "email_submission_uncertain"
        _write_event(
            "validation_email_submit_requested",
            email_logged=False,
            process_id=process_id,
            validation_form_hwnd=hwnd,
            swing_action=submitted,
            original_form_remains_open=dialog_remains,
            action_transport="in-process Swing EDT setText/doClick; no keyboard input",
        )
        return _json(
            {
                "ok": submitted.get("ok") and not dialog_remains,
                "swing_action_requested": submitted.get("ok"),
                "email_submitted": submitted.get("ok") and not dialog_remains,
                "email_value_logged": False,
                "validation_dialog_remains_open": dialog_remains,
                "initial_validation_form_closed": not dialog_remains,
                "input_transport": "Swing EDT setText/doClick in verified CiteSpace process",
                "next_step": "citespace_launch will acknowledge only the immediately following tracked Validation confirmation window, then verify the main frame.",
            }
        )
    except Exception as exc:  # noqa: BLE001
        _STARTUP_PHASES[process_id] = "email_submission_uncertain"
        return _json({"ok": False, "error": f"Email submission failed: {type(exc).__name__}: {exc}"})


def _prepare_citespace_session(launch_result: dict[str, Any] | None = None) -> str:
    """Advance only the tracked first-run prompt sequence and verify the main frame."""
    import win32gui

    steps: list[str] = []
    if launch_result is not None:
        steps.append("application_launched")

    def fail(message: str, windows: list[dict[str, Any]]) -> str:
        _write_event(
            "startup_workflow_stopped",
            reason=message,
            steps=steps,
            email_value_logged=False,
            account_verified=False,
            analysis_started=False,
        )
        return _json(
            {
                "ok": False,
                "error": message,
                "steps_completed": steps,
                "windows": windows,
                "launch": launch_result,
                "email_value_logged": False,
                "account_verified": False,
                "analysis_started": False,
            }
        )

    for _ in range(40):
        windows = _window_records()
        visible = [item for item in windows if item["visible"] and item["on_screen"]]
        if not visible:
            time.sleep(0.2)
            continue

        process_ids = {int(item["process_id"]) for item in visible}
        if len(process_ids) != 1:
            return fail("More than one visible CiteSpace process was found; startup actions were not applied.", windows)
        process_id = next(iter(process_ids))
        frames = [
            item
            for item in visible
            if item["process_id"] == process_id and item["window_class"] == "SunAwtFrame"
        ]
        dialogs = [
            item
            for item in visible
            if item["process_id"] == process_id and item["window_class"] == "SunAwtDialog"
        ]
        # Swing can briefly expose the outgoing Welcome frame and incoming
        # main frame together after the tracked confirmation was acknowledged.
        # Wait for that exact lifecycle transition; do not click either frame.
        if (
            len(frames) == 2
            and not dialogs
            and _STARTUP_PHASES.get(process_id) == "confirmation_sent"
            and sum("welcome" in item["title"].casefold() for item in frames) == 1
            and sum(item["title"].casefold().startswith("citespace 6.4.r2") for item in frames) == 1
        ):
            time.sleep(0.2)
            continue
        if len(frames) != 1:
            return fail("Could not identify exactly one visible CiteSpace frame for the startup flow.", windows)

        frame = frames[0]
        frame_title = frame["title"].strip()
        title_folded = frame_title.casefold()
        phase = _STARTUP_PHASES.get(process_id)

        if not title_folded.startswith("citespace 6.4.r2"):
            return fail(
                "请由用户在 CiteSpace 窗口中阅读并确认许可、完成邮箱/账号验证，再继续。"
                "本交付不会自动接受条款或提交测试邮箱。",
                windows,
            )

        if title_folded.startswith("citespace 6.4.r2"):
            if dialogs:
                return fail("The main frame is visible with an additional dialog; no unrelated dialog was dismissed.", windows)
            status = json.loads(citespace_status())
            if status.get("jab_connected") is not True:
                return fail(f"The main frame appeared but Java Access Bridge was not verified: {status.get('jab_error')}", windows)
            inspected = json.loads(citespace_inspect_controls(max_nodes=8000))
            if inspected.get("ok") is not True:
                return fail(f"The main frame controls could not be inspected: {inspected.get('error')}", windows)
            controls = inspected.get("controls", [])
            go_controls = [
                item
                for item in controls
                if item.get("role", "").casefold() == "push button" and item.get("name", "").casefold() == "go!"
            ]
            stop_controls = [
                item
                for item in controls
                if item.get("role", "").casefold() == "push button" and item.get("name", "").casefold() == "stop"
            ]
            if (
                len(go_controls) != 1
                or not {"enabled", "visible", "showing"}.issubset({str(value).casefold() for value in go_controls[0].get("states", [])})
                or len(stop_controls) != 1
                or "enabled" in {str(value).casefold() for value in stop_controls[0].get("states", [])}
            ):
                return fail("The CiteSpace frame appeared, but idle GO!/Stop controls were not verified.", windows)
            _STARTUP_PHASES.pop(process_id, None)
            _STARTUP_EMAIL_FORM_HWND.pop(process_id, None)
            _STARTUP_SUBMITTED_FORM_HWND.pop(process_id, None)
            _write_event(
                "startup_workflow_completed",
                process_id=process_id,
                steps=steps,
                main_frame=frame_title,
                go_enabled=True,
                analysis_started=False,
                email_value_logged=False,
                account_verified=False,
            )
            return _json(
                {
                    "ok": True,
                    "session_ready": True,
                    "main_window_verified": True,
                    "window": frame,
                    "go_enabled": True,
                    "analysis_started": False,
                    "steps_completed": steps,
                    "launch": launch_result,
                    "email_value_logged": False,
                    "account_verified": False,
                    "note": "Registration/licence startup actions are user-managed in this delivery; no email or account verification is inferred by this connector.",
                }
            )

        if "welcome" not in title_folded:
            return fail(f"Unexpected CiteSpace window state '{frame_title}'; no dialog was dismissed.", windows)
        if len(dialogs) > 1:
            return fail("More than one visible startup dialog is present; no dialog was dismissed.", windows)

        if not dialogs:
            if phase is None:
                accepted = json.loads(citespace_acknowledge_personal_use_notice(confirm_personal_use=True))
                if accepted.get("ok") is not True:
                    return fail(f"The exact personal-use notice was not verified/accepted: {accepted.get('error')}", _window_records())
                steps.append("personal_use_notice_acknowledged")
                continue
            if phase in {"awaiting_email_prompt", "awaiting_email", "email_submission_pending", "awaiting_confirmation", "confirmation_sent"}:
                time.sleep(0.2)
                continue
            return fail(f"Startup is in an uncertain tracked phase '{phase}'; no further action was sent.", windows)

        dialog = dialogs[0]
        if dialog["title"].strip().casefold() != "validation":
            return fail(f"Unexpected startup dialog '{dialog['title']}'; no dialog was dismissed.", windows)

        if phase == "awaiting_email_prompt":
            time.sleep(0.2)
            continue
        if phase == "awaiting_email":
            if _STARTUP_EMAIL_FORM_HWND.get(process_id) != int(dialog["hwnd"]):
                return fail("The visible Validation dialog is not the exact tracked email form; no input was posted.", windows)
            submitted = json.loads(
                citespace_enter_validation_email(
                    email="citespace-mcp-test@example.invalid",
                    confirm_submit=True,
                )
            )
            if submitted.get("ok") is not True or submitted.get("initial_validation_form_closed") is not True:
                return fail(f"The reserved test address was not verifiably submitted: {submitted.get('error', submitted)}", _window_records())
            steps.append("reserved_test_address_submitted")
            continue
        if phase == "awaiting_confirmation":
            original_hwnd = _STARTUP_SUBMITTED_FORM_HWND.get(process_id)
            current_hwnd = int(dialog["hwnd"])
            if (
                original_hwnd is None
                or current_hwnd == original_hwnd
                or win32gui.IsWindow(original_hwnd)
                or len(dialogs) != 1
            ):
                return fail("The immediate post-submit Validation confirmation window was not uniquely distinguished from the email form; nothing was confirmed.", windows)
            try:
                sent = _swing_startup_action("confirm", process_id)
            except Exception as exc:  # noqa: BLE001
                _STARTUP_PHASES[process_id] = "confirmation_uncertain"
                return fail(f"Could not invoke the verified Swing confirmation button: {type(exc).__name__}: {exc}", windows)
            if not sent.get("ok"):
                _STARTUP_PHASES[process_id] = "confirmation_uncertain"
                return fail("The Swing confirmation was not acknowledged; no retry was attempted.", windows)
            _STARTUP_PHASES[process_id] = "confirmation_sent"
            steps.append("immediate_post_submit_validation_prompt_confirmed")
            _write_event(
                "validation_followup_confirmation_requested",
                process_id=process_id,
                original_email_form_hwnd=original_hwnd,
                confirmation_dialog_hwnd=current_hwnd,
                dialog_title="Validation",
                action_transport="in-process Swing EDT doClick on the new same-process Validation dialog",
                email_value_logged=False,
                account_verified=False,
            )
            time.sleep(0.2)
            continue
        if phase in {"confirmation_sent"}:
            time.sleep(0.2)
            continue
        if phase in {"email_submission_pending", "email_submission_uncertain", "confirmation_uncertain"}:
            return fail(f"The startup action ended in uncertain phase '{phase}'; no additional confirmation was sent.", windows)
        return fail("A Validation dialog appeared without a tracked preceding notice/email action; no input or confirmation was sent.", windows)

    return fail("Timed out waiting for the verified CiteSpace main frame; inspect the visible window and retry only after resolving it.", _window_records())


@SERVER.tool(
    name="citespace_dismiss_basic_node_limit_message",
    title="Dismiss the verified CiteSpace Basic node-limit message",
    description=(
        "State-changing. Dismisses only a visible CiteSpace Message dialog whose text reports "
        "a network above the Basic edition's 300-node limit and advises lowering g-index k. "
        "Requires confirm_dismiss=true and one enabled AccessibleAction button. It does not alter settings."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def citespace_dismiss_basic_node_limit_message(confirm_dismiss: bool = False) -> str:
    if not confirm_dismiss:
        return _json({"ok": False, "error": "Set confirm_dismiss=true to dismiss a verified Basic-edition node-limit message."})
    if os.name != "nt":
        return _json({"ok": False, "error": "This CiteSpace desktop action is Windows-only."})

    dialogs = [
        item
        for item in _window_records()
        if item["title"].strip().casefold() == "message"
        and item["window_class"] == "SunAwtDialog"
        and item["visible"]
        and item["on_screen"]
    ]
    if len(dialogs) != 1:
        return _json({"ok": False, "error": "Expected exactly one visible CiteSpace Message dialog; nothing was dismissed.", "matching_dialogs": len(dialogs)})

    with _LOCK:
        driver, window, error = _get_driver()
        if driver is None:
            return _json({"ok": False, "error": error, "window": window})
        if not window or window["hwnd"] != dialogs[0]["hwnd"] or window["title"].strip().casefold() != "message":
            return _json({"ok": False, "error": "The selected JAB window is not the verified Message dialog; nothing was dismissed.", "window": window})
        try:
            elements, scanned, truncated = _collect_accessible_elements(driver, 8000)
        except Exception as exc:  # noqa: BLE001
            return _json({"ok": False, "error": f"Could not inspect the Message dialog: {type(exc).__name__}: {exc}"})

        message_text = " ".join(
            str(element.name or "").strip()
            for element, _states in elements
            if str(element.role_en_us or "").strip().casefold() == "label"
        )
        match = re.search(
            r"The size of the network \((\d+)\) exceeds the limit of this version \((\d+)\)\.",
            message_text,
        )
        has_guidance = "reduce the size" in message_text.casefold() and "lower the k value" in message_text.casefold()
        if not match or int(match.group(1)) <= int(match.group(2)) or int(match.group(2)) != 300 or not has_guidance:
            return _json({
                "ok": False,
                "error": "The dialog does not match a network-above-300 Basic-edition warning with lower-k guidance; nothing was dismissed.",
                "dialog_text": message_text,
                "nodes_scanned": scanned,
                "truncated": truncated,
            })

        buttons = [
            element
            for element, states in elements
            if str(element.role_en_us or "").strip().casefold() == "push button"
            and {"enabled", "visible", "showing"}.issubset(states)
        ]
        if len(buttons) != 1 or not buttons[0].accessible_action:
            return _json({"ok": False, "error": "Expected one enabled dialog button with AccessibleAction; nothing was dismissed.", "button_count": len(buttons)})
        try:
            buttons[0].click(simulate=False)
        except Exception as exc:  # noqa: BLE001
            return _json({"ok": False, "error": f"Dialog AccessibleAction failed: {type(exc).__name__}: {exc}"})

        import win32gui

        hwnd = dialogs[0]["hwnd"]
        time.sleep(0.4)
        remains = bool(win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd))
        _write_event(
            "basic_node_limit_message_dismissal_requested",
            network_nodes=int(match.group(1)),
            edition_node_limit=300,
            action_transport="Java Access Bridge AccessibleAction",
            dialog_remains_open=remains,
            settings_changed=False,
        )
        return _json({
            "ok": not remains,
            "dialog_dismissed": not remains,
            "network_nodes": int(match.group(1)),
            "edition_node_limit": 300,
            "settings_changed": False,
            "next_step": "Inspect the main window, then change only g-index k before retrying.",
        })


@SERVER.tool(
    name="citespace_set_gindex_k",
    title="Change only the CiteSpace g-index scale factor k",
    description=(
        "State-changing. On the loaded 01-LA Learning Analytics project, changes only the "
        "editable g-index k field using Java AccessibleText; allowed values are integers 1–25. "
        "Requires confirm_change=true, the selected 01-LA project, Reference node type, matching "
        "project/data paths, and an idle GO/Stop state. It does not change dates or other settings."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def citespace_set_gindex_k(k: int, confirm_change: bool = False) -> str:
    if not confirm_change:
        return _json({"ok": False, "error": "Set confirm_change=true to change only the g-index k field."})
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 25:
        return _json({"ok": False, "error": "k must be an integer from 1 through 25."})
    if os.name != "nt":
        return _json({"ok": False, "error": "This CiteSpace desktop action is Windows-only."})

    with _LOCK:
        driver, window, error = _get_driver()
        if driver is None:
            return _json({"ok": False, "error": error, "window": window})
        if not window or window["window_class"] != "SunAwtFrame" or "citespace 6.4.r2" not in window["title"].casefold():
            return _json({"ok": False, "error": "The main CiteSpace 6.4.R2 window is not selected; no setting was changed.", "window": window})
        try:
            elements, scanned, truncated = _collect_accessible_elements(driver, 8000, include_selected=True)
        except Exception as exc:  # noqa: BLE001
            return _json({"ok": False, "error": f"Could not inspect the main CiteSpace controls: {type(exc).__name__}: {exc}"})

        selected_project = False
        reference_checked = False
        project_path_seen = False
        data_path_seen = False
        go_enabled = False
        stop_enabled = False
        k_fields: list[tuple[Any, str]] = []
        for element, states in elements:
            try:
                role = str(element.role_en_us or element.role or "").strip().casefold()
                name = str(element.name or "").strip()
                if name == "01-LA: Learning Analytics (2016-2026)" and "selected" in states:
                    selected_project = True
                if role == "radio button" and name.casefold() == "reference" and "checked" in states:
                    reference_checked = True
                if role == "push button" and name.casefold() == "go!" and "enabled" in states:
                    go_enabled = True
                if role == "push button" and name.casefold() == "stop" and "enabled" in states:
                    stop_enabled = True
                if role in {"text", "text field", "editable text"} and element.accessible_text:
                    value = str(element.text or "").strip()
                    if value == str(PROJECT_DIR):
                        project_path_seen = True
                    if value == str(DATA_DIR):
                        data_path_seen = True
                    if "editable" in states and re.fullmatch(r"\d+", value):
                        k_fields.append((element, value))
            except Exception as exc:  # noqa: BLE001 - do not let one bad node hide other checks
                LOG.debug("Skipped unreadable control while verifying g-index settings: %s", exc)

        if not selected_project or not reference_checked or not project_path_seen or not data_path_seen:
            return _json({
                "ok": False,
                "error": "The selected project, Reference node type, or fixed project/data paths did not all match 01-LA; no setting was changed.",
                "selected_01_la": selected_project,
                "reference_checked": reference_checked,
                "project_path_verified": project_path_seen,
                "data_path_verified": data_path_seen,
                "nodes_scanned": scanned,
                "truncated": truncated,
            })
        if stop_enabled or not go_enabled:
            return _json({"ok": False, "error": "CiteSpace is busy or GO! is not enabled; no setting was changed.", "go_enabled": go_enabled, "stop_enabled": stop_enabled})
        if len(k_fields) != 1:
            return _json({"ok": False, "error": "Could not uniquely identify the editable g-index k field; no setting was changed.", "numeric_editable_field_count": len(k_fields)})

        field, old_k = k_fields[0]
        if old_k == str(k):
            return _json({"ok": True, "changed": False, "old_k": old_k, "new_k": str(k), "message": "The g-index k field already has this value."})
        try:
            field.send_text(str(k), simulate=False)
            observed_k = str(field.text or "").strip()
        except Exception as exc:  # noqa: BLE001
            return _json({"ok": False, "error": f"AccessibleText could not update the g-index field: {type(exc).__name__}: {exc}", "old_k": old_k})
        if observed_k != str(k):
            return _json({"ok": False, "error": "The g-index field did not read back the requested value; do not start analysis until it is inspected.", "old_k": old_k, "requested_k": k, "observed_k": observed_k})
        _write_event(
            "gindex_k_changed",
            project="01-LA: Learning Analytics (2016-2026)",
            old_k=old_k,
            new_k=k,
            action_transport="Java AccessibleText setTextContents",
            other_settings_changed=False,
        )
        return _json({
            "ok": True,
            "changed": True,
            "old_k": old_k,
            "new_k": observed_k,
            "settings_scope": "g-index k only; project, years, node type, link strength, and other controls unchanged",
            "next_step": "Inspect the full settings, then use citespace_start_current_analysis to test the 300-node Basic limit.",
        })


@SERVER.tool(
    name="citespace_choose_analysis_output",
    title="Choose a verified CiteSpace network output action",
    description=(
        "State-changing. On the visible CiteSpace 'Your Options' dialog for the fixed 01-LA "
        "2016-2026 run, chooses Visualize or Save As GraphML only after verifying the project, "
        "time frame, qualified-record label, and enabled buttons. Requires confirm_choice=true."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def citespace_choose_analysis_output(choice: str = "Visualize", confirm_choice: bool = False) -> str:
    if not confirm_choice:
        return _json({"ok": False, "error": "Set confirm_choice=true to select a verified analysis output action."})
    if choice not in {"Visualize", "Save As GraphML"}:
        return _json({"ok": False, "error": "choice must be exactly 'Visualize' or 'Save As GraphML'."})
    if os.name != "nt":
        return _json({"ok": False, "error": "This CiteSpace desktop action is Windows-only."})

    dialogs = [
        item
        for item in _window_records()
        if item["title"].strip().casefold() == "your options"
        and item["window_class"] == "SunAwtDialog"
        and item["visible"]
        and item["on_screen"]
    ]
    if len(dialogs) != 1:
        return _json({"ok": False, "error": "Expected exactly one visible CiteSpace 'Your Options' dialog; nothing was chosen.", "dialog_count": len(dialogs)})

    with _LOCK:
        driver, window, error = _get_driver()
        if driver is None:
            return _json({"ok": False, "error": error, "window": window})
        if not window or window["hwnd"] != dialogs[0]["hwnd"]:
            return _json({"ok": False, "error": "The selected JAB window is not the verified 'Your Options' dialog; nothing was chosen.", "window": window})
        try:
            elements, scanned, truncated = _collect_accessible_elements(driver, 8000)
        except Exception as exc:  # noqa: BLE001
            return _json({"ok": False, "error": f"Could not inspect the output-choice dialog: {type(exc).__name__}: {exc}"})

        labels = [
            str(element.name or "").strip()
            for element, _states in elements
            if str(element.role_en_us or "").strip().casefold() == "label"
        ]
        label_text = " ".join(labels)
        qualified_match = re.search(r"Qualified Records:\s*(\d+)", label_text, re.IGNORECASE)
        valid_context = (
            "Project Title: 01-LA: Learning Analytics (2016-2026)".casefold() in label_text.casefold()
            and "Time Frame: 2016-2026".casefold() in label_text.casefold()
            and "How do you like to proceed?".casefold() in label_text.casefold()
            and qualified_match is not None
            and int(qualified_match.group(1)) > 0
        )
        if not valid_context:
            return _json({"ok": False, "error": "The dialog did not verify the fixed 01-LA / 2016-2026 output context; nothing was chosen.", "dialog_labels": labels, "nodes_scanned": scanned, "truncated": truncated})

        buttons = {
            str(element.name or "").strip(): (element, states)
            for element, states in elements
            if str(element.role_en_us or "").strip().casefold() == "push button"
        }
        expected_buttons = {"Visualize", "Save As GraphML", "Cancel"}
        target = buttons.get(choice)
        if set(buttons) != expected_buttons or target is None or not {"enabled", "visible", "showing"}.issubset(target[1]) or not target[0].accessible_action:
            return _json({"ok": False, "error": "The three expected output choices and one enabled target were not verified; nothing was chosen.", "button_names": sorted(buttons)})

        try:
            target[0].click(simulate=False)
        except Exception as exc:  # noqa: BLE001
            return _json({"ok": False, "error": f"Output-choice AccessibleAction failed: {type(exc).__name__}: {exc}"})

        import win32gui

        hwnd = dialogs[0]["hwnd"]
        time.sleep(0.5)
        remains = bool(win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd))
        _write_event(
            "analysis_output_choice_requested",
            choice=choice,
            project="01-LA: Learning Analytics (2016-2026)",
            time_frame="2016-2026",
            qualified_records=int(qualified_match.group(1)),
            action_transport="Java Access Bridge AccessibleAction",
            dialog_remains_open=remains,
        )
        return _json({
            "ok": not remains,
            "choice": choice,
            "qualified_records": int(qualified_match.group(1)),
            "dialog_dismissed": not remains,
            "action_transport": "Java Access Bridge AccessibleAction",
            "next_step": "Inspect the resulting CiteSpace visualization/output; this choice does not itself verify file export.",
        })


@SERVER.tool(
    name="citespace_list_project_files",
    title="List files under the fixed 01-LA project",
    description=(
        "Read-only inventory limited to this task's 01-LA project directory. "
        "It distinguishes input/configuration files from non-empty candidate outputs and "
        "does not infer completed analysis from source records."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def citespace_list_project_files() -> str:
    return _json(_result_inventory())


@SERVER.tool(
    name="citespace_start_current_analysis",
    title="Start the analysis currently configured in CiteSpace",
    description=(
        "State-changing. Starts only the already-selected CiteSpace analysis by the "
        "visible, enabled GO! control using Java AccessibleAction. It does not change the "
        "project, analysis mode, time range, or settings. Before calling, inspect the UI "
        "and confirm the intended project/settings with confirm_current_settings=true. "
        "The response means requested, not completed; verify generated files separately."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def citespace_start_current_analysis(confirm_current_settings: bool = False) -> str:
    if not confirm_current_settings:
        return _json(
            {
                "ok": False,
                "error": "Inspect the current CiteSpace project/settings first, then set confirm_current_settings=true.",
            }
        )
    if not PROJECT_DIR.is_dir():
        return _json({"ok": False, "error": f"The fixed 01-LA project directory is missing: {PROJECT_DIR}"})

    with _LOCK:
        driver, window, error = _get_driver()
        if driver is None:
            return _json({"ok": False, "error": error, "window": window})
        title = str(driver.root_element.name or (window or {}).get("title", ""))
        if "welcome" in title.casefold():
            return _json(
                {
                    "ok": False,
                    "error": "CiteSpace is still on its Welcome/notice screen; acknowledge it first, then inspect the active project.",
                    "window_title": title,
                }
            )

        targets, _notice, scanned, truncated = _find_named_controls(
            driver, {"go!", "stop"}, 8000
        )
        go_element = targets.get("go!")
        stop_element = targets.get("stop")
        stop_is_enabled = bool(
            stop_element is not None
            and "enabled" in {str(state).casefold() for state in stop_element.states_en_us}
        )
        go_states = (
            {str(state).casefold() for state in go_element.states_en_us}
            if go_element is not None
            else set()
        )
        go_is_visible = {"enabled", "visible", "showing"}.issubset(go_states)
        if stop_is_enabled:
            return _json({"ok": False, "error": "CiteSpace reports an enabled Stop control; an analysis may already be running."})
        if not go_is_visible:
            return _json(
                {
                    "ok": False,
                    "error": "No visible, enabled GO! control was verified; nothing was clicked.",
                    "nodes_scanned": scanned,
                    "truncated": truncated,
                }
            )

        if go_element is None:
            return _json({"ok": False, "error": "The verified GO! control could not be reacquired; nothing was clicked."})
        try:
            go_element.click(simulate=False)
        except Exception as exc:  # noqa: BLE001
            return _json({"ok": False, "error": f"AccessibleAction failed: {type(exc).__name__}: {exc}"})

        _write_event(
            "current_analysis_start_requested",
            window_title=title,
            fixed_project_directory=str(PROJECT_DIR),
            action_transport="Java Access Bridge AccessibleAction",
            completion_claim=False,
        )
        return _json(
            {
                "ok": True,
                "action_requested": True,
                "analysis_status": "requested_not_verified_complete",
                "window_title": title,
                "output_verification": "Call citespace_list_project_files; only non-empty CiteSpace outputs count as evidence.",
            }
        )


from workflow import register_workflow_tools
register_workflow_tools(SERVER, sys.modules[__name__])

if __name__ == "__main__":
    SERVER.run(transport="stdio")
