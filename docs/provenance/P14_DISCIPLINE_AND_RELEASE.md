# P14 cross-discipline and release verification

Date: 2026-08-15

Status: `LOCAL_GATES_PASS`

## Scope

P14 adds field coverage analysis, automatic first-use initialization for
unregistered disciplines, humanities/history literature-form boundaries,
hash-bound novelty integration, and GitHub publication engineering.

## Frozen boundaries

- 15 top-level MCP tools and all legacy action enums remain unchanged.
- A method change still invalidates the old receipt before any protected
  output; a discipline registry/profile/evidence change now does the same.
- Literature, journal, book, catalog, and primary-source outputs require
  clickable HTTPS evidence links.
- Journal discovery candidates are not rankings or index-membership evidence.
- SkillOpt cannot change evidence, initialization, rerun, hyperlink, module
  budget, or 512 MiB serial/no-GPU gates.

## SkillOpt

Four serial Optuna TPE rounds completed with 12 trials per round. All four were
accepted at objective `1.2083333333333333`; each positive and negative case
passed, the three-module maximum held, and hard gates were excluded. Detailed
local trial evidence is stored under `evals/p14-skillopt/` and is intentionally
excluded from public packages.

## Verification ledger

Focused P14 tests: PASS (6 tests). A live history initialization passed all
five anonymous routes and produced 20 journal candidates, 8 book/edition leads,
and 8 catalog/primary-source leads with HTTPS provenance. The whole-plugin
incremental suite passed 69/69 files. The real Lean regression passed 6/6 in
323.367 seconds with a 460,664,832-byte aggregate peak, 304 successful working-
set trims, and zero trim failures. Python compilation, repository validation,
plugin validation, and all four root/focused Skill validations pass.

Public archives are built only after these gates. Their final byte sizes and
SHA-256 digests are published in the release's separate checksum asset so the
archives do not attempt to contain self-referential hashes. GitHub transport is
a delivery check, not research-evidence validation.
