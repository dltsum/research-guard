# P18 optional active AI-reviewer optimization verification

Date: 2026-08-16

Status: **PASS for the focused P18 contract, four SkillOpt rounds, and the
current P5-P14/P16-P18 release contract**

## Corrected product boundary

P18 adds a user-selected strategy that actively adapts a manuscript to improve
scores from a registered AI-reviewer panel. It is not the defensive
`ai_robustness` audit and is never silently enabled. The two modes remain
separate subroutes of the existing `paper_audit` MCP tool, preserving the
17-tool public surface.

The active route uses four executable steps:

1. `ai_optimize_plan` binds the baseline manuscript, exact venue/year/track,
   current official reviewer guidance, fresh primary research records, goal,
   dimensions, and `selected_by=user` receipt.
2. `ai_optimize_register` admits one unchanged baseline plus 1-8 complete
   candidates. It rejects changes to citations, numbers, formulas, and exact
   paragraphs containing limitations, ethics, risks, criticism, or negative
   results.
3. External reviewer agents evaluate every candidate with the same panel of at
   least two distinct models, prompts, score scales, and venue dimensions. Each
   evaluation is bound to the candidate content hash; no hidden model call is
   made by Research Guard.
4. `ai_optimize_select` normalizes scores, computes `mean - 0.5 * population
   standard deviation`, applies registered tie-breaks, and may return the
   baseline with `NO_ROBUST_IMPROVEMENT`.

The selected score is panel- and prompt-local evidence, not an acceptance
probability or a scientific-quality guarantee.

## Evidence used to shape the strategy

- [How Can Rhetoric Reward-Hack AI Reviewers?](https://arxiv.org/abs/2608.08975)
  motivated priority on evidence framing, novelty stance, and then scope
  framing, while warning against assuming recursive or reviewer-guided rewrites
  will transfer reliably.
- [Evaluating the Impact of Reviewer Guideline Design on LLM-Based Automated
  Peer Review](https://arxiv.org/abs/2607.22553) motivated binding candidates
  to current official venue reviewer guidance instead of inventing a generic
  keyword rubric.
- [TitleTrap](https://aclanthology.org/2025.eval4nlp-1.10/) and
  [Style Over Substance](https://aclanthology.org/2025.coling-main.21/) motivated
  truthful title/presentation candidates and separate factual, evidence, and
  style dimensions so polish cannot mask scientific regression.

These are bounded empirical findings, not universal causal recipes. Every
literature-backed product claim retains a clickable primary-record URL.

## Focused tests

Twelve P18 behavioral tests pass. They cover explicit user selection, current
official venue evidence, protected-content freezing, candidate hash binding,
same-panel enforcement, duplicate-panel-slot rejection, post-registration
candidate-drift rejection, minimum model diversity, variance-penalized
selection, baseline retention, manuscript-audit integration, and MCP schema
exposure.

## SkillOpt evidence

Four serial rounds passed all behavioral and static gates. Candidate comparison
rejected prompt-only advice, unconditional automatic optimization, and a new
top-level tool; it admitted the existing-tool plan/register/select/status
subroutes.

| Round | Result | Peak aggregate task-owned working set |
|---:|---|---:|
| 1 | PASS | 167,469,056 bytes |
| 2 | PASS | 169,742,336 bytes |
| 3 | PASS | 172,449,792 bytes |
| 4 | PASS | 175,415,296 bytes |

The ignored development receipt is `evals/p18-skillopt/report.json`; its
content-level report SHA-256 is
`add9b7bd4a3c48911f00851a9611fa22323421fb5f5111075ea0de50cee70b7b`.

## Release regression

A clean serial run passed all 42 current-contract test files and 260 tests with
zero resumed files. Peak aggregate task-owned working set was 204,570,624
bytes, below the 536,870,912-byte limit.

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
| P17 AI-reviewer robustness/figure quality | 7 |
| P18 active AI-reviewer optimization | 12 |

Archived P0-P4 tests that require superseded automatic semantic classification
remain outside the replacement contract.
