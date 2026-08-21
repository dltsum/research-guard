---
name: research-design-guard
description: Evidence-bounded ideas, hypotheses, experiments, resource-aware task DAGs, frozen metrics, and validation-only optimization with human selection and mandatory novelty gates.
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

When the user explicitly authorizes finding directions, use the executable
`direction_action` workflow in
[direction-exploration-contract.md](references/direction-exploration-contract.md).
Plan first to freeze the redacted local resource snapshot; curate 5–15 unranked
candidates; and activate, coarse-test, and collision-check each current method
revision. Coarse evidence must be a managed reproducibility PASS and remains a
local pilot signal. A method/protocol/range/tracked-file change requires a new
revision and fresh coarse-test plus collision evidence. Finalize exactly five
eligible options for user selection; never rank or choose one.

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
For multi-stage, resource-sensitive work, inventory first and use the typed
`resource_plan_action` contract in
[RESOURCE_AWARE_TASK_PLANNING.md](../../docs/RESOURCE_AWARE_TASK_PLANNING.md).
The main agent selects each profile; execution stays serial and GPU-off. Do not
plan a whole-task deadline unless the user supplied it, and inspect a durable
receipt before resolving or replaying `unknown` completion.
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
