<!-- research-guard-doc-pair: readme | revision: 2026-08-22.2 -->
# Research Guard

[English](README.md) | [简体中文](README.zh-CN.md)

![Research Guard evidence lifecycle: idea, literature, method gate, analysis, and audited manuscript](assets/readme/research-guard-evidence-lifecycle.png)

Research Guard is a portable academic-research Skill and Codex plugin. It adds
executable MCP routes, hooks, hash-bound receipts, and fail-closed gates to the
full path from idea exploration and literature search to experiment analysis,
writing, figures, formulas, review, and release.

It does **not** prove global novelty, scientific truth, venue acceptance, or
research quality. Every PASS is limited to the recorded sources, artifacts,
hashes, and checks.

## Start here

| I want to… | Start with |
|---|---|
| Let an agent install and verify everything | Copy the request below into the agent |
| Install it myself | Use the checksum-verified commands below |
| Understand a capability before installing | Read “Choose a capability” and the linked documentation |

### Give this to an agent

```text
Install the Research Guard Skill from https://github.com/dltsum/research-guard.
Download the release archive matching this machine, verify it against the
published checksum file, run scripts/install.ps1 on Windows or scripts/install.sh
on Linux/macOS, and validate the traditional Skill, Codex plugin, MCP server,
hook, and core Python runtime. Then tell me to start a new agent session and load
research-guard. Do not install optional Git, TeX, or Lean/Mathlib automatically.
When a requested feature needs a missing component, show reuse-existing,
install-system/install, and not_now with download and installed sizes; execute
only my explicit choice. If I choose not_now, report that check as NOT_RUN,
never PASS.
```

