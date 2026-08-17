# Experiment metric contract

Before viewing results, call `research_design` with `action=status` and
`metrics_action=plan`.
Freeze metric roles, directions, units, estimands, aggregation, legal ranges,
missingness, optimization/final-test splits, candidate budget, and the selection
boundary. The plan is bound to current method and experiment hashes.

`metrics_action=analyze` accepts only project-local UTF-8 CSV data at
independent-run level. It rejects duplicate run identifiers, missing or
non-finite values, protocol-illegal values, undeclared columns, and excess
candidates. Its baseline differences are descriptive, not causal or
significance claims. Keep final-test data in a separate sealed artifact: the
optimization analyzer rejects any row labeled with the frozen final-test split.

Participant-level, clustered, longitudinal, complex-survey/weighted,
psychometric/IRT, and qualitative data require a registered specialist
analysis. Never aggregate or flatten those records merely to enter the core
engine.

`metrics_action=optimize` compares only observed candidates on the frozen
optimization split. Apply declared constraints and report the feasible set and
Pareto frontier. Never use final-test summaries for tuning, ranking, or
selection. Scalar ranking requires complete user-supplied weights and reference
scales with `optimization_selected_by=user`; it still returns
`USER_SELECTION_REQUIRED` and never executes an experiment.
