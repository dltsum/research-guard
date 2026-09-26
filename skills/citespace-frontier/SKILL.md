---
name: citespace-frontier
description: Explore a field's frontier hotspots, burst topics, or intellectual structure. Use when the user wants to survey frontier hotspots, technology burst points, emerging trends, or co-citation/keyword networks of a research area. First settles the analysis mode with the user (real CiteSpace engine vs LLM-native analysis), then orchestrates Research Guard scope analysis, honest corpus building, and the companion citespace-mcp plugin, and leaves the graph display open for the user.
---

# CiteSpace Frontier Loop

This Skill coordinates Research Guard components with the **citespace-mcp**
companion plugin (real CiteSpace engine, `citespace_*` MCP tools). Research
Guard never reimplements network construction and never presents a hand-drawn
or model-imagined graph as a CiteSpace result.

Keep this file lean on purpose: load `references/tool-catalog.md` only when
you need the tool surface, and `references/operations.md` only for window,
session-lifetime, and capture mechanics. Do not preload either.

## Step 0 — Analysis mode gate (ask once, then remember)

Unless the user already named a mode, ask **once** before any analysis work
(first confirm tool mode is even available: the citespace-mcp plugin is
installed and its `citespace_*` MCP tools are visible — see
docs/CITESPACE_INTEGRATION.md; if not, say so and offer LLM-native mode
only):

- **Tool analysis (CiteSpace engine).** Real network construction, burst
  detection, and native visualization. Requires a registered literature
  corpus address (see Data source registry below).
- **LLM-native analysis.** The model reads the provided papers/corpus itself,
  reasons over them, and may propose or generate its own plots (trend charts,
  co-occurrence matrices) on request. Label every such figure explicitly as
  an LLM-produced analysis aid — never as a CiteSpace graph.

Record the user's choice in the session and do not re-ask for the same
request (the choice is per-session by design; only the corpus registry below
is durable). If the user later switches modes, restart from this gate.

## Data source registry (tool mode only)

Tool analysis needs a corpus address (a directory of UTF-8 WoS full-record
`.txt` exports, or a single such `.txt` file). Registry file:
`citespace_sources.json` inside a `.research-guard` directory in the user's
home directory (`%USERPROFILE%` on Windows, `$HOME` elsewhere — resolve the
home directory with the host's own convention and create the directory on
first write). It maps a user-chosen label to `{"data_directory": ...,
"registered_at": ..., "notes": ...}`.

1. If the user names a corpus label already in the registry, or gives a path
   equal to a registered `data_directory`, use the registered address
   **without asking again**.
2. If no suitable entry exists, ask the user for the address once, verify the
   path exists and contains WoS-format exports, then append the entry.
3. Never invent an address, never rename arbitrary JSON/BibTeX to WoS format,
   and never fabricate cited-reference (CR) data. If no export exists,
   produce the exact search strategy and required export fields and ask the
   user for the WoS export.

## Non-negotiable constraints

- Never use browser automation. Public HTTP APIs, Web search, and existing
  connectors only.
- One CiteSpace instance and one analysis at a time.
- **Leave the graph display open.** Do not call
  `citespace_finish_research_view`, do not close the CiteSpace window, and do
  not kill the application. Capture views with
  `citespace_capture_research_view` (`close_after` stays `false`) and tell
  the user the native window remains open. Closing it is the user's decision.
- **Hold the display with a session that outlives you** (mechanics in
  `references/operations.md`). Before claiming the window is open, verify
  with `citespace_status` that a `CiteSpace: Display Merged` window is
  actually visible at hand-back time.
- Fail closed: unrecognized dialogs, missing data, or hash/count mismatches
  block the step; never substitute invented output.

## Required flow (tool mode)

1. **Scope with Research Guard.** Restate the user's frontier question (topic,
   years, comparison intent). Use `frontier_analysis` on any work set the
   user already has before expanding the corpus, and use the discipline
   profile to pick node type (Reference for intellectual foundations, Keyword
   for topics/burst points, Author/Institution/Country for collaboration).
   Record terms, synonyms, and field boundaries — they feed the provenance
   section of the hand-back report.
2. **Resolve the corpus address** via the Data source registry above.
3. **Run the engine.** In order: `citespace_prepare_research` (keep the
   `run_id`) → `citespace_activate_research` → `citespace_configure_research`
   → `citespace_start_research` → `citespace_poll_research(export=true)`
   (bounded polls; never re-issue GO after a lost response — inspect
   `citespace_research_state` first). Tool names and parameters:
   `references/tool-catalog.md`.
4. **Verify before interpreting.** `citespace_analyze_graph`, then
   `citespace_capture_research_view` on the Display Merged window, then
   `citespace_verify_native_counts`. A native-vs-GraphML count mismatch must
   be prominent in the report.
5. **Ground the interpretation.** `citespace_read_evidence` and
   `citespace_graph_neighborhood` before claiming specific relations; re-query
   original external sources for important nodes; register external reads
   with `citespace_record_research_sources`, then
   `citespace_write_research_report` with `heading`/`text`/`evidence_ids`.
6. **Hand back, display open.** Report the question, corpus scope and
   provenance, exact settings, what the real graph shows (with evidence IDs),
   limitations and sensitivity, the run_id, and the artifact paths (GraphML,
   node CSV, report). End by stating that the CiteSpace visualization window
   was left open for the user.

## LLM-native mode

Read the corpus or papers directly, state the mode explicitly in the report,
and ground every claim in quoted or cited text. If the user wants figures,
propose the plot list first (what each plot shows and from which data),
generate them only from real extracted numbers, and label each as
"LLM analysis aid — not a CiteSpace visualization".

## Interruption recovery

After any interruption, resume from `citespace_research_state(run_id)`; never
replay a reserved run. If the CiteSpace app was closed externally,
`citespace_launch` is the generic startup recovery entry point, but a
completed run's display is never closed by this Skill itself.
