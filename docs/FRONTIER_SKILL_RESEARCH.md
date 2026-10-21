<!-- research-guard-doc-pair: frontier-skill-research | revision: 2026-10-22.1 -->
# Frontier Skill research

[English](FRONTIER_SKILL_RESEARCH.md) | [简体中文](FRONTIER_SKILL_RESEARCH.zh-CN.md)

P24 is an optional experiment for comparing a Skill's research effects.
Ordinary installation and use do not require P24 registration, fingerprints,
state chains, or signed receipts. Ask for the work directly.

## Scientific basis

The implemented mechanism uses a small, audited subset of current primary work:

- [SkillOpt](https://arxiv.org/abs/2605.23904) motivates bounded edits,
  validation-gated acceptance, rejected-edit memory, and a final heldout check.
- [SkillLens](https://arxiv.org/abs/2605.23899) separates experience generation,
  extraction, and consumption, and motivates evaluation on the actual target
  agent because negative transfer can occur.
- [Arbor](https://arxiv.org/abs/2606.11926) motivates a persistent hypothesis
  tree that retains failed branches and artifact/evidence links over long work.
- [HDSO](https://arxiv.org/abs/2606.22330) motivates auditable hypothesis-driven
  optimization and explicit resistance to sparse-trajectory shortcuts.
- [SLIM](https://arxiv.org/abs/2605.10923) and
  [SkillOS](https://arxiv.org/abs/2605.06614) motivate contribution-aware
  retain/retire decisions and delayed evidence rather than permanent admission
  by default.
- [Skill-Inject](https://arxiv.org/abs/2602.20156),
  [SkillAttack](https://arxiv.org/abs/2604.04989), and
  [SkillSieve](https://arxiv.org/abs/2604.06550) motivate fail-closed supply-chain
  triage, context-aware review, and multi-round adversarial testing.

The repository records immutable implementation commits separately. No upstream
code is executed or copied merely because its paper informed this contract.

## Workflow

1. `frontier_skill_action=plan` saves the question, target agent and harness,
   candidate ID/repository/version, data splits, and metrics. Optional
   `validation_rounds` defaults to 1 and accepts 1–10.
2. `record_source` saves paper, implementation, or specification links,
   versions, mechanisms, and limitations.
3. `register_hypothesis` saves the proposed mechanism, expected effect, and
   falsifier.
4. After actual execution, `record_trial` reads a result JSON with its run ID,
   case IDs, and measured metrics. Baseline and candidate checksums are not
   required. The code computes improvement and safety regression from values.
5. Experiments requiring independent evaluation still separate held-out data
   from development and complete the task-selected rounds.
6. `finalize` summarizes measured evidence and rejected branches. Missing,
   failed, and insufficient evidence keeps its actual status. `status` reads
   saved work; optional `verify` checks relevant files without digest matching.

## Installation and evaluation

`domain_skill_action=admit` can install a domain Skill after scanning the actual
content. Trigger optimization and P24 are optional. Without target-agent
research, the record says `NOT_EVALUATED`; installation is not proof of gain.
Optimization no longer requires repeating two or three cycles.

An optional `frontier_protocol_id` attaches the corresponding evaluation using
the candidate ID, repository, and version. No artifact checksum must be passed
back. Static scanning is triage, and installation never automatically runs
third-party scripts.

See the [simplified workflow](../references/skill-lab-workflow.md) and
[executable examples](../tests/test_simplified_skill_lab.py). Local evidence is
limited to the measured target, cases, and metrics.
