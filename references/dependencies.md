# Dependency model

The migration archive is deliberately modular. Core Python, Pint, SymPy,
z3-solver, scientific plotting/export libraries, plugin code, hooks, catalogs,
templates, and the 15-tool MCP server are bundled and installed offline. Pint,
SymPy, and Z3 are core because a triggered formula audit cannot silently omit
dimensional, algebraic, or constraint checks. The MCP transport is implemented
with Python's standard library, so no third-party MCP framework is required.

Optional components are never installed merely because the Skill was loaded. Detection is read-only and does not start compilers. Each component has three explicit choices: reuse and register a detected compatible environment, install the bundled/fixed environment, or leave it disabled.

- `portable-git`: private portable Git used by controlled domain-Skill acquisition and Lean installation.
- `tex-basic`: portable MiKTeX for real TeX-to-PDF compilation. Extra packages may require the configured TUNA CTAN mirror.
- `lean-mathlib`: fixed Lean 4.33.0 and Mathlib v4.33.0. Its download is much smaller than its final precompiled cache; allow roughly 9-13 GB installed.

The first-load inventory also reports three informational integration boundaries.
They are deliberately not install buttons because their environments, model terms, or
licenses need a separate project-level decision:

- `structured-parser-adapters`: accepts normalized, locator-preserving output from
  Docling, GROBID, Marker, or a separately licensed MinerU environment.
- `advanced-statistics`: optional SciPy/statsmodels oracle and extended statistical
  diagnostics; core recomputation remains standard-library only.
- `active-review-ui`: optional ASReview interface/backend; the bundled prioritizer
  remains available and cannot make include/exclude decisions.

The archive's only MCP runtime is the bundled 15-tool `research-guard` server.
It uses JSON-RPC over standard input/output and the bundled Python standard
library; no Node-based MCP SDK or external MCP server is an implicit dependency.
Specialized external providers remain outside the release boundary until they
are separately selected, licensed, and configured by the user.

The dependency manager stores decisions and append-only receipts below `%USERPROFILE%\.research-guard\dependencies` (or `RESEARCH_GUARD_HOME` in isolated tests). Capability code reads only these receipts and registered paths; the machine's ambient `PATH` is not an authorization mechanism.

Installation, optimizer execution, regression, compiler validation, and release
packaging are incremental and serialized. The total task-owned aggregate physical
working-set budget is 512 MiB. Standard work divides it into a 384 MiB child tree
and 128 MiB orchestrator; Lean validation divides it into a 464 MiB child tree and
48 MiB orchestrator and trims reclaimable working sets above 384 MiB. A Windows
Job Object binds every descendant to the owned tree and a 10 ms monitor enforces
the aggregate. Work starts only with 768 MiB machine headroom and terminates only
the owned child tree if free RAM falls below 512 MiB. GPU use is disabled. Test
files and SkillOpt rounds write hash-bound receipts so interrupted work resumes
without replaying verified units. Packaging streams files and stores
already-compressed payloads without recompression.

The bundled scientific runtime defaults OpenBLAS, OpenMP, MKL, and NumExpr to one thread and Matplotlib to the non-interactive `Agg` backend. A caller may deliberately override these environment variables for an admitted experiment, but ordinary Skill operations do not consume all local cores or create unbounded BLAS worker memory.
