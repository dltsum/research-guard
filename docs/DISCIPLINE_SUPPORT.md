# Cross-discipline support

Research Guard separates field detection, source discovery, index membership,
and venue quality. The registry routes work and records evidence; it never
labels a journal “good,” proves that it is indexed, or replaces a subject
expert.

## Current coverage

Seven broad profiles own default publication and extended-source routing:

- computer science;
- engineering;
- mathematics and statistics;
- natural science;
- medicine and life science;
- social science;
- humanities.

Fifteen specialized profiles add literature forms, query lenses, and
field-specific boundaries:

- history;
- philosophy;
- literature;
- linguistics;
- archaeology and classics;
- art history;
- religious studies;
- economics and finance;
- psychology and behavioral science;
- education;
- educational technology;
- sociology and anthropology;
- political science and public policy;
- law and criminology;
- communication and media studies.

The machine-readable authority is
[`assets/discipline-registry.json`](../assets/discipline-registry.json).

## First-use initialization

The main agent must choose the field; request text is never keyword-classified.
Call `research_design` with `action=status`, `discipline_action=analyze`, the
full `request_text`, an explicit `discipline`/broad domain,
`discipline_selected_by=main_agent`, and a rationale. Before the call, tell the user:

> 首次构建该领域知识需要联网查询多个官方公开来源，可能耗时数分钟；完成后会复用本地哈希绑定档案。

If the field is not registered, `analyze` returns `INITIALIZATION_REQUIRED` and
performs no network work. After the user has been informed, the main agent calls
`discipline_action=initialize` separately. The serial, low-volume initializer
stores normalized evidence under the
project's `.research-guard/discipline-profiles/` directory. The registry,
profile, and source snapshots are bound into the novelty search-plan hash.
Changing or corrupting any of them invalidates the old collision receipt. The
main agent must then call `classify_domain` again with the explicit profile ID;
no profile refresh silently changes the route.

The anonymous live minimum is:

- [OpenAlex API](https://help.openalex.org/quickstart/) for broad scholarly
  discovery; keyless free calls are supported and an optional free key raises
  the allowance;
- [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
  for DOI and journal metadata;
- [DOAJ public search](https://doaj.org/docs/widgets/) for open-access journal
  and article discovery.

Domestic official routes are used directly. Foreign routes use the configured
credential-free local proxy only when needed. A failed required source produces
`COVERAGE_INCOMPLETE`; cached model knowledge cannot satisfy the gate.

## Humanities and history

History cannot be reduced to journal articles. Its profile distinguishes:

- monographs, book chapters, and reviews;
- critical editions and the exact edition cited;
- archival/catalog records and collection identifiers;
- primary sources with creator, date, provenance, repository, collection,
  series, box/folder/item, language, and transcription/translation boundaries;
- secondary scholarship, historiography, period, geography, and terminology.

Public discovery catalogs include:

- [ERIH+](https://kanalregister.hkdir.no/publiseringskanaler/erihplus/search.action?a=true);
- [JSTOR advanced search](https://www.jstor.org/action/showAdvancedSearch);
- [Project MUSE](https://muse.jhu.edu/search);
- [OpenEdition](https://search.openedition.org/?lang=en);
- [PhilPapers](https://philpapers.org/);
- [Open Library Search API](https://openlibrary.org/dev/docs/api/search);
- [Library of Congress JSON API](https://www.loc.gov/apis/json-and-yaml/);
- [zbMATH Open](https://zbmath.org/);
- [RePEc IDEAS](https://ideas.repec.org/);
- [ERIC](https://eric.ed.gov/).

Education and educational technology additionally expose official venue,
method-standard, and public-data discovery records. Their design and
measurement boundaries are documented in
[EDUCATION_SUPPORT.md](EDUCATION_SUPPORT.md). These records are not rankings and
do not replace live exact-venue evidence.

Subscription sources such as MathSciNet, MLA International Bibliography, and
Historical Abstracts remain explicit manual/institutional routes. Research
Guard does not scrape them or claim coverage without an authorized capture.

## Adding a field

A proposal must include field aliases, literature forms, official public and
manual catalogs, query lenses, interpretation boundaries, main-agent selection
examples, and overlap ownership. Run three to five bounded SkillOpt rounds over
selection validation and continuation receipts, never automatic routing.
Initialization, evidence hashes, complete collision reruns, hyperlinks, and
resource limits are hard gates and cannot be optimized away.
