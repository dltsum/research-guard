# P12 SkillOpt report

Date: 2026-08-14
Status: PASS

## Scope

The optimization covers only two bounded configuration surfaces:

- intent priorities for the overlapping `structured_evidence` and
  `research_integrity` routes;
- smoothing and prior weight for the human-only systematic-review prioritizer.

The method-change overlay, full collision-family requirement, maximum of three
modules, human-only inclusion decisions, source links, exact locators, and all
other hard gates were frozen and were not optimization variables.

## Execution

Four serial rounds used Optuna TPE with 18 trials per round. Each round froze
train, validation, and held-out routing cases plus a separate held-out
active-review ordering case. Prompt cost was estimated from selected runtime
instructions.

Every candidate configuration was written to a separate file, SHA-256 bound
through environment variables, and used by each P12 test worker. A candidate
could update the active configuration only after:

1. objective was no worse than the current accepted baseline;
2. every train, validation, and held-out routing case passed;
3. the held-out review ordering passed;
4. every P12 test file passed under that candidate hash.

## Results

| Round | Candidate result | Regression | Decision |
|---:|---|---|---|
| 1 | below accepted baseline | PASS | rejected |
| 2 | below accepted baseline | PASS | rejected |
| 3 | equal to accepted baseline | PASS | accepted |
| 4 | below accepted baseline | PASS | rejected |

Rejected rounds are successful negative evidence, not a failed optimization
run. The report gate requires every round to be evaluated consistently, every
candidate to receive its own regression, all hard cases to pass, and the final
accepted objective to be at least the original baseline.

- Initial objective for this final rerun: `1.593371428332024`
- Final accepted objective: `1.593371428332024`
- Selected routing priorities:
  - `structured_evidence = 98`
  - `research_integrity = 86`
- Selected active-review parameters:
  - `smoothing = 0.2548600047366858`
  - `prior_weight = 0.26137691640156624`
- Accepted round: 3
- Rejected rounds: 1, 2, and 4
- Per-round candidate regression: PASS for all four rounds

This final rerun started from the configuration selected by the preceding
four-round development run. It therefore confirms non-degradation rather than
claiming a second improvement: 72 trials were evaluated, each round ran its own
P12 regression, and no lower-scoring candidate replaced the accepted baseline.

The machine-readable report and per-test receipts are local evaluation
artifacts under `evals/` and are excluded from the Git repository. This
summary exposes the reproducible configuration and admission logic without
publishing machine-specific logs.
