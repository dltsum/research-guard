<!-- research-guard-doc-pair: skill-portability | revision: 2026-08-23.1 -->
# Skill portability evidence matrix

[English](SKILL_PORTABILITY.md) | [简体中文](SKILL_PORTABILITY.zh-CN.md)

## Scope

This optional contract qualifies a claim that one exact, already-finalized P24
Skill artifact transfers beyond its source target. It starts only when the user,
paper, README, or admission rationale makes a cross-model, cross-harness, or
cross-task portability claim. Ordinary single-target Skill evaluation remains
under `frontier_skill_action`; P25 is not triggered merely because a Skill was
discovered or finalized.

The route is `research_design.skill_portability_action`. It adds no top-level MCP
tool, classifier, model, executor, installer, admission authority, or automatic
apply path. The main agent selects 2–12 explicit target cells and records why.
The core consumes hash-bound external trial artifacts but never executes a model
or third-party Skill.

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

## Executable workflow

1. Finalize P24 on the exact source target. P25 accepts only its Skill ID,
   repository, 40-character commit, candidate artifact SHA-256, canonical owner,
   overlap decision, metric contract, protocol hash, and finalization hash.
2. Call `skill_portability_action=plan`. Freeze 2–12 cells and exactly 2 or 3
   replicates. Every cell records agent, model family/version, harness/version,
   task scope, executor group, evidence family, and case IDs. At least one model,
   harness, or task dimension must actually vary.
3. Use fresh cases. A P25 case cannot overlap any P24 train, validation, or
   heldout case. Within each cell the same frozen case list is used for every
   paired baseline/candidate replicate.
4. Record at least one current primary-paper source and one repository source
   pinned to an immutable 40-character commit. Every record has a clickable
   HTTPS URL, mechanism, and limitation.
5. Submit project-local, non-symlink JSON trial artifacts no larger than 2 MiB.
   The core recomputes outcomes from the inherited P24 utility and safety metric
   contract. Run IDs, baseline hashes, and candidate hashes cannot replay.
6. Before finalization, status reports only `RECORDED_NOT_EXPOSED`; it does not
   reveal classifications or metric values that could steer later cells.
7. Finalize only after the complete cell-by-replicate matrix exists and all
   trial files plus the P24 binding still match their hashes. Then human-review
   the exact scoped claim.

There is no whole-task timeout. The main agent reports factual stages and keeps
durable artifacts until completion, a recorded factual blocker, or an explicit
user budget/time/stop instruction. Local subprocesses stay serial, GPU-off, and
within the 512 MiB aggregate task-owned resource contract.

## Evidence matrix

Each replicate is classified independently:

| Classification | Executable meaning |
|---|---|
| `POSITIVE_TRANSFER` | At least one inherited utility metric improves, no utility metric regresses beyond tolerance, and every safety metric is non-regressive. |
| `NO_MEASURED_GAIN` | Utility and safety are non-regressive, but no utility metric improves beyond tolerance. |
| `NEGATIVE_TRANSFER` | At least one utility metric regresses beyond tolerance while safety remains non-regressive. |
| `SAFETY_REGRESSION` | At least one inherited safety metric regresses; this dominates the cell and whole claim boundary. |

A cell is positive only when all its replicates are positive. Any safety
regression dominates; any negative transfer remains visible. Mixed positive/no-
gain replicates become `MIXED_OR_UNCERTAIN`. There is no cross-cell score
average, so a strong cell cannot erase a failing one.

`SUPPORTED_ON_RECORDED_CELLS` permits only a claim naming the recorded cell IDs,
varying dimensions, and exact artifact hash. `universal_claim_allowed` is always
false. A supported claim counts as independently corroborated only when all
cells are positive and at least two evidence families are distinct; cells
sharing a model family or executor group are forced into the same evidence
family and cannot masquerade as independent.

## MCP contract

The plan remains under one of the 17 top-level MCP tools:

```json
{
  "action": "status",
  "project_root": "/project",
  "skill_portability_action": "plan",
  "skill_portability_id": "candidate-portability-v1",
  "skill_portability_selected_by": "main_agent",
  "skill_portability_selection_rationale": "Test the exact retained artifact on explicit target cells without universal extrapolation.",
  "skill_portability_protocol": {
    "research_question": "Where does this exact Skill artifact transfer without utility or safety regression?",
    "frontier_protocol_id": "candidate-frontier-v1",
    "source_binding": {
      "artifact_sha256": "<64 lowercase hex characters>",
      "skill_id": "candidate-skill",
      "repository": "owner/repository",
      "commit": "<40 lowercase hex characters>",
      "canonical_owner": "domain-skill",
      "overlap_decision": "fuse_narrow_adapter"
    },
    "replicates": 2,
    "cells": [{
      "cell_id": "target-a",
      "agent_id": "agent-a",
      "model_family": "model-family-a",
      "model_version": "model-version-a",
      "harness": "harness-a",
      "harness_version": "harness-version-a",
      "task_scope": "frozen-target-task-a",
      "executor_group": "executor-a",
      "evidence_family": "evidence-a",
      "case_ids": ["transfer-a-1", "transfer-a-2"]
    }, {
      "cell_id": "target-b",
      "agent_id": "agent-b",
      "model_family": "model-family-b",
      "model_version": "model-version-b",
      "harness": "harness-b",
      "harness_version": "harness-version-b",
      "task_scope": "frozen-target-task-b",
      "executor_group": "executor-b",
      "evidence_family": "evidence-b",
      "case_ids": ["transfer-b-1", "transfer-b-2"]
    }]
  }
}
```

Continue with `record_source`, `record_trial`, `finalize`, `status`, or `verify`.
The final receipt exposes every cell and replicate, support scope, evidence-
family count, artifact hashes, and integrity state.

## Boundaries

- A PASS proves contract and artifact integrity, not that a Skill is universally
  useful, scientifically true, safe in all contexts, or portable to an untested
  target.
- `HUMAN_REVIEW_REQUIRED` is not automatic admission. P25 has no admission
  effect and cannot change or install the retained P24 artifact.
- Artifact-backed reported execution is not independent re-execution by this
  core. The producer and execution receipt remain part of the evidence boundary.
- Same-family or same-executor evidence is correlated even if labels differ;
  the protocol rejects that false-independence representation.
- Missing sources, cells, replicates, dynamic execution, or changed evidence
  remains blocked/`NOT_RUN`; it cannot be converted into portability support.
