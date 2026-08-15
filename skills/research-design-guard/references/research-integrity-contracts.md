# Research integrity design subroutes

Load this reference only for preregistration, computational reproducibility,
or active-learning systematic reviews.

- `action=preregister`: freeze questions, hypotheses, outcomes, exclusions,
  sample-size basis, analysis, missingness, multiplicity, stopping, and seed
  policy. Only `selected_by=user` is admissible. Changes are new versioned
  preregistrations plus explicit deviation entries, never overwrites. Every
  deviation field must exist, and its `original` value must match the frozen
  protocol or the latest prior replacement for that field.
- `action=repro_plan`: freeze argv (never shell syntax), working directory,
  input hashes, declared outputs, parameters, seeds, environment, and expected
  checks. The plan also captures the current OS/architecture/Python fingerprint
  and command-executable SHA-256, and rechecks both before launch.
  `repro_execute` uses the shared RAM/Job Object guard. `repro_submit`
  cannot replace the frozen checks and must provide hash-verifiable stdout and
  stderr receipts. Exit code alone cannot PASS; output presence/hash and all
  independently recomputed declared checks must also pass. Even then, an
  externally submitted result is `REVIEW_REQUIRED`; only `repro_execute`
  running the frozen plan through the shared resource guard can return `PASS`.
  A managed run must use fresh versioned output paths. If any declared output
  already exists, execution fails before command launch; the guard never deletes
  or overwrites a user's prior result to manufacture a clean rerun.
- `action=review_rank`: prioritize unscreened records from explicit human
  include/exclude examples, requiring at least one of each class. The algorithm
  never assigns inclusion decisions; every scholarly record requires a
  clickable HTTPS primary URL.

Method changes invalidate all derived receipts. Resource-bounded reruns refuse
to start below the configured headroom and terminate only their owned process
tree at the low-water mark.
