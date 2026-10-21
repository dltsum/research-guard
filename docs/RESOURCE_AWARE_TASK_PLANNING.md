# Resource-aware task planning

Use `research_design.resource_plan_action` when the task needs a resumable
multi-stage plan or explicit resource budgets. Ordinary questions do not need
an empty resource plan. The main agent interprets each stage; the planner
records dependencies, resources, and actual outcomes.

1. `inventory` reads current CPU, memory, disk, and installed profiles.
2. `plan` saves the task stages, declared artifacts, dependencies, and selected
   resource constraints. Users do not provide policy or plan fingerprints.
3. `execute` runs a ready managed task through the existing reproducibility
   runner. It records the actual exit status, duration, resource observation,
   and output paths, without artifact or execution checksum gates.
4. `record` saves caller-reported stages honestly. It cannot impersonate a
   managed execution or supply invented runner measurements.
5. `status` reads the current plan and completed stages. Optional `verify`
   checks relevant file paths and actual execution states. File contents may
   be edited without invalidating the plan by historical byte comparisons.

Task classes include managed CPU work, LLM assistance, external waits, and
installation or formal-tool stages when their dependencies are available.
The task's declared budget and command/path safety remain enforced. Network,
GPU use, and external spending follow the user's authorization.

An interrupted task with an unknown external completion state is reconciled
against its saved execution result before retrying. If completion cannot be
determined, the planner reports `UNKNOWN`; it does not invent success or launch
a duplicate non-idempotent action.

Artifacts are recorded by path and size for ordinary inspection. State chains,
transition digests, profile fingerprints, and signed receipts are not required.
See the [workflow](../references/skill-lab-workflow.md) and
[managed execution examples](../tests/test_resource_task_planning.py).
