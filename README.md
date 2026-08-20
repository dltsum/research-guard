# Research Guard

[English](README.md) | [简体中文](README.zh-CN.md)

Research Guard is a portable academic-research Skill and Codex plugin. It
combines concise agent instructions with executable MCP routes, hooks,
hash-bound receipts, and fail-closed gates from idea exploration and literature
search through experiment analysis, writing, figures, formulas, and final audit.

It does not prove global novelty, scientific truth, venue acceptance, or
research quality. Every PASS is limited to the recorded sources, artifacts,
hashes, and checks.

## Give this to an agent

```text
Install the Research Guard Skill from https://github.com/dltsum/research-guard.
Download the release archive matching this machine, verify it with
SHA256SUMS.txt, run scripts/install.ps1 on Windows or scripts/install.sh on
Linux/macOS, validate the traditional Skill, Codex plugin, MCP server, and core
Python runtime, then start a new agent session and load research-guard. Do not
install optional Git, TeX, or Lean/Mathlib automatically. When a requested
feature needs one, show me reuse-existing, install-system/install, and not_now
with download/install sizes; execute only my explicit choice. If I choose
not_now, report the omitted check as NOT_RUN, never PASS.
```

Release assets:

- Windows x64 offline modular package:
  [research-guard-windows-x64-modular.zip](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-windows-x64-modular.zip)
- Linux x64 venv package: `research-guard-linux-x64.zip`
- macOS Intel venv package: `research-guard-macos-x64.zip`
- macOS Apple Silicon venv package: `research-guard-macos-arm64.zip`
- Integrity files: `SHA256SUMS.txt` for the Windows offline archive and
  `SHA256SUMS-posix.txt` for Linux/macOS archives

The Windows archive remains about 300 MB because it includes the audited core
Python runtime. Linux/macOS archives do not carry Windows binaries; their
installer creates an isolated venv from a supported system Python. Exact
requirements and degradation rules are in [REQUIREMENTS.md](REQUIREMENTS.md).

## Manual installation

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

On macOS, replace `sha256sum` with `shasum -a 256` if GNU coreutils is not
installed. The installer verifies every file against `RELEASE_MANIFEST.json`,
uses one process at a time, disables GPU execution, and installs per user.

## What you can ask

| Request | Main capability | Enforced boundary |
|---|---|---|
| “Explore this idea and check whether it collides with prior work.” | Explicit discipline selection, ideation, multi-source novelty search | Every result has an HTTPS DOI/primary-record link; every method/profile change invalidates the old receipt and forces a complete rerun |
| “Find papers and write Related Work.” | Literature discovery, claim-evidence relations, citation audit, academic writing | Citations require DOI/original-record links and source locators; identity is separate from claim support |
| “Design my study and analyze the metrics.” | Hypothesis/experiment registration, frozen metric plan, descriptive analysis, constrained comparison | Units, estimand, missingness, legal ranges, split boundary, and candidate budget are hash-bound; final test cannot tune or select |
| “Plan this research task for the CPU, RAM, disk, network, and time I have.” | Main-agent-selected resource DAG, serial profiles, checkpoints, resumable stage receipts | Host inventory is not entitlement; GPU stays off; unknown estimates and completion remain explicit; user budgets are never invented |
| “Optimize these experiment configurations.” | Feasibility constraints, Pareto frontier, optional user-weighted ranking | Observed validation candidates only; weights/reference scales belong to the user; result remains `USER_SELECTION_REQUIRED` |
| “Help with an education or educational-technology paper.” | ERIC/public-source routing, education methods/data, venue discovery | Preserve learner/classroom/teacher/school/institution levels; live-check exact venue/year/track/stage |
| “Write or audit this paper.” | Paper spine, cited drafting, language, venue evidence, 2–3-role audit | Web facts, numbers, code, experiments, and evidence are checked separately; role effort is at most `high` |
| “Make this less defensive / Nature-accessible / less templated.” | Non-defensive prose, rhetorical retrieval, translation, humanized revision | Do not delete warranted uncertainty, limitations, ethics, risks, criticism, or negative results |
| “Verify every equation.” | Lean, Pint, SymPy, Z3, numerical/protocol checks | Five results are separate; all symbols must be defined and used; unavailable Lean is `NOT_RUN`, not PASS |
| “Compile this LaTeX for venue X.” | Exact venue evidence and TeX compilation | Static checking cannot claim compiled PDF success; exact current official instructions are required |
| “Make a statistical/vector/architecture figure.” | Data-bound SVG/PDF/PNG rendering and final-size review | Hash source data; inspect occlusion, space, alignment, margins, typography, and exact venue style |
| “Respond to reviewers.” | Comment ledger, evidence-bound revision, rebuttal | Every response has status/evidence; no promise of unfinished experiments or acceptance prediction |
| “Optimize for AI reviewers.” | Optional active score-aware adaptation | Explicit user opt-in, fixed multi-model panel, same rubric for all complete candidates; frozen citations/numbers/formulas/disclosures |
| “Audit AI-reviewer manipulation or sensitivity.” | Separate robustness audit | Blocks hidden instructions and fake prestige; reports model-specific sensitivity without score optimization |
| “Use an LLM to help with this research step.” | Native-subagent-first delegated assistance | One entry/economy subagent at low reasoning by default; local main-agent fallback if unavailable; external APIs require an explicit user/protocol exception and a hash-bound receipt |
| “Find a specialist Skill for this new domain.” | GitHub/SkillsHub discovery, quarantine, 2–3 SkillOpt rounds, overlap audit | No remote Skill execution before provenance/security/admission checks |

