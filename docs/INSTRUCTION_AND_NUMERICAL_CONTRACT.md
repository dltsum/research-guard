<!-- research-guard-doc-pair: instruction-and-numerical | revision: 2026-10-22.1 -->
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

For complex work, optional `instruction_action=register` saves the request
text, task ID, requirements, dependencies, and expected deliverables. Ordinary
tasks do not need contract registration.

`record` saves actual progress, file paths, JSON states, source links, or review
notes. File fingerprints, state chains, and signed receipts are not required.
Ordinary edits do not invalidate completed work. JSON execution results must
still agree with the claimed status, and incomplete work remains incomplete.

An explicit user waiver records the decision and reason with `waive`, without
a message checksum. `status` reads saved progress; optional `verify` produces a
current report. Stop Hooks are advisory and do not block for missing
registration, fingerprints, or receipts.

## Constructive numerical audit

Call `numerical_action=construct` after planning a paper audit with
`audit_features.constructive_numerical=true` and selecting either
`methodology_statistics` or `formal_math_lean`. A general audit does not need a
fixed reviewer count, a special selector label, or a minimum-length rationale.

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
| `PASS` | Recorded requirements complete | Allowed |
| `ACTION_REQUIRED` | Work remains incomplete | Advisory only; no block |
| `USER_DECISION_REQUIRED` | User decision remains pending | Advisory only; no block |
| `BLOCKED` | Forbidden; only a factual blocked handoff is allowed | Handoff allowed, never converted to PASS |
| `NOT_CERTIFIED` | Forbidden | Numerical result remains unresolved |

Instruction events record actual progress without a digest chain. Stop Hooks
do not re-scan all registered files. Constructive numerical records save the
complete input manifest, solver output, and process resource telemetry without
requiring a receipt hash. Reusing an audit ID with updated constraints runs the
updated manifest and replaces that audit's saved result.

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
  legal anchors into the boundary/limit/overflow model audit to test current
  model behavior. A model file path is sufficient; no model checksum is required.
- Select mathematical channels for the requested question. A claimed Lean pass
  requires real compilation of the supplied file with an available compatible
  runtime; no fixed-version registration or receipt chain is required. Reading
  historical status does not compile edited source. Rerun `lean_check` to check
  an edit, and report a missing runtime or compiler failure as such. A units
  check needs a units engine; this does not make Pint mandatory for ordinary
  writing or standalone Lean checks.