| Platform | Release archive |
|---|---|
| Windows x64, bundled audited Python runtime | [research-guard-windows-x64-modular.zip](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-windows-x64-modular.zip) |
| Linux x64, isolated venv | [research-guard-linux-x64.zip](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-linux-x64.zip) |
| macOS Intel, isolated venv | [research-guard-macos-x64.zip](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-macos-x64.zip) |
| macOS Apple Silicon, isolated venv | [research-guard-macos-arm64.zip](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-macos-arm64.zip) |
| Integrity records | [SHA256SUMS.txt](https://github.com/dltsum/research-guard/releases/latest/download/SHA256SUMS.txt) · [SHA256SUMS-posix.txt](https://github.com/dltsum/research-guard/releases/latest/download/SHA256SUMS-posix.txt) |

The Windows archive remains about 300 MB because it carries the audited core
runtime. Linux and macOS use a supported system Python to create an isolated
venv. Exact Python and non-Python dependencies, download sizes, installed sizes,
reuse rules, and truthful degradation behavior are in
[REQUIREMENTS.md](REQUIREMENTS.md).

On first load, the agent should:

1. show the available capability groups and currently reusable dependencies;
2. ask only when the requested capability actually needs a missing optional
   component; and
3. preserve the requested work through a named degradation when possible, while
   keeping every omitted check visibly `NOT_RUN`.

### Manual, checksum-verified installation

Windows x64:

```powershell
$release = 'https://github.com/dltsum/research-guard/releases/latest/download'
Invoke-WebRequest "$release/research-guard-windows-x64-modular.zip" -OutFile research-guard.zip
Invoke-WebRequest "$release/SHA256SUMS.txt" -OutFile SHA256SUMS.txt
$expected = ((Get-Content SHA256SUMS.txt | Where-Object { $_ -match 'research-guard-windows-x64-modular.zip' }) -split '\s+')[0].ToLowerInvariant()
$actual = (Get-FileHash research-guard.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 mismatch: $actual" }
Expand-Archive research-guard.zip -DestinationPath research-guard-release
powershell -NoProfile -ExecutionPolicy Bypass -File .\research-guard-release\research-guard\scripts\install.ps1
```

Linux x64 or macOS:

```sh
# Set ASSET to research-guard-linux-x64.zip, research-guard-macos-x64.zip,
# or research-guard-macos-arm64.zip.
curl -fLO "https://github.com/dltsum/research-guard/releases/latest/download/$ASSET"
curl -fLO https://github.com/dltsum/research-guard/releases/latest/download/SHA256SUMS-posix.txt
grep " $ASSET$" SHA256SUMS-posix.txt | sha256sum -c -
unzip "$ASSET" -d research-guard-release
sh research-guard-release/research-guard/scripts/install.sh
```

On macOS, use `shasum -a 256` instead of `sha256sum` when GNU coreutils is not
installed. Each installer verifies `RELEASE_MANIFEST.json`, runs serially with
GPU disabled, and installs per user. Every main-branch platform job also builds
and clean-installs its exact archive, then exposes it as a 3-day verified CI archive
in the [CI workflow](https://github.com/dltsum/research-guard/actions/workflows/ci.yml).

## How the guardrail works

The banner depicts the same five-stage contract used by the plugin:

Before the first mutation in a multistep request, the main agent registers the
complete request as atomic requirements with acceptance criteria, dependencies,
required evidence, and forbidden substitutions. The append-only ledger blocks
premature Stop or completion claims if any mandatory item is pending, changed,
or unsupported; it does not replace the main agent's semantic judgment.

1. **Frame the idea.** The main agent explicitly selects the discipline and a
   small set of relevant modules; no keyword classifier or small routing model
   makes that semantic choice.
2. **Build the evidence map.** Literature routes query appropriate public and
   registered scholarly sources, retain source locators, and return clickable
   HTTPS DOI or primary-record links.
3. **Freeze and guard the method.** The method, field profile, query plan, and
   tracked artifacts are hash-bound. Any material method/profile revision
   invalidates the old receipt and forces a complete collision-search rerun.
4. **Execute and verify.** Experiments, metrics, code, formulas, numbers, and
   figures use separate executable checks with explicit resource and protocol
   boundaries.
5. **Audit the manuscript.** The main agent selects only 2–3 relevant audit
   roles, with effort no higher than `high`, and reports facts, claims,
   limitations, and unresolved checks separately.

The illustration contains no claims or formulas; its generation prompt and
visual inspection record are preserved in
[asset-provenance.json](assets/readme/asset-provenance.json).

## Choose a capability

| Say this | What starts | Non-negotiable result |
|---|---|---|
| “Carry out every requested step and prove completion.” | `instruction_action=register`, an atomic requirement ledger, evidence-bearing transitions, and final verification | Registered requirements cannot silently disappear; changed evidence invalidates PASS; only the user can waive an item; a blocked handoff is never completion |
| “Explore this idea and check whether it collides with prior work.” | Explicit discipline selection, idea exploration, multi-source novelty search | Every result has an HTTPS DOI/primary-record link; every method/profile change invalidates the old receipt and forces a complete rerun |
| “Find papers and write Related Work.” | Literature discovery, claim–evidence mapping, citation audit, academic writing | Citations require original-record links and source locators; identity and claim support are verified separately |
| “Design my study and analyze the metrics.” | Hypothesis/experiment registration, `metrics_action=plan`, descriptive analysis, constrained comparison | Units, estimand, missingness, legal ranges, split boundary, and candidate budget are frozen; final-test data cannot tune or select |
| “Plan this project for the resources I have.” | Resource-aware task planning with `resource_plan_action=inventory`, a serial DAG, checkpoints, and `resource_plan_action=execute` | Host inventory is not entitlement; GPU stays off; unknown estimates and completion remain explicit; only user-supplied budgets bind |
| “I authorize you to find directions with my local resources.” | Authorized local-resource direction exploration through `direction_action` | Each current revision needs positive managed pilot evidence and a strict linked collision receipt; return exactly five unranked choices for the user |
| “Optimize these experiment configurations.” | Feasibility constraints, Pareto frontier, optional user-weighted ranking | Compare observed validation candidates only; weights and reference scales belong to the user; no automatic winner |
| “Help with education or educational technology research.” | ERIC/public-source routing, domain methods, data sources, and venue discovery | Preserve learner/classroom/teacher/school/institution levels; live-check exact venue/year/track/stage |
| “Write or audit this paper.” | Paper spine, cited drafting, venue evidence, code/experiment checks, 2–3-role audit | Web facts, numbers, code, experiments, and evidence are checked separately; role effort is at most `high` |
| “Make this less defensive, Nature-accessible, or less templated.” | Non-defensive prose, rhetorical retrieval, translation, humanized revision | Never erase warranted uncertainty, limitations, ethics, risks, criticism, or negative results |
| “Verify every equation and give legal parameter values.” | Lean logic, Pint dimensions, SymPy equivalence, Z3 satisfiability, and `numerical_action=construct` | Model sourced equations/inequalities; report marginal legal intervals and jointly feasible anchors separately; every symbol is defined and used; unavailable Lean is `NOT_RUN`, not PASS |
| “Compile this LaTeX for venue X.” | Exact venue evidence, template audit, TeX compilation | Static checking cannot claim compiled-PDF success; current official venue/year/track/stage instructions are required |
| “Make a statistical, vector, or architecture figure.” | Data-bound SVG/PDF/PNG rendering and final-size visual review | Hash source data; inspect occlusion, space use, alignment, margins, typography, and exact venue style |
| “Respond to reviewers.” | Comment ledger, evidence-bound revision, rebuttal | Every response has a status and evidence; no promise of unfinished work or acceptance prediction |
| “Actively optimize for an AI-reviewer panel.” | Optional score-aware adaptation | Explicit opt-in, fixed multi-model panel, same rubric for complete candidates, and frozen citations/numbers/formulas/disclosures |
| “Audit AI-reviewer manipulation or sensitivity.” | Separate AI-reviewer robustness mode | Block hidden instructions and fake prestige; report model-specific sensitivity without score optimization |
| “Use an LLM to help with this research step.” | Native-subagent-first LLM delegation | One serial entry/economy subagent at low reasoning by default; local fallback if unavailable; an external API needs an explicit exception and receipt |
| “Find a specialist Skill for this new domain.” | GitHub/SkillsHub discovery, quarantine, 2–3 SkillOpt rounds, overlap audit | No remote Skill execution before provenance, security, and admission checks |
| “Audit this code, experiment, or scientific image.” | Reproducibility receipts, protocol legality, integrity forensics, image audit | Transport, capacity, local smoke, and exit codes are not silently promoted to scientific or causal evidence |

The exhaustive manuscript lifecycle is documented in
[PAPER_WRITING_CAPABILITIES.md](docs/PAPER_WRITING_CAPABILITIES.md).

## Research lifecycle and enforced gates

- **Instruction adherence.** A multistep request is decomposed by the main agent
  into a hash-bound atomic ledger before work mutates the project. Dependencies,
  acceptance criteria, forbidden substitutions, file/receipt evidence, explicit
  user waivers, and completion authority are executable states. Pending or
  drifted evidence blocks Stop; factual `BLOCKED` permits only a blocked handoff.
- **Literature and collision search.** Search has no arbitrary whole-task
  deadline. Linked stages persist and remain visible. Work stops only after
  recorded coverage completes, a factual blocker is saved, or the user supplies
  a time/budget/stop instruction. All literature outputs have clickable HTTPS
  links.
- **Experiment metrics.** Planning freezes metric roles, direction, units,
  estimands, aggregation, legal ranges, missing-data policy, optimization split,
  final-test split, and candidate budget. The analyzer accepts independent-run
  UTF-8 CSV data, rejects protocol-illegal values, and keeps final-test data out
  of selection. Clustered, longitudinal, survey, participant-level, IRT, and
  qualitative data require a specialist model rather than silent flattening.
- **Resource-aware work.** Multi-stage work uses a versioned, hash-bound serial
  DAG. Only one READY managed task executes; external/LLM work uses receipts;
  absent final evidence is `UNKNOWN` and never automatic retry authority.
- **Writing and venues.** Chapter names, layout, formatting, figures, and
  narrative style require live official evidence for the exact
  venue/year/track/stage. Citations bind original records and claim locators.
- **Language.** Non-defensive, Nature-accessible, translation, wording,
  conference-writing, and humanization modules preserve scientifically necessary
  uncertainty. Limitations and possible ethics omissions become explicit user
  decision checklists.
- **Formula and constructive numerical audit.** Lean, Pint, SymPy, Z3, and
  numerical behavior are five independent results. The constructive route
  normalizes sourced linear equations/inequalities, derives exact marginal
  legal intervals, and proposes complete jointly feasible anchors that are
  rechecked against every registered constraint and the paper protocol.
  Marginal intervals are never presented as a jointly feasible Cartesian box;
  unused, undefined, illegal, or confounding parameters cannot receive PASS.
- **Figures and images.** Outputs bind source and artifact hashes and undergo
  final-size checks for occlusion, space use, alignment, gutters, typography,
  accessibility, and the exact venue’s current rules.
- **Paper audit.** The role pool covers citation support, numbers, formulas,
  code/reproducibility, experiments/statistics, language/venue fit, image
  integrity, OpenReview calibration, and optional AI-reviewer modes. Only 2–3
  roles are selected for one run, preventing trigger overload.

Research Guard keeps 17 top-level MCP tools. New capabilities are typed
subroutes under their canonical owner so overlapping features do not create
duplicate triggers or interfaces.

## Dependencies and graceful degradation

The release contains the traditional Skill, Codex plugin, MCP server, hooks,
core Python runtime contract, and all source needed for deterministic validation.
Optional components are never installed merely because the plugin loaded.

| Optional component | Used for | If unavailable or declined |
|---|---|---|
| Git | specialist Skill acquisition and repository provenance | Keep discovery results; remote Skill admission/installation remains `NOT_RUN` |
| TeX distribution | real venue-template compilation | Perform static source checks only; never claim compiled PDF proof |
| Lean + Mathlib | theorem-level logic checks | Report Lean `NOT_RUN`; Pint, SymPy, Z3, and protocol-numeric results remain separate |
| Network/private indexes | current literature, venue, and subscription coverage | Preserve completed public results and list missing source coverage explicitly |

The dependency manager prefers a validated existing installation, shows the
estimated download and installed sizes before any install, and accepts only the
user’s `reuse`, `install`, or `not_now` choice. Domestic package sources can be
used directly; foreign sources may use the user-configured proxy. No omitted
component can be converted into PASS.

## Platform and resource contract

| Boundary | Limit |
|---|---:|
| Supported targets | Windows x64; Linux x64; macOS x64/arm64 |
| Total task-owned aggregate RSS/working set | 512 MiB |
| Standard worker / orchestrator | 384 MiB / 128 MiB |
| Installer worker / orchestrator | 448 MiB / 64 MiB |
| Lean worker / orchestrator | 464 MiB / 48 MiB |
| Parallel workers | 1 |
| GPU | disabled |
| Start / run low-water free RAM | 768 MiB / 512 MiB |

Windows uses a Job Object. Linux and macOS use an owned process group plus
`psutil` process-tree telemetry. Bound violations terminate only the task-owned
tree. Numerical runtimes are pinned to one thread. CI validates Windows x64,
Linux x64, macOS x64, and macOS arm64 independently; a successful archive build
alone is never installation evidence.

## Documentation

Every file declared bilingual is registered in
[documentation-parity.json](assets/documentation-parity.json). CI verifies both
members, their shared revision, complete level-two section skeleton, link set,
image set and accessibility, and normalized content hashes. It also rejects any
unregistered `.zh-CN.md` file. This guarantees maintained pairing and structural
parity; it does not claim that a machine proved translation quality.

- [Documentation maintenance policy](docs/DOCUMENTATION_POLICY.md) · [中文维护策略](docs/DOCUMENTATION_POLICY.zh-CN.md)
- [Requirements and dependencies](REQUIREMENTS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Cross-discipline support](docs/DISCIPLINE_SUPPORT.md)
- [Education support](docs/EDUCATION_SUPPORT.md)
- [Paper writing and audit capabilities](docs/PAPER_WRITING_CAPABILITIES.md)
- [Instruction adherence and constructive numerical audit](docs/INSTRUCTION_AND_NUMERICAL_CONTRACT.md) · [中文契约](docs/INSTRUCTION_AND_NUMERICAL_CONTRACT.zh-CN.md)
- [Time and continuation policy](docs/TIME_AND_CONTINUATION_POLICY.md)
- [Native-subagent-first LLM delegation](docs/SUBAGENT_DELEGATION.md)
- [Resource-aware task planning](docs/RESOURCE_AWARE_TASK_PLANNING.md)
- [Authorized local-resource direction exploration](docs/DIRECTION_EXPLORATION.md)
- [Cross-platform migration assurance](docs/provenance/P21_CI_MIGRATION_ASSURANCE.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
- [Security policy](SECURITY.md)

## Development

```sh
python -m pip install --disable-pip-version-check -r requirements-dev.txt
python -X utf8 scripts/documentation_parity.py
python -X utf8 scripts/validate_repository.py
python -X utf8 scripts/run_incremental_tests.py --pattern "test_documentation_parity.py" --suite docs
python -X utf8 scripts/build_modular_package.py --platform linux-x64 --output dist/research-guard-linux-x64.zip
```

When a registered bilingual document changes, edit both members, run
`python -X utf8 scripts/documentation_parity.py --refresh-hashes`, inspect the
pair, and then run validation. See [CONTRIBUTING.md](CONTRIBUTING.md).

The source checkout excludes large audited payloads, cached venue pages,
templates, and paper PDFs. It is a development checkout, not the Windows offline
release artifact.

## License

Research Guard is available under the [MIT License](LICENSE). Included and
referenced third-party components retain their own licenses; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
