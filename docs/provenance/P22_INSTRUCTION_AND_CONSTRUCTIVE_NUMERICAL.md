# P22 instruction adherence and constructive numerical audit

## Frozen user outcomes

1. Enhance agent adherence with executable state, not prompt-only wording.
2. Make numerical audit constructive: model a registered system of equations
   and inequalities, derive legal intervals, and emit jointly feasible numeric
   anchor assignments.

## Acceptance contract

- Keep exactly 17 top-level MCP tools. Instruction adherence is a typed
  `research_design.instruction_action` subroute; constructive numerical audit
  is a typed `paper_audit.numerical_action` subroute.
- The main agent performs semantic decomposition. No keyword classifier or
  small routing model decides whether a task is multistep.
- Atomic mandatory requirements retain acceptance criteria, forbidden
  substitutions, dependencies, evidence kinds, append-only transitions, and
  an integrity-checked completion receipt.
- A Stop hook rejects an active contract with pending, user-decision, or stale
  evidence. A factual blocked handoff remains visibly incomplete and cannot
  obtain a PASS receipt. User waivers require explicit user authority and a
  user-message SHA-256.
- The instruction ledger never overrides system, developer, safety, legal,
  privacy, or factual constraints.
- Numerical construction accepts only source-located linear rational protocol
  constraints. Pint validates units, SymPy emits the canonical algebraic model,
  Z3 proves SAT/UNSAT and marginal bounds, and exact arithmetic rechecks every
  complete anchor against every bound and relation.
- Marginal intervals are labeled as projections, never as a Cartesian-product
  guarantee. Every proposed anchor is one complete jointly feasible assignment.
- Nonlinear, dimensionally inconsistent, unsourced, unused, infeasible, or
  numerically unsafe inputs fail explicitly; no heuristic candidate is called
  certified.
- Execute serially with GPU disabled and an aggregate 512 MiB owned-task cap.
- Run at least four consecutive SkillOpt/regression rounds, bilingual document
  validation, repository validation, package installation smoke, and all four
  platform CI jobs before release handoff.

## Work log

- 2026-08-22: inspected Hook, MCP multiplexers, formula worker, paper-audit
  state machine, resource guard, packaging, CI, and bilingual maintenance
  contracts; froze the design above before implementation.
- 2026-08-22: rejected prompt-only obedience, keyword/small-model intake, new
  top-level tools, floating-point clipping, Cartesian products of marginal
  ranges, and nonlinear certification by a linear core. Admitted one typed,
  append-only instruction ledger under `research_design` and one exact,
  unit-aware linear constructor under `paper_audit`.
- 2026-08-22: both focused suites passed all five functional rounds: pending
  Stop enforcement, dependency/evidence enforcement, drift invalidation,
  user-waiver/blocked-handoff semantics, MCP/integrity preservation; and
  feasible unit-aware construction, dimension/UNSAT failure, strict/integer
  endpoints, ID/tamper failure, and paper-audit role/receipt integration.
- 2026-08-22: final four consecutive combined SkillOpt rounds passed 10 tests
  and all 11 static overlap/admission checks per round. Report SHA-256:
  `3c568278aa7ab775b44c88597a8efbc3b9430af1b5a577da8107ebf5ab914b4a`.
  Maximum observed aggregate owned working set was 324,034,560 bytes, below
  the frozen 536,870,912-byte cap; execution remained serial and GPU-off.
- 2026-08-22: registered a third bilingual documentation pair and refreshed
  normalized source, translation, and pair hashes. Structural automation does
  not replace human bilingual semantic review.
- 2026-08-22: dogfooding the ledger exposed a stale-evidence recovery defect:
  an old `satisfied` label became invalid but could not be re-evidenced. The
  core now treats only currently valid satisfaction as terminal, permits a new
  chained event after evidence drift, and prevents dependent requirements from
  consuming stale satisfied labels. Focused and four-round SkillOpt suites were
  rerun after this correction.
