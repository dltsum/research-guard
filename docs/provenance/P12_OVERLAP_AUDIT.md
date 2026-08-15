# P12 overlap and admission audit

## Ownership decisions

| Capability | Existing overlap | Canonical decision |
|---|---|---|
| Structured ingestion | paper audit file hashing; optional pypdf | Keep `paper_audit` as owner. Add a normalized parser boundary; do not bundle Docling/MinerU/Marker/GROBID models. |
| Claim-evidence | paper audit claim inventory; knowledge graph | Keep manuscript claims in `paper_audit`. The general knowledge graph cannot issue support/refute verdicts. |
| Extended collision | publication novelty search; manual sources | Extend the one novelty receipt with typed source families. No parallel collision gate is permitted. |
| Preregistration | experiment-design contract | Keep design planning editable, then freeze a separate user-selected immutable protocol and deviation ledger. |
| Statistics | numeric comparison role; experiment audit | Add deterministic recomputation under `paper_audit`; do not claim study validity or robustness from p-value consistency. |
| Reproducibility | experiment log artifact; resource guard | Reuse the one resource guard and research-design owner. Exit code alone cannot pass. |
| Active review | systematic-review artifact | Fuse ranking into the existing artifact flow while preserving human-only inclusion decisions. ASReview remains optional. |
| Record health | DOI verification; citation audit | Keep identity formatting separate. Material Crossref updates invalidate dependent audit/citation receipts without rewriting history. |

## Rejected integrations

- Wholesale cloning, executing, or prompt-loading of any compared repository.
- Treating fork count, stars, or benchmark claims as correctness evidence.
- Shipping parser models, JVM services, R/Shiny, compiled SciPy/statsmodels, or
  Linux tracing stacks in the core archive.
- Letting an LLM, classifier, or active-learning score decide systematic-review
  inclusion, limitation handling, ethics handling, or collision resolution.
- Treating metadata snippets as evidence that a paper supports or refutes a
  claim.
- Treating successful process exit as computational reproducibility.
- Scraping Google Scholar as required coverage; unstable scraping is replaced
  by official APIs or hash-bound user-imported official evidence.

## Hard integration invariants

The MCP surface remains 15 tools. Routing selects at most three modules. Every
method-change entry point invalidates derived P12 records and forces the full
publication plus extended-source search. All scholarly outputs expose HTTPS DOI
or primary-record links. Heavy optional stacks use first-load selection and the
shared resource guard; the core remains standard-library-first.

Statistical robustness is limited to user-declared alternative-estimate
tolerances, sign changes, and interval-crossing changes. It does not infer
design robustness from p-value consistency. Reproduction submissions cannot
replace frozen expected checks; outputs and stream receipts remain hash-bound.
External submissions cannot claim PASS even when their files verify; PASS is
reserved for a shared-resource-guard rerun. Claims with only insufficient
evidence and nonmaterial scholarly-record drift also remain explicitly
non-PASS.
