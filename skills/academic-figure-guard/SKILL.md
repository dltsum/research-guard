---
name: academic-figure-guard
description: Create and audit publication plots, vector diagrams, and reference-guided scientific illustrations with manuscript tracing, image provenance, and three-agent review. Use for paper figures, reference adaptation, revision, or figure QA.
---

# Academic Figure Guard

Default to English for figure titles, labels, legends and callouts, even when
the conversation or source diagram is Chinese. An explicit user language choice
overrides this default. Preserve identifiers, notation and quoted source text;
translate meanings faithfully and retain a terminology mapping when revising.

Make mechanism panels visibly interact through the paper's actual inputs,
outputs and feedback, not isolated decorated boxes. Arrange panels and ports
before routing: prefer straight arrows, then one-turn paths; minimize actual
turns subject to correct direction, clear labels and obstacle avoidance.
Do not delete a required interaction to meet a bend budget. See the routing
and interaction review in the reference contract.

For conceptual reference-guided illustrations, read
[reference-illustration-contract.md](references/reference-illustration-contract.md).
Use `paper_audit` with `figure_action=reference_plan/reference_audit` to record
the figure contract and actual reviews when useful. `reference_status` is an
optional progress query, not another verification step.
Read the manuscript; preserve requested facts, boxes and connector meanings.
Preserve reference composition, information structure, component art, colors,
line styles, typography, semantics, hierarchy and scale. Adapt to the paper
without dropping information or simplifying detailed colorful UI.

Use the latest built-in image tool; record availability and model-selection limits.
When the user explicitly authorizes programmatic local repair or vector rebuilding,
use that route for the approved scope; retain reference UI detail and editable
sources. Do not treat one approval as permanent permission for future images.
For repair or layout-only revisions, read
[repair-and-layout-playbook.md](references/repair-and-layout-playbook.md).
For task-linked code UI, obsolete-text/artifact cleanup, or compact resizing, also
read [task-faithful-repair.md](references/task-faithful-repair.md). Apply only the
requested changes; a one-image height adjustment is not a default figure policy.
Inspect assembled components. Preserve exact required wording/formulas and the
meaning of translated labels; never invent measurements.
Every verification round requires three independent agents: information, style,
and detail. Preserve the actual dialogue, paired native crops and feedback;
complete at least two rounds and repair final findings. Pixel differences alone
do not certify quality. Without a supplied reference, render every verified
[historical style](assets/style-library/registry.json), resolving actual private
reference files first. Deliver all seven artifact classes defined in the contract.

Before fill approval, run the [all-pixel procedure](../../docs/FIGURE_FLAT_FILL_AUDIT.md).
Missing scope is NOT_RUN, never PASS. Repair failed fills and recheck current pixels;
reviewer booleans cannot override absent or failed measurements.
For reported defect crops, verify actual scope overlap and complete assembled
boundaries; an unrelated clean patch cannot certify the reported defect.

For statistical plots or exact formal vectors, use `figure_action=plan` when useful.
Record claim, sources, physical dimensions and SVG/PDF/PNG outputs. Select
appropriate roles and effort. Check current official venue/year/track/stage
rules when applicable.

Require raw CSV, estimator, uncertainty, replicate unit, missingness, declared
transformations and seed. No generated quantitative data, silent row exclusions,
decorative 3D/rainbow/dual axes, truncated bar baselines, or automatic scientific
emphasis. Explicit emphasis requires `emphasis_selected_by=user`.

Render specs, run `figure_action=audit`, and inspect the final-size PNG under
[visual-quality-contract.md](references/visual-quality-contract.md). Deliver files,
reviews and reproduction code; preserve earlier versions. Recheck changed content,
not unchanged bookkeeping. Ordinary edits need no new plan or checksum receipt.
