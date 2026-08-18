# Architecture and enforcement boundaries

## Canonical owners

| Owner | Scope | Executable enforcement |
|---|---|---|
| `research-novelty-guard` | method registration, publication and extended-source routing, collision review | method hashes, source/family-attempt ledger, hook invalidation, signed receipt |
| `research-design-guard` | discipline profiles, ideas, strategy, hypotheses, experiments, frozen metrics, validation-only constrained comparison, native-subagent-first LLM assistance, preregistration, reproducibility, active review, domain adapters, knowledge, research artifacts | field registry/evidence hashes, method/experiment/data hashes, delegation plans and artifact receipts, user-selection fields, split gates, typed state, resource guard, append-only ledgers |
| `paper-audit-guard` | manuscript ingestion, claims/evidence, citations, statistics, record health, formulas, code, experiments, optional active AI-reviewer adaptation, and robustness | source/parser hashes, exact locators, claim inventory, Crossref updates, Lean, numeric/result checks, same-panel candidate selection, and anti-manipulation receipts |
| `academic-language-guard` | wording, translation, Nature-accessible and venue-grounded writing | protected spans, translation contract, user-decided limitation/ethics ledger |
| `academic-figure-guard` | statistical and vector research graphics | explicit main-agent roles, raw-data contracts, deterministic rendering, output hashes, final-size occlusion/space/alignment and venue review |

All capabilities reuse 17 top-level MCP tools. Two narrow tools expose the
module catalog and persist the main agent's explicit selection; citation and figure
operations are subroutes of `paper_audit`; domain Skills, knowledge, research
artifacts, discipline profiles, experiment metrics, LLM-assistance delegation, and evolution proposals are subroutes of `research_design`; venue
evidence is a subroute of `language_assist`.

## LLM-assistance delegation boundary

The MCP server does not claim that it can spawn a host-native subagent or
intercept every provider connector. It creates and verifies the execution
contract the host agent must follow. The default plan requires one serial native
entry/economy subagent at low reasoning. If the host exposes no subagent, the
plan requires main-agent local execution rather than an external API fallback.

External APIs are fail-closed exceptions: the user must explicitly select the
provider, or a registered protocol must require cross-provider identity and the
user must authorize that exception. Every completed unit binds a project-local
artifact hash. A native same-host or same-model subagent is never labeled as an
independent provider or a distinct reviewer model.

## Discipline initialization

The static registry covers seven broad and fifteen specialized profiles. A
request outside the registry enters a narrow initialization seam rather than a
new top-level tool. The initializer performs serial, bounded discovery against
current official public sources, stores normalized response snapshots, and
binds their hashes into the novelty query plan.

OpenAlex, Crossref, and DOAJ own anonymous journal discovery. Humanities adds
book/edition and catalog discovery, while the profile explicitly separates a
catalog record from verified primary-source relevance. Candidate order is
deterministic discovery order, not a venue ranking. Any profile, registry, or
evidence change invalidates the prior collision receipt.

P12 integrity functions preserve this surface: `paper_audit.integrity_action`
owns ingestion, claim evidence, statistics, and record health;
`research_design.integrity_action` owns preregistration, bounded reruns, and
review prioritization.

## Main-agent semantic selection

The prompt hook does not rank keywords or choose a domain, module, reviewer
role, or semantic method-change label. It returns a compact contract. The main
agent reads the complete request, inspects the registered catalogs, and calls
`select_research_modules` with one to three non-overlapping owners, a rationale,
and an explicit `method_change` boolean. Code validates IDs, overlap, count,
provenance, and hashes but never substitutes its own semantic choice.

Domain selection follows the same boundary: method registration first enters
`DOMAIN_SELECTION_REQUIRED`; only a `classify_domain` call carrying an explicit
main-agent selection creates the source plan. The legacy tool name is retained
for compatibility and performs no classification. Paper audit planning likewise
requires two or three explicit roles and declared audit features.

Method-change handling is an explicit main-agent safety declaration:

```text
main-agent semantic judgment + method_change=true
  -> invalidate live novelty receipt
  -> register complete adjusted method
  -> rerun the complete collision search
```

Tracked `method_files` retain an independent deterministic hash backstop. This
avoids both keyword false positives and silent receipt reuse after an observed
file change.

## Long-running search continuation

Collision search is a persistent queue of source-query work units. Every unit
saves its query, source, result links, error, attempt evidence, raw hashes, and
progress hash atomically. A tool call advances a scheduling slice and may return
`IN_PROGRESS`; the main agent reports the stage facts and continues from the
checkpoint.

If all planned units have been attempted but any required unit failed, the tool
returns `ACTION_REQUIRED` rather than finalizing. No retry count is inferred.
The main agent must retry explicit unit IDs, register admissible manual evidence,
or submit a hash-bound `blocker_decision` covering every failed required unit.
Only the last option permits a `BLOCKED` stop state.

There is no wall-clock research deadline. `attempt_timeout_seconds` is only a
single transport-attempt safety bound. Child-process and CI timeouts similarly
protect an owned process tree; none is evidence that research coverage is
complete. Research stops after coverage completion, a persisted factual blocker,
or an explicit user budget/time/stop instruction.

