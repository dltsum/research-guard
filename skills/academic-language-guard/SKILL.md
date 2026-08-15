---
name: academic-language-guard
description: Evidence-bounded academic writing, translation, and conference review with user-decided limitation/ethics checklists, deterministic fidelity contracts, defensive-writing safeguards, and source-linked rhetorical cards. Use when writing, translating, revising, polishing, configuring a conference manuscript, or auditing scholarly prose.
---

# Academic Language Guard

Use the research-guard `language_assist` tool. This Skill improves how an argument is expressed; it does not own novelty, citations, formulas, experiments, or scientific acceptance.

For conference writing, outlines, chapter names, layout, formatting, or narrative advice, first call `language_assist` with `venue_action=resolve` and the exact venue, year, track, and stage. If the result is `ONLINE_ACQUISITION_REQUIRED`, do the returned live searches, download the exact official policy/template and award-paper evidence, then call `venue_action=register`; do not substitute a nearby year or invent a structure. Hard rules come only from official policy/template evidence. Paper headings and narrative cards remain source-located observations, and a single exemplar is never a venue-wide norm. Every returned source and paper keeps its clickable `https://` links.

The bundled CCF seventh-edition catalog contains all A and B conferences across all ten official categories. Use it only to identify and route venues. A CCF A/B label is not current author guidance and never authorizes chapter names, layout, formatting, or narrative without exact venue/year/track/stage evidence.

Then start with `action=plan`. Pass UTF-8 manuscript paths whenever available; otherwise pass the exact draft text. Bind existing paper-audit `claim_ids`. Register any phrase whose uncertainty or scope is evidence-required in `protected_spans`, with a concrete reason. Use `task_mode=translation` with exact source and target text. For new conference drafting, pass the verified `venue_receipt_sha256`; a free-form contract cannot authorize chapter/layout/narrative choices. Read [review-contracts.md](references/review-contracts.md) for either mode or whenever a checklist appears.

Run `action=analyze`. Treat the returned categories differently:

- Preserve protected epistemic qualifiers and disclosures. Present material limitations and potential ethics omissions as the returned checklist; only the user may choose an outcome.
- Resolve repeated hedge stacks, imagined-critic disclaimers, disclaimer-first framing, generic throat-clearing, and internal process narration.
- Treat AI-like/style signals only as textual revision candidates, never proof of authorship.
- Never strengthen a scientific claim merely to sound confident. If a rewrite could alter meaning, edit the manuscript, then plan and analyze again.

For argument help, use `action=retrieve` with section, paragraph role, discipline, venue, and evidence type when known. Retrieve only 2-4 rhetorical cards. Every card must retain its clickable `https://` source link. Reuse the structural move, evidence placement, transition relation, or boundary placement; do not copy source wording or perform synonym substitution.

When importing an exemplar, use `action=register_card`. Store a structured rhetorical description and source locator, not a full paragraph, paper body, or prose template. A short verification excerpt may be used only within the tool's limit.

If blockers remain, either revise the tracked text and replan or use `action=resolve` to retain a finding with a substantive justification. Submit checklist choices through `decisions`, always with `selected_by=user`. Edit-required choices cannot be waived; edit the tracked text and replan.

Finish with `action=finalize`, then `action=verify`. Do not state that language review or paper audit passed without a current `PASS` receipt. Any manuscript change or receipt tampering invalidates PASS. Literature and exemplar outputs must always include clickable `https://` hyperlinks.
