# Resource-aware task planning

Research Guard can turn a resource-sensitive research objective into a
hash-bound, resumable task DAG. The main agent decides what each stage means and
which registered profile it needs; no keyword classifier or small model makes
that semantic choice. The executable planner validates the declared graph,
resources, budgets, artifacts, transitions, and receipts.

Simple one-response work does not need a resource plan. Use this route for
multi-stage work, child processes, large inputs or outputs, optional components,
network stages, LLM assistance, external waits, or any user-specified resource
budget.

## Workflow

All operations are typed subroutes of the existing `research_design` MCP tool:

1. `resource_plan_action=inventory` performs bounded, read-only inventory. It
   redacts hostnames, absolute paths, environment values, and device IDs. Host
   CPU/RAM/disk observations are explicitly separated from the plugin's actual
   execution entitlement.
2. `resource_plan_action=plan` accepts a main-agent-selected task list and
   dependencies, validates an acyclic graph, records the current resource
   snapshot, and emits dependency waves plus a serial execution order.
3. `resource_plan_action=execute` is available only for a `managed_standard`
   task linked to a fresh user-selected `reproducibility_run_id`. It delegates
   to `research_integrity.execute_reproducibility`; it does not interpret or
   execute a second command contract. The resulting process-guard telemetry,
   duration, output hashes, plan hash, and execution hash are recorded
   automatically.
4. `resource_plan_action=record` persists caller-observed `running`,
   `completed`, `failed`, `blocked`, or `unknown` transitions for stages owned
   elsewhere. A linked reproducibility task cannot be completed through this
   caller-reported route. Expected artifacts are hashed.
5. `resource_plan_action=status` returns the one currently executable stage,
   explicit blockers, and durable progress.
6. `resource_plan_action=verify` checks policy/profile drift, state hashes,
   transition hashes, artifact size/hash integrity, and any linked
   reproducibility plan/execution receipt.

Calling `plan` again with the same `resource_plan_id` creates a new revision and
preserves the previous revision. It never silently edits the old plan.

## Registered profiles

| Profile | Use | Enforcement boundary |
|---|---|---|
| `inline_light` | Small main-agent operation without a child process | 128 MiB orchestrator preflight; no child-process enforcement claim |
| `managed_standard` | Python, analysis, validation, rendering, packaging | `resource_guard.run_managed`; 384 MiB worker + 128 MiB orchestrator. Optional `execute` binding delegates to the frozen reproducibility owner. |
| `managed_install` | Installer execution and isolated package validation | `resource_guard.run_managed_install`; 448 MiB worker + 64 MiB orchestrator |
| `managed_lean` | Lean/Mathlib whole-file verification | `resource_guard.run_managed_lean`; 464 MiB worker + 48 MiB orchestrator |
| `llm_assistance` | Native subagent or main-agent-local assistance | Requires the existing delegation plan/receipt; host resource accounting is explicitly not proven |
| `external_wait` | Remote, CI, provider, or human-controlled stage | Completion requires a project-local expected artifact/receipt |

All profiles remain serial, use one numerical thread, and have no admitted GPU
route. A GPU request returns `GPU_NOT_ADMITTED`; it is not silently moved to an
unregistered device or machine.

## Task contract

Each task declares:

- `task_id`, `summary`, `resource_class`, and `depends_on`;
- `completion_semantics`: `read_only`, `idempotent`, or `stateful`;
- `expected_artifacts` for every idempotent, stateful, LLM, or external-wait
  stage;
- `network_required`, `gpu_required`, `cpu_threads`, and any optional component;
- optional `reproducibility_run_id` for a `managed_standard` task whose ordered
  `expected_artifacts` exactly equal the frozen reproducibility outputs;
- evidence-based estimates for peak memory, download, disk write, duration, and
  external cost when those resources matter.

Unknown estimates remain unknown. When a user supplies a download, disk, time,
or cost budget, `budget_selected_by=user` is mandatory. A stage that consumes a
budgeted resource but omits its estimate returns an explicit
`*_ESTIMATE_REQUIRED` issue; the planner never invents a value. Network
connectivity is not probed or inferred: the plan must declare whether network
use is admitted.

Example task payload:

```json
{
  "action": "status",
  "project_root": ".",
  "resource_plan_action": "plan",
  "resource_plan_id": "paper-audit-01",
  "resource_task_goal": "Audit the manuscript and preserve every stage receipt.",
  "resource_selected_by": "main_agent",
  "resource_constraints": {
    "network_allowed": true,
    "max_download_bytes": 52428800,
    "minimum_remaining_disk_bytes": 1073741824,
    "budget_selected_by": "user"
  },
  "resource_tasks": [
    {
      "task_id": "source-check",
      "summary": "Verify current cited records.",
      "resource_class": "inline_light",
      "depends_on": [],
      "expected_artifacts": ["receipts/source-check.json"],
      "completion_semantics": "idempotent",
      "network_required": true,
      "gpu_required": false,
      "cpu_threads": 1,
      "estimated_download_bytes": 1048576,
      "estimated_disk_write_bytes": 262144
    }
  ]
}
```

The example budget is illustrative, not a plugin default.

## Managed execution binding

Use the binding only after `integrity_action=repro_plan` has frozen the exact
user-selected argv command, working directory, inputs, outputs, parameters,
seeds, environment, executable hash, runtime fingerprint, and expected checks.
Then include that versioned `run_id` as the task's `reproducibility_run_id` and
call `resource_plan_action=execute` for the one READY task.

The resource planner does not accept a command. The reproducibility subsystem
remains the canonical command owner, while `resource_guard.run_managed` remains
the canonical process-memory owner. A successful binding records
`observation_source=managed_reproducibility_receipt`; caller-reported telemetry
cannot produce that source or complete a linked task.

This route is deliberately narrower than a general scheduler:

- it runs only `managed_standard`, serial, CPU-only, non-network-declared work;
- a user disk-write budget blocks this route because complete process-tree disk
  I/O is not measured; output size is not misreported as disk writes;
- a user wall-clock budget is checked against measured execution duration;
- a managed command PASS that exceeds that budget is preserved as a resource
  task failure, together with the valid execution receipt;
- after interruption, an already persisted valid final receipt is reconciled
  into the task state without rerunning the command;
- if no final execution receipt exists, the linked stage remains unresolved and
  automatic replay is forbidden.

## Continuation and replay safety

There is no whole-task deadline unless the user supplies one. Transport and
child-process attempt limits remain engineering safety bounds only. A long plan
must save artifacts and report factual progress after each stage.

`unknown` means a stage may have completed but lacks a verified final receipt.
It returns `RECEIPT_INSPECTION_REQUIRED`, prevents downstream execution, and
cannot be resolved until `resource_observation.receipt_inspected=true` is
recorded. This prevents a stateful provider call, remote run, or publication
action from being silently replayed.

For a linked managed reproducibility stage, calling `execute` while its task
state is `RUNNING` or `UNKNOWN` performs receipt reconciliation, not a retry. If
the exact frozen reproducibility record already contains a valid final managed
receipt, the planner adopts it and records `receipt_inspected=true` plus
`reconciled_existing_receipt=true`. If that receipt is absent, the call returns
`RECEIPT_INSPECTION_REQUIRED` and does not launch a child process. A new run
requires an explicit new reproducibility run ID and a new plan revision.

The planner coordinates execution; it is not a second scheduler. Its one local
`execute` route calls the already registered reproducibility and resource-guard
owners. It does not execute remote workflows, install dependencies, spawn
subagents, or authorize external writes by itself.
