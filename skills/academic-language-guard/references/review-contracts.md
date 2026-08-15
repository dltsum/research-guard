# Review contracts

## Decision boundary

`material_limitation` and `potential_ethics_omission` are checklist items. Show each question, excerpt, and allowed choices to the user. Never select for the user. `revise_preserving_substance`, `omit_with_justification`, and `add_disclosure` require an actual edit and a new plan. `already_disclosed_at_locator` requires a locator. A potential omission is a review candidate, not a finding of misconduct or proof that an omission exists.

## Translation boundary

Use `task_mode=translation` with exact `source_text`, `draft_text`, source and target languages, plus a terminology ledger when needed. Re-analysis must provide both source and target. The deterministic contract compares numbers, percentages, citation tokens, HTTPS URLs, code identifiers, LaTeX references, registered terms, epistemic qualifiers, material limitations, negation, and explicit causal markers. A PASS on these invariants is not a complete semantic-equivalence proof; read the source and target for subject, scope, logical direction, and technical meaning.

## Conference boundary

Before new conference drafting, resolve an exact venue-year-track-stage profile through `venue_action=resolve`. A PASS binds local official policy/template assets, award-paper records, paper files, observations, and links by hash. A missing or damaged profile returns `ONLINE_ACQUISITION_REQUIRED`: perform the listed online acquisition and register project-local evidence before writing. Never fall back to another year/stage.

Official policy and template evidence alone may impose layout, page, format, or required-section rules. High-quality papers may supply only their own observed heading sequence and source-located narrative moves. Do not convert a single paper into a venue norm or copy its prose. A legacy free-form official contract is retained only for auditing an already supplied structured manuscript; it cannot authorize a new outline, chapter name, layout, or narrative. The document check covers source-registered required sections, undefined LaTeX references, and missing figure/table captions or labels; formal math, numeric truth, citations, experiments, and current venue compliance remain paper-audit responsibilities.

## Style boundary

Textual patterns are revision candidates, never evidence of AI authorship. Do not use fixed sentence/paragraph lengths, blanket active/passive conversion, thesaurus substitution, personality injection, deliberate errors, or venue-independent page rules. Preserve citation keys, formulas, numbers, qualifiers, limitations, disclosures, technical identifiers, and the author's defensible voice.
