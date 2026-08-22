# Research upstream audit

The original eight repositories were pinned to immutable commits and every
`SKILL.md` entrypoint at those commits was inspected. The machine-readable
result is `assets/research-repositories/original-eight-skill-audit.json`.

| Repository | Commit | License | Files | Skill entrypoints | Integration decision |
|---|---|---:|---:|---:|---|
| Academic Research Skills | `bc1478d8747b8fa2665aef5c8260f19999ce59cb` | CC-BY-NC-4.0 | 2402 | 4 | patterns only; no public content/code fusion |
| Nature Skills | `fe7f972c8d5d1c7e08f5ee742dc49fa493614930` | Apache-2.0 | 686 | 19 | selective paper-card/log/response contracts |
| Scientific Agent Skills | `5ad4aae76bc40257b914367afacc6fd686a282d5` | MIT | 2417 | 161 | narrow just-in-time domain adapter source |
| ARIS | `e12e07c7b85ee1a4dc07e5463089aa16836af2bf` | MIT | 693 | 187 | audit/evolution patterns; orchestration rejected |
| AI Research Skills | `773a52944ba4747a18bd4ae9ade53fff041adcbc` | MIT | 529 | 98 | narrow AI-engineering adapters only |
| Research Paper Writing Skills | `77e7c2c1ba06f7d71844873147665437a03aac1b` | MIT | 43 | 1 | claim/evidence pattern already owned |
| PaperSpine | `66dfbf0d620e00735274ce699eaf93ab4518da1e` | MIT | 468 | 5 | argument-spine pattern already owned |
| Paper Craft Skills | `3be47a2a53cc35a411c587bca5231a08de57287a` | no license | 41 | 3 | discovery only; redistribution rejected |

Across 478 entrypoints, 322 overlap an existing canonical owner, 128 are narrow
domain-Skill candidates, 27 informed selective research-artifact contracts, and
one self-evolution entry informed the proposal-only boundary. No complete
third-party orchestrator was imported.

## Additional curated implementations

The repository registry records URLs, licenses, immutable commits, purpose, and
overlap verdicts for SkillOpt, SkillLens, Arbor, Skill-Inject, SkillWeaver,
GraphRAG, LightRAG, PaperQA2, STORM, ASReview, DeerFlow, CSL styles, citeproc-js,
and Citation.js. They are knowledge sources or optional external backends, not
vendored dependencies.

- [SkillOpt](https://arxiv.org/abs/2605.23904) informed bounded
  rollout-reflect-edit-validate acceptance and rejected-edit memory.
- [SkillLens](https://arxiv.org/abs/2605.23899) established that extraction and
  target consumption differ and that negative transfer requires evaluation on
  the actual target agent/harness.
- [Arbor](https://arxiv.org/abs/2606.11926) informed the persistent hypothesis
  tree and preservation of failed artifact/evidence branches.
- [Skill-Inject](https://arxiv.org/abs/2602.20156) and
  [SkillAttack](https://arxiv.org/abs/2604.04989) informed fail-closed instruction
  scanning and multi-round adversarial evaluation boundaries. Static rules are
  documented as triage, never proof of safety.
- [SkillWeaver](https://arxiv.org/abs/2504.07079) and
  [HASP](https://arxiv.org/abs/2605.17734) remain reference-only: automatically
  synthesized executable Skill programs conflict with quarantine and explicit
  execution authority.
- NetworkX is the small deterministic runtime graph. GraphRAG and LightRAG were
  rejected as default backends because they add model/indexing infrastructure
  unnecessary for compact provenance retrieval.
- ASReview is an optional domain adapter for active-learning screening; it does
  not make inclusion decisions.
- Citation.js/CSL or citeproc may be used externally for styles beyond the
  compact built-in four; Crossref identity and claim support gates stay intact.
- PaperQA2 is an optional project RAG backend when the user supplies local full
  text and model/embedding configuration. It is not a default dependency.

Popularity and install counts are discovery signals only. Admission requires a
compatible license, immutable commit, fail-closed quarantine scan, exactly 2-3
proxy trigger/file-selection rounds, current primary and immutable implementation
sources, exactly 2-3 artifact-backed target-harness validation rounds, one locked
final heldout run, no utility or safety regression, and an exact artifact/hash,
overlap-owner, and canonical-owner binding. The frontier protocol produces a
human-review proposal and never admits or executes a Skill automatically.
