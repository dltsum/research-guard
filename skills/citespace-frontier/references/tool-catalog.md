# citespace-mcp tool catalog (load on demand)

The companion plugin exposes 26 `citespace_*` tools. Call them in the order
grouped below; never invent parameters — read the tool's own description via
the MCP `tools/list` schema when unsure.

## Session / lifecycle

- `citespace_launch` — start (or recover) the instrumented CiteSpace app.
- `citespace_status` — live windows, pids, active run; use it to verify a
  display window is actually visible before claiming so.
- `citespace_research_state` — persisted run state; the only safe resume
  point after an interruption.

## Run pipeline (strict order)

1. `citespace_prepare_research` — registers question, corpus, settings;
   returns the `run_id` everything else takes. Every source entry needs
   `title`/`url`/`note`.
2. `citespace_activate_research` — binds the app to the run; closes an idle
   previous display for a new run.
3. `citespace_configure_research` — writes the CiteSpace project settings.
4. `citespace_start_research` — submits processing. Never re-issue GO after a
   lost response; inspect `citespace_research_state` first.
5. `citespace_poll_research` — bounded polling; pass `export=true` so the
   GraphML/nodes export is produced with the native view.

## Analysis and evidence

- `citespace_analyze_graph` — metrics and ranked nodes over the export.
- `citespace_graph_neighborhood` — ego-neighborhood evidence for a node.
- `citespace_read_evidence` — read a registered evidence artifact.
- `citespace_verify_native_counts` — reconcile native display counts vs the
  GraphML export; surface any mismatch prominently.

## Display and capture

- `citespace_capture_research_view` — screenshot a live window; keep
  `close_after=false`. The merged display window title is
  `CiteSpace: Display Merged - (c) ...` — prefix-match it, never exact-match
  the short prefix.
- `citespace_finish_research_view` — closes the view. **Forbidden in this
  Skill's flow** (the display is left open for the user).

## Reporting

- `citespace_record_research_sources` — register external reads.
- `citespace_write_research_report` — write report sections with
  `heading`/`text`/`evidence_ids`.

## Corpus discovery

- `citespace_search_literature` — search/discovery helper for building the
  corpus honestly; pair with Web search for source checking.
