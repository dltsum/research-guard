<!-- research-guard-doc-pair: documentation-policy | revision: 2026-08-22.1 -->
# Bilingual documentation maintenance

[English](../README.md) | [简体中文](../README.zh-CN.md)

## Scope

Research Guard treats a document as bilingual only when its English and
Simplified Chinese paths are both registered in
[assets/documentation-parity.json](../assets/documentation-parity.json). The
manifest is the complete set of bilingual promises made by the project. An
English-only provenance or machine-contract file is not silently labeled as
translated.

All registered pairs use one pair id and one shared revision marker. Every
`.zh-CN.md` file in the publishable source tree must belong to exactly one pair.

## Required maintenance workflow

When either member of a registered pair changes:

1. edit the English and Simplified Chinese files in the same focused change;
2. preserve the same level-two section order, public link targets, and image
   targets unless the pair manifest is deliberately revised;
3. perform human bilingual review for meaning, terminology, omissions, command
   correctness, claim boundaries, and natural language quality;
4. update the shared revision marker in both documents and in the manifest;
5. run `python -X utf8 scripts/documentation_parity.py --refresh-hashes` only
   after both files have been reviewed;
6. inspect the resulting manifest diff; and
7. run `python -X utf8 scripts/documentation_parity.py` plus the repository and
   regression validators described in [CONTRIBUTING.md](../CONTRIBUTING.md).

The refresh command updates normalized content hashes. It does not translate,
approve, or silently repair either document.

## What CI enforces

The executable validator in
[scripts/documentation_parity.py](../scripts/documentation_parity.py) checks:

- manifest schema, unique ids, safe relative paths, and exact pair coverage;
- both files and identical pair/revision markers;
- the complete declared level-two heading skeleton in both languages;
- identical Markdown link targets and identical image targets;
- non-empty localized alt text, local image existence, dimensions, aspect ratio,
  file-size bound, provenance record, and recorded asset digest;
- required common and language-specific contract tokens;
- normalized content hashes and the combined pair hash; and
- absence of unregistered `.zh-CN.md` files.

Negative and repository-level cases are in
[tests/test_documentation_parity.py](../tests/test_documentation_parity.py).

## What CI does not claim

Structural parity is not semantic equivalence. Matching headings, links, images,
tokens, and normalized content hashes cannot prove that a translation is
accurate, complete, idiomatic, or appropriate for its audience. That judgment
requires human bilingual review. CI reports only the checks it actually ran and
does not turn a structural PASS into a language-quality PASS.

Likewise, the README illustration is orientation material, not evidence for a
research claim. Its provenance and visual audit do not prove scientific truth.

## Adding another bilingual pair

Create both documents, add one pair record to
[assets/documentation-parity.json](../assets/documentation-parity.json), declare
the complete level-two section mapping and required non-linguistic tokens, and
add the same pair/revision marker to both files. If an image is shared, declare
its dimension, aspect-ratio, size, provenance, and digest contract. Then run the
hash refresh, add focused positive and negative tests, and complete human review
before publication.
