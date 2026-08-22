# P24 frontier Skill research verification

Date: 2026-08-23

## Scope and frozen decision

P24 adds one academic-frontier Skill evaluation protocol under the existing
`research_design` owner. It does not add a top-level MCP tool, model, automatic
field classifier, installer, generic executor, or automatic self-evolution
route. The implementation must remain serial, GPU-off, and within the existing
536,870,912-byte aggregate task-owned working-set limit.

The frozen architecture decision is:

- retain `domain_skill_core` as the only discovery, quarantine, proxy
  optimization, and explicit admission owner;
- retain `research_knowledge_core` as the only compact evidence graph owner;
- retain `self_evolution_core` as proposal-only;
- add `frontier_skill_research_core` only as an artifact-backed hypothesis and
  target-harness evaluation subroute;
- make its final receipt mandatory for new domain-Skill admission; and
- never execute a third-party Skill during scanning, optimization, or frontier
  evaluation.

## Current primary sources and implementation snapshots

The mechanism was derived from current primary records, not search snippets:

- [SkillOpt](https://arxiv.org/abs/2605.23904): bounded edits, validation-gated
  acceptance, rejected-edit memory, and final heldout evaluation.
- [SkillLens](https://arxiv.org/abs/2605.23899): extraction and consumption are
  different stages; negative transfer requires target-agent evaluation.
- [Arbor](https://arxiv.org/abs/2606.11926): persistent hypotheses, artifacts,
  evidence, and failed branches across long-horizon work.
- [HDSO](https://arxiv.org/abs/2606.22330): auditable hypothesis-driven
  optimization and sparse-trajectory shortcut risk.
- [SLIM](https://arxiv.org/abs/2605.10923) and
  [SkillOS](https://arxiv.org/abs/2605.06614): contribution-aware lifecycle and
  delayed evidence.
- [Skill-Inject](https://arxiv.org/abs/2602.20156),
  [SkillAttack](https://arxiv.org/abs/2604.04989), and
  [SkillSieve](https://arxiv.org/abs/2604.06550): supply-chain injection,
  multi-round attack discovery, and layered triage.

Anonymous GitHub API inspection on 2026-08-23 recorded these immutable heads in
`assets/research-repositories/registry.json`:

| Repository | Commit | License | Decision |
|---|---|---|---|
| [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) | `bdfdc30a8e17309c06cdbe8449f01bdecc120203` | MIT | bounded lifecycle mechanism source |
| [microsoft/SkillLens](https://github.com/microsoft/SkillLens) | `c5ee10f6b566cd2ccf96f7cef115eba59606b01b` | MIT | target-consumption evaluation source |
| [brucelai/arbor](https://github.com/brucelai/arbor) | `5c9bfee05a44631e0982c22f4915ad3a7ff41fa1` | Apache-2.0 | narrow hypothesis-tree pattern only |
| [aisa-group/skill-inject](https://github.com/aisa-group/skill-inject) | `182f3d9d9836e81cdae213e9b9cec1d9be96eea3` | MIT | adversarial reference only |
| [OSU-NLP-Group/SkillWeaver](https://github.com/OSU-NLP-Group/SkillWeaver) | `f2a63d65d0f6ff46ac30e817cede8797f8f25b97` | MIT | executable synthesis rejected |

Popularity and install counts were not admission evidence. The public
`superagent-ai/skills@skill-security` candidate was inspected only as a
comparison point; it was not installed or admitted. Its deterministic scanner
ideas overlap the canonical quarantine owner, and its static results cannot
replace target-context adversarial evidence.

## Baseline defect and implementation

The pre-change regression demonstrated a real fail-open: `curl ... | sh` in a
non-executable `SKILL.md` produced a `review` finding but the aggregate scan
status remained `PASS`. The recorded baseline suite
`evals/incremental-tests/p24-baseline-scanner/` failed exactly that assertion,
with a peak aggregate owned working set of 105,529,344 bytes.

The fix makes every finding fail closed and adds bounded deterministic checks
for instruction override, approval/guardrail bypass, concealed actions,
sensitive-data instructions, hidden Unicode controls, and cross-file
sensitive-source to outbound-network-sink correlation. The result explicitly
states that static analysis is triage and that dynamic adversarial evaluation is
`NOT_RUN` unless separately supplied.

The frontier protocol freezes the exact Skill ID/repository/commit, disjoint
splits, metrics, tolerance, the baseline artifact, and two or three validation rounds. It records clickable primary and
immutable implementation sources, parent-linked hypotheses, project-local JSON
trial artifacts, and a hash chain. Code recomputes utility improvement and
safety non-regression. Heldout is locked until validation completes, runs once
on the last accepted artifact, and remains hidden from status until finalization.
Finalization preserves rejected branches and returns `HUMAN_REVIEW_REQUIRED`;
it exposes no apply operation. Explicit admission additionally binds the exact
Skill identity, candidate artifact, canonical owner, and overlap decision.

## Focused tests and resource evidence

The first post-fix domain/graph/evolution smoke passed eight tests under
`evals/incremental-tests/p24-scanner-frontier-smoke-1/`; peak aggregate owned
working set was 114,020,352 bytes. The first frontier protocol smoke passed nine
tests under `evals/incremental-tests/p24-frontier-core-smoke-1/`; peak aggregate
owned working set was 125,464,576 bytes.

The focused cases cover:

- dangerous Markdown instructions and executable scripts;
- hidden Unicode and cross-file sensitive-source/outbound-sink behavior;
- split overlap and non-main-agent selector rejection;
- validation-before-heldout ordering and heldout non-disclosure;
- safety regression, utility non-regression, and candidate digest continuity;
- state and artifact tampering;
- rejected-branch retention without apply authority;
- exact admission binding; and
- preservation of the 17-tool MCP surface.

The repeated P24 SkillOpt report is generated at
`evals/p24-frontier-skillopt/report.json`. Evaluation logs are local evidence and
remain excluded from the public package; the deterministic runner, tests,
bilingual operator contract, and this bounded provenance report are included.

Four consecutive post-hardening P24 SkillOpt rounds passed on 2026-08-23. Each
round executed all 21 focused frontier plus legacy domain/graph/evolution tests
and all 13 static architecture gates. The highest observed aggregate task-owned
working set was 191,639,552 bytes, below the 536,870,912-byte limit. The sealed
content digest embedded in the report is
`3e5827deff72c4600a5af082fb7829c6764309f9871771280e8201248b151c3a`; the final
report file SHA-256 is
`d971c6c6cafedfc46e257b3ac1a9f4b8e4b981112e70debf5ff1370828e187b4`.

## Claim boundaries

These tests establish local contract behavior, data-flow enforcement, tamper
detection, resource compliance, packaging inclusion, and regression status.
They do not prove that a third-party Skill is globally safe, that a paper's
claims are true, that one target harness represents all agents, or that a
positive local metric is a scientific effectiveness result. Missing dynamic
evaluation or source coverage remains explicit and cannot be promoted to PASS.