The exhaustive paper lifecycle map is in
[docs/PAPER_WRITING_CAPABILITIES.md](docs/PAPER_WRITING_CAPABILITIES.md).

## Resource-aware task planning

Resource-sensitive multi-stage work uses a typed subroute of the existing
`research_design` owner:

1. `resource_plan_action=inventory` collects a bounded, privacy-redacted CPU,
   RAM, disk, policy, and profile snapshot. It does not probe network or GPU
   runtime usability and does not treat host inventory as process entitlement.
2. `resource_plan_action=plan` validates the main agent's task DAG, expected
   artifacts, dependency order, resource profile, optional components, and any
   user-selected download/disk/time/cost budget. Execution remains serial.
3. `resource_plan_action=record` stores actual stage transitions, artifacts,
   hashes, and managed-process memory telemetry. An absent final receipt is
   `UNKNOWN`, never automatic retry authority.
4. `status` exposes the one next ready task and factual blockers; `verify`
   detects policy, state, transition, and artifact drift.

Simple one-response work is exempt. The planner coordinates existing owners: it
does not replace the 512 MiB process guard, dependency manager, LLM-delegation
contract, or remote executor. See
[docs/RESOURCE_AWARE_TASK_PLANNING.md](docs/RESOURCE_AWARE_TASK_PLANNING.md).

## Experiment metrics

Metric work is a typed subroute of the existing `research_design` owner, not a
new top-level tool:

1. `action=status, metrics_action=plan` freezes primary/secondary/diagnostic/safety roles,
   direction, unit, estimand, aggregation, legal range, missing policy,
   optimization/final-test splits, and candidate budget.
2. `metrics_action=analyze` reads a project-local UTF-8 CSV at independent-run
   level, rejects duplicates/missing/non-finite/illegal values, hashes the data,
   and reports per-configuration summaries and explicitly descriptive baseline
   differences. It rejects any row from the frozen final-test split, which must
   remain in a separate sealed artifact during selection.
3. `metrics_action=optimize` applies declared feasibility constraints and
   reports the Pareto frontier using the frozen optimization split. It never
   reads final-test summaries for selection. A scalar ranking is allowed only
   with user-selected weights and reference scales.
4. Clustered, longitudinal, complex-survey, participant-level, IRT, and
   qualitative data return `SPECIALIST_ANALYSIS_REQUIRED`; the core engine does
   not flatten them into independent rows.

## Education and educational technology

The two profiles are distinct. Education covers experimental and
quasi-experimental studies, multilevel/longitudinal models, surveys,
psychometrics/IRT, qualitative research, design-based research, and evidence
synthesis. Educational technology adds learning analytics, process mining,
EDM/AIED, CSCL, HCI/usability, knowledge tracing, fairness, privacy,
accessibility, and algorithmic-impact auditing.

