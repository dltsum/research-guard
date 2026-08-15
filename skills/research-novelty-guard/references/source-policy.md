# Source routing and evidence policy

## Source roles

| Source | Role | Typical route | Constraint |
|---|---|---|---|
| arXiv | Preprint discovery | CS, mathematics, physics, quantitative fields | Preprint status is not peer review. |
| Crossref | DOI and publisher metadata | All fields | Metadata coverage is broad but not exhaustive. |
| Semantic Scholar | Cross-domain discovery | All fields | Anonymous shared-pool access may return HTTP 429; an optional key improves reliability. |
| OpenAIRE, HAL, DataCite | Open repositories, research graph, datasets, software, and DOI records | All fields | Discovery evidence is not index-membership proof. |
| DBLP | Curated computer-science bibliography | Computer science | Venue coverage is strong but field-specific. |
| PubMed | Biomedical discovery | Medicine and life science | Verify publication type separately. |
| Europe PMC | Biomedical papers and preprints | Medicine and life science | Preprints and articles must be distinguished. |
| PMC | Biomedical full-text repository discovery | Medicine and life science | Repository presence and open-access status are recorded separately from peer review. |
| bioRxiv / medRxiv | Biomedical preprint discovery through Europe PMC | Medicine and life science | Preprints are not peer-reviewed clinical evidence. |
| ClinicalTrials.gov | Clinical study registry | Clinical research | A registered study is not a peer-reviewed paper. |
| OpenCitations | DOI citation/reference expansion | All fields | Citation edges supplement keyword search and do not establish semantic equivalence. |
| Unpaywall | DOI open-access lookup | All fields | The official API requires a contact email; OA availability is not quality evidence. |
| OpenAlex | Cross-domain scholarly graph | All fields | Current published API policy requires a free API key; do not depend on transitional guest access. |
| IEEE Xplore | Engineering and CS literature | CS and engineering | Live API access requires an IEEE API key. |
| Web of Science SCI/SSCI | Curated index search | Natural science and social science | Live API access requires institutional/API credentials. |
| CCF directory | Venue tier verification | Computer science | CCF is a venue catalogue, not a general full-text paper database. |
| CSSCI/C刊 | Chinese social-science venue verification | Social science and humanities | No stable public search API is assumed; fail closed until independently verified evidence is recorded. |

## Strict coverage

Require every source listed in `required_sources` to return a successful, attributable result set. A valid empty result is successful; a timeout, parsing error, or skipped source is not. Attempt every `supplemental_sources` adapter and preserve errors, missing credentials, and rate limits in `supplemental_gaps`; these gaps never masquerade as searched evidence. Keep anonymous manual sources and index directories under `manual_sources`. Deduplicate works by DOI first and normalized title second while retaining all source labels.

The search has no wall-clock research deadline. `attempt_timeout_seconds` limits one I/O attempt only. Each source-query unit is saved to a hash-bound checkpoint; `IN_PROGRESS` requires a user-facing stage update followed by continuation. A transport timeout is a unit result that may be retried or replaced by registered manual evidence, never a reason to call the overall research complete.

When required units fail, the search returns `ACTION_REQUIRED`. The main agent
chooses whether to retry specific IDs, register admissible manual evidence, or
submit a factual `blocker_decision` that covers every failed required unit and
explains why progress is unavailable. The tool encodes no retry-count heuristic.

When the user explicitly names SCI, SSCI, CCF, IEEE, CSSCI, C刊, or another source in the registered method's `required_sources`, promote it to hard coverage even if it is normally supplemental or manual. Missing credentials or an absent official adapter must then keep the gate at `COVERAGE_INCOMPLETE` until independently verified evidence is supported; never silently substitute a different database.

## Manual evidence registration

Use `request_manual_evidence` to generate source-specific questions and official entry URLs. A conclusive manual registration requires all of: the exact query or venue identifier, a compatible result status, an official-source URL, a non-empty project-relative capture/export file, its SHA-256, and the active method and query-plan hashes. `hits_present` also requires structured bibliographic records so collision scoring can inspect them.

Accepted literature statuses are `zero_results` and `hits_present`; accepted directory statuses are `index_verified` and `index_not_listed`. `access_blocked` and `inconclusive` may be recorded but must not satisfy required coverage. CCF, CSSCI, and C刊 are directory checks; Web of Science, IEEE, CNKI, Wanfang, and VIP source requirements need literature-search evidence rather than a venue-label screenshot alone.

Changing the captured file, method, or query plan invalidates the registration and any downstream receipt. Record the evidence as user-supplied official-source material, not as independently reproduced access by the agent.

Manual result pages must use an absolute official `https://` URL with no embedded credentials. Plain HTTP, user-info credentials, unofficial mirrors, and paths outside the active project fail closed.

The full direct-URL and access-mode inventory lives in [source-catalog.json](source-catalog.json). Prefer documented public APIs. Do not scrape Google Scholar, CNKI, Wanfang, VIP, or other sites without an official public API, and do not bypass captchas, login, paywalls, or institutional access controls.

Domestic `.cn` routes connect directly. Foreign API calls use the
credential-free `RESEARCH_GUARD_FOREIGN_PROXY` setting, which defaults to
`http://127.0.0.1:7897`; proxy failure is recorded as a source failure and does
not silently fall back to an unapproved route.

Index labels are separate claims. Do not infer SCI/SSCI, CCF, IEEE, CSSCI, or C刊 membership from a title, DOI, publisher, venue name, or a discovery source alone. `verify_index_membership` must return verified evidence before using an index label.

## Collision interpretation

The deterministic scorer is a recall-oriented candidate generator. It records exact identity, lexical overlap, deterministic text-vector similarity, component coverage, query diversity, and citation-neighbor signals. Treat high scores as review obligations, not plagiarism findings. Treat low scores as absence of a detected collision under the recorded queries, not global proof of originality.

Every potential/high candidate remains blocking until the method changes or a hash-bound differentiation record is registered and the complete search is rerun. A differentiation record must name concrete component differences and is an auditable research judgment, not independent proof. Exact title/identity collisions cannot be waived.

## Evidence manifests

Each search run writes an immutable evidence manifest under `.research-guard/evidence/runs/`. It records every structured query/source attempt, sanitized endpoint, status/error type, timestamps, result count, and raw-response path/hash. Secrets and contact-email values are redacted from stored URLs. Required-source query failures fail closed; supplemental failures remain explicit. Receipt verification rehashes the manifest and every raw payload.
