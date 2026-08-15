---
name: research-guard
description: Evidence-bounded cross-disciplinary academic research from field initialization and idea exploration through novelty checks, cited writing, executable Lean/Pint/SymPy/Z3/numerical formula verification, OpenReview calibration, scientific-image integrity, experiments, reproducibility, figures, and manuscript audit. Use for research ideas, literature, citations, method changes, humanities or STEM research, paper writing/auditing, equations, experiments, reviews, or academic images.
---

# Research Guard

This package is both a traditional Skill and a Codex plugin. Run the installer
only from an extracted release directory where both `RELEASE_MANIFEST.json`
and `scripts/install.ps1` are present:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
```

If those two release files are absent, this is the already-registered bootstrap
Skill. Do not retry a relative installer; continue with the absolute first-load
inventory command below. The release installer has already hash-verified and
installed the plugin and core runtime.

## First-load inventory

On the first load, run the dependency inventory using the bundled runtime and
show the feature list once. This is read-only and does not block core work:

```powershell
& "$env:USERPROFILE\.research-guard\runtime\python\python.exe" "$env:USERPROFILE\plugins\research-guard\scripts\dependency_manager.py" inventory
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

1. Analyze the user's discipline before deep work. If it is unregistered, warn that the first build may take minutes, query official public sources, and persist a hash-bound profile. History/humanities must include books, editions, archives, and primary-source boundaries, not journals alone.
2. Classify the user's fields and route searches to suitable scholarly sources.
3. Register a canonical method before novelty claims. Every method or bound discipline-profile change invalidates the prior receipt and forces a fresh collision search.
4. Every literature item, citation, journal candidate, or collision result must include a clickable HTTPS primary-record or DOI link.
5. Choose only 2-3 audit roles, never above `high` effort. Verify current web facts, numeric comparisons, code, and experiments where relevant.
6. Equation assistance requires one whole-manuscript Lean file, followed by `paper_audit verification_action=cross_verify`. Report five distinct records: Lean logic, Pint dimensions, SymPy equivalence, Z3 constraint satisfiability, and numerical/protocol legality. All symbols must be defined and used; numerical cases outside the frozen paper protocol fail before execution. Lean is optional and requires a user decision. If the user selects `not_now`, run only the other four executable checks, report Lean as `NOT_RUN_BY_USER`, return `DEGRADED`, and keep final manuscript submission blocked.
7. OpenReview calibration uses official public API v2 records with clickable forum URLs and cannot predict acceptance. Scientific-image audits bind originals/processed files/transformations and label suspicious signals `REVIEW_REQUIRED`, never as fraud findings.
8. Limitations and possible ethics omissions are user-decision checklists. Preserve uncertainty and do not fabricate evidence.
9. Structured ingestion, claim evidence, preregistration, statistics,
   reproducibility, active-review prioritization, and record-health checks use
   executable integrity subroutes; method changes invalidate their receipts.

See [dependency details](references/dependencies.md) for package, component, and degradation boundaries.
