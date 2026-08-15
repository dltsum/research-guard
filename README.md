# Research Guard

Research Guard is a Windows x64 Codex plugin and traditional Skill for
evidence-bounded academic research. It combines concise agent instructions with
executable MCP routes, hooks, hash-bound receipts, and fail-closed gates.

> 中文摘要：这是一个从研究想法、文献与撞车检索、实验设计，到论文写作、
> 公式核验、科研作图和全文审计的一体化 Skill。关键约束由代码和收据执行，
> 不依赖模型“记得遵守”。

## Why it exists

Research workflows often fail at the boundaries: a changed method keeps an old
novelty result, a citation resolves but does not support the claim, an equation
introduces an unused symbol, or a successful program exit is mistaken for a
valid experiment. Research Guard keeps these boundaries explicit and
machine-checkable.

It does **not** prove global novelty, paper correctness, venue acceptance, or
research quality. Every PASS is limited to the recorded sources, artifacts,
hashes, and checks.

## Core guarantees

- Detects the research field and routes literature work across publications,
  patents, trials, grants, datasets, software, and preregistrations as required.
- Covers seven broad and fourteen specialized discipline profiles. An
  unregistered field automatically receives a bounded, hash-bound first-use
  profile from official public sources; the user is warned that initialization
  may take several minutes.
- Treats history and humanities as more than journal search by tracking books,
  chapters, editions, reviews, archives, catalogs, and primary-source evidence.
- Invalidates the novelty receipt after every registered method change and
  blocks progress until the complete collision search is rerun.
- Returns a clickable HTTPS DOI or primary-record link for every literature,
  citation, and collision item.
- Separates bibliographic identity from claim support through exact source
  locators and claim-evidence relations.
- Supports immutable preregistration/deviation records, statistical
  recomputation, resource-bounded reruns, human-only review decisions, and
  correction/retraction monitoring.
- Selects only 2-3 audit roles at effort no higher than `high`.
- Reports five formula records separately: one manuscript-wide Lean proof file,
  Pint dimensional compatibility, SymPy algebraic equivalence under declared
  assumptions, Z3 parameter satisfiability, and hash-bound numerical
  boundary/limit/overflow tests admitted by the paper protocol.
- Calibrates review coverage from official public OpenReview API v2 records
  without predicting acceptance, and flags scientific-image provenance,
  duplicate, metadata, and pixel evidence for expert review without alleging fraud.
- Requires exact venue/year/track/stage evidence before recommending headings,
  layout, formatting, or narrative style.
- Produces data-bound statistical figures and editable vector diagrams with
  source and output hashes.
- Presents limitations and possible ethics omissions as decision checklists;
  it does not silently remove uncertainty.

See [the architecture](docs/ARCHITECTURE.md) for ownership and enforcement
boundaries, and [discipline support](docs/DISCIPLINE_SUPPORT.md) for the current
field matrix and public catalogs.

## Install from a release

The installable artifact is the `windows-x64-modular` release ZIP, not GitHub's
automatic source archive. Extract it and ask an agent:

> Install this package for me. It is a Skill.

