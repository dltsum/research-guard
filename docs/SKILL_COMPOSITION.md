<!-- research-guard-doc-pair: skill-composition | revision: 2026-08-23.1 -->
# Evidence-scoped Skill composition

[English](SKILL_COMPOSITION.md) | [简体中文](SKILL_COMPOSITION.zh-CN.md)

## Scope

This optional contract applies when the main agent wants to combine two or
three exact, finalized P24 Skill artifacts and make a claim about their joint
value or order. It is not triggered by ordinary single-Skill use. The main
agent must choose the components, target order, control order, target
agent/model/harness/task, metrics, cases, and rationale; no classifier, small
model, or popularity score may choose them.

Call `research_design` with `skill_composition_action=plan`. Each component
must bind its exact P24 protocol, Skill ID, repository, immutable commit,
artifact SHA-256, canonical owner, and overlap decision. Composition cases
must be fresh and disjoint from every component's P24 train, validation, and
heldout split.

## Scientific basis

[Generative Skill Composition for LLM Agents](https://arxiv.org/abs/2606.32025)
motivates measuring subset, count, and order instead of assuming that more
Skills are better. [Break It Down, Pass It On](https://arxiv.org/abs/2608.20274)
provides current evidence that modular decomposition and transfer require
task-level evaluation rather than name-level compatibility.

The implementation comparison is pinned to
[SkillsBench](https://github.com/benchflow-ai/skillsbench/tree/9a1f4dd5f7659f75707435da3ce854b6e48321d1),
[SR-Agents](https://github.com/oneal2000/SR-Agents/tree/277fd8d2bbd7d3b81a5cf4ffa6e87e18c7906e4f),
[PolySkill](https://github.com/simonucl/PolySkill/tree/fff8807d7501d93188f9f658f4d0af2f29f35c23),
and reference-only
[CompoSkill](https://github.com/Limax666/CompoSkill/tree/d7dc9d314f491eaace0b9e7c18e0c21ed3b71577).
These sources motivate the protocol; none proves that a local composition is
useful or safe. No CompoSkill code or content is copied because a redistributable
repository license was not verified.

## Executable workflow

1. Finalize every component through P24, then select exactly two or three
   components as `selected_by=main_agent` with a written rationale.
2. Freeze one target order and one different permutation as `control_order`.
   Freeze fresh cases, at least one utility metric, at least one safety metric,
   and exactly two or three replicates.
3. Declare source-located capability edges for each exact artifact. Supported
   nodes cover sensitive sources, bridge payloads, and effectful terminals;
   undeclared capabilities are not inferred.
4. Record clickable current sources with `record_source`. Finalization requires
   a primary paper and an immutable 40-character repository commit.
5. For every replicate, submit one project-local JSON artifact containing the
   same cases and component hashes plus these exact conditions: `baseline`,
   every `single.<skill_id>`, `ordered`, and `control_order`. Every condition
   needs a unique run SHA-256 and execution-receipt SHA-256.
6. Call `finalize`, then `verify`. Pre-final status is
   `RECORDED_NOT_EXPOSED`; final output is always
   `HUMAN_REVIEW_REQUIRED`.

The core records externally produced artifacts but never runs a model or
third-party Skill. There is no whole-task deadline unless the user specifies a
time or budget; the main agent provides linked stage updates and decides when
the registered evidence is complete.

## Evidence and path results

For each replicate, the target order is compared with the strongest observed
no-Skill or single-Skill reference and classified as
`POSITIVE_COMPOSITION_GAIN`, `NO_COMPOSITION_GAIN`, `INTERFERENCE`, or
`SAFETY_REGRESSION`. The control order is classified separately, and the order
effect remains visible. There is no cross-replicate score average.

The declared capability graph is also evaluated in target and control order.
An order-respecting path must cross at least two Skills from a sensitive source,
through declared bridge edges, to an effectful terminal. A target-order path
blocks the positive composition claim. A control-only path remains visible for
human review but does not rewrite the exact target-order measurement. This is
triage over main-agent-declared, source-located edges: it neither synthesizes an
attack nor proves safety or exploitability.

`scoped_claim_allowed=true` only when every replicate has positive composition
gain, no safety regression, and no declared target-order path. Even then, the
claim is limited to the exact artifacts, cases, target, metrics, evidence family,
and order. `universal_claim_allowed=false`,
`order_invariant_claim_allowed=false`, and `safety_claim_allowed=false` in
every state.

## MCP contract

The existing `research_design` owner exposes these subactions without adding a
top-level tool:

| Subaction | Required composition fields | Result |
|---|---|---|
| `plan` | `skill_composition_id`, protocol, `skill_composition_selected_by=main_agent`, rationale | Frozen, hash-bound protocol |
| `record_source` | ID, type, title, HTTPS URL, immutable ID, mechanism, limitations | Append-only source record |
| `record_trial` | Project-local JSON artifact path | Artifact and execution receipts recorded; outcome hidden |
| `finalize` | Complete source and replicate matrix | Per-replicate/order/path result plus `HUMAN_REVIEW_REQUIRED` |
| `status` | Composition ID | Current evidence without premature outcome leakage |
| `verify` | Composition ID | State, P24 binding, and artifact-integrity result |

The protocol and artifacts are append-only. A changed P24 finalization,
protocol, case boundary, or trial file causes verification failure instead of a
silent rebind.

## Boundaries

- This route qualifies one exact ordered-composition claim; it does not admit,
  install, apply, optimize, or execute any Skill.
- Repository popularity, trigger overlap, and a single successful run are not
  composition evidence.
- A control order is a comparison, not proof that every permutation was tested.
- Capability edges must carry source locators, but completeness still requires
  human review and, where authorized, separate dynamic adversarial evaluation.
- CPU execution is serial, GPU is off, and aggregate task-owned working set is
  capped at `512 MiB` (`536,870,912` bytes).
- Missing external execution, source, or final receipt is `NOT_RUN` or
  `ACTION_REQUIRED`, never PASS.
