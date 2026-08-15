# P13 release-final verification

Date: 2026-08-14

## Capability contract

- `paper_audit lean_check` keeps exactly one manuscript-wide Lean file and
  rejects placeholders plus illegal, unused, or confusing parameters.
- `paper_audit verification_action=cross_verify` returns five independent records: `lean`,
  `dimensional` (Pint), `symbolic` (SymPy), `constraints` (Z3), and
  `numerical_protocol` (hash-bound project Python model). A required FAIL or
  UNKNOWN blocks paper submission. SymPy expressions and Z3/protocol
  constraints use restricted syntax rather than Python evaluation.
- Numerical cases cover boundary, limit, overflow, and non-finite behavior.
  Parameter type, range, allowed-value, and structured combination constraints
  are checked against the frozen manuscript protocol before model execution.
- OpenReview calibration accepts public official API v2 records or a hash-bound
  test fixture, preserves forum URLs and review schemas, and explicitly cannot
  predict acceptance. Fixture-only evidence cannot close a formal paper audit.
- Scientific-image integrity binds originals, processed files, transformations,
  metadata, pixel statistics, and image/region hashes. Automatic signals return
  expert-review evidence, never a conclusion of fabrication or fraud.
- The router still selects at most three modules/roles and effort remains capped
  at `high`. The MCP surface remains 15 top-level tools.

## Dependency and resource boundary

Pint 0.25.3, SymPy 1.14.0, and z3-solver 5.0.0.0 are included in the offline
Python 3.14.3 core payload. Lean 4.33.0/Mathlib v4.33.0 and TeX remain explicit
first-load selections. All work remains serial and CPU-only under the 512 MiB
aggregate task-owned working-set policy.

## SkillOpt

Four independent bounded Optuna/TPE rounds, 12 trials each, optimized only
formula/image/paper routing priorities. The five result channels, protocol
legality, OpenReview conclusion boundary, image conclusion boundary, role
budget, and resource policy were not optimization parameters. A first rejected
run exposed a Z3 false positive and a mixed-intent miss; the implementation was
corrected and all four final rounds passed. Evidence is under
`evals/p13-skillopt/` and is excluded from release archives.

## Final verification

- Clean whole-plugin suite: 68/68 test files PASS with zero resumed files.
- The final invalidation-focused rerun also passed 68/68 with zero resumed;
  replacing an expert-reviewed image now invalidates the parent paper audit.
- Real Lean cold retry: 6/6 tests PASS in 298.144 seconds; peak owned working
  set 455,766,016 bytes, 304 successful trims, zero trim failures.
- Repository validation: PASS with the exact 512 MiB serial/no-GPU policy.
- Active/mirror comparison: 214/214 release-source files, zero path or SHA-256
  differences after excluding development/evaluation/build evidence.
- Isolated modular install: PASS; traditional Skill and plugin registered in a
  temporary user root; 15 MCP tools at version 0.5.0; first-load selection
  remained pending; bundled Pint 0.25.3, SymPy 1.14.0, and Z3 5.0.0 imported.
- Temporary isolated installation and dependency-build staging were deleted
  after verification.
