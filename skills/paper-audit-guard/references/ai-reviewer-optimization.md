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
- freshly verified `ai_review_online_evidence` containing
  `rhetoric-reward-hack-2026`, `reviewer-guidelines-2026`, and
  `titletrap-2025` with clickable primary HTTPS links;
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

Registration fails if a candidate changes the multiset of citations, numbers, or
formulas; changes a paragraph containing limitations, ethics, risks, criticism, or
negative results; or adds hidden/direct reviewer instructions. The response gives
the exact candidate input hashes and venue-rubric hash for evaluation.

## 3. Evaluate the same panel

Evaluate the baseline and every candidate with the same model/prompt/scale panel.
Use at least two distinct reviewer models and effort at most `high`. Each evaluation
must bind run, candidate, model, prompt, input, rubric, and review-output hashes;
report the overall score, every official rubric dimension, and explicit
meaning/evidence preservation decisions.

Do not silently substitute models, prompts, scales, or official criteria between
candidates. A failed or missing run is not a score.

## 4. Select and iterate

Call `review_action=ai_optimize_select` with the complete
`optimization_model_evaluations`. The executable selector ranks candidates using
cross-panel normalized mean minus half the population standard deviation, then
uses weighted official-rubric and worst-panel scores as tie-breakers. It may select
the baseline when no candidate gives a robust improvement.

Apply the selected manuscript and rerun novelty, citation, language, formula,
experiment, figure, and final paper gates affected by the edit. Another batch uses
a new versioned optimization ID. Continue while useful robust gains remain or until
the user's budget/stop instruction; do not stop at an arbitrary time limit.

The result is explicitly optimized for the registered AI-reviewer panel. It may
not transfer to another model, prompt, venue, or human reviewer and is never an
acceptance probability.
