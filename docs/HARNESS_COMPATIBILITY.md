<!-- research-guard-doc-pair: harness-compatibility | revision: 2026-09-25.1 -->
# Harness Compatibility

Research Guard ships one repository that several agent harnesses can load directly. This document lists, for each harness, the supported install path, the exact configuration snippet, and — where the harness plugin interface is not yet fully confirmed — the interface points another agent must discover before completing the integration.

The repository integration surface:

- `skills/` — five portable `SKILL.md` domain skills (the cross-harness standard format).
- `.mcp.json` — MCP stdio server `research-guard` (`scripts/mcp_launcher.py`). The launcher resolves the plugin root from `PLUGIN_ROOT`, `CLAUDE_PLUGIN_ROOT`, or either `${...}` placeholder expanded by the harness.
- `hooks/hooks.json` — SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, and Stop receipts. POSIX commands resolve the plugin root from `PLUGIN_ROOT` with a `CLAUDE_PLUGIN_ROOT` fallback; `commandWindows` entries use `%PLUGIN_ROOT%`.
- `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`, `kimi.plugin.json` — per-harness manifests that all point at the same surface above.

## Claude Code

The repository root is a complete Claude Code plugin: `.claude-plugin/plugin.json` plus the default component layout (`skills/`, `hooks/hooks.json`, `.mcp.json`).

Install for local development:

```
claude --plugin-dir /path/to/research-guard
```

Or add it as a personal marketplace entry and install persistently:

```
claude plugin marketplace add /path/to/parent-directory
claude plugin install research-guard@<marketplace-name>
```

Notes:

- Hook commands assume a POSIX `sh` on the PATH. On Windows, Claude Code's Git Bash environment satisfies this; the hooks then call `hooks/hook.sh`, which self-locates and needs no plugin-root variable.
- `agents/openai.yaml` is Codex-specific and is not a Claude Code subagent; Claude Code simply ignores non-Markdown entries.

## Codex

Already integrated. Run the installer, which copies the plugin into `~/plugins/research-guard`, registers a personal marketplace, and enables it:

```
python scripts/install_posix.py      # Linux / macOS
powershell -File install.ps1         # Windows (via scripts/install.sh equivalent)
```

The installer also materializes the skill into `~/.codex/skills/research-guard` and writes the MCP registration with absolute paths.

## Kimi Code CLI

