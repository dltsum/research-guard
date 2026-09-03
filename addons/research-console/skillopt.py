from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ADDON = Path(__file__).resolve().parent
PLUGIN = ADDON.parents[1]
EVIDENCE = PLUGIN / "evals" / "p23-research-console-ui"
sys.path.insert(0, str(PLUGIN / "scripts"))

from resource_guard import (  # noqa: E402
    ResourceGuardError,
    require_orchestrator_budget,
    require_start_headroom,
    run_managed_light,
)
from mcp_server import TOOLS  # noqa: E402


def _static_contract() -> dict[str, Any]:
    source = json.loads((ADDON / "addon-source.json").read_text(encoding="utf-8"))
    app = (ADDON / "research_console" / "static" / "app.js").read_text(encoding="utf-8")
    server = (ADDON / "research_console" / "server.py").read_text(encoding="utf-8")
    bridge = (ADDON / "research_console" / "codex_bridge.py").read_text(encoding="utf-8")
    modular = (PLUGIN / "scripts" / "build_modular_package.py").read_text(encoding="utf-8")
    public = (PLUGIN / "scripts" / "build_public_package.py").read_text(encoding="utf-8")
    parity = json.loads((PLUGIN / "assets" / "documentation-parity.json").read_text(encoding="utf-8"))
    plugin = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    checks = {
        "optional package has a hard size cap and embeds no core":
            source.get("package", {}).get("maximum_archive_bytes") == 25 * 1024**2,
        "one-run no-gpu resource boundary is declared":
            source.get("runtime", {}).get("maximum_parallel_codex_runs") == 1
            and source.get("runtime", {}).get("gpu_allowed") is False,
        "localhost token and origin controls are executable": all(token in server for token in (
            '("127.0.0.1", port)', "X-Research-Guard-Token", "compare_digest",
            "Content-Security-Policy", "ORIGIN_REJECTED",
        )),
        "workspace is explicit and browser control is absent": all(token in server for token in (
            "RESEARCH_GUARD_WORKSPACE", "WORKSPACE_REQUIRED",
        )) and "default=Path.cwd()" not in server
        and "webbrowser" not in server and "arguments.open" not in server,
        "prompt stays on stdin and diagnostics are filtered": all(token in bridge for token in (
            "stdin=subprocess.PIPE", 'compose_codex_prompt(request, self.preflight.plugin_root / "SKILL.md")', "SECRET_PATTERNS",
            "RESEARCH_GUARD_PLUGIN_ROOT", "_starting_run_id",
        )),
        "only the required local Research Guard MCP receives automatic approval": all(token in bridge for token in (
            "disabled_mcp_servers", "mcp_servers.research-guard.required=true",
            'mcp_servers.research-guard.default_tools_approval_mode=\"approve\"',
        )) and '"--ignore-user-config"' not in bridge and "dangerously-bypass" not in bridge,
        "static client has no remote API or html injection":
            "https://" not in app and "innerHTML" not in app and "eval(" not in app,
        "core builders do not admit addon source":
            '"addons"' not in modular.split("ROOT_DIRECTORIES", 1)[1].split("}", 1)[0]
            and '"addons"' not in public.split("ROOT_DIRECTORIES", 1)[1].split("}", 1)[0],
        "bilingual UI contract is registered": any(
            item.get("id") == "research-console-ui" for item in parity.get("pairs", [])
        ),
        "top-level MCP surface remains 17":
            "Optional Research Console UI" in plugin.get("interface", {}).get("capabilities", [])
            and len(TOOLS) == 17,
    }
    candidates = [
        {"candidate": "embed a second model or small automatic field router", "decision": "REJECT"},
        {"candidate": "call an external LLM API when Codex preflight fails", "decision": "REJECT"},
        {"candidate": "put a web framework and UI in every core archive", "decision": "REJECT"},
        {"candidate": "reuse the canonical MCP server as a browser backend", "decision": "REJECT"},
        {"candidate": "inherit every configured MCP server", "decision": "REJECT"},
        {"candidate": "drop Research Guard tools with --ignore-user-config", "decision": "REJECT"},
        {"candidate": "globally bypass approvals", "decision": "REJECT"},
        {
            "candidate": "thin localhost Codex CLI adapter with separate archive and shared resource policy",
            "decision": "ADMIT",
        },
    ]
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "overlap_candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated optional Research Console SkillOpt gates")
    parser.add_argument("--rounds", type=int, default=4, choices=(3, 4, 5))
    arguments = parser.parse_args()
    require_start_headroom()
    require_orchestrator_budget()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    run_root = EVIDENCE / dt.datetime.now(dt.timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    run_root.mkdir(parents=True, exist_ok=False)
    rounds: list[dict[str, Any]] = []
    command = [
        sys.executable, "-X", "utf8", "-W", "error::ResourceWarning",
        "-m", "unittest", "discover", "-s", str(ADDON / "tests"), "-v",
    ]
    for index in range(1, arguments.rounds + 1):
        static = _static_contract()
        try:
            completed = run_managed_light(command, cwd=PLUGIN, timeout=180)
            output = (completed.stdout or "") + (completed.stderr or "")
            record = {
                "round": index,
                "status": "PASS" if completed.returncode == 0 and static["status"] == "PASS" else "FAIL",
                "static_contract": static,
                "test_returncode": completed.returncode,
                "test_output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
                "test_stdout_tail": (completed.stdout or "")[-10_000:],
                "test_stderr_tail": (completed.stderr or "")[-10_000:],
                "resource_usage": completed.resource_usage,
            }
        except ResourceGuardError as exc:
            record = {
                "round": index,
                "status": "FAIL",
                "static_contract": static,
                "test_returncode": None,
                "test_output_sha256": None,
                "test_stdout_tail": "",
                "test_stderr_tail": "",
                "resource_usage": None,
                "resource_guard_error": str(exc),
            }
        (run_root / f"round-{index:02d}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        rounds.append(record)
        if record["status"] != "PASS":
            break
    report = {
        "schema_version": 1,
        "status": "PASS" if len(rounds) == arguments.rounds and all(item["status"] == "PASS" for item in rounds) else "FAIL",
        "requested_rounds": arguments.rounds,
        "round_count": len(rounds),
        "run_root": run_root.relative_to(PLUGIN).as_posix(),
        "rounds": rounds,
    }
    report["report_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (run_root / "report.json").write_text(rendered, encoding="utf-8")
    (EVIDENCE / "report.json").write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
