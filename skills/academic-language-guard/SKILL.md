---
name: academic-language-guard
description: Evidence-bounded academic writing, translation, conference prose, and user-controlled limitation/ethics checklists with source-linked rhetorical guidance.
---

# Academic Language Guard

Use `language_assist action=plan` with manuscript text/paths, task mode, and
existing paper-audit claim IDs. Register evidence-sensitive phrases in
`protected_spans`; use exact source and target text for translation. For
conference structure, headings, layout, or style, resolve the exact venue,
year, track, and stage first. If official evidence is missing, return
`ONLINE_ACQUISITION_REQUIRED`, obtain the current policy/template, then
register it. Every returned paper/source keeps a clickable `https://` link.

Run `action=analyze`, preserve uncertainty, disclosures, negative findings,
limitations, and potential-ethics checklists, and let the user choose checklist
outcomes. Remove hedge stacks, imagined critics, disclaimer-first framing,
generic throat-clearing, and process narration without strengthening claims.
“Remove AI traces” means precise prose cleanup—not detector evasion, hidden AI
use, synonym spinning, or deliberate errors. Nature-like prose is a profile
(clear concepts, direct evidence, limited jargon), never invented Nature format.

For a paper line, question, or title, call `spine_action=plan` first. Preserve
the local observation, elevate it to a macro problem, name one mechanism,
require cross-context predictions/falsifiers, and return five unranked
macro/meso/local candidates. Bind collision only after the exact method search;
nearby work sharpens the mechanism rather than forcing a smaller question.

For rhetorical help, call `action=retrieve` and keep only 2–4 structured cards
with source locators; reuse moves, not wording. Register exemplars with
`action=register_card`, never full paragraphs. For user-selected active
AI-reviewer adaptation, register complete candidates through
`paper_audit review_action=ai_optimize_register`; preserve evidence and
uncertainty. Finish `action=finalize` then `action=verify`; any manuscript or
receipt change requires replanning. See `docs/PAPER_WRITING_CAPABILITIES.md`.
