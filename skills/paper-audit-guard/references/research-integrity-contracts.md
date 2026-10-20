# Research integrity subroutes

Load this reference only for structured ingestion, claim-evidence mapping,
statistical consistency, or scholarly-record health.

Call the MCP tool `paper_audit` with `action="status"`; select these subroutes
with **`integrity_action`**, not `action`. A read-only state query is:

```json
{"name":"paper_audit","arguments":{"action":"status","integrity_action":"status","project_root":"/absolute/project"}}
```

- `integrity_action=ingest`: bind PDF/Markdown/LaTeX/text to its source hash and parser
  output. Core PDF extraction is text-only. Docling, GROBID, MinerU, and Marker
  enter only through a project-local normalized JSON adapter with block
  locators; parser output is not automatically authoritative.
- `integrity_action=ingest_status`: inspect a registered ingestion by `document_id`.
- `integrity_action=claim_evidence`: require `selected_by=user`, a non-empty claim graph,
  exact locators, source SHA-256 values, excerpts, substantive edge rationales,
  and clickable HTTPS primary records for literature/registries. Literature
  must identify an ingested document and exact block; local and registry
  excerpts must occur in the UTF-8 normalized source extract. Support and
  refute together require conflict review. A claim connected only by
  `insufficient` edges returns `EVIDENCE_INSUFFICIENT`, never `PASS`.
  A claim with refutation but no support returns `CLAIMS_REFUTED`; the receipt
  status cannot be mistaken for acceptance of the claim.
- `integrity_action=statistics`: recompute APA-like `t`, `z`, `r`, `F`, chi-square, and
  `Q` reports with rounding-aware checks and declared estimate-sensitivity
  cases. An identified but unrecomputed expression fails closed. PASS is
  limited to those checks and is not a design-validity verdict.
  Display compatibility propagates the reported statistic's half-last-digit
  rounding range through the supported tail calculation, then compares it
  with the reported p-value precision. The receipt retains the point p-value
  and the numerical rounding range separately. A range crossing alpha has
  indeterminate computed significance, not a definite decision error. These
  ranges are neither confidence intervals nor certified numerical enclosures.
- `integrity_action=record_health`: resolve current Crossref update relations for a DOI.
  Retractions, expressions of concern, corrections, withdrawals, removals,
  or reinstatements return `ACTION_REQUIRED`. Other changed metadata returns
  `REVIEW_REQUIRED`. Both invalidate dependent receipts and preserve history.
  Crossref indexing/deposit service timestamps alone are not treated as a
  scholarly-record change.
- `integrity_action=status`: inspect the persisted integrity ledger without
  rerunning ingestion, statistical checks or network retrieval.

All records are method-bound and append-only. A method change invalidates
derived records and requires the complete paper plus extended collision search.