The deterministic entrypoint is:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
```

The installer verifies `RELEASE_MANIFEST.json`, installs the bundled core
runtime offline, registers the traditional bootstrap Skill and plugin, and then
stops at the first-load component choice.

On first load it reports the complete feature list, download sizes, installed
sizes, and compatible local environments. Git, TeX, and Lean/Mathlib each offer
three explicit choices: reuse a verified existing environment, install the
fixed component, or leave it disabled. Loading the Skill never starts a
compiler or download by itself.

## Source checkout

The Git repository intentionally excludes binary payloads larger than GitHub's
normal source limit, cached venue pages, template archives, and paper PDFs.
Those assets remain in the hash-verified modular release.

For development:

```powershell
python -m pip install -r requirements-dev.txt
python scripts/run_incremental_tests.py --pattern "test_p10_*.py" --pattern "test_p11_*.py" --pattern "test_p12_*.py" --pattern "test_p13_*.py" --pattern "test_p14_*.py" --suite local-development
```

Verified test files are recorded individually and are resumed only when their
contract hash still matches. Use `--no-resume` for a deliberate clean run.

## Resource contract

Research Guard does not need 6 GiB for its own work. All optimizer, regression,
packaging, compiler-validation, and managed reproduction work is serialized:

| Profile / boundary | Limit |
|---|---:|
| Total task-owned aggregate working set | 512 MiB |
| Standard worker process tree | 384 MiB |
| Standard orchestrator/installer | 128 MiB |
| Lean worker process tree | 464 MiB |
| Lean orchestrator | 48 MiB |
| Parallel workers | 1 |
| Machine headroom before start | 768 MiB |
| Machine low-water abort | 512 MiB |
| GPU | disabled |

A Windows Job Object owns each worker tree; a 10 ms monitor sums the physical
working set of every owned process and terminates only that tree on a limit or
machine low-water violation. Lean gets more of the same 512 MiB envelope and
trims reclaimable working sets above 384 MiB, trading speed for memory.
Scientific runtimes use one thread. Test files and SkillOpt rounds write atomic,
hash-bound receipts, so work proceeds in small units instead of repeatedly
loading the entire suite.

## Repository layout

```text
.codex-plugin/      Codex plugin manifest
agents/             Skill UI metadata
assets/             discipline/source catalogs, schemas, licensed assets, payload manifests
hooks/              deterministic prompt-time routing and invalidation
references/         on-demand agent references
scripts/            MCP server, executable guards, installers, tests and builders
skills/             five focused Skills with progressive disclosure
tests/              deterministic P0-P14 regression suites
docs/               architecture, upstream audit, provenance and development logs
.github/            CI, issue forms and pull-request template
SKILL.md             traditional Skill bootstrap and mandatory invariants
```

The plugin keeps 15 top-level MCP tools. New capabilities are admitted as typed
subroutes under a canonical owner instead of expanding the surface indefinitely.

## Build artifacts

Build the GitHub-safe source release:

```powershell
python scripts/build_public_package.py --output dist/research-guard-source.zip
```

Build the complete, hash-manifested migration artifact on a release workstation
where the audited payloads are present:

```powershell
python scripts/build_modular_package.py --output dist/research-guard-windows-x64-modular.zip
```

Both builders run inside the 384 MiB worker limit and stream files. The modular
builder refuses archives above 1 GiB.

## Evidence, dependencies, and provenance

- [Dependency and first-load model](references/dependencies.md)
- [Architecture and trust boundaries](docs/ARCHITECTURE.md)
- [Cross-discipline support and initialization](docs/DISCIPLINE_SUPPORT.md)
- [Original and additional upstream audit](docs/UPSTREAM_AUDIT.md)
- [P12 component registry](docs/provenance/P12_COMPONENT_REGISTRY.json)
- [P13 release-final verification report](docs/provenance/P13_RELEASE_VERIFICATION.md)
- [P14 cross-discipline and release verification](docs/provenance/P14_DISCIPLINE_AND_RELEASE.md)
- [P12 overlap audit](docs/provenance/P12_OVERLAP_AUDIT.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

Anonymous scholarly routes are preferred where an official public interface
exists. Domestic sources are accessed directly; the local port 7897 proxy is
used only for unavailable foreign routes. Subscription indexes and other
non-anonymous systems require user-supplied official exports and never accept an
arbitrary web page as registry evidence.

## Contributing and security

Read [CONTRIBUTING.md](CONTRIBUTING.md) before changing a gate, source adapter,
or canonical owner. Report vulnerabilities according to
[SECURITY.md](SECURITY.md). Project decisions follow [GOVERNANCE.md](GOVERNANCE.md),
and usage questions follow [SUPPORT.md](SUPPORT.md). Never submit papers, credentials, private provider
responses, or unreleased research data to an issue.

## License

Research Guard is available under the [MIT License](LICENSE). Included and
referenced third-party components retain their own licenses; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
