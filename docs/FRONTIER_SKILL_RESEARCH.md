<!-- research-guard-doc-pair: frontier-skill-research | revision: 2026-08-23.3 -->
# Frontier Skill research and admission

[English](FRONTIER_SKILL_RESEARCH.md) | [简体中文](FRONTIER_SKILL_RESEARCH.zh-CN.md)

## Scope

This contract governs the discovery, local evaluation, and admission of a
third-party academic Skill. It is a typed subroute of the existing
`research_design` owner, not another installer, executor, model, or top-level
tool. The main agent selects the target field, target agent, harness, and
canonical owner; no keyword classifier or small routing model makes that
semantic choice.

The contract does not claim that a popular Skill is useful, that static scanning
proves safety, or that one agent's result transfers to another. Search results,
stars, installs, and token overlap are discovery or proxy evidence only.
Every retained candidate is tested on the actual target agent and frozen harness.

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

## Executable workflow

Use `frontier_skill_action` in this order:

1. `plan` freezes a versioned question, target agent/harness, candidate Skill
   ID/repository/commit, baseline artifact SHA-256, disjoint
   train/validation/heldout case IDs, metric directions, tolerances, exactly
   2–3 validation rounds, and the main-agent rationale.
2. `record_source` accepts only clickable HTTPS primary-paper and
   implementation/benchmark/specification records with immutable identifiers,
   mechanisms, and limitations.
3. `register_hypothesis` creates an append-only parent-linked branch with its
   expected effect, falsifier, sources, canonical owner, and overlap decision.
4. `record_trial` reads a bounded project-local JSON artifact. Validation rounds
   are append-only in frozen order, and every protocol-level `run_id` is unique.
   Code recomputes utility improvement and every safety non-regression from
   frozen metrics; caller-supplied PASS labels are not accepted.
5. The heldout split stays locked until every validation round passes. It runs
   exactly once on the last accepted artifact, and its result is not exposed by
   status until finalization.
6. `finalize` requires a primary paper, an implementation/specification source,
   exactly the frozen validation rounds, one accepted heldout run, unchanged
   artifact identity, and no safety regression. It returns
   `HUMAN_REVIEW_REQUIRED`, preserves rejected/reference branches, and exposes
   no automatic apply route.
7. `verify` rechecks the hash chain and every recorded trial artifact. Changed
   state or evidence invalidates the receipt.

There is no whole-task timeout. The main agent continues with stage updates and
durable artifacts until the protocol is complete, factually blocked, or the user
sets a budget/time/stop instruction. Every local subprocess remains under the
serial GPU-off 512 MiB resource contract.

## Security and admission

Quarantine scanning reads every bounded text file. Known remote-shell,
credential, encoded-execution, instruction-override, approval-bypass,
concealment, sensitive-data, hidden-Unicode, and broad-delete patterns are
fail-closed even when they appear in `SKILL.md` rather than an executable file.
It also correlates a sensitive source in one file with an outbound sink in
another. A review finding cannot silently become PASS.

Static scanning remains triage, not a proof of benign intent. The receipt says
when dynamic adversarial evaluation is `NOT_RUN`. Third-party scripts are never
executed automatically, and executable-program synthesis from
[SkillWeaver](https://arxiv.org/abs/2504.07079) or
[HASP](https://arxiv.org/abs/2605.17734) remains reference-only because it would
cross the quarantine and authorization boundary.

The existing 2–3-round Optuna route now labels its result as a trigger/file-
selection proxy. `domain_skill_action=admit` additionally requires a finalized
frontier protocol whose candidate Skill ID, repository, commit, artifact SHA-256,
canonical owner, and overlap decision exactly match the staged Skill. Admission is still an explicit call;
the frontier mechanism never installs or admits by itself.

## MCP contract

The route stays under one of the 17 top-level MCP tools:

```json
{
  "action": "status",
  "project_root": "/project",
  "frontier_skill_action": "plan",
  "frontier_protocol_id": "graph-skill-v1",
  "frontier_selected_by": "main_agent",
  "frontier_selection_rationale": "Evaluate this exact candidate on the frozen target research harness.",
  "frontier_protocol": {
    "research_question": "Does the candidate improve specialist graph research support?",
    "target_agent": "target research agent",
    "target_harness": "project-local frozen harness",
    "baseline_artifact_sha256": "<64 lowercase hex characters>",
    "candidate_identity": {
      "skill_id": "graph-skill",
      "repository": "owner/repository",
      "commit": "<40 lowercase hex characters>"
    },
    "splits": {
      "train": ["train-1"],
      "validation": ["validation-1"],
      "heldout": ["heldout-1"]
    },
    "metrics": [
      {"name": "utility", "direction": "maximize", "kind": "utility", "tolerance": 0.0},
      {"name": "unsafe_rate", "direction": "minimize", "kind": "safety", "tolerance": 0.0}
    ],
    "validation_rounds": 2
  }
}
```

Subsequent calls use `record_source`, `register_hypothesis`, `record_trial`,
`finalize`, `status`, or `verify`. Trial files stay inside `project_root`, are
non-symlink JSON files no larger than 2 MiB, and are bound by SHA-256.

## Boundaries

- A local test proves only the recorded target/harness/cases and metrics; it is
  not a general scientific-effectiveness claim.
- A source URL plus immutable identifier establishes provenance, not that every
  upstream claim is true or applicable.
- A rejected branch is evidence, not failure to make progress; it remains in the
  hypothesis tree so later work does not repeat it silently.
- `HUMAN_REVIEW_REQUIRED` is not admission. Only the existing explicit admission
  gate can consume one exact retained proposal.
- Missing network coverage, unavailable dynamic evaluation, or a declined
  dependency remains explicit `NOT_RUN`/blocked evidence and never becomes PASS.
