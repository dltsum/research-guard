---
name: paper-audit-guard
description: Evidence-bounded manuscript audit and optional active AI-reviewer adaptation with linked citations, language, equations, numbers, figures, code, experiments, and OpenReview calibration.
---

# Paper Audit Guard

Read the manuscript and perform the requested work directly. Use
`paper_audit action=plan` when a structured audit is useful. Choose roles and
effort for the actual task; there is no fixed role count, effort ceiling,
mandatory registration, or hash/receipt prerequisite for writing or editing.
Use clickable primary sources and distinguish verified venue rules from
formatting context supplied by the user.

For claim audits, inspect the current manuscript and its actual evidence.
Check quantitative values, citation correspondence, experimental provenance,
and contradictory evidence. Existing files need no advance registration.
An explicit new submission rereads the current manuscript; unchanged claim
locations keep useful IDs so corrected evidence can be submitted in the same plan.

Explicit role `status`/`verdict` require `PASS`; `passed` requires JSON `true`.
Nonapproval or contradictory outcomes block submission and revoke old PASS on
status/verify. Legacy omissions remain supported; findings do not prove semantics
or independent execution.

For a paper main line or title, use `language_assist spine_action=plan` if it
helps connect observations, mechanisms, predictions, falsifiers and candidate
titles. Preserve the user's outline. For prose, use `language_review` as useful;
preserve scientific uncertainty, limitations, disclosures and negative findings.
Checklist suggestions are advisory, and reviewer actions keep their actual actor.
When reference-based writing is requested, preserve the reference's functional
logic and deliver the requested draft, layout, correspondence analysis and
verification materials. Retain the three actual agent audits of logic matching,
defensive writing and scientific validity, together with their dialogue and fixes.

For requested equation checks, use an available compatible local Lean runtime
and actually compile the supplied source. Report Lean logic, Pint dimensions,
SymPy equivalence, Z3 satisfiability, and numerical/protocol legality
separately; define and use every parameter. Constructive values require legal
marginal intervals plus jointly feasible anchors, never an unverified Cartesian
product.

Use `review_action=calibrate` for current OpenReview records without predicting
acceptance. Figure audits inspect the actual reference and output at final size:
content, style, occlusion, spacing, alignment, labels, uncertainty and accessibility.
For reference-guided illustrations, preserve all requested information and retain
three actual agent reviews per round: information completeness, style matching
and visual details. Deliver the seven requested artifact classes and trace.
Optional `ai_optimize_*` is user-selected only: it may improve
truthful framing/navigation/language, never manipulate reviewers, fabricate
prestige, alter numbers/citations/formulas, or delete limitations.

For code and experiments, inspect configuration, seeds, raw results, recomputation,
controls, missingness, and scope. Status reads recorded results; ordinary edits
do not invalidate them. Explicitly rerun affected checks to evaluate new content,
and report execution scope truthfully. No digest, signature or cross-receipt
chain is required. Read the detailed contracts in
`docs/PAPER_WRITING_CAPABILITIES.md` and `references/` before specialized work.
