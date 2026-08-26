---
name: paper-audit-guard
description: Fail-closed manuscript audit and optional active AI-reviewer adaptation with 2-3 roles, linked evidence, language receipts, five-way formula verification, constructive numerical intervals and joint anchors, OpenReview calibration, image integrity, and experiments. Use for paper writing, review, AI-reviewer score optimization, formulas, legal parameter values, citations, images, or experiments.
---

# Paper Audit Guard

The main agent chooses 2-3 registered roles and explicit `audit_features`; keyword routing is forbidden. Call `paper_audit action=plan` with `selected_by=main_agent`, a rationale, manuscript/evidence paths, and effort no higher than `high`.

Every literature result needs a clickable primary `https://` link and current external facts require online verification. DOI identity does not prove claim support. When `claim_inventory=REQUIRED`, submit one `claim_evidence_items` record per claim and bind raw/code evidence during planning; missing, weak, contradictory, ambiguous, or numerically mismatched support fails closed.

With manuscript files, complete `language_review`, preserve necessary uncertainty and disclosures, and present limitations/ethics choices to the user. Resolve exact venue/year/track/stage evidence before venue-specific structure or style.

When writing the paper's main line or suggesting titles, invoke the
`language_assist` `spine_action` subroute before drafting sections. It requires
an explicit macro problem, a unifying method/mechanism, at least two
cross-context predictions, falsifiers, source-linked evidence planning, and
five unranked titles at macro/meso/local levels. A narrow local observation is
an evidence-bearing case, not the contribution ceiling. Bind the canonical
collision receipt after the method is formed; a nearby collision triggers
mechanism differentiation or a higher-level framing, never automatic retreat.
Every method revision still requires a fresh strict collision search, and the
user chooses the title.

If `lean_required`, use one manuscript-wide `.lean` file, disable `autoImplicit`, mark every formula, register every parameter purpose/use, and reject placeholders or illegal, unused, or confusing parameters. Run `action=lean_check`, then `verification_action=cross_verify`; report Lean, Pint, SymPy, Z3, and protocol-admitted numerical results separately.

For constructive values, select `methodology_statistics` or `formal_math_lean`, set `constructive_numerical=true`, and call `numerical_action=construct`. Supply source-located variables, units, bounds, purposes, and structured constraints. Distinguish marginal legal intervals from jointly feasible anchors; every anchor must satisfy all types, relations, bounds, and binary64 checks.

Use `review_action=calibrate` for OpenReview without predicting acceptance. Image audits bind originals, outputs, and transformations; signals are not misconduct findings and require hash-bound human review. AI-reviewer robustness measures sensitivity. Optional active adaptation follows [ai-reviewer-optimization.md](references/ai-reviewer-optimization.md), rejects manipulation, preserves all evidence and disclosures, and never treats scores as acceptance probabilities. Reviewer-model work first calls `research_design delegation_action=plan`.

For experiments, bind raw results, code, configuration, seeds, recomputation, dead paths, and scope. Submit all role, claim, numeric, online, literature, and experiment evidence; completion requires `verify=PASS`, and tracked edits invalidate receipts. See [research-integrity-contracts.md](references/research-integrity-contracts.md) and the [writing matrix](../../docs/PAPER_WRITING_CAPABILITIES.md) for full procedures.
