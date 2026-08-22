from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence

from .contracts import ChatRequest, ContractError, compose_codex_prompt


SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)([?&](?:token|key|secret)=)[^&\s]+"),
    re.compile(r"(?i)(\b(?:token|api[_-]?key|secret)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"\b(?:ghp|github_pat|sk)-[A-Za-z0-9_-]{12,}\b"),
)
BASE_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[+.-]|$)")
MCP_CONFIG_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
MINIMUM_PLUGIN_VERSION = (0, 7, 0)


class BridgeError(ContractError):
    pass


@dataclass(frozen=True, slots=True)
class BridgePreflight:
    command_prefix: tuple[str, ...]
    codex_version: str
    plugin_root: Path
    plugin_version: str
    mcp_command: str
    mcp_args: tuple[str, ...]
    disabled_mcp_servers: tuple[str, ...]
    resource_policy: dict[str, Any]


def _safe_text(value: Any, *, maximum: int = 4000) -> str:
    text = str(value or "")
    home = str(Path.home())
    if home:
        text = text.replace(home, "~").replace(home.replace("\\", "/"), "~")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda match: match.group(1) + "[REDACTED]" if match.lastindex else "[REDACTED]", text)
    if len(text) > maximum:
        return text[: maximum - 1] + "…"
    return text


def _run_probe(command: Sequence[str], *, timeout: float = 30) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command), text=True, capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BridgeError("CODEX_PROBE_FAILED", f"Codex preflight failed: {_safe_text(exc)}", http_status=412) from exc


def _plugin_version_supported(value: Any) -> bool:
    matched = BASE_VERSION.match(str(value or ""))
    return bool(matched) and tuple(int(part) for part in matched.groups()) >= MINIMUM_PLUGIN_VERSION


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_key_segment(value: str) -> str:
    if not MCP_CONFIG_ID.fullmatch(value):
        raise BridgeError("MCP_NAME_UNSUPPORTED", "A configured MCP server uses an unsupported identifier.", http_status=412)
    return value


def _load_plugin_mcp(plugin_root: Path) -> tuple[str, tuple[str, ...]]:
    try:
        value = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BridgeError("PLUGIN_MCP_INVALID", "The installed Research Guard MCP declaration is invalid.", http_status=412) from exc
    servers = value.get("mcpServers") if isinstance(value, dict) else None
    if not isinstance(servers, dict) or set(servers) != {"research-guard"}:
        raise BridgeError("PLUGIN_MCP_INVALID", "Research Console requires exactly one canonical Research Guard MCP server.", http_status=412)
    server = servers["research-guard"]
    if not isinstance(server, dict) or set(server) != {"command", "args"}:
        raise BridgeError("PLUGIN_MCP_INVALID", "The Research Guard MCP server must be a local stdio command.", http_status=412)
    command = server.get("command")
    arguments = server.get("args")
    if not isinstance(command, str) or not command.strip() or not isinstance(arguments, list) or not all(
        isinstance(item, str) for item in arguments
    ):
        raise BridgeError("PLUGIN_MCP_INVALID", "The Research Guard MCP command or arguments are invalid.", http_status=412)
    replacements = [command, *arguments]
    resolved = [item.replace("${PLUGIN_ROOT}", str(plugin_root)) for item in replacements]
    if any("${" in item for item in resolved):
        raise BridgeError("PLUGIN_MCP_INVALID", "The Research Guard MCP declaration contains an unresolved variable.", http_status=412)
    return resolved[0], tuple(resolved[1:])


