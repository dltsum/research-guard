# Time and continuation policy

Research Guard does not impose a wall-clock deadline on research. Unless the
user explicitly supplies a time, cost, source-count, or stopping budget, the
main agent owns the decision to continue or stop from factual progress.

## Research loop

1. The main agent selects the field and modules from the registered catalogs.
2. Each source-query work unit is written atomically to a hash-bound checkpoint.
3. `IN_PROGRESS` means: return linked stage results to the user, then continue.
4. A failed required unit returns `ACTION_REQUIRED`, not `COMPLETE`. The main
   agent must retry it, register admissible manual evidence, or explicitly
   record a factual blocker covering every failed required unit.
5. Only completed coverage, a persisted explicit factual blocker, or a user's
   explicit budget/time/stop instruction ends the research loop.

No fixed number of retries is encoded. Transport failure, tool-call duration,
or lack of a result within one attempt is never treated as proof that the
research is complete.

For resource-sensitive multi-stage work, the same rule is machine-readable in
`research_design.resource_plan_action`: the plan stores a serial DAG and stage
artifacts, while a user-supplied wall-clock budget is accepted only with
`budget_selected_by=user`. Without that field there is no whole-task deadline.
An `UNKNOWN` stage returns `RECEIPT_INSPECTION_REQUIRED` and cannot authorize a
replay. For a linked `managed_standard` stage, `resource_plan_action=execute`
records measured child duration from the canonical reproducibility executor.
`process_timeout_seconds` still bounds only that one owned child-process attempt;
it is not converted into a deadline for the remaining DAG.

## Remaining safety bounds

| Boundary | Public name | Purpose | Can end research? |
|---|---|---|---|
| One HTTP/API operation | `attempt_timeout_seconds` | Prevent one stalled socket from occupying the process forever | No |
| One compiler, verifier, installer, or reproducibility child | `process_timeout_seconds` | Terminate only the owned child process tree if it becomes non-responsive | No |
| One hook invocation | host hook timeout | Keep the editor/agent event loop responsive; durable work belongs in MCP tools | No |
| CI/release job | GitHub Actions `timeout-minutes` | Bound hosted runner cost and expose an infrastructure failure | No |
| Managed local worker | resource-guard timeout | Enforce the 512 MiB owned-process policy and recover from a wedged child | No |

These boundaries report explicit failure and preserve partial evidence. They
are engineering safeguards, not scientific stopping rules. Public MCP schemas
therefore avoid the ambiguous name `timeout`: network calls use
`attempt_timeout_seconds`, and local child processes use
`process_timeout_seconds`. The process guard rejects non-finite and non-positive
values before creating a child, so `NaN` cannot disable this attempt bound.

## User interaction contract

During long searches, the agent should report completed sources, linked records,
errors, checkpoint identity, and the next planned slice. Updates must describe
facts already saved; they must not inflate partial coverage into a novelty or
quality claim. The user may change or add a budget at any time, in which case
the new explicit constraint becomes the stopping boundary.
