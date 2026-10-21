# Optional active AI-reviewer adaptation

Use this workflow only after the user chooses active score-aware adaptation. It is
not the default paper audit.

## 1. Plan

Call `paper_audit` with:

- `review_action=ai_optimize_plan`;
- a versioned `ai_optimization_id`;
- `selected_by=user`;
- `optimization_goal=maximize_ai_reviewer_score`;
- the baseline UTF-8 `paper_files`;
- relevant verified `ai_review_online_evidence` with clickable primary links;
- `venue_reviewer_contract` for the exact venue/year/track/stage, with current
  official policy and reviewer-guideline URLs plus weighted criteria.

The returned priorities are evidence framing, novelty stance, scope framing,
truthful title presentation, reviewer navigation, and language polish. Apply only
dimensions relevant to the manuscript and venue.

## 2. Generate and register candidates

Use the main model to produce one to eight complete candidate manuscripts. Preserve
the scientific claims and do not expose candidates to the reviewer models before
their prompts and rubric are frozen. Then call
`review_action=ai_optimize_register` with `candidate_manuscripts`; each candidate
declares its files, dimensions, and concrete change summary.

Check that candidates preserve citations, numbers, formulas, limitations, ethics,
risks, criticism and negative findings. Reject hidden/direct reviewer instructions.
Record files, substantive changes and evaluation criteria; no input, output or
rubric digest is needed.

## 3. Evaluate the same panel

Evaluate the baseline and every candidate with the same model/prompt/scale panel.
Choose suitable agents and effort without a separate delegation-registration
step or escalation form. Use at least two genuinely
distinct reviewer model identities. Same-host or repeated same-model subagents do
not create independent panel evidence. If the registered protocol requires an
external provider, obtain the user's explicit exception and record the provider
model identity. Each evaluation records the run, candidate, actual model, prompt,
input files, rubric and actual review output. Report the overall score, every
official rubric dimension, and explicit
meaning/evidence preservation decisions.

Do not silently substitute models, prompts, scales, or official criteria between
candidates. A failed or missing run is not a score.

## 4. Select and iterate

Call `review_action=ai_optimize_select` with the complete
`optimization_model_evaluations`. The executable selector ranks candidates using
cross-panel normalized mean minus half the population standard deviation, then
uses weighted official-rubric and worst-panel scores as tie-breakers. It may select
the baseline when no candidate gives a robust improvement.

Apply the selected manuscript and rerun checks affected by substantive changes.
Ordinary file edits do not require signatures, receipts or a new versioned plan.
Continue while useful robust gains remain or until
the user's budget/stop instruction; do not stop at an arbitrary time limit.

The result is explicitly optimized for the registered AI-reviewer panel. It may
not transfer to another model, prompt, venue, or human reviewer and is never an
acceptance probability.
