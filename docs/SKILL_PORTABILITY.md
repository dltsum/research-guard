<!-- research-guard-doc-pair: skill-portability | revision: 2026-10-22.1 -->
# Skill portability evaluation

[English](SKILL_PORTABILITY.md) | [简体中文](SKILL_PORTABILITY.zh-CN.md)

Use this optional experiment when asking whether a Skill still works on another
model, harness, or task. It is not required for installation or ordinary use,
and no artifact or execution-receipt checksums are supplied.

## Scientific basis

The design uses a narrow, evidence-bounded reading of current primary work:

- [SkillLens](https://arxiv.org/abs/2605.23899) reports that extraction and
  consumption are distinct and that an extracted Skill can transfer negatively
  on a consuming target. This motivates target-cell evaluation rather than an
  assumption of portability.
- [SkillOpt](https://arxiv.org/abs/2605.23904) studies optimization and transfer
  across model and harness settings. This motivates freezing those identities
  and comparing the same artifact rather than silently re-optimizing it.
- [Workflow-Localized Mechanism Learning](https://arxiv.org/abs/2607.20999)
  motivates testing scoped transfer to nearby workflows, not a universal claim.
- [SkillRise](https://arxiv.org/abs/2607.26784) and
  [ReuseRL](https://arxiv.org/abs/2605.31509) motivate cross-task reuse and
  evolution questions while reinforcing the need to measure each target.

The implementation snapshots were inspected through public GitHub records on
2026-08-23 and pinned separately:
[SkillOpt at `bdfdc30a`](https://github.com/microsoft/SkillOpt/tree/bdfdc30a8e17309c06cdbe8449f01bdecc120203),
[SkillLens at `c5ee10f6`](https://github.com/microsoft/SkillLens/tree/c5ee10f6b566cd2ccf96f7cef115eba59606b01b), and
[Workflow-Localized Mechanism Learning at `019b7d9e`](https://github.com/xiaolin9595/workflow-localized-mechanism-learning/tree/019b7d9edd6cbc4e971d35443c83d120e5d0b974).
These sources informed the protocol; their code is not copied or executed.

## Workflow

1. `skill_portability_action=plan` identifies the source by its P24 protocol ID
   and the Skill ID/repository/version. Declare target cells, models, harnesses,
   tasks, and cases, with at least one actual variation dimension.
2. Optional `replicates` defaults to 1 and accepts 1–10. Keep target cases
   separate from source development and evaluation data.
3. Save supporting paper and implementation sources. After running the work,
   submit the result JSON path, run ID, cases, and metrics. Artifact, baseline,
   candidate, and execution-receipt digests are not required.
4. `finalize` summarizes the selected cell-by-replicate matrix. Missing runs
   remain missing. `status` reads progress; `verify` does not reject ordinary
   edits to files or explanatory text.

## Results

Each comparison retains `POSITIVE_TRANSFER`, `NO_MEASURED_GAIN`,
`NEGATIVE_TRANSFER`, or `SAFETY_REGRESSION`. A strong cell cannot average away
a failed cell. Same-model or same-executor results do not establish independent
cross-provider corroboration, and untested targets remain untested.

The core records externally produced run results; it does not launch a model
or third-party Skill. See the [workflow](../references/skill-lab-workflow.md)
and [checksum-free examples](../tests/test_simplified_skill_lab.py).