Official discovery routes include [ERIC](https://eric.ed.gov/),
[AERA](https://www.aera.net/Events-Meetings/Annual-Meeting),
[ISLS](https://www.isls.org/), [AIED](https://iaied.org/conferences),
[EDM](https://educationaldatamining.org/conferences/),
[LAK](https://www.solaresearch.org/events/lak/), and
[EC-TEL](https://ea-tel.eu/ec-tel-conference). Method anchors include
[IES SEER](https://nces.ed.gov/use-work/standards-excellence-education-research-seer)
and the [WWC handbooks](https://ies.ed.gov/ncee/wwc/Handbooks); public data
routes include [NCES DataLab](https://nces.ed.gov/datalab/onlinecodebook/),
[PISA](https://www.oecd.org/en/about/programmes/pisa/pisa-data.html), and
[UNESCO UIS](https://www.uis.unesco.org/en/data).

These links are discovery/method anchors, not rankings or permission to copy a
format. Writing still requires live official evidence for the exact
venue/year/track/stage. See [docs/EDUCATION_SUPPORT.md](docs/EDUCATION_SUPPORT.md).

## Core guarantees

- The main agent explicitly selects the field, 1–3 research modules, and 2–3
  audit roles. No keyword classifier or small routing model makes those choices.
- Collision search has no arbitrary whole-task deadline. It persists linked
  stage results, reports progress, and stops only on complete coverage, a saved
  factual blocker, or an explicit user time/budget/stop instruction.
- All literature and citation outputs include clickable HTTPS links.
- Exact venue/year/track/stage evidence is required before recommending
  headings, layout, formatting, or narrative style.
- Formula checks report Lean logic, Pint dimensions, SymPy equivalence, Z3
  satisfiability, and protocol-admitted numerical behavior separately.
- Figures bind source/output hashes and require final-size visual review.
- Limitations and possible ethics omissions are user-decision checklists; the
  system does not silently remove uncertainty.
- Optional dependencies are requested on demand. Declining one records a named
  degradation and never converts an omitted check into PASS.
- LLM-assisted work defaults to one serial native entry/economy subagent at low
  reasoning. If unavailable, the main agent continues locally rather than
  silently calling an API. External-provider exceptions are user-authorized and
  hash-bound; same-host/same-model subagents are not independent reviewers.
- Resource-sensitive multi-stage work has a versioned, hash-bound serial DAG.
  Missing estimates stay unknown; `UNKNOWN` completion requires receipt
  inspection; a whole-task deadline exists only when the user supplied it.

## Resource and platform contract

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

Windows uses a Job Object. Linux/macOS use an owned process group plus `psutil`
tree telemetry. Both terminate only the task-owned tree on a bound violation.
Threaded numerical runtimes are pinned to one thread.

The task planner exposes `inline_light`, `managed_standard`, `managed_install`,
`managed_lean`, `llm_assistance`, and `external_wait` profiles. Only the three managed child
profiles are claimed as locally memory-enforced; host-native subagent resources
remain host-managed and explicitly unproven by the plugin.

## Development

```sh
python -m pip install --disable-pip-version-check -r requirements-dev.txt
python -X utf8 scripts/validate_repository.py
python -m unittest tests.test_experiment_metrics tests.test_education_profiles -v
python -X utf8 scripts/build_modular_package.py --platform linux-x64 --output dist/research-guard-linux-x64.zip
```

The source checkout excludes large audited payloads, cached venue pages,
templates, and paper PDFs. It is a development checkout, not the Windows
offline release artifact.

## Repository map

```text
.codex-plugin/   plugin manifest
assets/          source, discipline, dependency, and venue registries
hooks/           deterministic selection and method-change backstops
scripts/         MCP server, guards, installers, analyzers, builders
skills/          focused Skills with progressive disclosure
tests/           deterministic regression and contract tests
docs/            capability, architecture, provenance, and field documentation
```

Research Guard keeps 17 top-level MCP tools; newer capabilities are typed
subroutes under their canonical owner to avoid trigger and interface sprawl.

## Documentation

- [Requirements and dependencies](REQUIREMENTS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Cross-discipline support](docs/DISCIPLINE_SUPPORT.md)
- [Education support](docs/EDUCATION_SUPPORT.md)
- [Paper writing and audit capabilities](docs/PAPER_WRITING_CAPABILITIES.md)
- [Time and continuation policy](docs/TIME_AND_CONTINUATION_POLICY.md)
- [Resource-aware task planning](docs/RESOURCE_AWARE_TASK_PLANNING.md)
- [Native-subagent-first LLM delegation](docs/SUBAGENT_DELEGATION.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
- [Security policy](SECURITY.md)

## License

Research Guard is available under the [MIT License](LICENSE). Included and
referenced third-party components retain their own licenses; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