def discover_preflight(command_prefix: Sequence[str] | None = None) -> BridgePreflight:
    if command_prefix is None:
        configured = os.environ.get("RESEARCH_GUARD_CODEX_EXECUTABLE", "").strip()
        executable = configured or shutil.which("codex")
        if not executable:
            raise BridgeError("CODEX_NOT_FOUND", "Codex CLI is not on PATH.", http_status=412)
        command_prefix = (executable,)
    prefix = tuple(str(item) for item in command_prefix)
    if not prefix:
        raise BridgeError("CODEX_NOT_FOUND", "Codex command is empty.", http_status=412)

    version_run = _run_probe([*prefix, "--version"], timeout=15)
    if version_run.returncode != 0 or "codex" not in version_run.stdout.casefold():
        raise BridgeError("CODEX_VERSION_UNAVAILABLE", "Codex CLI version preflight failed.", http_status=412)
    codex_version = version_run.stdout.strip()

    plugin_run = _run_probe([*prefix, "plugin", "list", "--json"], timeout=30)
    if plugin_run.returncode != 0:
        raise BridgeError("PLUGIN_LIST_FAILED", "Codex could not list installed plugins.", http_status=412)
    try:
        plugin_inventory = json.loads(plugin_run.stdout)
    except json.JSONDecodeError as exc:
        raise BridgeError("PLUGIN_LIST_INVALID", "Codex returned invalid plugin metadata.", http_status=412) from exc
    records = [
        item for item in plugin_inventory.get("installed", [])
        if isinstance(item, dict) and item.get("name") == "research-guard"
    ]
    if len(records) != 1 or records[0].get("installed") is not True or records[0].get("enabled") is not True:
        raise BridgeError(
            "RESEARCH_GUARD_NOT_READY",
            "Install and enable the Research Guard plugin, then start a new Codex session.",
            http_status=412,
        )
    if not _plugin_version_supported(records[0].get("version")):
        raise BridgeError(
            "RESEARCH_GUARD_VERSION_UNSUPPORTED",
            "Research Console requires Research Guard 0.7.0 or newer.",
            http_status=412,
        )
    source = records[0].get("source") or {}
    try:
        plugin_root = Path(str(source.get("path") or "")).expanduser().resolve(strict=True)
    except OSError as exc:
        raise BridgeError("PLUGIN_SOURCE_MISSING", "The installed Research Guard source path is unavailable.", http_status=412) from exc
    if not (plugin_root / "SKILL.md").is_file():
        raise BridgeError("PLUGIN_SKILL_MISSING", "The installed Research Guard SKILL.md is missing.", http_status=412)

    mcp_command, mcp_args = _load_plugin_mcp(plugin_root)
    mcp_run = _run_probe([*prefix, "mcp", "list", "--json"], timeout=30)
    if mcp_run.returncode != 0:
        raise BridgeError("MCP_LIST_FAILED", "Codex could not list configured MCP servers.", http_status=412)
    try:
        mcp_inventory = json.loads(mcp_run.stdout)
    except json.JSONDecodeError as exc:
        raise BridgeError("MCP_LIST_INVALID", "Codex returned invalid MCP metadata.", http_status=412) from exc
    if not isinstance(mcp_inventory, list) or len(mcp_inventory) > 128:
        raise BridgeError("MCP_LIST_INVALID", "Codex returned an invalid or excessive MCP inventory.", http_status=412)
    names: list[str] = []
    for item in mcp_inventory:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not MCP_CONFIG_ID.fullmatch(name) or name in names:
            raise BridgeError("MCP_LIST_INVALID", "Codex returned an invalid MCP server name.", http_status=412)
        names.append(name)
    disabled_mcp_servers = tuple(sorted(name for name in names if name != "research-guard"))

    policy_path = plugin_root / "assets" / "resource-policy.json"
    try:
        resource_policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BridgeError("RESOURCE_POLICY_MISSING", "The installed Research Guard resource policy is unavailable.", http_status=412) from exc
    required_policy = {
        "owned_task_budget_bytes": 512 * 1024**2,
        "run_min_free_bytes": 512 * 1024**2,
        "maximum_parallel_workers": 1,
        "gpu_allowed": False,
        "memory_metric": "aggregate_working_set",
    }
    for key, expected in required_policy.items():
        if resource_policy.get(key) != expected:
            raise BridgeError("RESOURCE_POLICY_DRIFT", f"Research Guard resource policy drifted at {key}.", http_status=412)
    sampling = resource_policy.get("sampling_interval_seconds")
    if not isinstance(sampling, (int, float)) or sampling <= 0 or sampling > 0.01:
        raise BridgeError("RESOURCE_POLICY_DRIFT", "Resource sampling must be positive and no slower than 10 ms.", http_status=412)

    return BridgePreflight(
        command_prefix=prefix,
        codex_version=codex_version,
        plugin_root=plugin_root,
        plugin_version=str(records[0].get("version") or "unknown"),
        mcp_command=mcp_command,
        mcp_args=mcp_args,
        disabled_mcp_servers=disabled_mcp_servers,
        resource_policy=resource_policy,
    )


