---
name: academic-figure-guard
description: Create and audit truthful publication figures, statistical plots, editable SVG/PDF vector graphics, and deterministic architecture/workflow diagrams. Use for research plotting, visualization, paper figures, charts, vector diagrams, figure revision, or figure QA.
---

# Academic Figure Guard

Call `paper_audit` with `action=status, figure_action=plan` before plotting. Fix the figure ID,
scientific claim, raw source files, final width/height, and SVG/PDF/PNG formats.
Use only the returned 2-3 roles and never request effort above `high`.

For quantitative figures, use project-local raw CSV data. Record the estimator,
uncertainty definition, replicate unit, missing-value policy, transformations,
and deterministic seed. Never use image generation for data or exact formal
diagrams. Never silently exclude rows, connect missing values, use decorative
3D/rainbow/dual axes, truncate bar baselines, or automatically emphasize
`Ours`. User-requested emphasis requires `emphasis_selected_by=user`.

Use `action=status, figure_action=render` with a structured spec. Supported statistical charts are
line, scatter, bar, box, histogram, and heatmap. Formal architecture and
workflow figures use deterministic nodes and edges. Color must have a redundant
marker, line, hatch, label, or edge-style cue. Include informative `alt_text`.

Rendering writes an append-only versioned bundle with raw-data/spec/output
hashes, derived statistics, SVG, PDF, 300-DPI PNG, and a reproduction script.
Run `action=status, figure_action=audit` to inspect actual exports. Then view the current PNG at final
physical size and submit `figure_action=visual_review` only after checking readability,
clipping, legend, uncertainty, redundant color, semantic accuracy, and panel
hierarchy. Unresolved issues require a new render.

Use `action=status, figure_action=verify` before delivery or manuscript-audit submission. Source, spec, manifest,
or output changes invalidate the receipt. Automated checks do not certify
scientific correctness, accessibility, or journal acceptance; verify current
official venue rules online when venue compliance is requested.
