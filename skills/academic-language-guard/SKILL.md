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

For a Nature-accessible prose request, use the official general writing principles:
explain concepts before specialist shorthand, reduce avoidable jargon and acronyms,
write direct evidence-led sentences, and keep titles informative to adjacent fields.
This is a prose profile, not a universal Nature format. Resolve the exact Nature
journal/article type and its current author instructions before deciding structure,
length, layout, figures, or files. Do not remove critical findings, limitations,
ethics, uncertainty, or negative results to sound more confident.

“Remove AI traces” means revise high-precision textual artifacts such as chat residue,
template throat-clearing, vague promotion, and mechanical process narration. Never
claim authorship detection, optimize against an AI detector, hide reportable AI use,
force sentence-length variation, perform synonym spinning, or introduce errors.

For argument help, first use `spine_action=plan` when the user is asking for a
paper main line, research question, or title. The plan is deliberately
macro-first: preserve the local observation, elevate it to a problem that
matters beyond the named case, name one unifying method or mechanism, and
require cross-context predictions and falsifiers. Register the resulting
`spine` with `spine_action=register` and return five unranked title candidates
across macro, meso, and local levels. Do not silently narrow the question merely
because a nearby paper exists. Use `spine_action=bind_collision` only after the
exact method revision has completed the canonical strict novelty search; this
keeps collision evidence as a differentiation check rather than the objective
of idea generation. The user owns the final framing choice.

For rhetorical cards, use `action=retrieve` with section, paragraph role,
discipline, venue, and evidence type when known. Retrieve only 2-4 rhetorical
cards. Every card must retain its clickable `https://` source link. Reuse the
structural move, evidence placement, transition relation, or boundary placement;
do not copy source wording or perform synonym substitution.

When importing an exemplar, use `action=register_card`. Store a structured rhetorical description and source locator, not a full paragraph, paper body, or prose template. A short verification excerpt may be used only within the tool's limit.

If blockers remain, either revise the tracked text and replan or use `action=resolve` to retain a finding with a substantive justification. Submit checklist choices through `decisions`, always with `selected_by=user`. Edit-required choices cannot be waived; edit the tracked text and replan.

Finish with `action=finalize`, then `action=verify`. Do not state that language review or paper audit passed without a current `PASS` receipt. Any manuscript change or receipt tampering invalidates PASS. Literature and exemplar outputs must always include clickable `https://` hyperlinks.

If the user explicitly chooses active AI-reviewer adaptation, language assistance
may generate separate evidence-framing, novelty-stance, scope, title, navigation,
or polish candidates. Do not choose among them from prose intuition alone. Register
complete candidates through `paper_audit review_action=ai_optimize_register`, use
the same hash-bound multi-model reviewer panel, and let the executable selector
rank them. Candidate generation must retain protected uncertainty and disclosures.

For the full manuscript lifecycle, rebuttal, reviewer interfaces, optional active
AI-reviewer adaptation, robustness, figures, formulas, and explicit boundaries, read
[../../docs/PAPER_WRITING_CAPABILITIES.md](../../docs/PAPER_WRITING_CAPABILITIES.md).
