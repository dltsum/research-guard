---
name: research-guard
description: Evidence-bounded cross-disciplinary academic research from field initialization and idea exploration through novelty checks, cited writing, executable Lean/Pint/SymPy/Z3/numerical formula verification, OpenReview calibration, scientific-image integrity, experiments, reproducibility, figures, and manuscript audit. Use for research ideas, literature, citations, method changes, humanities or STEM research, paper writing/auditing, equations, experiments, reviews, or academic images.
---

# Research Guard

This package is both a traditional Skill and a Codex plugin. Run an installer
only from an extracted, hash-verified release directory with
`RELEASE_MANIFEST.json`. Windows x64 uses the bundled offline runtime; Linux
x64 and macOS x64/arm64 create an isolated venv from Python 3.11+:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
# Linux/macOS
sh scripts/install.sh
```

If those two release files are absent, this is the already-registered bootstrap
Skill. Do not retry a relative installer; continue with the absolute first-load
inventory command below. The release installer has already hash-verified and
installed the plugin and core runtime.

## First-load inventory

On the first load, run the dependency inventory using the installed runtime and
show the feature list once. This is read-only and does not block core work.
Resolve the registered core Python from `.research-guard/dependencies/components/core-runtime.json`;
on a standard install the commands are:

```powershell
& "$env:USERPROFILE\.research-guard\runtime\python\python.exe" "$env:USERPROFILE\plugins\research-guard\scripts\dependency_manager.py" inventory
# Linux/macOS
"$HOME/.research-guard/runtime/python/bin/python" "$HOME/plugins/research-guard/scripts/dependency_manager.py" inventory
```

Do not ask the user to choose every optional component during onboarding. Core
research is ready after installation. When a requested capability needs an
optional component, call `research_design` with `dependency_action=need` and
the component ID. Show its detected environment, download and installed sizes,
and the `reuse`, `install`, and `not_now` choices. Execute only the user's
choice. `not_now` records a bounded degradation; label every omitted check
`NOT_RUN` and never use an unregistered ambient executable. Mutating dependency
actions require `dependency_selected_by=user`; CLI actions require
`--confirmed-by-user`.

## Workflow invariants

1. Do not infer fields, modules, reviewer roles, or method changes with keyword rules or a small classifier. The main agent must inspect the complete request, call `list_research_modules`, and register its explicit 1-3 module choice with `select_research_modules`, `selected_by=main_agent`, a rationale, and an explicit `method_change` boolean.
2. Register a canonical method, then register the main agent's explicit broad-domain choice with `classify_domain`. The tool name is retained for compatibility but it never classifies text. For an unregistered discipline, first call `discipline_action=analyze`, tell the user the live build may take minutes, then call `initialize` separately and re-register the domain binding. History/humanities must include books, editions, archives, and primary-source boundaries, not journals alone.
3. Every method or bound discipline-profile change invalidates the prior receipt and forces a fresh collision search. Semantic method changes are declared by the main agent; tracked method-file hashes remain a deterministic backstop.
4. Every literature item, citation, journal candidate, or collision result must include a clickable HTTPS primary-record or DOI link.
5. The main agent must choose and register only 2-3 audit roles plus explicit `audit_features`, never above `high` effort. Verify current web facts, numeric comparisons, code, and experiments where relevant.
6. Equation assistance requires one whole-manuscript Lean file, followed by `paper_audit verification_action=cross_verify`. Report five distinct records: Lean logic, Pint dimensions, SymPy equivalence, Z3 constraint satisfiability, and numerical/protocol legality. All symbols must be defined and used; numerical cases outside the frozen paper protocol fail before execution. Lean is optional and requires a user decision. If the user selects `not_now`, run only the other four executable checks, report Lean as `NOT_RUN_BY_USER`, return `DEGRADED`, and keep final manuscript submission blocked.
7. OpenReview calibration uses official public API v2 records with clickable forum URLs and cannot predict acceptance. Scientific-image audits bind originals/processed files/transformations and label suspicious signals `REVIEW_REQUIRED`, never as fraud findings.
8. AI-reviewer work has two user-visible modes. `ai_robustness` audits manipulation and sensitivity without optimizing. The optional `ai_optimize_*` workflow is activated only by `selected_by=user`; it binds current official venue reviewer guidance, generates/registers evidence-bounded presentation candidates, evaluates every candidate with the same multi-model panel, and selects by robust normalized score. It may optimize evidence/novelty/scope framing, truthful title presentation, reviewer navigation, and language polish. Both modes reject hidden instructions, fabricated prestige, changed citations/numbers/formulas, or deletion of valid limitations, ethics, risks, criticism, and negative results.
9. For scientific figures, the main agent chooses 2-3 roles. Final-size review must cover occlusion, balanced space use, text/line and panel alignment, margins/gutters, and the exact current venue style when a target is known.
10. For long research work, follow [research-progression-contract.md](references/research-progression-contract.md): short verifiable stages, incremental durable evidence and progress updates, no arbitrary whole-task timeout, and no retry after unknown completion without inspecting receipts.
11. Limitations and possible ethics omissions are user-decision checklists. Preserve uncertainty and do not fabricate evidence.
12. Structured ingestion, claim evidence, preregistration, statistics,
   reproducibility, active-review prioritization, and record-health checks use
   executable integrity subroutes; method changes invalidate their receipts.
13. Collision search has no wall-clock research deadline. `attempt_timeout_seconds` applies to one transport attempt only. When `run_novelty_search` returns `IN_PROGRESS`, immediately report its factual linked stage results, preserve the checkpoint, and continue calling it. A failed required unit returns `ACTION_REQUIRED`: retry it, register admissible manual evidence, or submit an explicit main-agent `blocker_decision` covering every failed required unit. Stop only when coverage completes, that factual blocker is saved and surfaced, or the user explicitly sets a budget, time limit, or stop instruction.
14. Education and educational-technology work uses the explicit registered profile. Expose official venue and method links, but live-check the exact venue/year/track/stage before adopting structure or style. Preserve learner/classroom/teacher/school/institution levels; do not flatten clustered, longitudinal, weighted, psychometric, or qualitative data.
15. Before result analysis, freeze `metrics_action=plan`. The core analyzer accepts independent-run CSV data, enforces legal ranges and candidate budgets, and binds data/method/experiment hashes. `metrics_action=optimize` may compare only observed candidates on the frozen optimization split. It never uses the final test split for selection; scalar ranking requires user-supplied weights and reference scales and still returns `USER_SELECTION_REQUIRED`.
16. Before work that would otherwise require an external LLM API, call `research_design delegation_action=plan`. Default to one available native entry/economy subagent, serial execution, and `low` reasoning. If unavailable, use `main_agent_local`; never silently fall through to an API. An API exception requires the user's explicit provider choice or a registered cross-provider protocol. Submit a project-local hash-bound artifact receipt. Same-host or same-model subagents are assistance, not independent multi-model evidence. See [the delegation contract](docs/SUBAGENT_DELEGATION.md).

See [dependency details](references/dependencies.md) for package, component, and degradation boundaries.
