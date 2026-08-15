# Architecture and enforcement boundaries

## Canonical owners

| Owner | Scope | Executable enforcement |
|---|---|---|
| `research-novelty-guard` | method registration, publication and extended-source routing, collision review | method hashes, source/family-attempt ledger, hook invalidation, signed receipt |
| `research-design-guard` | discipline profiles, ideas, strategy, hypotheses, experiments, preregistration, reproducibility, active review, domain adapters, knowledge, research artifacts | field registry/evidence hashes, user-selection fields, typed state, resource guard, Optuna admission, append-only ledgers |
| `paper-audit-guard` | manuscript ingestion, claims/evidence, citations, statistics, record health, formulas, code and experiments | source/parser hashes, exact locators, claim inventory, Crossref updates, Lean, numeric/result checks |
| `academic-language-guard` | wording, translation, venue-grounded writing | protected spans, translation contract, user-decided limitation/ethics ledger |
| `academic-figure-guard` | statistical and vector research graphics | raw-data contracts, deterministic rendering, output hashes, final-size review |

All capabilities reuse the existing 15 top-level MCP tools. Citation and figure
operations are subroutes of `paper_audit`; domain Skills, knowledge, research
artifacts, discipline profiles, and evolution proposals are subroutes of `research_design`; venue
evidence is a subroute of `language_assist`.

## Discipline initialization

The static registry covers seven broad and fourteen specialized profiles. A
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

## Intent router

The prompt hook ranks deterministic English regex and Chinese term signals.
It selects one primary and at most two secondary modules. Overlap precedence is
explicit: venue evidence owns venue layout over generic language; formula
verification owns formula audit; paper audit owns manuscript audit; citation
search owns citation lookup. A generic research-context fallback prevents
research requests from having no owner.

Discipline initialization owns first-use field coverage over generic domain
Skill acquisition. The router can still select citation search beside it, but
suppresses the overlapping domain-Skill module so a single prompt does not
bootstrap two competing field representations.

Method-change detection is not a module. It is an independent safety overlay:

```text
research context + adjustment signal
  -> invalidate live novelty receipt
  -> register complete adjusted method
  -> rerun the complete collision search
```

This means a three-module mixed request cannot push novelty invalidation out of
the active context.

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
