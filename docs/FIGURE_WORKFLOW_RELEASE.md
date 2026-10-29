# Figure workflow release 0.7.3

## Scope and value

Version 0.7.2 established precise flat-color repair of a reference diagram and
layout-only conversion to one row. Version 0.7.3 adds focused lessons from a
task-linked code illustration and a requested compact revision.
It extends Research Guard rather than replacing it with an image generator.
The Skill controls requirements, tools, review and evidence; the host supplies
image generation and real reviewers. Deterministic repair needs explicit consent.

## Focused 0.7.3 changes

Read [task-faithful repair](../skills/academic-figure-guard/references/task-faithful-repair.md)
only for task/code UI, obsolete-content cleanup or compact resizing:

- Map actual source/target versions, paths, inclusive line ranges and literal
  excerpts consistently across views. Mark schematic proposals and receipts;
  source verification is not a new model run or a measured performance result.
- Remove the full obsolete text footprint, including braces and fringes, while
  preserving nearby icons. Distinguish accidental pale halos from intentional
  glass lighting, including window-frame/header junctions and malformed controls.
- Preserve layer order when repainting chrome: exclude known title/arrow
  foreground geometry or restore it above the repair without hiding crossings.
  A constant-color annular inset is a local option, not a universal glass style.
- Compact only as requested; preserve readable text, component geometry and
  task meaning. Add useful missing task content, not duplicated ornamental UI.
- After final resampling, remap and inspect masks/exclusions, boxes and anchors;
  rerun current-pixel checks and final-size review. Old PASS counts do not carry
  forward. A scoped fill result is not whole-image or print-legibility approval.

The motivating user request reduces one image's height from 1448 to 1378 pixels
(about 4.83%). This is a case-specific requested change, not a default ratio,
aspect-warp mandate or claim that this Skill update rendered/approved the image.
The new behavioral fixtures reuse the existing pixel/geometry checker; no image
renderer, packaging implementation or unrelated capability changes in this update.

## Workflow

1. Read the source and references; map terminology, required components and flows.
2. Choose reference contributions; default to English unless instructed otherwise.
3. Preserve rich UI components; align panels/ports before minimizing arrow turns.
4. Render using the authorized route; retain editable components and final output.
5. Inventory intended flat surfaces and exclusions before measuring color.
6. Scan every eligible pixel against declared RGBA; run defect negative controls.
7. Review information, style and detail with real agents and actual final images.
8. Repair, rescan and follow up; preserve failed versions instead of overwriting
   their conclusions. Deliver usable files, scripts, records and limitations.

See the [playbook](../skills/academic-figure-guard/references/repair-and-layout-playbook.md)
and [pixel procedure](FIGURE_FLAT_FILL_AUDIT.md).

## What the two historical 0.7.2 cases established

The companion submission bundle contains the actual artifacts and review notes.
These are two sequential inputs on one scientific figure, not two unrelated
domains and not a statistical quality benchmark.

| Case | Request | Final scoped evidence | Important review correction |
|---|---|---|---|
| Precise repair | Keep the accepted design, remove noise and uneven fills | 4,826,778 eligible pixels; zero RGBA violations | Restore summary bars and stacked-document motif |
| Single-row layout | Change 2×2 to 1×4 without changing meaning | 7,600,434 eligible pixels; zero RGBA violations | Restore four endpoint-role labels and visible arrowheads |

The two images contain respectively 6,292,656 and 9,125,400 total pixels.
Excluded text, strokes and fixed edge bands are explicitly counted; the figures
are not entirely flat. Both cases include four detected negative controls.
Review records apply to those artifacts, not every future generation.

## Reproduction and installation

Python 3.11+ is required. Pillow is enough for the generic rectangle pixel checker;
the two scene-mask case scripts also use NumPy. Re-rendering the historical case
requires Windows Times New Roman; checking supplied PNG/masks does not.

From the repository directory:

```sh
python scripts/component_install.py --components figures --target ../research-guard-figures
python -m unittest discover -s tests -p "test_p31_flat_fill_evidence.py" -v
python -m unittest discover -s tests -p "test_figure_connector_turns.py" -v
python -m unittest discover -s tests -p "test_figure_repair_boundaries.py" -v
```

Use `--install-python-deps` only when installing the selected dependencies is
needed. Read [the install prompt](../INSTALL_PROMPT.md) for virtual environments,
MCP registration and in-place updates. A source ZIP is not an embedded runtime.

## Platform and evidence boundaries

Codex produced the two real tasks. Claude Code was available locally but had no
authenticated session at release time; it is **not a verified second host**.
No ChatGPT Skills or WorkBuddy run is claimed. Compatible folder structure and
manifests are not execution evidence. A second host needs an actual Skill-triggered
task, input, tool calls, output and follow-up result before claiming the bonus.

For the new task-linked illustration, the local provenance records an exact
three-line reference span, moved between source and target locations, and a
bounded exact-match scan of 337 eligible Python files. The span is intentionally
partial; author-only selection evidence is not agent input. These existing
records are not a benchmark rerun or new compact-candidate audit. The parent
delivery notes retain excluded pixels and print-readability limitations. Private
source data and exact task identifiers are not copied into this shared guidance.

Keep software unit tests, installation/MCP tests, real task reviews and platform
runs separate. Do not award a made-up grade: map evidence to the evaluator's
criteria (usefulness 30%, reuse 25%, actual effect 30%, documentation 15%).
