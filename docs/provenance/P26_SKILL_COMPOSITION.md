<!-- research-guard-doc-pair: p26-skill-composition | revision: 2026-08-23.3 -->
# P26 Skill composition verification

## Scope and frozen decision

P26 closes one narrow evidence gap: finalized Skills may each work alone without
showing that their combination adds value, that an order matters, or that their
capabilities do not form a harmful path. P26 adds an optional ordered-composition
matrix under the existing `research_design` owner. It adds no top-level MCP
tool, classifier, model, executor, optimizer, installer, admission authority, or
apply path.

The frozen decision requires exactly two or three main-agent-selected, finalized
P24 artifacts; fresh cases; one target order and one different control order;
utility and safety metrics; and exactly two or three replicates. Every replicate
contains no-Skill, every single Skill, target-order, and control-order evidence.
All outcomes and declared cross-Skill paths remain visible.

## Current primary sources and implementation snapshots

Current public records were inspected on 2026-08-23:

- [Generative Skill Composition for LLM Agents](https://arxiv.org/abs/2606.32025)
  motivates measuring Skill subset, count, and order.
- [Break It Down, Pass It On](https://arxiv.org/abs/2608.20274) motivates
  task-level evaluation of modular transfer and composition.

Anonymous public GitHub metadata pinned these implementation snapshots:

| Repository | Immutable commit | Decision |
|---|---|---|
| [benchflow-ai/skillsbench](https://github.com/benchflow-ai/skillsbench/tree/9a1f4dd5f7659f75707435da3ce854b6e48321d1) | `9a1f4dd5f7659f75707435da3ce854b6e48321d1` | Apache-2.0 method source; large payload remains external |
| [oneal2000/SR-Agents](https://github.com/oneal2000/SR-Agents/tree/277fd8d2bbd7d3b81a5cf4ffa6e87e18c7906e4f) | `277fd8d2bbd7d3b81a5cf4ffa6e87e18c7906e4f` | MIT method source; no runtime dependency |
| [simonucl/PolySkill](https://github.com/simonucl/PolySkill/tree/fff8807d7501d93188f9f658f4d0af2f29f35c23) | `fff8807d7501d93188f9f658f4d0af2f29f35c23` | MIT method source; no code fusion |
| [Limax666/CompoSkill](https://github.com/Limax666/CompoSkill/tree/d7dc9d314f491eaace0b9e7c18e0c21ed3b71577) | `d7dc9d314f491eaace0b9e7c18e0c21ed3b71577` | reference only; no redistributable license verified |

Popularity was not used as correctness, safety, or admission evidence. The
adopted implementation is a local standard-library contract, not a copy of an
upstream implementation.

## Baseline and implementation

The initial focused test failed as expected with `ModuleNotFoundError` because
`skill_composition_core` did not yet exist. The first implementation round
passed 11 core behavior tests and exposed one missing MCP route; after routing
through the existing `research_design` owner, all 37 P24-P26 focused tests
passed without adding an eighteenth tool.

The implementation now:

- binds every component to the exact P24 protocol, finalization, artifact,
  owner, overlap decision, and occupied-case boundary;
- rejects P24 case leakage, automatic component selection, identical target and
  control orders, incomplete conditions, replayed receipts, artifact drift,
  state-chain drift, and changed P24 bindings;
- recomputes `POSITIVE_COMPOSITION_GAIN`, `NO_COMPOSITION_GAIN`,
  `INTERFERENCE`, and `SAFETY_REGRESSION` against the strongest measured
  no-Skill/single-Skill reference;
- preserves control classifications and order effects without a score average;
- detects main-agent-declared, source-located, order-respecting capability paths
  crossing at least two Skills; and
- limits positive support to the exact recorded order while keeping
  `universal_claim_allowed=false`, `order_invariant_claim_allowed=false`, and
  `safety_claim_allowed=false`.

## Focused tests and repeated SkillOpt

Four consecutive SkillOpt rounds passed. Every round executed the same 44 tests
covering P26 composition, P25 portability, P24 frontier evaluation, and the P10
canonical MCP/router surface, plus 12 static architecture gates. Coverage
includes positive/no-gain/interference/safety results, target/control order
effects, target and control-only paths, exact P24 bindings, split leakage,
pre-final non-disclosure, ordering, replay, source identity, tampering, actual
MCP dispatch, and the unchanged 17-tool surface.

The largest aggregate task-owned working set was 236,027,904 bytes, below the
536,870,912-byte limit; no working-set trim or trim failure occurred. The local
report is `evals/p26-skill-composition-skillopt/report.json`; its sealed content
digest is `f086c3956f0ee3d4ca356cb1c413c4be5c721de8564be0c15a3876117cacecef`
and its file SHA-256 is
`74b0a6e7e2b1fa9c11749246b86fa094e4765bda3f7679f6d3e0cab5d79974f9`.
Evaluation logs and the local SkillOpt JSON stay local; the deterministic
runner, tests, contracts, and this bounded provenance report ship in the public
package.

A separate whole-repository local run recorded 83 PASS test files and two FAIL
test files. Every recorded failure in those two files was a live anonymous-
source transport call: port 7897 accepted HTTP CONNECT and then returned a TLS
EOF for Crossref, PubMed, OpenAlex, Europe PMC, DataCite, DBLP, HAL, DOI,
OpenAIRE, Zenodo, or ClinicalTrials requests. No assertion or required source
was relaxed. The local whole-suite result therefore remains `ACTION_REQUIRED`
until the external route can be rerun successfully; focused P26 and deterministic
package gates remain separately evidenced as PASS.

## Packaging and publication gates

P26 is registered as required in repository validation, the provenance-safe
source archive, and all four platform migration archives. A prepublication
construction produced all five archive variants. The rebuilt Windows proof
archive was 305,068,965 bytes with SHA-256
`21d167ed53b49546ea1996a60d3e2e512da9337419858ba06dad127f1f7967fb` and
then passed a clean redirected-user-root installation. The installed verifier
reported 17 MCP tools, the P26 route, and pinned Pint 0.25.3, SymPy 1.14.0, and
Z3 5.0.0; installation peak aggregate working set was 342,421,504 bytes.

The bilingual registry binds the English and Simplified Chinese operator
contract and this provenance pair to shared revisions, headings, links, and
normalized hashes. Final archive identities are produced only after this pair
is frozen and belong in release/CI receipts rather than inside an archive input
that would change its own hash. Installed-plugin refresh, remote push, and
exact-commit CI are not claimed by this prepublication record and remain
separate post-commit gates. Archive construction alone is not installation or
publication evidence.

## Claim boundaries

These results establish local contract behavior, data-flow enforcement,
tamper detection, bounded repeated regression, and registered package inclusion.
They do not prove either cited paper, real-world composition benefit, complete
capability-edge coverage, exploitability, global safety, independent model
execution, or venue acceptance. `HUMAN_REVIEW_REQUIRED` is not admission.
Missing executions, conditions, sources, receipts, or human review remain
blocked/`NOT_RUN` and cannot become a positive claim.
