<!-- research-guard-doc-pair: citespace-integration | revision: 2026-09-26.1 -->
# CiteSpace Integration

Research Guard coordinates with the companion **citespace-mcp** plugin when a user wants to explore a field's frontier hotspots, technology burst points, or collaboration structure with the real CiteSpace engine. Research Guard supplies scope analysis, evidence discipline, and reporting; citespace-mcp drives the local CiteSpace application and returns real graphs. Neither side reimplements the other, and no invented graph is ever presented as a CiteSpace result.

## What the companion plugin provides

- An MCP server (`citespace`) exposing `citespace_*` tools: generic startup/control tools plus the `citespace_prepare/activate/configure/start/poll/analyze` research workflow tools, evidence readback, source registration, and report writing.
- A bundled narrow Java Access Bridge adapter that completes the verified CiteSpace Basic startup sequence without browser automation.
- A `citespace-research` skill describing the full research loop. Research Guard's `citespace-frontier` skill builds on it and adds the Research Guard scope phase and the keep-the-display-open rule.

## Prerequisites

- A local CiteSpace installation (the plugin's verified engine is CiteSpace 6.4.R2 Basic on Windows) and the companion Java runtime the plugin package declares.
- The citespace-mcp plugin installed for your harness (a release ZIP such as `citespace-mcp-workflow-<version>_codex.<date>.zip`).
- A literature corpus: UTF-8 WoS full-record `.txt` export. If none exists, the flow stops after producing the exact search strategy and required export fields — it never fabricates cited-reference data.

## Install alongside Research Guard

Both plugins are ordinary MCP plugins and coexist; each harness loads them independently:

- **Claude Code**: `claude --plugin-dir /path/to/citespace-mcp` next to the Research Guard plugin, or install both from personal marketplaces.
- **Codex**: install the release ZIP through Codex's plugin install flow; Research Guard remains installed via its own installer.
- **Kimi Code CLI**: `/plugins install /path/to/citespace-mcp` (the package ships a Codex-format manifest; Kimi reads the same `.mcp.json` and `skills/` layout).

After install, confirm both servers answer: the Research Guard tools (`research_design`, …) and the `citespace_*` tools must both be visible to the agent before starting a frontier loop.

## The frontier loop (agent-side)

1. Scope with Research Guard: restate the question, analyze candidate search scopes with the frontier components, and choose the node type from the research purpose (Reference = co-citation foundations, Keyword = topics/bursts, Author/Institution/Country = collaboration).
2. Build the corpus honestly: `citespace_search_literature` and Web search for discovery; a real WoS export for the actual network.
3. Drive the engine through the research workflow tools in order, keeping the `run_id`.
4. Verify (`citespace_analyze_graph` → `citespace_capture_research_view` → `citespace_verify_native_counts`) before interpreting; count mismatches are reported prominently.
5. Ground every claim with `citespace_read_evidence` / `citespace_graph_neighborhood`, register external sources, and write the evidence-indexed report.
6. Hand back artifacts (GraphML, node CSV, report, run_id) **and leave the native visualization window open for the user**.

## Keep the display open

The `citespace-frontier` skill forbids closing the graph display when work completes: no `citespace_finish_research_view`, no window close, no application kill after capture. `citespace_capture_research_view` is always used with `close_after=false`. The user decides when to close the window. If a run must be torn down for a *new* run, that happens only inside `citespace_activate_research`, which never kills an active analysis.

## Failure handling

Unrecognized dialogs, missing WoS data, Basic node-cap failures, and native-vs-export count mismatches all block their step with state preserved. Recovery starts from `citespace_research_state(run_id)`; `citespace_launch` is the generic startup recovery entry. A completed run's parameters or corpus are never silently changed.
