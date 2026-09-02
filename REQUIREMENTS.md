# Requirements and dependency contract

This document is the complete installation and runtime dependency map for
Research Guard. End users install one release archive for their operating
system. Every archive contains the same Skill/plugin source and feature
contracts; runtime delivery differs by platform.

## 1. Host requirements

| Requirement | End-user contract |
|---|---|
| Operating system | Windows x64; Linux x64; macOS x64 or arm64 |
| Agent | A local-file/command-capable agent that can load a traditional `SKILL.md`; Codex can also register the included plugin, hooks, and MCP server |
| Administrator rights | Not required for the default per-user installation; an existing environment may have its own policy |
| System Python | Windows offline package: not required. Linux/macOS: CPython 3.11 or newer with `venv` and `pip` |
| Node.js / MCP SDK | Not required; MCP uses Python standard-library JSON-RPC over stdio |
| GPU | Not used |
| Runtime memory policy | At most 512 MiB aggregate task-owned working set, one worker, CPU only |
| Resource task planner | Included in the core runtime; no scheduler, model, database, or additional package is required |
| Optional Research Console UI | A current logged-in Codex CLI, installed/enabled Research Guard 0.7.0+, the core registered Python 3.11+ with `psutil`, and a modern local browser; each turn disables other MCP servers and requires/approves only the canonical local Research Guard server; no Node.js or web framework |
| Free memory before a managed task | At least 768 MiB; the owned child tree stops if machine free memory falls below 512 MiB |
| Release download | Windows offline artifact: approximately 300 MB with the current audited payload set. Linux/macOS: source+manifest archive followed by displayed core dependency downloads. The release page and platform checksum file are authoritative |

