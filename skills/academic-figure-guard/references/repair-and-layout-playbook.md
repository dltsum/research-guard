# Precise repair and layout-only revision

## 1. Freeze meaning, not file fingerprints

Record the input, requested change, target layout and language, and the
source → payload → destination list. Inventory labels, ports, icons, stacked
pages, bars and status indicators. Preserve the design; a simplified
wireframe is not an equivalent repair. No hash registration is needed.

When combining references, state which supplied/verified reference contributes
composition, component style, palette or connector treatment. Combine concepts,
not contradictory layouts; do not claim unavailable reference files were used.

## 2. Choose the authorized rendering route

Use the host image tool for normal image generation/editing. Explicit user
authorization permits programmatic local repair or vector rebuilding. For exact
flat-fill repair, a shared scene description can produce editable SVG and a
deterministic PNG. State font/rendering dependencies. Do not silently replace
reference typography or remove component details to make numerical checks pass.

## 3. Inspect pixels under the correct contract

Read the [fill procedure](../../../docs/FIGURE_FLAT_FILL_AUDIT.md). Register all
intended surfaces before examining their colors. Derive masks from geometry, not
from whether pixels happen to match the desired color. Include occluded/tiny
surfaces in the inventory with an explicit no-testable-interior reason.

Use `expected_rgba` for exact-color requests. The standard checker accepts
rectangular interiors and explicit exclusions; irregular geometry needs a
documented decomposition or a scene-derived checker included with the result.
Do not imply that the rectangle CLI automatically inventories an arbitrary image.
Count every eligible pixel; document border/text/antialiasing/shadow exclusions.
Report unique covered pixels separately when declared rectangles overlap.

Test the checker with an RGB perturbation, an alpha-only perturbation, and a
uniform-but-wrong fill. A whole-render replay is a separate export-consistency
check, not an independent proof that content, design or masks are correct.

## 4. Change layout without changing the mechanism

A 2×2 → 1×4 request changes placement, not graph topology. Preserve panel order
when requested, but do not invent a left-to-right pipeline. Reuse component
primitives; do not stretch a bitmap. Remap each port and its role/payload label.
Prefer straight links, then one elbow. Use an exterior two-turn feedback route
only where needed and explain it. Place arrowheads at visible port boundaries,
not underneath an opaque port circle. Inspect label collisions at final scale.

## 5. Review the actual final candidate

Follow the reference contract's real information/style/detail agents and rounds.
Keep failed reviews unchanged. After fixes, inspect the revised image and record
follow-up findings; an old PASS does not cover changed pixels or missing icons.
Recheck affected content, not timestamps or repeated bookkeeping. If required
native reviewers are unavailable, record NOT_RUN instead of imitating them.

## 6. Deliver useful evidence

Include before/after images, editable output, scene/component assets, input and
prompt record, inventory/masks/exclusions, measurement scripts and results,
failed findings, fixes and final reviews. Keep output quality and all evidence
when compressing. Distinguish these claims:

- Unit fixtures: checker/software behavior.
- Real tasks: observed improvements and limitations in the supplied inputs.
- Platform execution: actual host invocation, not a version command or OS port.
- Whole-figure quality: semantic/style/detail review plus appropriate measurement.

At least two distinct input cases and a repeatable installation path make the
Skill assessable. Do not manufacture scores, reviewers, platform runs or missing
assets. Summarize capabilities and remaining evidence gaps in the delivery README.
