---
name: research-design-guard
description: Evidence-bounded instruction adherence, research design, resource DAGs, frozen metrics, human selection, and novelty gates.
---

# Research Design Guard

For multistep work, call `instruction_action=register` before mutation. The main agent supplies requirements, acceptance criteria, dependencies, evidence, prohibitions, and rationale; classifiers cannot. Record evidence-bearing changes and call `verify` before completion. Receipt drift invalidates PASS; only a hash-bound explicit user choice may waive a requirement.

The main agent explicitly selects discipline and domain with a rationale. Unknown fields return `INITIALIZATION_REQUIRED`; initialize separately and warn that first use may be slow. Never substitute a classifier or neighboring field. Every literature lead needs a clickable `https://` evidence URL, and profile changes require rebinding plus a full novelty rerun.

Call `plan_ideation` with its fixed problem anchor and 2-3 lenses. Each candidate needs a mechanism, falsifier, minimum experiment, differentiator, feasibility, and linked prior work. Preserve order; commit only the user's choice. Commitment returns `NOVELTY_CHECK_REQUIRED`.

Direction finding requires explicit user authorization and the [direction contract](references/direction-exploration-contract.md): freeze a redacted resource snapshot, coarse-test and collision-check each current revision, then present exactly five unranked eligible choices. Any method, protocol, range, or tracked-file change requires fresh evidence.

For risk, parameters, decisions, adversity, or inversion, call `plan_strategy`; use 2-3 main-agent-selected modules, evidenced assumptions, criterion-bearing branches, fallbacks, and user choices. Never invent probabilities, weights, thresholds, ranks, or preferences.

Register hypotheses with evidence separated from rivals, predictions, falsifiers, and operationalizations. Register experiments with units, independence, assignment, controls, estimand, power basis, missingness, multiplicity, stopping, interpretations, run order, ablations, and ethics. Never invent sample sizes or effects.

Use the [metrics](references/experiment-metrics-contract.md), [resource](../../docs/RESOURCE_AWARE_TASK_PLANNING.md), [delegation](../../docs/SUBAGENT_DELEGATION.md), [extended research](references/extended-research-contracts.md), and [integrity](references/research-integrity-contracts.md) contracts when triggered. Resource execution is serial and GPU-off; no whole-task deadline exists unless the user sets one. External LLM work defaults to one native low-effort entry/economy subagent, otherwise local main-agent work.

Every method-changing branch invalidates novelty evidence. Use `paper_audit` for manuscripts/formulas. A design is ready only when `research_design action=verify` returns `PASS`.