def normalize_codex_event(value: dict[str, Any]) -> dict[str, Any]:
    event_type = str(value.get("type") or "unknown")
    if event_type == "thread.started":
        return {"kind": "thread", "thread_id": str(value.get("thread_id") or "")}
    if event_type == "turn.started":
        return {"kind": "status", "phase": "thinking", "message": "Codex turn started."}
    if event_type == "turn.completed":
        usage = value.get("usage") if isinstance(value.get("usage"), dict) else {}
        safe_usage = {
            key: int(number) for key, number in usage.items()
            if key in {"input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"}
            and isinstance(number, int)
        }
        return {"kind": "usage", "usage": safe_usage}
    if event_type == "item.completed":
        item = value.get("item") if isinstance(value.get("item"), dict) else {}
        item_type = str(item.get("type") or "unknown")
        if item_type == "agent_message":
            return {"kind": "assistant", "text": str(item.get("text") or "")}
        if item_type == "error":
            return {"kind": "warning", "message": _safe_text(item.get("message"))}
        summary = {"item_type": item_type}
        for key in ("name", "server", "tool", "status"):
            if item.get(key) not in (None, ""):
                summary[key] = _safe_text(item[key], maximum=500)
        if item_type == "command_execution" and item.get("command"):
            summary["command"] = _safe_text(item["command"], maximum=500)
        return {"kind": "activity", "event": summary}
    if event_type in {"error", "turn.failed"}:
        return {"kind": "error", "code": event_type, "message": _safe_text(value.get("message") or value.get("error"))}
    return {"kind": "activity", "event": {"event_type": event_type}}


def _close_pipe_safely(pipe: Any) -> OSError | None:
    if pipe is None or pipe.closed:
        return None
    try:
        pipe.close()
    except OSError as exc:
        return exc
    return None


def _close_process_pipes(process: subprocess.Popen[str]) -> None:
    for pipe in (process.stdin, process.stdout, process.stderr):
        _close_pipe_safely(pipe)


