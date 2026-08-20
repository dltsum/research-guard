# P19 resource-aware task-planning overlap audit

Audit date: 2026-08-21. Repository fork counts are time-bound discovery signals,
not quality rankings. Official documentation and upstream repositories were
used only to compare architecture; no upstream runtime or code was vendored.

| Upstream | Current comparison evidence | Useful mechanism | Research Guard decision |
|---|---|---|---|
| Snakemake | [repository, 655 forks at audit](https://github.com/snakemake/snakemake); [resource and output contracts](https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html) | DAG dependencies, per-job resource declarations, checkpoint/output completion criteria | Admit DAG and expected-artifact semantics. Reject its scheduler/runtime because declared resources alone are not live memory enforcement. |
| Nextflow | [repository, 784 forks at audit](https://github.com/nextflow-io/nextflow); [dynamic task resources](https://nextflow.io/docs/edge/process.html#dynamic-task-resources) | Process-level resources, attempt traces, explicit retry states | Admit observed-resource receipts and versioned replanning. Reject automatic memory escalation and retry because both could cross the frozen 512 MiB policy or replay unknown work. |
| DVC | [repository](https://github.com/iterative/dvc); [pipeline definition](https://dvc.org/doc/user-guide/project-structure/dvcyaml-files); [lock and run-cache design](https://dvc.org/blog/dvc-1-0-release/) | Explicit commands, dependencies, outputs, parameters, and machine-written hashes | Admit the separation between human-selected contracts and generated hashes. Reuse the existing reproducibility plan rather than adding DVC or a second cache/runtime. |
| Common Workflow Language | [CommandLineTool v1.2 specification](https://www.commonwl.org/v1.2/CommandLineTool.html); [network-access contract](https://www.commonwl.org/user_guide/topics/command-line-tool.html#network-access) | Validate requirements before execution; bind inputs/outputs; fail if required runtime semantics cannot be met | Admit fail-closed execution admission and exact output binding. Because the local executor cannot prove network isolation or full disk-write telemetry, reject those managed bindings instead of claiming them. |
| Dask/distributed | [Dask repository, 1.9k forks at audit](https://github.com/dask/dask); [distributed repository, 769 forks at audit](https://github.com/dask/distributed); [resource annotations](https://docs.dask.org/en/stable/api.html#dask.annotate) | Task graph metadata and resource annotations | Admit typed task metadata. Reject the distributed scheduler and treat annotations as planning intent only, never hard enforcement. |
| Ray | [repository, 7.7k forks at audit](https://github.com/ray-project/ray); [placement groups](https://docs.ray.io/en/latest/ray-core/scheduling/placement-group.html) | Atomic admission and observable pending/infeasible resource states | Admit explicit admission failures. Reject cluster runtime, autoscaling, GPU scheduling, and placement groups for this local serial plugin. |
| Local `get-available-resources` Skill | Bounded read-only snapshot, host/effective separation, privacy redaction | Missing means unknown; inventory is not entitlement; accelerator visibility is not usability | Admit the semantics and bounded probes. Research Guard keeps its smaller registered snapshot instead of copying the Skill runtime. |
| Local `experiment-queue` Skill | Manifest DAG, preconditions, expected outputs, durable transitions | Checkpoint and resume semantics | Admit DAG/state ideas. Reject SSH, multi-GPU, and remote queue execution because they overlap neither the local owner nor the GPU-off policy. |
| Local `autonomous-dispatcher` Skill | Concurrency gate and stale-state handling | Coordinator-only boundary | Admit the serial gate and explicit stale/unknown state. Reject GitHub/cron/auth dispatch surfaces. |

## Canonical-owner result

`research_design.resource_plan_action` is the sole task-planning owner. The
existing `resource_guard` remains the sole local process-memory enforcement
owner; `research_integrity.execute_reproducibility` remains the sole frozen local
command-execution owner; `delegation_action` remains the sole LLM-assistance
owner; the dependency manager remains the sole installer/decline owner. The
resource planner's `execute` action accepts only a versioned run ID and copies
the canonical execution receipt. No new top-level MCP tool, worker pool,
distributed scheduler, GPU route, API fallback, or automatic semantic
classifier was added.

## SkillOpt contract

Four resource-managed rounds passed. They exercise inventory privacy, DAG ordering, cycles,
resource/profile overflow, network/GPU decisions, user budgets, unknown
completion, delegation interlock, frozen reproducibility binding, automatic
guard telemetry, caller-telemetry rejection, plan/execution-receipt tampering,
non-finite timeout rejection, measured time-budget overrun, no-replay receipt
reconciliation after interruption, artifact tampering, versioned replanning, and the
unchanged 17-tool surface. Each round must remain under the aggregate
536,870,912-byte owned-task limit; the highest measured aggregate working set
was 202,522,624 bytes. Evidence is generated under the ignored
`evals/resource-task-planning-skillopt/` directory and is not packaged as a
claim-bearing runtime dependency.

The supported release regression completed 22/22 test files without resume.
The rebuilt Windows archive then passed a clean isolated installation and
17-tool MCP smoke. That run used 402,911,232 bytes peak worker working set,
30,932,992 bytes peak orchestrator working set, and 433,209,344 bytes peak
aggregate working set. Its registered `managed_install` limits were 469,762,048
worker bytes plus 67,108,864 orchestrator bytes, still exactly bounded by the
536,870,912-byte total policy. The isolated directory was deleted after PASS.