Install from the platform-matched release. The Windows asset is
[`research-guard-windows-x64-modular.zip`](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-windows-x64-modular.zip),
not GitHub's automatic source archive. Verify the Windows asset against
[`SHA256SUMS.txt`](https://github.com/dltsum/research-guard/releases/latest/download/SHA256SUMS.txt)
and Linux/macOS assets against
[`SHA256SUMS-posix.txt`](https://github.com/dltsum/research-guard/releases/latest/download/SHA256SUMS-posix.txt).

## 2. What the release archives contain

The Windows x64 archive contains the audited binary payloads below. Linux and
macOS archives omit every Windows binary and create
`~/.research-guard/runtime/python` as an isolated venv from the supported system
Python. Their installer tries the Tsinghua PyPI mirror first and then official
PyPI; the official fallback uses the optional installer-selected proxy when set,
or connects directly when it is not.

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
| psutil | 7.0.0 | Linux/macOS physical-memory and owned-process-tree telemetry |
| SymPy | 1.14.0 | Symbolic/algebraic equivalence |
| z3-solver | 5.0.0.0 | Parameter-constraint satisfiability |
| PyYAML | 6.0.3 | Structured configuration and validation |

Executable instruction adherence adds no dependency: it uses the standard
library for canonical JSON, SHA-256, atomic replacement, and append-only event
verification. Constructive numerical audit reuses the bundled Pint, SymPy, and
Z3 distributions. Its certified path is deliberately limited to structured
linear rational equations/inequalities; it computes exact marginal projections
and complete jointly feasible anchors, then rechecks every anchor with exact
rationals and binary64 safety checks. Unsupported nonlinear or specialist
models remain `NOT_CERTIFIED` and do not trigger an automatic solver install.

Resource-aware DAG planning uses Python's standard library plus the already
bundled `psutil` fallback. It adds no distributed scheduler or model runtime.
Its `managed_standard`, `managed_install`, and `managed_lean` profiles reuse the existing process
guard; `llm_assistance` reuses the existing delegation contract.

The runtime also contains the audited transitive distributions recorded in
[`assets/runtime-distributions.json`](assets/runtime-distributions.json):
alembic 1.19.1, colorama 0.4.6, colorlog 6.12.0, contourpy 1.3.3,
cycler 0.12.1, fonttools 4.63.0, greenlet 3.5.5, kiwisolver 1.5.0,
Mako 1.4.1, MarkupSafe 3.0.3, packaging 26.3, pyparsing 3.3.2,
python-dateutil 2.9.0.post0, six 1.17.0, SQLAlchemy 2.0.52, tqdm 4.70.0,
and typing_extensions 4.16.0.

For source development, use Python 3.11 or newer and the direct dependencies in
[`requirements-dev.txt`](requirements-dev.txt):

```powershell
python -m pip install --disable-pip-version-check -r requirements-dev.txt
```

The development builders accept `--mode development` and inspect the current
checkout in place. This mode does not copy a version, hydrate third-party
payloads, pin raw source components, or calculate source-file hashes. The exact
versions above remain a reproducible runtime snapshot for release/CI; they are
not a requirement to create a development inspection receipt. See the Python
Packaging User Guide on abstract runtime requirements versus pinned environment
files: <https://packaging.python.org/en/latest/discussions/install-requires-vs-requirements/>.

The source checkout is not the end-user installer because it intentionally
omits the audited binary payloads and generated `RELEASE_MANIFEST.json`.
Maintainers building the Windows archive from Git first run
`python -X utf8 scripts/hydrate_release_payloads.py`. The committed
[`assets/payload-bootstrap.json`](assets/payload-bootstrap.json) pins one prior
project release by byte count and SHA-256; hydration then cross-checks every
payload against both release and payload manifests. The Windows builder fails
closed if a payload is missing, altered, or unregistered. This maintainer-only
step does not change the one-archive end-user installation path.

## 4. Optional non-Python components

| Component ID | Enables | Download after package install | Installed estimate | Missing-component behavior |
|---|---|---:|---:|---|
| `portable-git` | Controlled remote domain-Skill staging; Lean installer prerequisite | 0 if using bundled payload or a verified existing Git | 90–180 MB | Ask `reuse/install/not_now`. `not_now` keeps anonymous GitHub/SkillsHub discovery, but blocks remote Skill staging/admission and Lean installation |
| `tex-basic` | Real TeX-to-PDF compilation and venue-template compile smoke | 0 for the bundled installer; approved extra packages may use TUNA CTAN | 0.9–1.6 GB | Ask first. `not_now` runs static TeX source checks only and reports compiler, PDF, layout, fonts, and venue compile as not run |
| `lean-mathlib` | Whole-manuscript Lean proof compilation and formula/parameter coverage | About 0.6–1.6 GB | About 8.5–12.5 GB | Ask first. `not_now` runs Pint, SymPy, Z3, and protocol numerical checks, records Lean as `NOT_RUN_BY_USER`, returns `DEGRADED`, and blocks final manuscript PASS |

Lean is pinned to `leanprover/lean4:v4.33.0`, Mathlib tag `v4.33.0`, and
commit `db584cd6d46c92f209a44c0f1c829460d327499d`. A compatible existing
environment must pass the real import/compile smoke before registration.

On Windows, optional installers use only the hash-audited bundled payloads. On
Linux/macOS, Research Guard detects and validates an existing system Git, TeX,
or Lean environment. If absent, it asks the user to install with the host
package manager and then select `reuse_existing`, or to choose `not_now`.
Research Guard does not silently run `apt`, `dnf`, `brew`, or another privileged
package manager.

### Optional Research Console UI

The visual UI is distributed only as
[`research-guard-ui-addon.zip`](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-ui-addon.zip)
with a separate
[`SHA256SUMS-ui.txt`](https://github.com/dltsum/research-guard/releases/latest/download/SHA256SUMS-ui.txt).
It is excluded from every core archive and is never downloaded on first load.
Its deterministic builder enforces a 25 MiB archive ceiling; the release asset
size and checksum are authoritative.

The add-on reuses the registered core Python and requires its existing `psutil`.
It also requires a logged-in Codex CLI whose machine-readable interface supports
`codex exec --json`, `codex exec resume`, `codex plugin list --json`, `codex mcp
list --json`, and per-server MCP approval mode, plus an
installed and enabled Research Guard plugin. It adds no Python distribution,
Node.js package, browser framework, model, TeX/Lean component, or external LLM
API. Installation is per user, versioned, checksum-bound, and download-free.

If a prerequisite is absent, UI preflight fails explicitly. The degradation is
to use Research Guard from the normal agent/Codex interface; the missing UI is
`NOT_RUN`, while all underlying core capabilities remain available subject to
their own dependencies. Complete install, security, resource, packaging, and
maintenance instructions are in
[`docs/RESEARCH_CONSOLE_UI.md`](docs/RESEARCH_CONSOLE_UI.md).

## 5. Optional external integrations

These are not silently installed and are not required for core operation.

The AI-reviewer robustness audit and active-adaptation selector use the bundled
standard-library runtime and primary-record registry; neither installs a reviewer
model nor makes a hidden model call. Robustness `model_evaluations` are sensitivity
evidence only. Active adaptation requires explicit user opt-in and externally run,
hash-bound `optimization_model_evaluations` for the same panel of at least two
reviewer models across the baseline and every candidate.

For any LLM-assisted research step, the host should expose a native subagent
facility. Research Guard defaults to one serial entry/economy subagent at low
reasoning and needs no model download or API credential. If the host has no
subagent, the main agent completes the bounded task locally. An external LLM API
is never an automatic dependency: it is an explicit user/protocol exception,
and its provider/model output must be recorded through the delegation receipt.

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

```sh
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
- `install`: on Windows, install the pinned/bundled component after explicit
  approval; on Linux/macOS, ask the user to install it with the host package
  manager and then register the detected environment;
- `not_now`: write an append-only decision receipt and use only the declared
  degradation.

The MCP mutations require `dependency_selected_by: "user"`; the equivalent CLI
commands require `--confirmed-by-user`. These fields may be set only after the
user makes the displayed choice.

`install` and `update` are aliases for the same idempotent optional-component
operation. A component is one short transaction with a JSON receipt; `resume`
and `cancel` continue or stop unfinished units. `clean` removes named generated
session/cache paths, while `hard-clean` additionally removes generated run,
receipt, and transaction caches but retains source, conclusions, and installed
components. Both cleanup modes report each path and released bytes and can be
rerun after interruption. The POSIX installer and PowerShell installer expose
the same commands without requiring a release manifest for cleanup.

A selected but failed/incomplete installation is not a degradation; it is an
explicit error. A declined capability is never reported as PASS. The user can
later enable it by making a new explicit `reuse` or `install` choice.

## 7. Network and storage policy

- Prefer official anonymous scholarly APIs and domestic mirrors.
- Access domestic sources directly. Foreign sources use the optional
  credential-free proxy selected during installation (or the explicit
  `RESEARCH_GUARD_FOREIGN_PROXY` process setting); when neither is configured,
  they use a direct route. The installer never imports ambient
  `HTTP_PROXY`/`HTTPS_PROXY` values into its saved configuration.
- Never persist proxy credentials, provider tokens, papers, or private research
  data in dependency receipts.
- Store installed runtime state and append-only dependency receipts below
  `%USERPROFILE%\.research-guard` on Windows or `~/.research-guard` on POSIX,
  unless `RESEARCH_GUARD_HOME` is set.
- Store the plugin below the user `plugins/research-guard` directory and the
  traditional bootstrap Skill below `$CODEX_HOME/skills/research-guard` (or the
  platform-equivalent default `~/.codex/skills/research-guard`).
- Store project-specific task plans, stage transitions, and artifact hashes
  below the project's `.research-guard/resource-task-plans/` directory. These
  files contain no hostname or absolute project path and should be handled with
  the same confidentiality as the project itself.

For licenses and provenance, see
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and
[`assets/payload-manifest.json`](assets/payload-manifest.json).
