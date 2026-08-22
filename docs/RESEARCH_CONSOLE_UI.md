<!-- research-guard-doc-pair: research-console-ui | revision: 2026-08-23.3 -->
# Optional Research Console UI

[English](https://github.com/dltsum/research-guard/blob/main/docs/RESEARCH_CONSOLE_UI.md) | [简体中文](https://github.com/dltsum/research-guard/blob/main/docs/RESEARCH_CONSOLE_UI.zh-CN.md)

## Scope

Research Console is an optional, localhost-only browser interface for talking to
Codex while using the installed Research Guard Skill. It is distributed as
`research-guard-ui-addon.zip`; it is deliberately absent from every core
Research Guard archive and does not change the 17 top-level MCP tools.

The add-on contains a small standard-library HTTP server, static HTML/CSS/
JavaScript, and a controlled Codex CLI bridge. It bundles no model, core plugin,
Python runtime, TeX, Lean, external LLM API client, or automatic field
classifier. The main Codex agent still reads the complete user request and
selects the necessary Research Guard modules. The visible focus controls are
explicit user preferences, limited to three, not a small-model router.

## Install and launch

Install and enable the core Research Guard plugin first. Download
[research-guard-ui-addon.zip](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-ui-addon.zip)
and [SHA256SUMS-ui.txt](https://github.com/dltsum/research-guard/releases/latest/download/SHA256SUMS-ui.txt),
verify the archive digest, extract it, and run its `install.py` with the Python
registered by the core installation. The installer verifies every packaged
file, reuses the core `psutil`, checks that Codex and Research Guard are enabled,
checks the required per-server MCP controls through machine-readable Codex
output, and creates a versioned per-user installation. It downloads nothing.

You can give an agent this instruction:

```text
Install the optional Research Console from the Research Guard release. Verify
research-guard-ui-addon.zip against SHA256SUMS-ui.txt, run install.py with the
Python registered by the installed Research Guard core, launch it for my chosen
workspace, and give me the localhost URL. Do not install another model or call
an external LLM API.
```

Manual launch after installation:

```powershell
python "$HOME/.research-guard/addons/research-console/0.1.0/launch.py" --workspace "C:\path\to\research"
```

```sh
python3 "$HOME/.research-guard/addons/research-console/0.1.0/launch.py" --workspace "/path/to/research"
```

Exact host requirements and degradation behavior remain authoritative in
[REQUIREMENTS.md](https://github.com/dltsum/research-guard/blob/main/REQUIREMENTS.md).

## Interaction model

The workspace, sandbox, language, and up to three focus areas remain visible.
The default is “Let Codex choose.” New turns use `codex exec --json`; continued
turns use the returned Codex thread identifier. Prompts travel over standard
input and never appear in process arguments. NDJSON events expose assistant
messages, activity, citations, diagnostics, resource samples, usage, completion,
and factual failure states as they arrive.

Every turn enumerates configured MCP servers, disables every server except
`research-guard`, and explicitly binds the installed plugin's canonical local
stdio command. The Research Guard server is marked required, so startup fails
if it cannot initialize. Only that server receives Codex's documented
`default_tools_approval_mode = "approve"`; this is a narrow non-interactive
approval, not a global approval-policy change or a dangerous sandbox bypass.
Use a full Codex client when a task depends on another MCP server. See the
[Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
for the per-server approval and required-server keys.

This turn-oriented design follows Codex's documented
[non-interactive JSONL and resume interface](https://learn.chatgpt.com/docs/non-interactive-mode).
The richer [Codex App Server](https://learn.chatgpt.com/docs/app-server) is the
official deep-integration surface for client-managed approvals, user-input
requests, and full conversation history. Version 0.1 deliberately does not
implement that larger bidirectional protocol; it stays a small optional console.

There is no whole-task timeout. A running turn emits heartbeat and progress
events until Codex completes, the user presses Stop, the browser disconnects,
the resource guard aborts the owned process tree, or Codex reports failure.
Stage results remain visible and the main agent decides when research coverage
is complete unless the user supplied a time or budget limit.

Because a host may have more Skill descriptions than Codex can preload, the
bridge first verifies the installed plugin and places the exact installed
`SKILL.md` path in the compact visible turn context. The private child-process
environment also carries the plugin root for its local MCP launcher. The bridge
does not paste all module prompts into every turn.

## Security and privacy

The server binds only to `127.0.0.1` on a random port. Every API request requires
a per-launch random token. The token begins in the URL fragment, is moved to
browser `sessionStorage`, and is sent only in a custom same-origin header. The
server rejects foreign origins and sends a restrictive Content Security Policy,
frame, referrer, MIME, permissions, and cross-origin headers.

The interface uses no remote script, font, analytics, external API, or HTML
injection. Citations are created as safe DOM links and only `https://` targets
are clickable. The bridge redacts common credentials and the user-home prefix
from displayed diagnostics. Prompts and answers are not written by the UI
server; browser persistence is limited to workspace/thread metadata and local
preferences. Codex and any selected Research Guard module retain their own
documented persistence boundaries.

The UI exposes only `read-only` and `workspace-write` sandboxes. It never offers
dangerous bypass mode. A resumed Codex thread preserves the sandbox and working
directory established for that session.

Launching the dedicated console authorizes automatic calls only to the local
Research Guard MCP server for the submitted task. Those tools still enforce
their own evidence, dependency-consent, resource, and workspace contracts; the
console does not auto-download dependencies or turn a failed gate into PASS.
Other configured MCP servers are disabled for the turn rather than approved.

## Resource behavior

Research Console reuses the installed `assets/resource-policy.json`: one active
turn, GPU disabled, numerical thread counts fixed to one, at most 512 MiB
aggregate working set for the UI server plus its owned descendants, at least
512 MiB free physical memory, and 10 ms sampling. A breach terminates the owned
Codex process tree and is reported as an error, never PASS.

The add-on performs no background indexing or automatic model inference. It
starts Codex only after a user submits a message and supports an explicit Stop
control. The 512 MiB limit governs task-owned processes, not the whole operating
system; host inventory is not a claim that a turn will fit.

## Packaging and release

The deterministic add-on builder emits one archive and one checksum file. Its
manifest binds the add-on version, core compatibility, Python/Codex/`psutil`
requirements, file hashes, resource policy, security boundary, and archive
size. The build fails if the archive exceeds 25 MiB or contains the core MCP
server, plugin manifest, payload archive, model, or runtime.

Core package builders whitelist their files and exclude the complete `addons/`
tree. CI separately proves both directions: the UI archive is installable, and
all core archives remain UI-free. Release assets are optional and do not alter
the core checksum records.

## Maintainer workflow

The maintained source is under
[addons/research-console](https://github.com/dltsum/research-guard/tree/main/addons/research-console).
For every behavioral change:

1. update this English/Chinese pair together and refresh the registered hashes;
2. run the UI unit, HTTP, security, accessibility, bridge, packaging, and
   isolated-install tests serially;
3. run multiple add-on SkillOpt rounds under the core resource guard;
4. visually inspect a headless-browser screenshot at desktop and narrow width;
5. prove the core package still excludes `addons/`; and
6. rebuild the deterministic archive and publish its checksum.

The release workflow and maintainer checks are documented in
[CONTRIBUTING.md](https://github.com/dltsum/research-guard/blob/main/CONTRIBUTING.md).

## Known boundaries

- The UI is a transport and observability surface, not an independent reviewer,
  evidence source, scientific validator, or proof of completion.
- Version 0.1 does not render Codex App Server approval or structured user-input
  requests. A task needing a new interactive approval must be continued in a
  full Codex client; the UI never auto-accepts or bypasses it.
- It requires a working logged-in Codex CLI and an installed, enabled Research
  Guard plugin. If either is unavailable, the add-on fails preflight instead of
  silently switching to an external API.
- Browser closure cancels only the currently owned turn when the stream breaks;
  Codex-side durable receipts must still be inspected before any replay.
- Displayed citations are convenience links. Research Guard’s literature and
  citation gates remain responsible for identity, source-location, and claim-
  support verification.
- Any unavailable verification remains `NOT_RUN`, never PASS.
- Accessibility checks and visual inspection reduce UI defects but do not prove
  universal accessibility.
