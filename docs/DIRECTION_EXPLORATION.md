# Research direction exploration

Use `research_design.direction_action` when the task asks for research options
and pilot evidence. The user authorizes the work; the main agent interprets the
request, retains failed ideas, and presents the requested number of options.
There is no arbitrary five-option requirement.

1. `plan` saves the question, scope, and user authorization.
2. `register` saves each candidate's mechanism, prior work, falsifier, feasible
   minimal experiment, and coarse-test protocol.
3. `activate` selects a candidate for the existing literature and experiment
   tools. It does not require unchanged method-file bytes.
4. Actually run the coarse test through managed reproducibility, then use
   `record_iteration` with the run ID and declared result JSON path. Hashes of
   the candidate, method, protocol, result, or execution are not required.
5. `bind_collision` attaches the current literature-search outcome. Missing
   required coverage or unresolved collision candidates remain incomplete;
   a signed receipt is not required.
6. `revise` records a substantive method change as a new candidate revision.
   New scientific claims need corresponding evidence. Ordinary formatting and
   note edits do not trigger fingerprint failures.
7. `finalize` presents 1–20 task-selected candidates whose recorded pilot and
   literature results support presentation. It does not choose a winner for
   the user or infer a global ranking.

`status` summarizes saved results without opening and fingerprinting every
artifact. Optional `verify` checks relevant result JSON and scientific outcome;
an invalid or changed scientific outcome is reported explicitly. A positive
pilot is a local coarse signal, not a final validation or TEST result.

Resources remain task-scoped: use the resource planner when execution budgets
or multiple stages need coordination. Local commands retain path/command safety
and actual execution status. See the [simplified workflow](../references/skill-lab-workflow.md).
