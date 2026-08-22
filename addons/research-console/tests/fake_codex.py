from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


THREAD_ID = "11111111-2222-4333-8444-555555555555"


def emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False), flush=True)


def main() -> int:
    arguments = sys.argv[1:]
    if arguments == ["--version"]:
        print("codex-cli 0.test")
        return 0
    if arguments == ["plugin", "list", "--json"]:
        plugin_root = os.environ.get("FAKE_RESEARCH_GUARD_PLUGIN_ROOT", "")
        print(json.dumps({
            "installed": [{
                "pluginId": "research-guard@personal",
                "name": "research-guard",
                "version": os.environ.get("FAKE_PLUGIN_VERSION", "0.7.0+codex.test"),
                "installed": True,
                "enabled": True,
                "source": {"source": "local", "path": plugin_root},
            }],
            "available": [],
        }))
        return 0
    if len(arguments) >= 3 and arguments[-3:] == ["mcp", "list", "--json"]:
        print(json.dumps([
            {"name": "research-guard", "enabled": True},
            {"name": os.environ.get("FAKE_MCP_NAME", "unrelated-test-server"), "enabled": True},
        ]))
        return 0
    if not arguments or arguments[0] != "exec":
        print("unsupported fake Codex invocation", file=sys.stderr)
        return 2
    joined = " ".join(arguments)
    required_overrides = (
        "mcp_servers.unrelated-test-server.enabled=false",
        "mcp_servers.research-guard.required=true",
        'mcp_servers.research-guard.default_tools_approval_mode="approve"',
    )
    if any(value not in joined for value in required_overrides) or "--ignore-user-config" in arguments:
        print("Research Guard MCP isolation was not supplied", file=sys.stderr)
        return 4

    prompt = sys.stdin.read()
    if "installed Research Guard instructions at" not in prompt or "SKILL.md" not in prompt or "User request:" not in prompt:
        print("Research Guard UI context was not supplied", file=sys.stderr)
        return 3
    delay = float(os.environ.get("FAKE_CODEX_DELAY_SECONDS", "0"))
    if delay > 0:
        time.sleep(delay)
    emit({"type": "thread.started", "thread_id": THREAD_ID})
    emit({"type": "turn.started"})
    emit({
        "type": "item.completed",
        "item": {
            "id": "command-1",
            "type": "command_execution",
            "status": "completed",
            "command": "curl -H 'Authorization: Bearer test-secret-value' https://example.invalid",
        },
    })
    emit({
        "type": "item.completed",
        "item": {
            "id": "mcp-1",
            "type": "mcp_tool_call",
            "server": "research-guard",
            "tool": "list_research_modules",
            "status": "completed",
            "result": {"module_count": 15},
        },
    })
    emit({
        "type": "item.completed",
        "item": {
            "id": "message-1",
            "type": "agent_message",
            "text": "Bridge PASS with a [primary record](https://doi.org/10.1234/example).",
        },
    })
    emit({
        "type": "turn.completed",
        "usage": {"input_tokens": 12, "cached_input_tokens": 0, "output_tokens": 8, "reasoning_output_tokens": 0},
    })
    print(f"diagnostic path={Path.home()} token=unsafe-test-token", file=sys.stderr, flush=True)
    return int(os.environ.get("FAKE_CODEX_EXIT_CODE", "0"))


if __name__ == "__main__":
    raise SystemExit(main())
