---
name: academic-figure-guard
description: Create and audit truthful publication figures, statistical plots, editable SVG/PDF vector graphics, and deterministic architecture/workflow diagrams. Use for research plotting, visualization, paper figures, charts, vector diagrams, figure revision, or figure QA.
---

# Academic Figure Guard

Call `paper_audit` with `action=status, figure_action=plan` before plotting. Fix
the figure ID, claim, raw sources, final dimensions, and SVG/PDF/PNG outputs.
The main agent must pass 2-3 `selected_roles`, `selected_by=main_agent`, and a
rationale. Include the kind-specific role and `visual_evidence_integrity`;
automatic role selection and effort above `high` are forbidden.

When a publication target is known, first search its exact current official
figure rules. Bind venue, year, track, stage, official policy/rules URLs,
access time, and extracted rules in `venue_contract`, and select `venue_style`.
Memory, nearby years, rankings, or exemplars cannot substitute.

Quantitative figures require project-local raw CSV, estimator, uncertainty,
replicate unit, missing policy, transformations, and deterministic seed. Never
silently exclude rows or use generated imagery, decorative 3D/rainbow/dual
axes, truncated bar baselines, or automatic `Ours` emphasis. Explicit emphasis
requires `emphasis_selected_by=user`.

Render with a structured spec. Supported charts are line, scatter, bar, box,
histogram, and heatmap; formal diagrams use deterministic nodes and edges.
Use redundant color cues and informative `alt_text`.

Rendering creates append-only SVG/PDF/300-DPI PNG, statistics, spec, manifest,
source/output hashes, and reproduction script. Run `figure_action=audit`, then
inspect the current PNG at final physical size. The visual review must confirm
readability, clipping, legend, uncertainty, redundant cues, semantics, panel
hierarchy, no content occlusion, balanced space use, text/line alignment, and
balanced margins/gutters. A venue contract also requires
`venue_style_conformant`. Efficient space use must not create crowding.

Read [visual-quality-contract.md](references/visual-quality-contract.md), then
call `figure_action=verify`. Any unresolved issue requires a new render. Source,
spec, manifest, output, venue, or reported-number changes invalidate receipts
and require rechecking affected prose, tables, figures, formulas, rounding, and
visible labels. PASS never proves scientific correctness or acceptance.