See [the full time-boundary audit](TIME_AND_CONTINUATION_POLICY.md).

Writing, experiments, audits, and deep research use the same durable progression
principles: short independently verifiable stages, incremental checkpoints and
factual user-visible progress, explicit missing/invalid/not-run/unknown states,
and receipt inspection before replay after unknown completion. See the
[research progression contract](../references/research-progression-contract.md).

## Evidence and hyperlink rule

Every literature-producing path must return a clickable `https://` DOI or
primary-record link. DOI metadata verification establishes bibliographic
identity only; it does not show that a source supports a claim. Claim support is
checked separately by the manuscript claim-evidence ledger.

Current external facts such as venue rules, corrections/retractions, dataset
licenses, benchmarks, and software versions require live verification. Local
hashes establish which evidence was checked, not that it remains current.

## Venue hierarchy

1. Current official venue policy and template: hard layout/format authority.
2. Award or high-quality paper: descriptive headings and narrative observations
   for that paper only.
3. CCF A/B catalog: venue discovery and classification only.

No lower level can authorize rules belonging to a higher level. Missing exact
venue/year/track/stage evidence returns `ONLINE_ACQUISITION_REQUIRED`.

## Formula and experiment boundary

Formula assistance uses exactly one manuscript-wide Lean file, disables
implicit undeclared parameters, maps each formula to an ID, and checks that
every registered parameter is legal and used. Formula changes require another
full-file Lean check.

Code/experiment review hash-binds raw results, configurations, scripts, and
paper claims. It checks result existence, ground-truth provenance, dead paths,
aggregation, seeds, scope, and reported numbers. Passing code execution alone
is not an empirical or scientific-quality claim.

Metric plans bind method and experiment hashes before results are analyzed.
The core analyzer accepts independent-run CSVs and validates protocol ranges,
missingness, duplicate run identifiers, and candidate budgets. Optimization
uses only the frozen optimization split, reports feasible and Pareto sets, and
requires user-owned weights/scales for scalar ranking. Final-test summaries are
never inputs to candidate selection. Clustered, longitudinal, weighted, IRT,
and qualitative designs require their registered specialist analysis.

## Cross-platform runtime boundary

The source MCP entrypoint is shell-neutral. Windows x64 releases retain the
audited offline Python runtime and Job Object process ownership. Linux x64 and
macOS x64/arm64 releases create an isolated Python 3.11+ venv and use a process
group plus `psutil` descendant telemetry. Every platform keeps the same 512 MiB
aggregate owned-task limit, serial execution, one-thread numerical defaults,
and GPU-off policy. Optional Windows payload installers never run on POSIX;
POSIX reuses a validated host dependency or records an explicit degradation.

## Research-artifact contracts

- Paper Card: exactly Sections 01-16, verified primary-record URL, and explicit
  page/structure/source-limited locator mode.
- Systematic review: frozen protocol, DOI/arXiv/OpenAlex-style dedup keys,
  recomputed flow counts, and only `selected_by=user` inclusion decisions.
- Experiment log: immutable source files and raw measurements, explicit units,
  timestamps, parameters, anomalies, and separate interpretations.
- Reviewer response: every atomic issue has a status; answered issues require
  evidence; unresolved author input blocks delivery.

## P12 integrity receipts

- Ingestion accepts compact native text/PDF extraction or a normalized
  Docling/GROBID/MinerU/Marker output. Every block requires locator provenance;
  source and parser output are hash-bound.
- Claim-evidence graphs separate support, refutation, and insufficiency.
  Literature/registry evidence requires a clickable primary record. Literature
  evidence is bound to an ingested block; local and registry excerpts must
  occur in a hash-bound UTF-8 normalized source extract. Insufficiency alone
  cannot satisfy a claim, and refutation without support is reported as
  `CLAIMS_REFUTED` rather than a generic PASS.
- Preregistration freezes the declared analysis contract; changes append a
  user-selected deviation instead of altering history.
- Statistical PASS covers only successfully recomputed APA-like reports.
- Reproducibility runs use the shared RAM/Job Object guard. Submitted checks
  must match the frozen definitions; receipt hashes, exit code, declared
  outputs, and every independently recomputed expected check must all pass.
  External submissions remain review-required; only a managed frozen rerun
  can produce reproduction PASS. Managed reruns require fresh versioned output
  paths and refuse to launch over pre-existing artifacts. The frozen plan also
  binds the OS/architecture/Python fingerprint and command-executable hash.
- Active review ranks only undecided records and cannot assign inclusion.
- Crossref update relations preserve prior snapshots. Material updates require
  action; any other metadata drift requires review. Both invalidate dependent
  paper-audit receipts. Indexing/deposit service timestamps alone are excluded
  from the scholarly metadata hash.

## Trust model

The plugin does not claim global proof of novelty, correctness, accessibility,
venue acceptance, or research quality. PASS is bounded to the recorded source
plan, artifacts, hashes, external receipts, and checks. Stale or changed inputs
invalidate receipts instead of being silently accepted.
