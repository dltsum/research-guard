# Third-party notices

## Included code

`scripts/citation_formatter.py` is a byte-identical copy of the
`ref-style-converter` implementation supplied by the project owner. Its
`SKILL.md` declares the MIT License. Imported SHA-256:
`6088c3d2d5649dda8457fb8bdfbae96bd7c525b50311993f40708b610b984bef`.
Research Guard wraps it with mandatory DOI metadata verification; its heuristic
free-text parser is not a bibliographic verification mechanism.

Runtime dependencies retain their own licenses:

- Python 3.14.3 - Python Software Foundation License 2.0
- NetworkX - BSD-3-Clause
- Optuna - MIT
- Matplotlib - PSF-based license
- NumPy - BSD-3-Clause and bundled component licenses
- Pillow - MIT-CMU
- pypdf - BSD-3-Clause
- Pint 0.25.3 - BSD-3-Clause
- SymPy 1.14.0 - BSD-3-Clause
- z3-solver 5.0.0.0 - MIT
- Git for Windows MinGit - GPL-2.0-only and bundled component notices
- Elan - MIT OR Apache-2.0

The bundled Elan v4.2.3 installer archive contains only `elan-init.exe`.
Therefore this release separately includes the exact upstream v4.2.3 license
texts at `assets/licenses/elan-v4.2.3-LICENSE-MIT` (SHA-256
`920d8685aa3276617133e07d67502148a619eb274b3bba58c9b45d718b687831`)
and `assets/licenses/elan-v4.2.3-LICENSE-APACHE` (SHA-256
`8173d5c29b4f956d532781d2b86e4e30f83e6b7878dce18c919451d6ba707c90`).
Their upstream URLs are the corresponding files under
`https://github.com/leanprover/elan/tree/v4.2.3/`.

The complete 27-distribution Python runtime inventory is recorded in
`assets/runtime-distributions.json`. The corresponding wheel METADATA and
license files remain inside `python-runtime.zip`; the inventory does not replace
those authoritative license texts.

The modular Windows archive also contains the official MiKTeX Basic installer.
MiKTeX is a container distribution whose installed packages retain their own
licenses. It is not run until the user selects TeX installation. Lean and
Mathlib are not vendored in the <=1 GiB archive; the fixed Elan bootstrap is
vendored, while Lean 4.33.0 and Mathlib v4.33.0 are downloaded only after an
explicit selection. Exact payload URLs, byte sizes, and SHA-256 values are in
`assets/payload-manifest.json`.

## Referenced but not vendored

Repository URLs, commit IDs, licenses, and audit classifications in
`assets/research-repositories/` are factual provenance metadata. The package
does not vendor the code or prose of the referenced research Skill,
GraphRAG/RAG, review, or citation repositories. Consult each linked repository
for its license.

The package also excludes cached conference web pages, paper PDFs, and template
ZIPs without an audited redistribution right. `assets/venue-evidence/registry.json`
retains their official URLs and expected evidence metadata so users can acquire
and register exact venue evidence independently.
