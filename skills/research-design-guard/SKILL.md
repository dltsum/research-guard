---
name: research-design-guard
description: Evidence-bounded ideation, hypotheses, experiment design, power, and ablations with human selection and mandatory novelty gates. Use for research questions, mechanisms, studies, controls, or execution readiness.
---

# Research Design Guard

For field-specific work, the main agent must explicitly choose the discipline and broad domain. Call `research_design action=status discipline_action=analyze` with `discipline_selected_by=main_agent` and a rationale. Warn that a first field-knowledge build queries several official sources and may take minutes. Unknown fields return `INITIALIZATION_REQUIRED`; call `initialize` separately and never auto-download or substitute model memory/a neighboring field. Every literature lead needs a clickable `https://` evidence URL. Profile initialization or refresh requires explicit domain rebinding and a complete novelty rerun.

Before ideation, call `plan_ideation`. Use its 2-3 lenses and fixed problem anchor. Each candidate needs a mechanism, falsifier, minimum experiment, differentiator, feasibility, and linked prior work.

For domain Skills, provenance, artifacts, or proposal-only evolution, read [extended-research-contracts.md](references/extended-research-contracts.md). Never execute third-party Skills or apply proposals.

For preregistration, bounded reproduction, or review prioritization, read [research-integrity-contracts.md](references/research-integrity-contracts.md). Preserve human decisions; exit status alone never proves reproducibility.

Call `register_candidates`; preserve user order and never select. Commit only the user's choice with `selected_by=user`.

Commitment returns `NOVELTY_CHECK_REQUIRED`. Every method change invalidates the receipt and requires another full collision search.

For strategy, risk, parameters, decision trees, adversity, or inversion, call `plan_strategy` after commitment and use only its 2-3 modules. Register the user's objective, evidenced assumptions, parameter states, criterion-bearing branches, fallbacks, and linked inversions. Never invent probabilities, weights, thresholds, ranks, or preferences.

Present every branch. Record only the user's explicit choice. A method-changing branch immediately invalidates novelty.

Call `register_hypothesis`; separate observation, evidence, hypothesis, rivals, predictions, falsifiers, and operationalization.

Before execution, call `register_experiment`. Declare units, independence, assignment, controls, estimand, power basis, missingness, multiplicity, stopping, interpretations, run order, ablations, and ethics/feasibility. Never invent sample sizes or effects.

Use `paper_audit` and one manuscript-wide Lean file for formulas. Do not call a design ready until `research_design action=verify` returns `PASS`.
