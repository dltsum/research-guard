---
name: citespace-frontier
description: Explore a field's frontier hotspots, burst topics, or intellectual structure with the real CiteSpace engine. Use when the user wants to survey frontier hotspots, technology burst points, emerging trends, co-citation or keyword networks of a research area. Orchestrates Research Guard scope analysis, honest corpus building, and the companion citespace-mcp plugin, and leaves the graph display open for the user.
---

# CiteSpace Frontier Loop

This Skill coordinates Research Guard components with the **citespace-mcp**
companion plugin (real CiteSpace engine, `citespace_*` MCP tools). Research
Guard never reimplements network construction and never presents a hand-drawn
or model-imagined graph as a CiteSpace result.

Prerequisites: the citespace-mcp plugin is installed and its MCP server is
running next to Research Guard (see docs/CITESPACE_INTEGRATION.md), a local
CiteSpace Basic installation is available, and the user supplied or authorized
a literature corpus.

## Non-negotiable constraints

- Never use browser automation. Public HTTP APIs, Web search, and existing
  connectors only.
- One CiteSpace instance and one analysis at a time.
- **Leave the graph display open.** When the analysis completes, do not call
  `citespace_finish_research_view`, do not close the CiteSpace window, and do
  not kill the application. Capture views with
  `citespace_capture_research_view` (its `close_after` stays `false`) and tell
  the user the native visualization window remains open on their desktop.
  Closing it is the user's decision.
- Fail closed: unrecognized dialogs, missing data, or hash/count mismatches
  block the step; never substitute invented output.

## Required flow

1. **Scope with Research Guard.** Restate the user's frontier question (topic,
   years, comparison intent). Use `research_design` frontier components to
   analyze candidate search scopes: call `frontier_analysis` on any work set
   the user already has to see existing bursts before expanding the corpus, and
   use the discipline profile to pick node type (Reference for intellectual
   foundations, Keyword for topics/burst points, Author/Institution/Country
   for collaboration). Record terms, synonyms, and field boundaries.
2. **Build an honest corpus.** The CiteSpace importer accepts UTF-8 WoS
   full-record `.txt` exports. Use `citespace_search_literature` plus Web
   search for discovery and source checking; if a suitable export is absent,
   produce the exact search strategy and required export fields and ask the
   user for the WoS export. Never rename arbitrary JSON/BibTeX to WoS format
   and never fabricate cited-reference (CR) data.
3. **Run the engine.** In order: `citespace_prepare_research` (keep the
   `run_id`) → `citespace_activate_research` → `citespace_configure_research`
   → `citespace_start_research` → `citespace_poll_research(export=true)`
   (bounded polls; never re-issue GO after a lost response — inspect
   `citespace_research_state` first).
4. **Verify before interpreting.** `citespace_analyze_graph`, then
   `citespace_capture_research_view` on the Display Merged window, then
   `citespace_verify_native_counts`. A native-vs-GraphML count mismatch must
   be prominent in the report; exported density/degree are then not
   native-network values.
5. **Ground the interpretation.** `citespace_read_evidence` and
   `citespace_graph_neighborhood` before claiming specific relations; re-query
   original external sources for important nodes. Register external reads with
   `citespace_record_research_sources`, then
   `citespace_write_research_report` with `heading`/`text`/`evidence_ids`
   sections.
6. **Hand back, display open.** Report the question, corpus scope and
   provenance, exact settings, what the real graph shows (with evidence IDs),
   limitations and sensitivity, the run_id, and the artifact paths
   (GraphML, node CSV, report). End by stating that the CiteSpace
   visualization window was left open for the user.

## Interruption recovery

After any interruption, resume from `citespace_research_state(run_id)`; never
replay a reserved run. If the CiteSpace app was closed externally,
`citespace_launch` is the generic startup recovery entry point, but a
completed run's display is never closed by this Skill itself.
