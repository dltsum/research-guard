# P20 local-resource direction-exploration overlap audit

Audit date: 2026-08-22. Fork counts are time-bound adoption signals, not
correctness or quality rankings. Official repositories and documentation were
used for architectural comparison only; no upstream code, model, or runtime was
vendored.

| Upstream | Snapshot evidence | Useful mechanism | Research Guard decision |
|---|---|---|---|
| SakanaAI AI-Scientist | [repository, about 2k forks at audit](https://github.com/SakanaAI/AI-Scientist); [paper](https://arxiv.org/abs/2408.06292) | iterative idea reflection, experiment planning, literature novelty loop | Admit the idea–experiment–novelty ordering. Reject self-reported novelty/feasibility scores and a binary global-novelty verdict; retain complete source coverage, collision resolution, links, and signed receipts. |
| Microsoft RD-Agent | [repository, about 1.8k forks at audit](https://github.com/microsoft/RD-Agent); [Microsoft Research overview](https://www.microsoft.com/en-us/research/articles/rd-agent-an-open-source-solution-for-smarter-rd/) | separation of research proposal and development/real-world feedback | Admit explicit proposal versus execution phases. Reject a new agent runtime, automatic direction selection, API dependency, and overlapping experiment executor. |
| Karpathy autoresearch | [repository, about 13.2k forks at audit](https://github.com/karpathy/autoresearch); [experiment-loop contract](https://github.com/karpathy/autoresearch/blob/master/program.md) | short sequential experiments, fixed evaluation, complete attempt log, keep/discard feedback | Admit frozen pilot checks and full attempt history. Reject destructive reset/discard, endless GPU-specific execution, fixed five-minute experiments, and automatic “best” selection. |
| Optuna | [Study and trial documentation](https://optuna.readthedocs.io/en/stable/reference/generated/optuna.study.Study.html) | explicit trial history, objective direction, constraints, ask/tell lifecycle | Admit finite numeric validation and retained iterations. Do not add Optuna as a runtime dependency here; do not expose `best_trial` because this workflow must present five unranked choices. The existing metrics component remains the optimization owner after commitment. |

## Cross-component owner audit

`research_design.direction_action` is a coordinator only. Resource inventory
remains owned by `resource_plan_action=inventory`; local command execution and
its frozen argv/input/output/environment receipts remain owned by
`research_integrity.execute_reproducibility`; memory limits remain owned by
`resource_guard`; collision search and signed reports remain owned by
`research-novelty-guard`; post-commit metric optimization remains owned by
`metrics_action`.

The coordinator adds only the missing cross-owner lifecycle: explicit user
authorization, candidate-revision hashes, protocol-bound positive pilot checks,
historical evidence binding across candidate switches, simultaneous invalidation
of pilot/collision/choice eligibility after a method revision, and the exact
five-option user-choice gate. It adds no top-level MCP tool, classifier,
automatic ranker, GPU route, external LLM call, scheduler, or command contract.

## SkillOpt and adversarial contract

Four resource-managed rounds must pass. They cover user authorization, privacy-
redacted inventory, GPU-off admission, 5–15 candidate pool bounds, ranking-field
rejection, frozen method/protocol hashes, negative-to-positive iteration,
protocol-illegal numbers, managed-receipt-only evidence, exact five choices,
HTTPS literature links, method-revision invalidation, historical preservation,
artifact tampering, and the unchanged 17-tool MCP surface. Evidence is written
only under the ignored `evals/direction-exploration-skillopt/` directory.

## Executed evidence

The final post-fix run `run-20260821T221359Z` completed four of four rounds with
status `PASS`; its report hash is
`b60949e7295dec3e66e4e22199c579a5f5ee3c11692d31aaf4e25e11cc953292`.
The maximum aggregate task-owned working set across those rounds was
216,739,840 bytes (about 206.7 MiB), below the 536,870,912-byte hard budget.
The outer admission remained 805,306,368 free bytes, the runtime low-water
remained 536,870,912 free bytes, execution stayed serial, and GPU use remained
disabled.

The exact GitHub-CI public pattern set then passed 23 of 23 test files without
resuming cached results in suite `p20-release-preflight-final`. An earlier run
correctly exposed that nested execution had overridden an explicitly stricter
caller threshold. The final implementation reuses the runtime low-water only
for the default nested admission; caller-supplied stricter thresholds remain
binding. Resource-guard aborts and failed optimization attempts are retained in
separate timestamped evidence roots rather than overwritten.

The Windows migration candidate contained 231 files and stayed below the
1 GiB archive cap. A clean redirected-user installation verified the bundled
core runtime,
on-demand optional-component inventory, plugin/Skill copies, version 0.7.0, and
the 17-tool MCP surface. Its aggregate task-owned peak was 417,697,792 bytes,
within the 536,870,912-byte installation policy. The isolated test root was
moved to the Windows recycle bin after PASS. The final archive digest is emitted
by the post-documentation build rather than embedded here, which avoids making
the archive contain a self-referential digest.
