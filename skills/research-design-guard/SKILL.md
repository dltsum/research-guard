---
name: research-design-guard
description: Evidence-bounded ideas, hypotheses, experiments, frozen metrics, and validation-only optimization with human selection and mandatory novelty gates.
---

# Research Design Guard

The main agent explicitly selects the discipline and broad domain. Call
`discipline_action=analyze` with `discipline_selected_by=main_agent` and a
rationale. Warn that first-use live initialization may take minutes. An unknown
field returns `INITIALIZATION_REQUIRED`; call `initialize` separately. Never
substitute a classifier, model memory, or neighboring field. Every literature
lead needs a clickable `https://` evidence URL. Profile changes require domain
rebinding and a complete novelty rerun.

Call `plan_ideation`; use its 2–3 lenses and fixed problem anchor. Every
candidate needs a mechanism, falsifier, minimum experiment, differentiator,
feasibility, and linked prior work. `register_candidates` preserves user order
and never selects. Commit only the user's choice with `selected_by=user`.

Commitment returns `NOVELTY_CHECK_REQUIRED`. Every method-changing strategy
branch invalidates the receipt and forces a full collision rerun.

For risk, parameters, decisions, adversity, or inversion, call `plan_strategy`
and use only its 2–3 modules. Register objectives, evidenced assumptions,
parameter states, criterion-bearing branches, fallbacks, and linked inversions.
Never invent probabilities, weights, thresholds, ranks, or preferences. Present
every branch and record only the user's explicit choice.

Register a hypothesis with observations/evidence separated from rivals,
predictions, falsifiers, and operationalizations. Then `register_experiment`
with units, independence, assignment, controls, estimand, power basis,
missingness, multiplicity, stopping, interpretations, run order, ablations, and
ethics/feasibility. Never invent sample sizes or effects.

For metric analysis and optimization, read
[experiment-metrics-contract.md](references/experiment-metrics-contract.md).
Before any work that would otherwise call an external LLM API, use the
`delegation_action` contract in
[SUBAGENT_DELEGATION.md](../../docs/SUBAGENT_DELEGATION.md): one native
entry/economy subagent at low effort by default, otherwise main-agent local
fallback. External APIs require a user-selected or protocol-required exception.
For domain Skills/artifacts/evolution read
[extended-research-contracts.md](references/extended-research-contracts.md);
for preregistration/reproduction/review prioritization read
[research-integrity-contracts.md](references/research-integrity-contracts.md).

Use `paper_audit` and one manuscript-wide Lean file for formulas. A design is
ready only when `research_design action=verify` returns `PASS`.
