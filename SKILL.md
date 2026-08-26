---
name: research-guard
description: Evidence-bounded cross-disciplinary academic research with executable instruction adherence, authorized local-resource direction exploration, resource-aware task planning, field initialization, frontier Skill research, optional Skill portability and ordered-composition evidence, idea exploration, novelty checks, cited writing, Lean/Pint/SymPy/Z3 verification, constructive numerical constraint intervals and joint anchors, OpenReview calibration, scientific-image integrity, experiments, reproducibility, figures, manuscript audit, and an optional localhost Research Console. Use for multistep research work, research ideas, direction finding, literature, citations, method changes, specialist Skill discovery/evaluation, transfer or composition claims, resource-constrained workflows, humanities or STEM research, paper writing/auditing, equations, experiments, reviews, academic images, or an explicitly requested visual Codex interface.
---

# Research Guard

This package is both a traditional Skill and a Codex plugin. For a public
release, run an installer from an extracted release directory with
`RELEASE_MANIFEST.json`. Windows x64 uses the bundled offline runtime; Linux
x64 and macOS x64/arm64 create an isolated venv from Python 3.11+:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
# Linux/macOS
sh scripts/install.sh
```

For ordinary research development, edit this one source tree in place and use
the development build mode; it does not clone a version, create a ZIP, pin raw
components, or calculate source-file hashes:

```powershell
python -X utf8 scripts/build_modular_package.py --platform windows-x64 --mode development
python -X utf8 scripts/build_public_package.py --mode development
```

The release path remains available when a distributable archive is explicitly
needed. Development and release are deliberately separate behaviours.

If `RELEASE_MANIFEST.json` is absent, do not run the release installer against a
development checkout: use the in-place development build above, or treat an
already-installed copy as the already-registered bootstrap Skill and continue with the absolute
first-load inventory command below. Do not retry a relative installer. The
release installer has already validated and installed the plugin and core runtime
when it was used.

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

`install` and `update` are one idempotent operation (the latter is an alias).
Each optional component is an independently resumable short transaction;
`resume` and `cancel` operate on unfinished units without a repository-wide
lock. Use `clean` to remove named generated session/cache paths and
`hard-clean` to remove all generated session caches for a fresh exploration;
both report bytes and every removal, and can be rerun after interruption.

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
17. For resource-sensitive multi-stage work, call `research_design resource_plan_action=inventory`, then register a main-agent-selected DAG with `resource_plan_action=plan`. Simple one-response work is exempt. Use only the registered serial CPU profiles; GPU remains disabled. Host inventory is not process entitlement, missing estimates remain unknown, and download/disk/time/cost budgets require `budget_selected_by=user`. If a `managed_standard` stage has a fresh user-selected frozen reproducibility plan whose outputs exactly match the task artifacts, use `resource_plan_action=execute`; this delegates to the existing integrity executor and records its process-guard telemetry and execution hash. Never complete such a linked task through caller-reported telemetry. Other owners use `record`. For an interrupted linked stage, `execute` may adopt an already persisted valid final receipt without rerunning the command; if no final receipt exists, automatic replay is forbidden. Managed execution is offline-only and unavailable under a user disk-write budget because those properties are not fully instrumented. See [resource-aware task planning](docs/RESOURCE_AWARE_TASK_PLANNING.md).
18. After the user explicitly authorizes direction finding, use `research_design direction_action=plan` before proposing directions. It freezes the redacted local resource snapshot; then register 5-15 unranked candidates, activate each exact revision, bind only managed coarse-test PASS receipts with recomputed protocol legality, and bind a strict complete collision-search receipt with HTTPS literature links. A method/protocol/range/tracked-file revision clears both evidence classes and any active choice set while retaining history. Finalize exactly five eligible directions in neutral registration order and return `USER_SELECTION_REQUIRED`; never name a winner. See [local-resource direction exploration](docs/DIRECTION_EXPLORATION.md).
19. Before the first project mutation in a multistep request, the main agent must call `research_design instruction_action=register` with the complete request, atomic mandatory requirements, acceptance criteria, dependencies, required evidence kinds, and forbidden substitutions. Record outcomes only with current evidence. Changed file/JSON evidence invalidates PASS; only an explicit user message can waive an item. Call `verify` before claiming completion. `ACTION_REQUIRED` and `USER_DECISION_REQUIRED` block Stop; `BLOCKED` permits only a factual blocked handoff and is never completion. Simple one-response work is exempt. See [the instruction-adherence contract](docs/INSTRUCTION_AND_NUMERICAL_CONTRACT.md).
20. When a user asks for legal numeric values, parameter intervals, or constructive numerical support, plan `paper_audit` with `audit_features.constructive_numerical=true` and select `methodology_statistics` or `formal_math_lean`. Call `numerical_action=construct` with source-located variables and linear rational equations/inequalities. Keep Pint dimensions, SymPy form/rank, Z3 satisfiability, and exact protocol rechecks distinct. Label derived intervals as marginal projections; never imply their Cartesian product is feasible. Return only complete jointly feasible anchors rechecked against every bound, type, relation, and binary64 risk. Anchors are design points, not observations, optima, or automatic recommendations. Unsupported nonlinear/specialist systems remain `NOT_CERTIFIED`.
21. The Research Console is an optional, separately installed presentation adapter. It adds no research owner, MCP tool, classifier, model, or PASS state and is excluded from every core package. The UI may expose visible user-selected focus preferences, bounded to three; the main Codex agent must still read the complete request and select the necessary modules. It must remain localhost-only, use the installed Codex CLI and plugin, stream factual states without a whole-task timeout, and reuse the 512 MiB aggregate resource guard. Missing UI prerequisites fail preflight or leave the UI `NOT_RUN`; they never trigger an external API or dependency download. See [the Research Console contract](docs/RESEARCH_CONSOLE_UI.md).
22. For a newly discovered professional Skill, quarantine and inspect it as a research component. Surface review findings for human judgment; do not turn ordinary research exploration into a security or attacker audit. The existing 2-3 Optuna rounds are trigger/file-selection proxies, not performance evidence. Before `domain_skill_action=admit`, use `frontier_skill_action=plan` to freeze the actual target agent/harness, exact Skill ID/repository/commit, disjoint train/validation/heldout cases, utility and research-quality metrics, and exactly 2-3 validation rounds. Record current primary-paper and immutable implementation/specification links, preserve parent-linked rejected hypotheses, submit project-local JSON trial artifacts, and run one locked heldout evaluation only after validation passes. Finalization returns `HUMAN_REVIEW_REQUIRED`; admission additionally requires exact identity, candidate digest, canonical owner, and overlap-decision matches. Never execute third-party Skill code. See [the frontier Skill contract](docs/FRONTIER_SKILL_RESEARCH.md).
23. Do not infer Skill portability from a single P24 target. Only when the user or output makes a cross-model, cross-harness, or cross-task transfer claim, use the optional `skill_portability_action=plan`. Bind the exact finalized P24 artifact, use 2-12 explicit cells with fresh non-P24 cases and exactly 2-3 replicates, preserve executor/evidence-family dependence, and report every cell separately. Negative transfer and research-quality regression cannot be averaged away; `universal_claim_allowed` is always false. The core records external artifacts but never executes, applies, installs, or admits a Skill. See [the Skill portability contract](docs/SKILL_PORTABILITY.md).
24. Do not infer that multiple Skills compose safely or synergistically. When the user or output makes a joint-value or ordering claim for 2-3 Skills, use the optional `skill_composition_action=plan`. The main agent selects exact finalized P24 artifacts, target/control orders, target, fresh cases, research-quality metrics, and 2-3 replicates. Each replicate must record no-Skill, every single Skill, target order, and control order with unique execution receipts. Preserve `NO_COMPOSITION_GAIN`, `INTERFERENCE`, research-quality regression, every order effect, and source-located cross-Skill capability paths; never average them away. A positive claim stays limited to the exact recorded order, and universal or order-invariant claims are always forbidden. The core never executes, installs, applies, optimizes, or admits a Skill. See [the Skill composition contract](docs/SKILL_COMPOSITION.md).

25. Research-development mode is exploratory, not an operations or threat-modeling exercise. Do not add safety/security audits, attacker assumptions, unusual repeated privilege checks, or fail-closed/fail-fast gates merely because a workflow is incomplete. Keep observability, expose the actual boundary or state inconsistency, and continue with a named degradation when the research objective remains meaningful. The exact user instruction is: “敏感哈希纯属神经病，镜像构建也要简化，不要神经病一样pin版本，原材料组件和你的构建无关，它就在那里，每一次构建产物的哈希如果能被攻击者拿到，那你防ta防什么狗屁用？我们现在只是科研开发，你考虑运维有什么狗屁用，谁会攻击我？” This does not waive citation, source-locator, formula, numerical, code, experiment, or manuscript-evidence checks; it keeps those checks focused on research validity rather than security theatre. The main agent follows the same boundary while maintaining this Skill: direct source edits, short checkpoints, and focused tests; no version mirror unless a release is explicitly requested.

26. When build/install/clean state is interrupted, preserve the short-unit receipt and continue from the last completed unit. Do not create a long transaction for a simple task, and do not claim completion from a timeout alone. A single inode/path is the unit of lifecycle state; source components and build outputs are not copied into versioned mirrors during development.

27. When the user asks for a paper main line, research question, or title, do not
    let collision avoidance collapse the idea into a tiny local feature. Use the
    `language_assist` `spine_action` route: record the local observation, lift it
    to a macro problem, state one unifying method/mechanism, and write at least
    two cross-context predictions plus falsifiers before drafting five unranked
    macro/meso/local title candidates. The local case is evidence for the
    broader question, not the ceiling of the contribution. Collision search is
    then a differentiation and evidence step on the exact method revision; a
    nearby paper prompts a sharper mechanism or higher-level framing, not an
    automatic retreat to a narrower question. Every literature link remains a
    clickable HTTPS primary record, and every semantic method change still
    invalidates the old collision receipt and requires a complete rerun. The
    user chooses the final title or framing; the Skill never declares a winner.

See [dependency details](references/dependencies.md) for package, component, and degradation boundaries.
