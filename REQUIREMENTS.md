# Requirements and dependency contract

This document is the complete installation and runtime dependency map for
Research Guard. End users install one Windows x64 release ZIP. There is no
separate minimal/full package.

## 1. Host requirements

| Requirement | End-user contract |
|---|---|
| Operating system | Windows x64 with Windows PowerShell 5.1 or PowerShell 7 |
| Agent | A local-file/command-capable agent that can load a traditional `SKILL.md`; Codex can also register the included plugin, hooks, and MCP server |
| Administrator rights | Not required for the default per-user installation; an existing environment may have its own policy |
| System Python | Not required; the release installs its own isolated Python 3.14.3 runtime |
| Node.js / MCP SDK | Not required; MCP uses Python standard-library JSON-RPC over stdio |
| GPU | Not used |
| Runtime memory policy | At most 512 MiB aggregate task-owned working set, one worker, CPU only |
| Free memory before a managed task | At least 768 MiB; the owned child tree stops if machine free memory falls below 512 MiB |
| Release download | Approximately 303.7 million bytes / 289.6 MiB for v0.6.4; the release asset page and `SHA256SUMS.txt` are authoritative |

Install from
[`research-guard-windows-x64-modular.zip`](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-windows-x64-modular.zip),
not GitHub's automatic source archive. Verify it against
[`SHA256SUMS.txt`](https://github.com/dltsum/research-guard/releases/latest/download/SHA256SUMS.txt).

## 2. What the single ZIP contains

| Payload | Bytes in current audited payload manifest | Installed/expanded estimate | Selection |
|---|---:|---:|---|
| Python 3.14.3 core runtime | 112,939,453 | 240–550 MB | Installed offline by the package installer |
| MinGit 2.55.0.3 x64 | 38,791,206 | 90–180 MB | Optional; installed or reused only after user choice |
| MiKTeX Basic 25.12 x64 installer | 148,882,184 | 0.9–1.6 GB | Optional; run only after user choice |
| Elan 4.2.3 bootstrap | 2,389,007 | Small bootstrap; Lean cache is separate | Used only after the user chooses Lean installation |
| Plugin, Skills, hooks, MCP, catalogs, templates, licenses, and tests | Remainder | Small compared with the runtimes | Installed with the package |

The archive does **not** contain an installed Lean/Mathlib tree, installed TeX
tree, model weights, paper PDFs, cached venue pages, external parser stacks, or
third-party domain Skills. Git source also excludes `assets/payloads/`, so
`git clone` stays small and is development-only.

## 3. Bundled Python dependencies

These distributions are already inside the isolated core runtime. Users do not
need to run `pip install` for normal operation.

| Distribution | Pinned version | Primary use |
|---|---:|---|
| matplotlib | 3.10.8 | Statistical and publication figures |
| numpy | 2.4.4 | Numerical and plotting arrays |
| Pillow | 11.3.0 | Raster/image inspection and export |
| pypdf | 6.15.0 | PDF checks |
| networkx | 3.6.1 | Evidence and knowledge graphs |
| optuna | 4.9.0 | Bounded 2–3 round SkillOpt |
| Pint | 0.25.3 | Dimensional compatibility |
| SymPy | 1.14.0 | Symbolic/algebraic equivalence |
| z3-solver | 5.0.0.0 | Parameter-constraint satisfiability |
| PyYAML | 6.0.3 | Structured configuration and validation |

The runtime also contains the audited transitive distributions recorded in
[`assets/runtime-distributions.json`](assets/runtime-distributions.json):
alembic 1.19.1, colorama 0.4.6, colorlog 6.12.0, contourpy 1.3.3,
cycler 0.12.1, fonttools 4.63.0, greenlet 3.5.5, kiwisolver 1.5.0,
Mako 1.4.1, MarkupSafe 3.0.3, packaging 26.3, pyparsing 3.3.2,
python-dateutil 2.9.0.post0, six 1.17.0, SQLAlchemy 2.0.52, tqdm 4.70.0,
and typing_extensions 4.16.0.

For source development, use Python 3.14 and the exact direct dependencies in
[`requirements-dev.txt`](requirements-dev.txt):

```powershell
python -m pip install --disable-pip-version-check -r requirements-dev.txt
```

The source checkout is not the end-user installer because it intentionally
omits the audited binary payloads and generated `RELEASE_MANIFEST.json`.

## 4. Optional non-Python components

| Component ID | Enables | Download after package install | Installed estimate | Missing-component behavior |
|---|---|---:|---:|---|
| `portable-git` | Controlled remote domain-Skill staging; Lean installer prerequisite | 0 if using bundled payload or a verified existing Git | 90–180 MB | Ask `reuse/install/not_now`. `not_now` keeps anonymous GitHub/SkillsHub discovery, but blocks remote Skill staging/admission and Lean installation |
| `tex-basic` | Real TeX-to-PDF compilation and venue-template compile smoke | 0 for the bundled installer; approved extra packages may use TUNA CTAN | 0.9–1.6 GB | Ask first. `not_now` runs static TeX source checks only and reports compiler, PDF, layout, fonts, and venue compile as not run |
| `lean-mathlib` | Whole-manuscript Lean proof compilation and formula/parameter coverage | About 0.6–1.6 GB | About 8.5–12.5 GB | Ask first. `not_now` runs Pint, SymPy, Z3, and protocol numerical checks, records Lean as `NOT_RUN_BY_USER`, returns `DEGRADED`, and blocks final manuscript PASS |

Lean is pinned to `leanprover/lean4:v4.33.0`, Mathlib tag `v4.33.0`, and
commit `db584cd6d46c92f209a44c0f1c829460d327499d`. A compatible existing
environment must pass the real import/compile smoke before registration.

## 5. Optional external integrations

These are not silently installed and are not required for core operation.

The AI-reviewer robustness audit and active-adaptation selector use the bundled
standard-library runtime and primary-record registry; neither installs a reviewer
model nor makes a hidden model call. Robustness `model_evaluations` are sensitivity
evidence only. Active adaptation requires explicit user opt-in and externally run,
hash-bound `optimization_model_evaluations` for the same panel of at least two
reviewer models across the baseline and every candidate.

| Integration | Approximate external size | Core fallback |
|---|---:|---|
| Docling, GROBID, Marker, or separately licensed MinerU | 1–12 GB installed, backend-dependent | Accept user-supplied text/normalized JSON and state missing layout/table/formula/OCR locators |
| SciPy/statsmodels advanced statistics | 150 MB–1.5 GB installed | Use bundled core recomputation; mark extended distributions, robustness diagnostics, and independent oracle not run |
| ASReview specialist UI/backend | 0.4–3 GB installed | Use bundled human-owned screening prioritizer; omit specialist UI/simulation/models |
| Venue templates and extra TeX packages | Venue-dependent | Acquire only the exact official venue/year/track/stage asset after user-approved network access |

Any integration with separate licenses, model terms, credentials, or
subscription access requires a project-level user decision. User-supplied
official exports are accepted for sources that do not support anonymous access.

## 6. On-demand decision protocol

Loading the Skill never downloads or compiles an optional component. The hook
and MCP route detect which requested feature needs which component. An agent
must inspect one component before acting:

```powershell
python scripts/dependency_manager.py need lean-mathlib
```

The installed plugin can expose the same operation through the existing
`research_design` MCP tool:

```json
{
  "action": "status",
  "project_root": ".",
  "dependency_action": "need",
  "dependency_component": "lean-mathlib"
}
```

The result is machine-readable and includes `status`, detected environments,
download/installed byte estimates, prerequisite, choices, and degradation. The
only valid follow-up actions are:

- `reuse`: verify and register a compatible existing environment;
- `install`: install the pinned/bundled component after explicit approval;
- `not_now`: write an append-only decision receipt and use only the declared
  degradation.

The MCP mutations require `dependency_selected_by: "user"`; the equivalent CLI
commands require `--confirmed-by-user`. These fields may be set only after the
user makes the displayed choice.

A selected but failed/incomplete installation is not a degradation; it is an
explicit error. A declined capability is never reported as PASS. The user can
later enable it by making a new explicit `reuse` or `install` choice.

## 7. Network and storage policy

- Prefer official anonymous scholarly APIs and domestic mirrors.
- Access domestic sources directly. Use `127.0.0.1:7897` only when a required
  foreign source is otherwise unavailable.
- Never persist proxy credentials, provider tokens, papers, or private research
  data in dependency receipts.
- Store installed runtime state and append-only dependency receipts below
  `%USERPROFILE%\.research-guard` unless `RESEARCH_GUARD_HOME` is set.
- Store the plugin at `%USERPROFILE%\plugins\research-guard` and the traditional
  bootstrap Skill below `%CODEX_HOME%\skills\research-guard` (or
  `%USERPROFILE%\.codex\skills\research-guard`).

For licenses and provenance, see
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and
[`assets/payload-manifest.json`](assets/payload-manifest.json).
