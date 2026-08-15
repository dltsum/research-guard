from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _run(command: list[str], *, env: dict[str, str], input_text: str | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, input=input_text, text=True, capture_output=True, env=env, timeout=timeout, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed: {command[0]}: {(completed.stderr or completed.stdout)[-2000:]}")
    return completed


def verify(user_root: Path) -> dict[str, object]:
    user_root = user_root.resolve()
    plugin = user_root / "plugins" / "research-guard"
    skill = user_root / ".codex" / "skills" / "research-guard"
    runtime = user_root / ".research-guard" / "runtime" / "python"
    python = runtime / "python.exe"
    for path in (plugin / "SKILL.md", skill / "SKILL.md", python, plugin / "scripts" / "mcp_server.py"):
        if not path.is_file():
            raise RuntimeError(f"isolated install is missing {path}")
    env = {
        **os.environ,
        "RESEARCH_GUARD_INSTALL_USER_ROOT": str(user_root),
        "RESEARCH_GUARD_HOME": str(user_root / ".research-guard"),
        "RESEARCH_GUARD_CODEX_ROOT": str(user_root / ".codex"),
        "PYTHONUTF8": "1",
    }
    versions = _run(
        [str(python), "-I", "-X", "utf8", "-c", "import json,pint,sympy,z3; print(json.dumps({'pint':pint.__version__,'sympy':sympy.__version__,'z3':z3.get_version_string()}))"],
        env=env,
    )
    version_data = json.loads(versions.stdout)
    if version_data != {"pint": "0.25.3", "sympy": "1.14.0", "z3": "5.0.0"}:
        raise RuntimeError(f"formula runtime version mismatch: {version_data}")
    inventory_run = _run([str(python), "-I", "-X", "utf8", str(plugin / "scripts" / "dependency_manager.py"), "inventory", "--json"], env=env)
    inventory = json.loads(inventory_run.stdout)
    if not inventory.get("first_load_pending") or len(inventory.get("components", [])) != 7:
        raise RuntimeError("isolated first-load inventory is invalid")
    initialized = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}}
    listed = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    mcp = _run(
        [str(python), "-I", "-X", "utf8", str(plugin / "scripts" / "mcp_server.py")],
        env=env, input_text=json.dumps(initialized) + "\n" + json.dumps(listed) + "\n",
    )
    responses = [json.loads(line) for line in mcp.stdout.splitlines() if line.strip()]
    if responses[0]["result"]["serverInfo"]["version"] != "0.6.0" or len(responses[1]["result"]["tools"]) != 15:
        raise RuntimeError("isolated MCP surface or version is invalid")
    return {
        "status": "PASS", "user_root": str(user_root), "plugin": str(plugin), "skill": str(skill),
        "runtime_versions": version_data, "mcp_tools": 15, "mcp_version": "0.6.0",
        "first_load_pending": True, "components": 7, "actionable_components": 3,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-root", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.user_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
