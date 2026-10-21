# Experiment metrics

Use `research_design action=status` with `metrics_action=plan` to define the
metrics needed for the study. State units, direction, aggregation, independent
units, missingness and the optimization/test boundary before using outcomes to
make decisions. No method, experiment or file digest needs to be supplied.

`metrics_action=analyze` reads the supplied project-local CSV and computes a new
analysis. Duplicate run identifiers, nonfinite numbers and missing required
data are actual input errors. Respect clustered/longitudinal data rather than
pretending repeated observations are independent runs. Differences from the
baseline are descriptive unless the study supports a stronger interpretation.

`metrics_action=optimize` compares the recorded candidates using declared
constraints and reports feasible choices and the Pareto frontier. Preserve
the final-test boundary: do not tune on held-out outcomes. User-supplied
weights and scales can express a user's preference without inventing it.

`status` and the compatibility alias `verify` read recorded summaries. They do
not reopen every data file or silently recompute an analysis. To use edited data,
call `analyze` again with the same analysis ID and path. There is no hash-refresh,
new-directory or registration requirement for an ordinary edit.
