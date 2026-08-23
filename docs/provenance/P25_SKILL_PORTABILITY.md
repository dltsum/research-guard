<!-- research-guard-doc-pair: p25-skill-portability | revision: 2026-08-23.1 -->
# P25 Skill portability verification

## Scope and frozen decision

P25 closes one narrow evidence gap: P24 evaluates one exact Skill artifact on
one frozen target but intentionally cannot establish transfer to another model,
harness, or task. P25 adds an optional target-cell evidence matrix under the
existing `research_design` owner. It triggers only for a portability claim and
does not add a top-level MCP tool, classifier, model, executor, installer,
admission authority, or apply path.

The frozen decision is to reuse the finalized P24 identity and metric contract;
freeze 2–12 explicit target cells and exactly 2 or 3 paired replicates; prohibit
P24 train/validation/heldout case reuse; retain per-cell outcomes; expose
executor/evidence-family dependence; and forbid universal extrapolation. The
core only records bounded external JSON artifacts and does not execute third-
party code or models.

## Current primary sources and implementation snapshots

Current primary records were inspected on 2026-08-23:

- [SkillLens](https://arxiv.org/abs/2605.23899) motivates target-consumption
  testing and explicit negative-transfer outcomes.
- [SkillOpt](https://arxiv.org/abs/2605.23904) motivates frozen target model and
  harness identities plus comparison of one unchanged artifact.
- [Workflow-Localized Mechanism Learning](https://arxiv.org/abs/2607.20999)
  motivates scoped nearby-workflow transfer tests.
- [SkillRise](https://arxiv.org/abs/2607.26784) and
  [ReuseRL](https://arxiv.org/abs/2605.31509) motivate cross-task reuse questions,
  not automatic evidence for an untested target.

Anonymous public GitHub metadata pinned these MIT repositories:

| Repository | Immutable commit | Decision |
|---|---|---|
| [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt/tree/bdfdc30a8e17309c06cdbe8449f01bdecc120203) | `bdfdc30a8e17309c06cdbe8449f01bdecc120203` | method source; no runtime dependency |
| [microsoft/SkillLens](https://github.com/microsoft/SkillLens/tree/c5ee10f6b566cd2ccf96f7cef115eba59606b01b) | `c5ee10f6b566cd2ccf96f7cef115eba59606b01b` | target-consumption source; no code fusion |
| [xiaolin9595/workflow-localized-mechanism-learning](https://github.com/xiaolin9595/workflow-localized-mechanism-learning/tree/019b7d9edd6cbc4e971d35443c83d120e5d0b974) | `019b7d9edd6cbc4e971d35443c83d120e5d0b974` | scoped transfer source; no execution |

Search popularity was not used as correctness or admission evidence. The
adopted component is a local contract, not a copy of an upstream implementation.

## Baseline and implementation

The pre-change suite at
`evals/incremental-tests/p25-baseline-missing-portability/` failed as expected:
`skill_portability_core` did not exist. Its peak aggregate owned working set was
125,759,488 bytes. The first implementation round exposed two integration
defects—validation error ordering and a missing MCP route—and remained FAIL.
They were corrected without weakening any assertion; the next incremental suite
at `evals/incremental-tests/p25-core-round-2/` passed P10 routing, P24 frontier,
and P25 portability groups.

The implementation now:

- consumes the exact finalized P24 artifact, owner, overlap decision, hashes,
  source cases, and metric contract;
- freezes model/harness/task variation, executor group, evidence family, cases,
  and ordered replicates;
- recomputes `POSITIVE_TRANSFER`, `NO_MEASURED_GAIN`, `NEGATIVE_TRANSFER`, and
  `SAFETY_REGRESSION` from inherited utility/safety tolerances;
- hides results before finalization and never emits a cross-cell average;
- rejects case leakage, replayed run hashes, artifact drift, state-chain drift,
  false independence, incomplete matrices, and changed P24 bindings; and
- permits only an all-positive claim scoped to the recorded cells and exact
  artifact while keeping `universal_claim_allowed=false`.

## Focused tests and repeated SkillOpt

The focused post-documentation integration ran 31 tests covering P25, P24, and
the canonical P10 MCP/router surface; all passed. It includes two- and three-
replicate paths, positive/no-gain/negative/safety behavior, P24 split leakage,
pre-final non-disclosure, source and identity checks, ordering, replay,
tampering, false independence, incomplete matrices, actual MCP dispatch, and
the unchanged 17-tool surface.

Four consecutive SkillOpt rounds passed. Every round executed the same 31 tests
and 13 static architecture gates. The largest aggregate task-owned working set
was 231,432,192 bytes, below the 536,870,912-byte limit; no working-set trim or
trim failure occurred. The local report is
`evals/p25-skill-portability-skillopt/report.json`; its sealed content digest is
`a77e8af507f4793444f89a23c24ecd294d01e658d3612bd481891a90e27ffde4`
and its file SHA-256 is
`04212fcbbf51bd969279864283ce63ce9458b391202aa71c5ff33b61ac381373`.
Evaluation logs stay local; the deterministic runner, tests, contracts, and this
bounded report ship in the public package.

## Packaging and publication gates

P25 is a required file set in repository validation, the provenance-safe source
archive, all four platform migration archives, and isolated-install verification.
CI and release workflows run both P24 and P25 suites. The bilingual documentation
registry binds the English and Simplified Chinese operator contract and this
provenance pair to shared revisions, headings, links, and normalized hashes.

Final package, isolated-install, installed-plugin, remote-push, and exact-commit
CI evidence are recorded only after those stages actually pass; an archive build
alone is not installation or publication evidence.

## Claim boundaries

These results establish local contract behavior, data-flow enforcement, tamper
detection, bilingual/package inclusion, and repeated regression status. They do
not prove any upstream paper claim, universal Skill portability, independent
model execution, scientific effectiveness, global safety, or venue acceptance.
`HUMAN_REVIEW_REQUIRED` is not admission. Missing execution, source coverage,
cells, or replicates remains blocked/`NOT_RUN` and cannot become support.
