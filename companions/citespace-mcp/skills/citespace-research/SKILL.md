---
name: citespace-research
description: 根据用户研究需求进行文献调研，调用本机 CiteSpace 构建真实知识图谱，再回读节点、边、指标和原始文献形成可核查解释。适用于 CiteSpace、文献计量、共被引、关键词共现、合作网络、知识图谱分析及其自动报告；不仅用于固定示例项目。
---

# CiteSpace research loop

Use Codex for research reasoning and interpretation; use CiteSpace as the actual
network-construction engine. Never replace an unavailable CiteSpace result with
an invented graph, a generic drawing, or a hand-computed network presented as native.

## Non-negotiable operating constraints

- Never use browser automation, browser-control skills, Playwright or Puppeteer.
  Use Web search, public HTTP APIs and existing connectors only.
- Run one CiteSpace instance and one analysis at a time. No GPU is needed.
- All analysis runs get distinct directories; source records and previous results
  are preserved. Never silently change a completed run's parameters or corpus.
- The host's request to perform analysis authorizes routine local workflow calls;
  do not ask for repeated GO/parameter/known startup-dialog confirmations.
- Current bundled engine is Windows CiteSpace 6.4.R2 Basic. Licence acceptance,
  email/account registration and verification are completed by the user. Do not
  submit a fabricated or `.invalid` address. The packaged launcher stops at
  startup forms; continue only after the user reaches the main interface.
- Startup fields/buttons are invoked by the bundled narrow Swing adapter, without
  foreground focus or keystrokes. The unchanged CiteSpace application JAR is run
  on the verified companion Java 22.0.1 JRE with a 1024 MiB heap cap; no GPU.

## 1. Understand and investigate

Extract the question, topic, years, corpus location and intended comparison.
Inspect the user's named project rather than automatically reusing `01-LA`.
Use `citespace_search_literature` and available Web search to establish terms,
synonyms, field boundaries and influential/recent papers. Exact DOI lookup is
preferred when interpreting graph nodes. Read abstracts/original sources rather
than treating titles or model memory as evidence. Record title, URL and a short
note saying what was actually read.

Choose analyses by the question, explaining each selection:

| Research purpose | Native node type | Meaning / required data |
|---|---|---|
| Intellectual foundations | Reference | Co-citation; full cited references CR |
| Topics and terminology | Keyword | Co-occurrence; DE / ID |
| Collaboration | Author / Institution / Country | AU / addresses C1 or C3 |
| Cited authors or journals | Cited Author / Cited Journal | CR |

Do not claim co-citation identifies causal influence or frequency measures
scientific quality. Reference and Keyword usually require separate runs.

## 2. Establish an honest corpus

The automatic importer currently accepts UTF-8 WoS full-record `.txt` exports.
It audits years, field availability, source hashes, exact duplicates and exclusion
reasons. Conflicting duplicate IDs stop the run instead of silently picking one.

Public bibliographic search is for discovery and source checking, not a complete
WoS/Scopus citation corpus. If a suitable export is absent, produce the actual
search strategy and precise required export fields, then report the missing data.
Do not fabricate CR, fetch a paid database without access, or rename an arbitrary
JSON/BibTeX file to WoS format. Other formats need a separately verified converter.
State dataset coverage and incomplete current-year data in the final interpretation.

## 3. Execute via the new workflow tools

1. `citespace_prepare_research`: title, question, data directory, years, node type,
   k, rationale, and source receipts. Keep returned `run_id`.
2. `citespace_activate_research`: backs up the native project registry, preserves
   all entries, registers an isolated project, normally restarts an **idle** app,
   then completes the known startup sequence. Never kill an active analysis.
3. `citespace_configure_research`: applies parameters using Java Access Bridge,
   verifies paths and actual control states, writes `verified_settings.json`.
4. `citespace_start_research`: reserves the submission on disk before GO. If it
   returns an uncertain outcome, inspect `citespace_research_state` and poll.
   Never issue another GO just because a response was lost.
5. `citespace_poll_research(export=true)`: bounded polls, not a tight loop. Match
   the actual completion dialog to this run, request native Visualize/export,
   then require two identical fresh graph hashes and valid GraphML.
6. `citespace_analyze_graph`: read real nodes/edges, native frequency/centrality
   where actually present, and explicitly identified derived graph statistics.
   Capture the native Display Merged window with `citespace_capture_research_view`,
   inspect its N/E count, then `citespace_verify_native_counts`. This installed
   build has produced a 1,059-edge native graph but a 1,000-edge GraphML: do not
   assume the auto-export is complete. A mismatch must be prominent in reports;
   exported density/degree are not then native-network density/degree.
7. `citespace_read_evidence`: retrieve relevant corpus abstracts and DOI records.
   Re-query external original sources for cited nodes outside the source corpus.
   Use `citespace_graph_neighborhood` to inspect real edges/weights around important
   nodes before claiming specific network relationships. Respect truncation flags.
8. `citespace_write_research_report`: supply grounded interpretation sections.
   Add newly read external sources with `citespace_record_research_sources` first.

The legacy fixed-01-LA tools remain available for compatibility; use the new
research tools for all general projects. `citespace_launch` remains the generic
startup recovery entry point.

## 4. Handle constraints without manipulating the conclusion

- Basic's node cap can require a smaller k. Record the failure and original
  parameters, dismiss only the verified node-limit message, and create a **new**
  run with a justified smaller k. Never secretly truncate exported nodes.
- Pick k for analytical scope/capacity, not to maximize a pleasing plot or Q.
  If a conclusion depends on it, compare another admissible setting explicitly.
- Clustering, timeline and burst results are **not automatically claimed** by
  GraphML parsing. A declared key with no values is missing, not zero.
  Default `Q=0`/`silhouette=0` in signature files is not a computed measurement.
- `citespace_read_research_artifact` can read native burst input/output and other
  text artifacts. Verify field meanings and mappings before making claims.
  Advanced cluster/timeline UI automation is not implemented in this release.
  If the installed workflow cannot export the requested analysis, say exactly so.
- Any unrecognized dialog, missing data or mismatched project blocks that step.
  Retain its state, explain the precise issue, and do not substitute fake output.

## 5. Return interpreted evidence, not just files

Report at least:

1. Research question, dataset scope, search provenance and exact settings.
2. What the actual graph shows: major nodes, relations, coverage and structure.
3. What original papers say, and how that supports or challenges the graph-based
   reading. Separate observed numbers, interpretive inference and open hypotheses.
4. Limitations and sensitivity relevant to the user's question.
5. Native GraphML, node CSV, readable HTML/Markdown report, graph artifact and
   a run identifier for reproducibility.

Every interpretation section has `heading`, `text`, `evidence_ids`.
Allowed evidence IDs are `graph:summary`, `node:<native-id>`,
`record:<record_id>` and `source:<1-based-index>` from the registered sources.
Validate source-content fit yourself: existence of an ID is not logical proof.

The included SVG is a deterministic re-rendering of actual CiteSpace edges,
**not** its native cluster/timeline layout. Do not call it one. If capturing a
native visualization, use the plugin's verified CiteSpace-window capture tool,
not browser automation, and inspect the image before claiming it is informative.

After interruption, start with the saved manifest; never replay a reserved run.
