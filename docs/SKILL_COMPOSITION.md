<!-- research-guard-doc-pair: skill-composition | revision: 2026-10-22.1 -->
# Skill composition evaluation

[English](SKILL_COMPOSITION.md) | [简体中文](SKILL_COMPOSITION.zh-CN.md)

This optional experiment asks whether a selected composition and order provide
measured gains. It does not restrict ordinary installation or use. The task
determines the components, order, target, and metrics.

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

## Workflow

1. `skill_composition_action=plan` selects two or three research components by
   P24 protocol ID and Skill ID/repository/version, without artifact checksums.
   Save the target order, a different control order, and fresh cases.
2. Select utility and safety metrics. Optional `replicates` defaults to 1,
   accepts 1–10, and follows the task's needs.
3. For capability-composition analysis, save source-located edges. Record
   reference sources supporting the experiment.
4. Actually run the no-Skill, each single-Skill, target-order, and control-order
   conditions. Result JSON includes a run ID, cases, conditions, and metrics.
   Component/run digests and signed execution receipts are not required.
5. `finalize` keeps each replicate, order, and path result separate. `status`
   reads saved work. Optional `verify` checks relevant files without state-chain
   recomputation or rejecting ordinary artifact edits.

## Results

Results may be `POSITIVE_COMPOSITION_GAIN`, `NO_COMPOSITION_GAIN`,
`INTERFERENCE`, or `SAFETY_REGRESSION`. One measured order does not establish
all permutations. Declared capability paths are triage, not proof of safety or
exploitability.

Missing conditions and runs never become success. The core records external
experiments and never launches a model or third-party Skill. See the
[workflow](../references/skill-lab-workflow.md) and
[checksum-free examples](../tests/test_simplified_skill_lab.py).