class CodexBridge:
    def __init__(self, preflight: BridgePreflight) -> None:
        self.preflight = preflight
        self._lock = threading.Lock()
        self._active: dict[str, subprocess.Popen[str]] = {}
        self._starting_run_id: str | None = None
        try:
            import psutil  # type: ignore
        except ImportError as exc:
            raise BridgeError(
                "RESOURCE_TELEMETRY_MISSING",
                "Launch the UI with the registered Research Guard core Python so psutil can enforce the 512 MiB contract.",
                http_status=412,
            ) from exc
        self._psutil = psutil

    @classmethod
    def from_environment(cls) -> "CodexBridge":
        return cls(discover_preflight())

    def public_status(self, default_workspace: Path) -> dict[str, Any]:
        with self._lock:
            active = list(self._active)
            if self._starting_run_id is not None:
                active.append(self._starting_run_id)
        policy = self.preflight.resource_policy
        return {
            "status": "READY",
            "codex": {"ready": True, "version": self.preflight.codex_version},
            "plugin": {"ready": True, "name": "research-guard", "version": self.preflight.plugin_version},
            "resource": {
                "memory_metric": policy["memory_metric"],
                "owned_limit_bytes": policy["owned_task_budget_bytes"],
                "run_min_free_bytes": policy["run_min_free_bytes"],
                "sample_seconds": policy["sampling_interval_seconds"],
                "maximum_parallel_runs": 1,
                "gpu_allowed": False,
            },
            "active_run_ids": active,
            "default_workspace": str(default_workspace),
            "mcp_isolation": {
                "required_server": "research-guard",
                "approval_scope": "research-guard MCP only",
                "disabled_other_server_count": len(self.preflight.disabled_mcp_servers),
            },
            "session_persistence": "Codex thread plus browser-local metadata; the UI server does not write prompt transcripts.",
        }

    def _mcp_overrides(self) -> list[str]:
        values: list[str] = []
        for name in self.preflight.disabled_mcp_servers:
            values.extend(["-c", f"mcp_servers.{_toml_key_segment(name)}.enabled=false"])
        values.extend([
            "-c", f"mcp_servers.research-guard.command={_toml_string(self.preflight.mcp_command)}",
            "-c", "mcp_servers.research-guard.args=" + json.dumps(list(self.preflight.mcp_args), ensure_ascii=False),
            "-c", "mcp_servers.research-guard.enabled=true",
            "-c", "mcp_servers.research-guard.required=true",
            "-c", 'mcp_servers.research-guard.default_tools_approval_mode="approve"',
        ])
        return values

    def _command(self, request: ChatRequest) -> list[str]:
        overrides = self._mcp_overrides()
        if request.thread_id:
            return [
                *self.preflight.command_prefix,
                "exec", *overrides, "resume", "--json",
                "--skip-git-repo-check", request.thread_id, "-",
            ]
        return [
            *self.preflight.command_prefix,
            "exec", *overrides, "--json", "--color", "never", "--skip-git-repo-check",
            "--sandbox", request.sandbox, "--cd", str(request.workspace), "-",
        ]

    def _environment(self) -> dict[str, str]:
        environment = dict(os.environ)
        environment.update({
            "RESEARCH_GUARD_PLUGIN_ROOT": str(self.preflight.plugin_root),
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
            "CUDA_VISIBLE_DEVICES": "",
            "HIP_VISIBLE_DEVICES": "",
            "ROCR_VISIBLE_DEVICES": "",
            "NVIDIA_VISIBLE_DEVICES": "none",
            "NO_COLOR": "1",
        })
        return environment

    def _owned_snapshot(self) -> tuple[int, int]:
        psutil = self._psutil
        root = psutil.Process(os.getpid())
        processes = [root, *root.children(recursive=True)]
        seen: set[int] = set()
        total = 0
        for process in processes:
            try:
                if process.pid not in seen:
                    total += int(process.memory_info().rss)
                    seen.add(process.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return total, int(psutil.virtual_memory().available)

    def _terminate_tree(self, process: subprocess.Popen[str]) -> None:
        psutil = self._psutil
        try:
            root = psutil.Process(process.pid)
            descendants = root.children(recursive=True)
        except psutil.NoSuchProcess:
            return
        for child in reversed(descendants):
            try:
                child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        try:
            root.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        _, alive = psutil.wait_procs([*descendants, root], timeout=3)
        for item in alive:
            try:
                item.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def cancel(self, run_id: str) -> bool:
        with self._lock:
            process = self._active.get(run_id)
        if process is None:
            return False
        self._terminate_tree(process)
        return True

    def stream(self, request: ChatRequest) -> Iterator[dict[str, Any]]:
        run_id = str(uuid.uuid4())
        with self._lock:
            if self._active or self._starting_run_id is not None:
                raise BridgeError("RUN_BUSY", "Only one Codex conversation turn can run at a time.", http_status=409)
            self._starting_run_id = run_id

        command = self._command(request)
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        try:
            process = subprocess.Popen(
                command,
                cwd=request.workspace,
                env=self._environment(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                shell=False,
                creationflags=creation_flags,
                start_new_session=os.name != "nt",
            )
        except OSError as exc:
            with self._lock:
                self._starting_run_id = None
            raise BridgeError("CODEX_START_FAILED", f"Codex could not start: {_safe_text(exc)}", http_status=502) from exc
        with self._lock:
            self._active[run_id] = process
            self._starting_run_id = None

        events: queue.Queue[dict[str, Any]] = queue.Queue()
        readers_done = {"stdout": False, "stderr": False}
        stop_monitor = threading.Event()
        resource_state = {"peak_owned_bytes": 0, "breach": None}

        def read_stdout() -> None:
            assert process.stdout is not None
            try:
                for raw in process.stdout:
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError:
                        events.put({"kind": "warning", "message": "Codex emitted a non-JSON stdout line."})
                        continue
                    if isinstance(value, dict):
                        events.put(normalize_codex_event(value))
            finally:
                events.put({"kind": "_reader_done", "reader": "stdout"})

        def read_stderr() -> None:
            assert process.stderr is not None
            try:
                for raw in process.stderr:
                    line = raw.strip()
                    if line:
                        events.put({"kind": "diagnostic", "message": _safe_text(line)})
            finally:
                events.put({"kind": "_reader_done", "reader": "stderr"})

        def monitor_resources() -> None:
            policy = self.preflight.resource_policy
            limit = int(policy["owned_task_budget_bytes"])
            low_water = int(policy["run_min_free_bytes"])
            interval = float(policy["sampling_interval_seconds"])
            last_report = 0.0
            while not stop_monitor.is_set() and process.poll() is None:
                owned, available = self._owned_snapshot()
                resource_state["peak_owned_bytes"] = max(int(resource_state["peak_owned_bytes"]), owned)
                if owned > limit:
                    resource_state["breach"] = "RESOURCE_WORKING_SET_ABORT"
                    events.put({
                        "kind": "error", "code": "RESOURCE_WORKING_SET_ABORT",
                        "message": f"Owned working set reached {owned:,} bytes; the Codex child tree was stopped.",
                    })
                    self._terminate_tree(process)
                    return
                if available < low_water:
                    resource_state["breach"] = "RESOURCE_LOW_WATER_ABORT"
                    events.put({
                        "kind": "error", "code": "RESOURCE_LOW_WATER_ABORT",
                        "message": f"Free physical memory fell to {available:,} bytes; the Codex child tree was stopped.",
                    })
                    self._terminate_tree(process)
                    return
                now = time.monotonic()
                if now - last_report >= 1:
                    events.put({"kind": "resource", "owned_bytes": owned, "available_bytes": available, "limit_bytes": limit})
                    last_report = now
                stop_monitor.wait(interval)

        stdout_thread = threading.Thread(target=read_stdout, name=f"rg-ui-stdout-{run_id[:8]}", daemon=True)
        stderr_thread = threading.Thread(target=read_stderr, name=f"rg-ui-stderr-{run_id[:8]}", daemon=True)
        monitor_thread = threading.Thread(target=monitor_resources, name=f"rg-ui-memory-{run_id[:8]}", daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        monitor_thread.start()

        input_error: str | None = None
        try:
            yield {
                "kind": "run", "run_id": run_id,
                "resumed": request.thread_id is not None,
                "sandbox": "session-preserved" if request.thread_id else request.sandbox,
                "workspace": str(request.workspace),
            }
            assert process.stdin is not None
            try:
                process.stdin.write(compose_codex_prompt(request, self.preflight.plugin_root / "SKILL.md"))
            except OSError:
                if resource_state["breach"] is None:
                    input_error = "CODEX_STDIN_CLOSED"
            close_error = _close_pipe_safely(process.stdin)
            if close_error is not None and resource_state["breach"] is None:
                input_error = "CODEX_STDIN_CLOSED"
            if input_error is not None:
                yield {
                    "kind": "error", "code": input_error,
                    "message": "Codex closed its input pipe before the research request was delivered.",
                }
                if process.poll() is None:
                    self._terminate_tree(process)
            while not all(readers_done.values()) or process.poll() is None or not events.empty():
                try:
                    event = events.get(timeout=5)
                except queue.Empty:
                    yield {"kind": "heartbeat", "elapsed": True}
                    continue
                if event.get("kind") == "_reader_done":
                    readers_done[str(event["reader"])] = True
                    continue
                yield event
            return_code = process.wait()
            success = return_code == 0 and resource_state["breach"] is None and input_error is None
            if not success and resource_state["breach"] is None and input_error is None:
                yield {"kind": "error", "code": "CODEX_EXIT_NONZERO", "message": f"Codex exited with code {return_code}."}
            yield {
                "kind": "done", "run_id": run_id, "success": success,
                "exit_code": return_code,
                "peak_owned_bytes": int(resource_state["peak_owned_bytes"]),
                "resource_breach": resource_state["breach"],
            }
        except GeneratorExit:
            self._terminate_tree(process)
            raise
        finally:
            stop_monitor.set()
            if process.poll() is None:
                self._terminate_tree(process)
            for thread in (stdout_thread, stderr_thread, monitor_thread):
                thread.join(timeout=2)
            _close_process_pipes(process)
            with self._lock:
                self._active.pop(run_id, None)
                if self._starting_run_id == run_id:
                    self._starting_run_id = None
