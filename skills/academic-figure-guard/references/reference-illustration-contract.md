# Reference-guided scientific illustration

Read the manuscript, identify its actual contribution, and list every fact the user
requires in the figure. Preserve the supplied reference's composition, hierarchy,
information structure, component drawing style, colors, typography, connector
style, box meaning and visual semantics. Adjust only to present the paper's actual
information. Do not delete requested information or invent empirical results.

## Language, interactions and economical routing

Use English for figure prose by default unless the user requests another language.
Translate domain terms consistently; do not translate variable names, code/API
identifiers, or source quotations that must remain exact. English text may need
different line breaks and box widths; do not shrink it until unreadable.

For multi-panel mechanisms, list the real source, payload, destination and
direction of each inter-panel interaction before layout. Render those exchanges
as labeled arrows/ports that actually meet the relevant panel or component.
Panel-level ports must identify their payload and internal role where ambiguous.
Decorative icons, duplicated destination text, or unmatched letter tags do not
substitute for requested visible interaction. Do not invent all-to-all links;
the number of panels follows the user's mechanism, not a universal four-box rule.

Optimize routing in this order: preserve semantics and readable labels; position
connected nodes/ports adjacent or aligned; avoid unrelated nodes/text; minimize
genuine direction changes; then shorten the route. Start with straight segments,
try one elbow only when needed, and justify two or more turns by a real obstacle
or feedback loop after trying a simpler layout. Do not choose a long zigzag merely
because it is below a permissive threshold. Do not fake fewer turns with rounded
corners, split edge IDs, or omitted arrows. Opposite flows use separate labeled
arrows, not an ambiguous double-headed line. Place labels beside shafts.

In `figure_pixel_audit.py`, declare polyline `edges` using actual image coordinates.
The default per-edge budget is one genuine turn. Use a tighter `max_bends: 0` for
aligned inter-panel links; a larger explicit budget needs `routing_reason`.
Duplicate points and forward-collinear samples are not bends; a reversal is.
An over-budget finding requires layout/routing revision, not a raised threshold.
This measures declared paths, not automatic raster tracing or a mathematical
proof of global minimum bends. Review undeclared visible paths and compare
feasible simpler layouts as well; an empty edge list is not evidence of success.
Final reference admission recomputes declared connector findings from those
coordinates; clearing the report's findings or marking review checks true cannot
override excessive turns, unjustified budgets or disconnected declared anchors.

For the four-panel memory example, preserve candidate records (a→c), interaction
feedback (b→a), verification requests (c→d), and verified results (d→c).
Keep internal Agent→Plan→Teaching action ordering and conditional verification;
never simplify these away while shortening connectors.

Use `figure_action=reference_plan/reference_audit/reference_status` when structured
tracking is useful. Provide paths to the manuscript, reference, final images and
review material. A bundle may use `{"outputs": [...]}` without a plan digest.
Normal source, image, crop or dialogue edits do not require replanning or checksum
updates. Check actual files and review the affected content.

Use the latest image tool actually available. Record its real prompt/output and
model-selection limits. It may generate separate components for assembly; inspect
the assembled final image. Explicit user authorization permits programmatic local
repair/vector rebuilding for that request; follow the
[repair/layout playbook](repair-and-layout-playbook.md), preserving design details.
Without a supplied reference, use every verified style
in `assets/style-library/registry.json` and read `historical-styles.md` for their
design guidance. Locate the actual available reference files; do not substitute
fabricated historical references.

Each review round uses three actual agents: information completeness, style
matching and detail quality. Inspect the final image at native resolution and
useful paired reference crops. Address blur, uneven fills, broken lines, awkward
multi-bend connectors, overlap, incorrect typography and misalignment. Preserve
actual dialogues and feedback across multiple rounds. Use ordinary image paths
and reviewer roles; no candidate/reference checksum needs to be supplied.

For intended flat fills, execute the [pixel procedure](../../../docs/FIGURE_FLAT_FILL_AUDIT.md)
before accepting `uniform_intended_fills`. Inventory every intended flat surface;
declare its interior and foreground/border exclusions, not just a clean sample.
An unmeasured fill is NOT_RUN. Correct failures, scan the edited pixels again,
then inspect semantic/style regressions; do not relax tolerance or invent an
intentional gradient to make a failing render pass. Keep failed reports.

Deliver seven classes:

1. Final high-resolution figure.
2. Audit records, especially reference-versus-final comparisons.
3. A runnable pixel comparison/inspection script and useful comparison results.
4. Separately generated component asset library.
5. Internet asset library with sources, licenses and actual usage; an empty library
   is valid when no Internet assets were used.
6. Mapping between the figure and manuscript logic.
7. Component explanations and a requirement-by-requirement information audit.

Record reference/candidate paths, dimensions and crop locations in pixel reports.
Pixel differences are observations, not style or scientific verdicts. The audit
should find real omissions or visible defects; do not duplicate the same pixel
computation merely to validate a previous report. Keep substantive failed checks
and missing materials explicit rather than manufacturing a PASS.
