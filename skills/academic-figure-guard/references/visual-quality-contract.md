# Figure quality review

Inspect the actual exported image at its intended physical size and useful native
resolution crops. Check labels, formulas, captions, contrast, line continuity,
alignment, overlap, connector meaning, hierarchy and consistency with the paper.
Check English labels by default (or the user's explicit language), terminology
consistency, and actual interactions between related mechanism panels. Trace
each source→payload→destination at the arrowhead. Prefer zero turns, then one;
additional turns require a visible routing need, not simply a large bend budget.
Ignore duplicate/forward-collinear sampling points when counting actual turns,
but count reversals. The declared-path checker supplements native image review;
it cannot certify untraced paths or global routing optimality.
For intended flat areas, use the [all-pixel fill procedure](../../../docs/FIGURE_FLAT_FILL_AUDIT.md);
a crop-only report or reviewer impression is not a uniform-fill measurement.
For layout changes, inventory port-role labels and component motifs before and
after the edit. A pixel PASS cannot excuse a missing icon or mislabeled arrow.
Check arrowheads at port boundaries so opaque circles do not conceal direction.
For quantitative plots, check the current raw data, estimator, uncertainty,
replicate unit, missing values and declared transformations. Do not invent data.

SVG/PDF should remain readable and PNG should have enough pixels for the intended
use. A new render or ordinary edit can be inspected directly; no prior checksum,
signed receipt, or repeated integrity audit is required. Record substantive
findings and fix them. Scientific image similarity detection is useful only when
requested or relevant to actual image evidence, not as a routine gate on diagrams.
