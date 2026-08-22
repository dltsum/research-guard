<!-- research-guard-doc-pair: instruction-and-numerical | revision: 2026-08-22.1 -->
# Instruction adherence and constructive numerical audit

[English](INSTRUCTION_AND_NUMERICAL_CONTRACT.md) | [简体中文](INSTRUCTION_AND_NUMERICAL_CONTRACT.zh-CN.md)

This contract documents two executable Research Guard capabilities. The main
agent still performs semantic judgment; local code preserves the selected
requirements and verifies the resulting evidence. See the
[Research Guard Skill](../SKILL.md) and the
[paper-writing capability matrix](PAPER_WRITING_CAPABILITIES.md) for the wider
workflow.

## Scope

- `research_design.instruction_action` protects explicitly selected multistep
  user requirements.
- `paper_audit.numerical_action` builds and audits a source-located linear
  rational constraint system.
- Both reuse the existing 17-tool MCP surface and 512 MiB serial, GPU-off
  process contract.
- Neither capability replaces system/developer/safety constraints, scientific
  judgment, current web verification, Lean theorem checking, or model execution.

## Instruction adherence

Before the first mutation in a multistep task, the main agent calls
`instruction_action=register` and records:

- one stable contract ID and a hash of the complete user request;
- atomic requirements with `mandatory`, acceptance criteria, dependencies,
  required evidence kinds, and forbidden substitutions;
- `instruction_selected_by=main_agent` plus a concrete decomposition rationale.

Evidence-bearing transitions use `instruction_action=record`. Supported evidence
is deliberately narrow: project-local file hashes, JSON receipts whose exact
status path equals the registered value, clickable HTTPS evidence locators, and
explicit manual-review checklists. A file or receipt change becomes
`evidence_invalid`. A user waiver uses `instruction_action=waive`,
`instruction_selected_by=user`, and the SHA-256 of the explicit user message.
The append-only ledger preserves every prior transition rather than rewriting
history. If previously satisfied evidence drifts, that item becomes active
again and may accept a new evidence-bearing event; dependent items cannot use
the stale label while its evidence is invalid.

`instruction_action=verify` issues the only completion PASS receipt. Its output
includes `completion_claim_allowed=true`. Simple one-response work is exempt,
because deciding whether a task is multistep remains a full-context main-agent
judgment rather than a keyword classifier.

## Constructive numerical audit

Call `numerical_action=construct` after planning a paper audit with
`audit_features.constructive_numerical=true` and selecting either
`methodology_statistics` or `formal_math_lean` among the 2–3 roles.

The manifest declares 1–32 real or integer variables. Every variable needs a
Pint unit, protocol source, purpose, and optional open/closed bounds. It must be
used by at least one of 1–64 structured linear equations or inequalities. Every
relation carries its own source, rational coefficients, coefficient units, and
right-hand-side unit. Zero coefficients, undeclared variables, nonlinear
syntax, dimensional mismatch, and affine/offset conversions fail explicitly.

The result keeps four records separate:

1. Pint dimensional normalization;
2. SymPy canonical linear relations and equality-system rank/RREF;
3. Z3 SAT/UNSAT/UNKNOWN plus an UNSAT core or exact projected bounds;
4. exact-rational protocol rechecks for every proposed complete anchor.

Each legal interval is labeled
`marginal_projection_subject_to_all_registered_constraints`. Marginal intervals
are not a Cartesian-product guarantee. `joint_anchors` are complete assignments
constructed under all constraints and then independently rechecked for bounds,
integer types, exact relation slack, and binary64 overflow/underflow risk.
These are jointly feasible anchors. Anchors are design points, not
observations, optima, or automatic parameter
recommendations.

## MCP examples

Instruction registration uses the existing `research_design` tool:

```json
{
  "action": "status",
  "project_root": "/project",
  "instruction_action": "register",
  "instruction_contract_id": "revision-v1",
  "instruction_request_text": "Implement and verify both requested features.",
  "instruction_scope": "This multistep implementation and release.",
  "instruction_selected_by": "main_agent",
  "instruction_selection_rationale": "The complete request contains two implementation deliverables and one release proof.",
  "instruction_requirements": [
    {
      "id": "implementation",
      "text": "Implement the executable routes.",
      "kind": "deliverable",
      "mandatory": true,
      "acceptance_criteria": ["Project-local implementation artifacts exist."],
      "required_evidence_kinds": ["file"],
      "forbidden_substitutions": ["Do not replace code with prompt text."],
      "depends_on": []
    }
  ]
}
```

A numerical variable and relation use exact structured values:

```json
{
  "action": "status",
  "project_root": "/project",
  "numerical_action": "construct",
  "numeric_constraint_manifest": {
    "audit_id": "protocol-v1",
    "protocol_id": "methods-v1",
    "source": "Methods pp. 3-4",
    "anchor_count": 3,
    "variables": [
      {
        "name": "duration",
        "type": "real",
        "unit": "second",
        "minimum": 0,
        "minimum_inclusive": false,
        "maximum": 10,
        "source": "Methods p. 3",
        "purpose": "duration allocated to one protocol run"
      }
    ],
    "constraints": [
      {
        "id": "budget",
        "source": "Methods Eq. 2",
        "relation": "<=",
        "terms": [{"variable": "duration", "coefficient": 1}],
        "rhs": {"value": 10, "unit": "second"}
      }
    ]
  }
}
```

## Evidence and stop states

| Status | Completion claim | Stop behavior |
|---|---|---|
| `PASS` | Allowed only with the current verification receipt | Allowed |
| `ACTION_REQUIRED` | Forbidden | Stop Hook blocks |
| `USER_DECISION_REQUIRED` | Forbidden | Stop Hook blocks until the user decides |
| `BLOCKED` | Forbidden; only a factual blocked handoff is allowed | Handoff allowed, never converted to PASS |
| `NOT_CERTIFIED` | Forbidden | Numerical result remains unresolved |

Instruction events are append-only and hash-chained. The Stop Hook re-hashes
registered files and JSON receipts. Constructive numerical records bind the
complete input manifest, solver output, process resource telemetry, and receipt
hash. Reusing an audit ID with different constraints is rejected.

## Boundaries and degradation

- The instruction ledger cannot automatically know every hidden acceptance
  condition. The main agent must decompose the complete request, while code
  prevents registered items from disappearing silently.
- An HTTPS evidence item proves only that a locator was registered; the relevant
  literature/citation route must still verify identity and claim support.
- Manual review is declared human/agent evidence, not independent executable
  proof.
- Certified numerical intervals currently cover linear rational constraints.
  Nonlinear, transcendental, stochastic, mixed categorical, or specialist
  protocol models return an explicit unsupported/not-certified result instead
  of heuristic anchors.
- The constructive route does not execute the paper's numerical model. Feed the
  legal anchors into the existing hash-bound boundary/limit/overflow model audit
  to test model behavior.
- Lean remains a separate whole-manuscript requirement whenever theorem or
  formula logic is in scope.
