# Research integrity routes

Use `research_design action=status` and select `integrity_action` when one of
these tasks is useful. The instruction ledger and preregistration routes are
optional study tools, not prerequisites for answering or editing files.

- `preregister` records a protocol the user actually chose. `record_deviation`
  keeps the original protocol and explains what changed, why, and whether the
  relevant results had already been seen. Do not label a retrospective decision
  as prospective.
- `repro_plan` records the actual command, input/output paths and any useful
  parameters, seeds or expected checks. Those details may be updated in place.
  No input hashes, executable fingerprint or receipt registration is required.
- `repro_execute` launches the command and reports its actual exit status,
  declared output existence and requested content checks. Reuse the output
  directory when rerunning; logs retain earlier execution history. The memory
  and timeout limits apply to the spawned process tree; parent RSS is observed.
- `repro_submit` records an externally supplied result as `REVIEW_REQUIRED`.
  That record does not assert the tool ran the experiment. A managed execution
  can report `PASS` only after the actual command and declared checks succeed.
- `review_rank` prioritizes unscreened records from genuine human include and
  exclude examples. It does not create human screening decisions.
- `status` reads the saved result. To obtain a new result after a source edit,
  explicitly execute the task again; the saved status is not a fresh execution.

Keep source observations and interpretations distinct. A record can be
corrected without an append-only or digest-seal ceremony.
