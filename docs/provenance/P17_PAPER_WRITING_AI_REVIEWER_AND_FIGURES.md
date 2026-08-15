# P17 paper-writing, AI-reviewer, and figure verification

Date: 2026-08-16

Status: **PASS for the current P5-P14/P16-P17 release-contract suite**

## Accepted architecture

- Complete paper-writing documentation now separates executable gates,
  main-agent writing judgment, optional dependencies, and non-claims.
- `paper_audit review_action=ai_robustness` owns AI-reviewer robustness. No new
  top-level MCP tool was added; the surface remains 17 tools.
- AI-reviewer evidence is bound to at least three primary-record URLs, including
  at least one peer-reviewed record, all freshly reverified within 30 days.
- Prompt injection, hidden reviewer commands, score-targeted paraphrase
  selection, and prestige manipulation fail. Critical limitations, risks,
  ethics, negative results, and criticism are protected rather than optimized
  away.
- Figure planning no longer selects roles from keywords. The main agent selects
  two or three roles, including kind/integrity coverage and venue style when a
  target is known.
- Final-size figure review explicitly gates content occlusion, balanced use of
  space, text/line alignment, margins/gutters, and exact venue conformance.
- Long research and writing use short durable stages, progress feedback,
  append-only/versioned evidence, and receipt inspection after unknown completion.

## SkillOpt evidence

Four serial P17 rounds passed seven behavioral tests and fourteen static
contract conditions per round. Candidate comparison rejected prompt-only
enforcement and a new standalone tool, admitting the integrated hash-bound
subroute. The process did not optimize manuscript scores or a semantic router.

| Round | Result | Peak aggregate task-owned working set |
|---:|---|---:|
| 1 | PASS | 166,060,032 bytes |
| 2 | PASS | 168,132,608 bytes |
| 3 | PASS | 170,082,304 bytes |
| 4 | PASS | 173,150,208 bytes |

The aggregate ignored development receipt is `evals/p17-skillopt/report.json`;
its SHA-256 is
`f4bee490edbeb647951552cec215d7c8dd63b0e87948b29054aeb51d4cf6804e`.

## Current-contract regression

The current P5-P14/P16-P17 groups pass 248 tests:

| Group | Tests |
|---|---:|
| P5 language and paper integration | 41 |
| P6 decisions, translation, and conference writing | 31 |
| P7 strategy | 26 |
| P8 academic figures | 23 |
| P9 venue evidence | 16 |
| P10 routing/domain integration | 26 |
| P11 resource and explicit selection | 19 |
| P12 integrity components | 33 |
| P13 formula/OpenReview/image integration | 12 |
| P14 discipline/release | 6 |
| P16 explicit selection/continuation | 8 |
| P17 AI-reviewer/figure quality | 7 |

An exploratory run of every archived historical test did not pass because P0-P4
and early P1/P5-P9 cases still encode superseded automatic classification,
15-tool, and pre-domain-selection behavior. Those expectations directly
conflict with the current user-mandated main-agent selection contract and are
not restored as compatibility behavior. The current release suite tests the
replacement contract explicitly.

## Claim boundary

PASS is limited to the tested hash-bound contracts. It does not establish paper
quality, global novelty, reviewer fairness, AI authorship, or acceptance
probability. The AI-reviewer registry contains primary study records; reported
associations and attacks remain model-, prompt-, venue-, and dataset-bounded.
