---
name: paper-audit-guard
description: Evidence-bounded manuscript audit and optional active AI-reviewer adaptation with linked citations, language, equations, numbers, figures, code, experiments, and OpenReview calibration.
---

# Paper Audit Guard

Use `paper_audit action=plan` for writing, review, or audit. The main agent
chooses 2–3 registered roles, explicit `audit_features`, rationale, files, and
effort no higher than `high`; keyword routing cannot choose them. Every
literature result needs a clickable primary `https://` link. Current venue
structure/style requires exact official venue/year/track/stage evidence.

With claims, register one `claim_evidence_items` record per claim and bind raw,
code, numeric, and online evidence. Missing, weak, contradictory, or changed
evidence prevents PASS. Every method revision invalidates the old collision
receipt and triggers a complete strict novelty search before the revision is
accepted; a nearby paper prompts mechanism differentiation, not automatic
narrowing.

For a paper main line or title, call `language_assist spine_action=plan` first:
lift a local observation to a macro problem, one unifying mechanism, two
cross-context predictions, falsifiers, and five unranked macro/meso/local titles.
The user chooses the final framing. For prose, call `language_review`; preserve
uncertainty, limitations, ethics, negative findings, and user-owned checklists.

For equations, use one manuscript-wide Lean file with `autoImplicit` disabled,
then `verification_action=cross_verify`. Report Lean logic, Pint dimensions,
SymPy equivalence, Z3 satisfiability, and numerical/protocol legality
separately; define and use every parameter. Constructive values require legal
marginal intervals plus jointly feasible anchors, never an unverified Cartesian
product.

Use `review_action=calibrate` for current OpenReview records without predicting
acceptance. Figure audits bind source/output/transformation hashes and inspect
final-size occlusion, spacing, alignment, labels, uncertainty, accessibility,
and venue style. Optional `ai_optimize_*` is user-selected only: it may improve
truthful framing/navigation/language, never manipulate reviewers, fabricate
prestige, alter numbers/citations/formulas, or delete limitations.

For code and experiments, bind configuration, seeds, raw results, recomputation,
controls, missingness, and scope. Finish with `action=verify`; tracked edits
invalidate receipts. Read the detailed contracts in
`docs/PAPER_WRITING_CAPABILITIES.md` and `references/` before specialized work.
