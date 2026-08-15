---
name: paper-audit-guard
description: Fail-closed manuscript audit and optional active AI-reviewer adaptation with 2-3 roles, linked evidence, language receipts, five-way formula verification, OpenReview calibration, image integrity, and experiments. Use for paper writing, review, AI-reviewer score optimization, formulas, citations, images, or experiments.
---

# Paper Audit Guard

The main agent must choose 2-3 roles and explicit `audit_features` from the registered role catalog. Call `paper_audit action=plan` with those values, `selected_by=main_agent`, a rationale, manuscript/evidence paths, and effort at most `high`. The tool validates coverage and never chooses roles from keywords.

For ingestion, claim graphs, statistics, or record health, read [research-integrity-contracts.md](references/research-integrity-contracts.md).

Every literature item needs a clickable primary `https://` link. Verify current external facts online.

For citation formatting, use `citation_action=verify_format` with a DOI. Identity does not prove claim support.

When `claim_inventory=REQUIRED`, submit one `claim_evidence_items` record per `claim_id` for every citation, quantitative, comparative, and scope claim. Bind raw/code evidence at planning. Weak, contradictory, missing, ambiguous, or numerically mismatched support fails. `BLOCKED` requires UTF-8 source.

With files, complete `language_review`: preserve necessary uncertainty and disclosures; show limitation/ethics decisions to the user. Resolve exact venue/year/track/stage evidence before venue-specific structure or style. Never invent evidence or choose those user decisions.

If `lean_required`, keep one manuscript-wide `.lean` file, disable `autoImplicit`, mark every formula, register every parameter purpose/use, and forbid placeholders or illegal/unused/confusing parameters. Run `action=lean_check`, then `verification_action=cross_verify`. It must separately report Lean logic, Pint dimensions, SymPy algebra, Z3 SAT/UNSAT/UNKNOWN, and numerical protocol results. Admit each boundary/limit/overflow case under the frozen protocol before executing its hash-bound model.

For OpenReview use `review_action=calibrate`; retain official forum links/schema and never infer acceptance. For images use `image_action=audit`; bind originals, outputs, and transformations. Duplicate/metadata/pixel signals are not misconduct findings. Close every current flag through hash-bound `image_action=review` at original resolution before submission.

For AI-reviewer work, present two explicit choices. Robustness mode selects
`ai_reviewer_robustness`, sets `audit_features.ai_reviewer=true`, and calls
`review_action=ai_robustness`; its scores are sensitivity evidence only. Active
adaptation selects `ai_reviewer_optimization`, sets
`audit_features.ai_reviewer_optimization=true`, and follows the executable
plan/register/select/status sequence in
[ai-reviewer-optimization.md](references/ai-reviewer-optimization.md). It requires
`selected_by=user`, current official venue reviewer guidance, freshly verified
strategy studies, the same panel of at least two reviewer models for baseline and
every candidate, and robust score-aware selection. Do not describe active mode as
mere robustness. Both modes reject hidden prompt injection, fabricated prestige,
or loss of citations, numbers, formulas, limitations, ethics, risks, criticism,
and negative results. Neither score is an acceptance probability.

If experiments are required, bind raw results/code/config; audit provenance, seeds, recomputation, dead paths, and evaluation scope.

Submit role findings, numeric checks, claims, linked online/literature checks, and required experiment evidence. Completion requires `verify=PASS`; tracked edits invalidate receipts.

Use the complete writing and review matrix in
[../../docs/PAPER_WRITING_CAPABILITIES.md](../../docs/PAPER_WRITING_CAPABILITIES.md)
when the request covers drafting, revision, rebuttal, disclosure, Nature-accessible
prose, translation, venue formatting, figures, or final submission.
