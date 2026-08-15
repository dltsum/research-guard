---
name: research-novelty-guard
description: Enforce version-bound cross-disciplinary literature collision checks for research ideas and methods. Use for idea exploration, novelty checks, method changes, related work, experiment proposals, or paper writing across computing, engineering, mathematics, science, medicine, social science, humanities, and history, including arXiv, IEEE, SCI/SSCI, CCF, CSSCI, and Chinese core journal requirements.
---

# Research Novelty Guard

Use the MCP tools as the authority. The Skill explains the order; code, evidence
manifests, hooks, and signed receipts enforce it.

## Required flow

1. Call `research_design action=status discipline_action=analyze` with the full request and explicit field when available. Warn first that an unregistered field's initial knowledge build may take minutes. Unknown fields must complete official-source initialization; history also requires books/editions/archive and primary-source discovery boundaries.
2. Call `register_method` with the project root and the complete method. `title`,
   `problem`, and `mechanism` are required. Include contributions, datasets,
   evaluation, aliases/keywords, required sources, and every method-bearing file
   when available.
3. Inspect `build_search_plan`, then call `run_novelty_search`. It executes every
   structured component query across domain-required publications, patents,
   trials, grants, datasets, software, and preregistrations, and records each
   source attempt. Never replace it with an unrecorded web search. Where no
   verified anonymous API exists, import a hash-bound official capture instead.
4. If coverage is incomplete, call `request_manual_evidence`. Ask for the exact
   query, official result URL, project-relative export/capture, result status,
   and structured records when hits exist; then call
   `register_manual_evidence` and rerun the complete search.
5. Inspect `get_collision_report`. For each potential/high candidate, either
   change the method or call `record_collision_resolution` with a detailed,
   component-specific distinction. Exact-identity collisions cannot be waived.
   Every resolution requires another complete search.
6. Accept protected research output only after `get_gate_status` is `PASS` and
   `researchctl.py verify --strict` succeeds.

## Method changes

Any change to the objective, mechanism, architecture, loss, data, training,
evaluation, contribution, or tracked method file invalidates the old report,
resolutions, and receipt. Register the complete changed method and repeat the
flow. An unchanged registration cannot clear a user-declared adjustment.

The live discipline profile and registry are part of the search-plan hash.
Any profile or evidence change invalidates the receipt and requires a complete rerun.

The prompt hook invalidates a live receipt as soon as it detects adjustment
language. File hooks cover declared `method_files`; untracked external changes
are outside the observation boundary and must not be claimed as detected.

## Evidence boundaries

- `COVERAGE_INCOMPLETE` means at least one required source was not successfully
  checked. A substitute source does not satisfy it.
- `COLLISION_REVIEW_REQUIRED` is a review obligation, not a plagiarism verdict.
- `PASS` means no unresolved collision was found under the recorded, hash-bound
  plan. It is not global proof of originality.
- Metadata search does not prove peer review, publication quality, or SCI/SSCI,
  CCF, CSSCI, IEEE, or Chinese core journal membership.
- Manual evidence is user-supplied official-source material bound by hash, not
  independently reproduced database access.

Use `list_sources` for official URLs and access constraints; see [source-policy.md](references/source-policy.md) for routing, manual evidence, and interpretation.
