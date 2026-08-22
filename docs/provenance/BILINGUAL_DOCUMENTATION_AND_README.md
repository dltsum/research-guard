# Bilingual documentation and README verification

Date: 2026-08-22

## Accepted architecture

The public bilingual promise is explicit rather than inferred. The registry at
`assets/documentation-parity.json` enumerates every English/Simplified Chinese
pair, its one shared revision, full level-two section mapping, common and
language-specific contract tokens, required images, normalized document hashes,
and combined pair hash. `scripts/documentation_parity.py` rejects an incomplete
pair, duplicate paths, unsafe paths, marker/revision drift, section drift, link
or image drift, empty alt text, missing local links, invalid image/provenance
records, stale hashes, and any unregistered `.zh-CN.md`.

The validator deliberately does not score or auto-publish translations.
Structural parity is not semantic equivalence, so human bilingual review remains
the language-quality owner.

## README information architecture

Both READMEs now use the same nine-section skeleton and thirty Markdown link
instances. Their first screen contains one copy-paste Agent installation request,
all four platform archives, checksum records, the approximately 300 MB Windows
boundary, first-load dependency decisions, and the requirements link. The rest
of the page provides a five-stage workflow, an eighteen-row capability chooser,
research gates, dependency degradation, platform/resource limits, documentation,
development commands, and license boundaries.

The common banner is a project-generated 2172 x 724 PNG (3:1, 1,084,531 bytes).
The first generation included formula/code glyphs and was rejected. The admitted
revision contains no words, letters, numbers, equations, or code glyphs. Its
generation prompts, digest, and final visual audit are recorded in
`assets/readme/asset-provenance.json`. PNG signature, ordered chunks, CRCs,
IDAT/IEND presence, dimensions, aspect ratio, file size, digest, alt text, and
provenance binding are executable checks.

## SkillOpt record

The first bounded attempt at
`evals/bilingual-documentation-skillopt/run-20260822T074405Z` retained a FAIL:
all eleven dynamic tests passed, but one static assertion searched for a fully
rendered hash-drift message that the implementation constructs by field name.
Peak aggregate task-owned working set was 142,680,064 bytes. The assertion was
narrowed to the three explicit hash fields and common drift branch; no production
gate was weakened.

The replacement run at
`evals/bilingual-documentation-skillopt/run-20260822T074450Z` completed four
consecutive PASS rounds. Each round ran eight documentation tests and three
public-package tests. Aggregate task-owned peaks were 142,393,344; 142,950,400;
142,643,200; and 144,195,584 bytes. No working-set trim was needed, GPU remained
off, and the 536,870,912-byte task limit was not approached. The final report
digest is `7ae21d7a4aa626c75c1df8e87998a04b51f4362c53ac6ff4319b5bf27565fc16`.

Evaluation directories are local append-only evidence and are intentionally
excluded from the public package. This document records the bounded result; it
does not promote documentation tests into a scientific-quality claim.
