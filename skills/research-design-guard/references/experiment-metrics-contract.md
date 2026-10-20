# Experiment metric contract

Before viewing results, call `research_design` with `action=status` and
`metrics_action=plan`.
Freeze metric roles, directions, units, estimands, aggregation, legal ranges,
missingness, optimization/final-test splits, candidate budget, and the selection
boundary. The plan is bound to current method and experiment hashes.

`metrics_action=analyze` accepts only project-local UTF-8 CSV data at
independent-run level. It rejects duplicate run identifiers, missing or
non-finite values, protocol-illegal values, missing required columns, and excess
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

`metrics_action=verify` checks current method/experiment and stored record hashes,
then reopens every analyzed project-local CSV and compares its actual bytes with
the analysis receipt. Missing, changed or out-of-project data cannot receive an
integrity PASS. Optimization repeats this data check for the chosen analysis
before consuming its saved summaries or writing a new optimization receipt.
These checks do not silently update hashes or rerun an analysis. An explicit
new analysis is required to bind intentionally changed data. Plain `status`
reports the current plan and record counts without claiming a fresh data audit.
