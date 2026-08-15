# Changelog

All notable release-level changes are recorded here. Development evidence and
optimization details live under `docs/provenance/`.

## Unreleased

## 0.6.2 - 2026-08-15

- Removed automatic keyword/small-model selection of disciplines, research
  modules, method-change labels, and paper-audit roles. The main agent now makes
  each semantic choice explicitly; executable code validates and hash-binds it.
- Replaced monolithic novelty-search timing with persistent source-query work
  units, linked stage updates, explicit retries, and no wall-clock research
  deadline.
- Required-source failures now return `ACTION_REQUIRED`. Only the main agent's
  explicit factual-blocker decision, full coverage, or a user-supplied budget or
  stop instruction can end an incomplete search.
- Renamed public operation bounds to `attempt_timeout_seconds` and
  `process_timeout_seconds`, audited every remaining timeout boundary, and
  completed four passing P16 SkillOpt rounds under the 512 MiB resource policy.

## 0.6.1 - 2026-08-15

- Consolidated end-user installation on the single approximately 300 MB
  Windows x64 modular archive and removed the custom source ZIP from releases.
- Added a first-screen copy-paste Agent installation request, deterministic
  checksum-verified manual commands, trigger examples, and a complete root
  dependency document.
- Replaced the global first-load optional-dependency block with executable,
  on-demand `reuse`, `install`, and `not_now` decisions.
- Added receipt-bound degraded TeX and formula paths. Declined TeX performs
  static checks only; declined Lean runs Pint, SymPy, Z3, and protocol-numeric
  checks but cannot produce a final formula or manuscript PASS.

## 0.6.0 - 2026-08-15

- Added seven broad and fourteen specialized discipline profiles, including
  humanities/history contracts for books, editions, archives, catalogs, and
  primary-source discovery.
- Added automatic, bounded first-use initialization for unregistered fields
  through current anonymous OpenAlex, Crossref, and DOAJ routes.
- Bound field registry, live profile, and source evidence hashes into the
  novelty plan so profile changes force a complete collision rerun.
- Added a typed `research_design.discipline_action` subroute while preserving
  all 15 top-level tools and legacy action enums.
- Completed four accepted P14 SkillOpt rounds and fixed multi-owner conflict
  evaluation across every selected router module.
- Added publication governance, support, discipline documentation, and a
  GitHub tag-release workflow.

## 0.5.0 - 2026-08-14

- Added separate Lean, Pint, SymPy, Z3, and protocol-admitted numerical formula records.
- Added official OpenReview review calibration without acceptance prediction.
- Added hash-bound scientific-image integrity audit and expert per-flag review.
- Bundled Pint, SymPy, and z3-solver into the offline core runtime while preserving the 512 MiB serial/no-GPU contract.

- Prepared the project for a public GitHub repository.
- Replaced whole-suite execution with serial, hash-resumable test and SkillOpt
  units under a 512 MiB task-owned memory ceiling.
- Added standard 384+128 MiB and Lean 464+48 MiB working-set profiles, with
  descendant accounting, 10 ms sampling, and Lean working-set trimming.
- Added hash-bound candidate configuration testing before SkillOpt admission.
- Converted package creation to bounded, streaming workers.

## 0.4.0 - 2026-08-14

- Added structured paper ingestion, claim-evidence graphs, extended collision
  families, preregistration, statistical recomputation, managed
  reproducibility, human-only active review, and record-health monitoring.
- Added a modular Windows x64 migration package with first-load component
  selection and an offline core runtime.
- Preserved five canonical Skills, 15 MCP tools, exact literature hyperlinks,
  mandatory method-change invalidation, Lean formula checks, venue evidence,
  academic figures, language safeguards, and multi-role paper audit.