The repository root contains `kimi.plugin.json` (Kimi's preferred manifest name, taking precedence over `.kimi-plugin/plugin.json`). The manifest reuses `skills/` and registers the MCP stdio server with a plugin-root-relative `./scripts/mcp_launcher.py` path.

Install from a local checkout or a Git URL inside Kimi Code:

```
/plugins install /path/to/research-guard
/plugins install https://github.com/<owner>/research-guard
/plugins mcp enable research-guard research-guard
```

Manage with `/plugins info research-guard`, `/plugins enable|disable research-guard`, and `/plugins reload`.

Interface points not yet confirmed (for a future agent to verify against Kimi's plugin documentation):

- Whether the manifest `hooks` field accepts Claude-style `SessionStart`/`UserPromptSubmit`/`PreToolUse`/`PostToolUse`/`Stop` events with `matcher` + `command` entries, and which plugin-root variable (`${PLUGIN_ROOT}` vs a Kimi-specific one) hook commands may use. The portable POSIX fallback in `hooks/hooks.json` already covers any harness that either substitutes `${PLUGIN_ROOT}` textually or exports `CLAUDE_PLUGIN_ROOT`; a Kimi-specific variable would need one more fallback branch.
- Whether `sessionStart.skill` should name one of the five skills for automatic activation.

## ZCode (Z.ai GLM harness)

ZCode supports MCP over stdio, HTTP, and SSE, and can import MCP configurations written for Claude Code or Codex CLI. Point it at this repository's `.mcp.json`, or add the equivalent entry directly:

```json
{
  "mcpServers": {
    "research-guard": {
      "command": "python",
      "args": ["-X", "utf8", "/absolute/path/to/research-guard/scripts/mcp_launcher.py"]
    }
  }
}
```

Replace `/absolute/path/to/research-guard` with the checkout location. Skills are portable `SKILL.md` files; if ZCode's skill loader expects a specific directory, copy or symlink `skills/research-design-guard` (and the other four) there.

## WorkBuddy (Tencent)

WorkBuddy reads MCP servers from `~/.workbuddy/mcp.json` and loads Claude-style skills from `~/.workbuddy/skills/`.

1. Copy (or symlink) the five skill directories into `~/.workbuddy/skills/`.
2. Merge into `~/.workbuddy/mcp.json`:

```json
{
  "mcpServers": {
    "research-guard": {
      "command": "python",
      "args": ["-X", "utf8", "C:/path/to/research-guard/scripts/mcp_launcher.py"]
    }
  }
}
```

## OpenClaw

OpenClaw configures MCP servers in `~/.openclaw/openclaw.json`; the same JSON shape as above applies. Two install routes:

1. **Direct MCP entry** — add the `research-guard` server (see the ZCode snippet) to `openclaw.json`.
2. **Plugin import via babelfish** — OpenClaw's `babelfish` plugin imports Claude Code and Codex plugins:

```
openclaw plugins install npm:@openclaw/babelfish
```

Then import this repository as a Claude Code plugin (`.claude-plugin/plugin.json`) or as a Codex plugin (`.codex-plugin/plugin.json`); babelfish translates skills, hooks, and the MCP registration.

## DSH (DeepSeek Harness) and other unconfirmed harnesses

The DSH plugin interface is not yet confirmed from public sources (only marketplace listing sites such as dsh.directory are reachable). Rather than guess, here is the checklist of interface points an integrating agent must discover in the target harness's own documentation or source, and how Research Guard satisfies each one once found:

1. **MCP stdio registration** — find where the harness stores MCP server definitions (a JSON file, a CLI `mcp add` command, or a UI). Register: command `python`, args `["-X", "utf8", "<absolute-repo-path>/scripts/mcp_launcher.py"]`. The launcher needs no environment variables; it re-execs into the installed runtime at `~/.research-guard/runtime/python` when present and otherwise validates dependencies in-process.
2. **Skill loading** — find the harness's skill/prompt-pack directory or manifest field. Each of the five directories under `skills/` is a self-contained Claude-standard `SKILL.md` skill; copy them or point the manifest at `./skills/`.
3. **Hook events** — find the harness's lifecycle hook mechanism and map these five events: session start (`SessionStart`, matchers `startup|resume|clear|compact`), before each user prompt is processed (`UserPromptSubmit`), before/after file-mutating or shell tool calls (`PreToolUse`/`PostToolUse`, matcher `Bash|apply_patch|Edit|Write`), and before the agent stops (`Stop`). Each hook entry runs one command with a 15-second timeout; use `sh "<repo>/hooks/hook.sh"` on POSIX or `"<repo>\scripts\hook.cmd"` on Windows. Both scripts self-locate, so any plugin-root variable the harness provides is only needed to find the script. Hooks communicate over stdin/stdout JSON exactly as Claude Code defines; if the harness uses a different wire format, write a thin adapter that relays JSON to `hooks/guard_hook.py` unchanged.
4. **Plugin manifest** — if the harness wants its own manifest file, model it on `kimi.plugin.json`: `name`, `version`, `description`, `author`, `license`, `skills: "./skills/"`, and an `mcpServers` map as in point 1.

If any point cannot be satisfied, stop and report which interface the harness lacks rather than silently degrading — the hooks and the MCP server are fail-closed by design.

## Verifying an installation

Whichever harness you used, verify through the MCP server:

1. Call the `research_design` tool with `{"action": "status"}`; a healthy install returns the current ledger state JSON.
2. Call `frontier_analysis` with `{"frontier_analysis_action": "status"}` to confirm the analysis modules loaded.
3. If hooks are active, submitting any prompt should produce no `DEPENDENCY_MISSING` output; that error means the Python runtime is absent and you should rerun `scripts/install.sh` / `install.ps1`.
