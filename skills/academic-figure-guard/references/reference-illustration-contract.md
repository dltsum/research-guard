# Reference-guided scientific illustration contract

Use this route for a conceptual paper illustration that must preserve a
reference design. Statistical data and exact formal diagrams retain the
deterministic route. A conceptual illustration can contain exact text, UI and
formulas, but these must be verified or overlaid from the locked manuscript;
generated pixels never establish a scientific measurement.

## Reading and design

Read the current manuscript and relevant supplements. Write a mechanism summary
and trace each user-required fact to a section, page, equation or explicit user
instruction. Separate literature claims from this paper's contributions and
results. Register the full information set before designing. Record ambiguities
instead of inventing a scientific relationship.

Inspect the supplied image at native resolution. Extract nine design dimensions:
composition, palette, components, connections, typography, hierarchy,
visual_semantics, information_structure and scale. Preserve the information
construction logic, art style of components, visual meaning inside boxes and
meaning of line styles. Allow only adaptations needed to represent the paper
clearly. A colorful UI, branching structure or detailed device illustration may
be essential to style; do not erase it merely to make generation easier.

If no reference was supplied, load the verified historical style catalog and
output every verified style once. A design family can have several reference
variants; preserve their source identities and choose the variant appropriate
to the requested composition. No hard-coded count is authoritative. Public
catalog metadata may have null image paths for private references; resolve the
actual files locally before planning. If unavailable, report the missing source
and do useful manuscript/spec work; do not fabricate a visual comparison.

## Executable API and plan schema

All paths are relative to `project_root`, and every material must be inside it.
The Python APIs live in `scripts/academic_figure_core.py` and are also available
through the existing `paper_audit` MCP tool, preserving its single tool owner:

- `figure_action=reference_plan`, `reference_contract={...}` calls
  `plan_reference_figure(root, contract)`.
- `figure_action=reference_audit`, `figure_id`, `reference_bundle={...}` calls
  `audit_reference_figure(root, figure_id, bundle)`.
- `figure_action=reference_status`, `figure_id` calls
  `get_reference_figure_status(root, figure_id)`.

The existing MCP envelope still requires `action` and `project_root`: use
`action=plan` for `reference_plan`, `action=verify` for `reference_audit`, and
`action=status` for `reference_status`. The `figure_action` selects the subroute.

The contract contains:

```json
{
  "figure_id": "mechanism",
  "figure_kind": "conceptual",
  "request_text": "The complete original user request",
  "paper_logic_summary": "How the actual paper works",
  "manuscript_files": ["paper.pdf"],
  "reference_files": ["reference.png"],
  "width_mm": 180,
  "height_mm": 100,
  "minimum_dpi": 300,
  "requirements": [
    {"id": "req-a", "text": "Full required information", "paper_anchor": "Section 3, paragraph 2"}
  ],
  "styles": [{
    "id": "chosen-style",
    "reference_file": "reference.png",
    "design_contract": {
      "composition": "Observed composition",
      "palette": "Observed colors and color roles",
      "components": "Observed component drawing language",
      "connections": "Observed line shapes, arrowheads and meanings",
      "typography": "Observed label hierarchy and fonts",
      "hierarchy": "Observed visual layers",
      "visual_semantics": "What visual encodings mean",
      "information_structure": "How the information is organized",
      "scale": "Overall aspect, object sizes and density"
    }
  }]
}
```

With no user reference, set `reference_files=[]`, add `style_catalog_file` and
include every catalog style whose `verified` is true. Each actual plan style
must have its resolved `reference_file`, `verified=true`, and nonempty
`source_threads`. The catalog, manuscript and references are hash-bound.

## Generation and audit rounds

Use the latest currently exposed built-in image generation/editing tool. The
present `image_gen.imagegen` interface does not expose a model selector. Record
`model_id=null`, `model_selection_supported=false`; a product or model name
remembered from another session is not evidence. Save the actual prompt, tool
record, availability evidence and returned image. Do not relabel deterministic
fixtures or hand-drawn placeholders as image-tool runs.

Components may be generated independently, then assembled with consistent
perspective, palette, lighting, text, line semantics and hierarchy. Keep every
individual material, prompt and origin. After assembly or any repair, inspect
the final composite again. A collection of good components does not prove the
composition is good.

Each of at least two rounds has three distinct agents. Provide the manuscript,
locked requirements, reference, current candidate, native crops and prior
feedback. Preserve actual conversation/feedback files. Agents may be reused
across rounds, but one identity cannot fill several roles in the same round.

| Role | Mandatory checks |
| --- | --- |
| information | all_requirements_present, paper_logic_preserved, edge_meanings_preserved, no_invented_claims |
| style | All nine design_contract dimensions |
| detail | no_blur, uniform_intended_fills, no_broken_lines, no_ugly_multibend_lines, no_overlap, text_centered, fonts_and_formulas_correct, native_resolution_inspected |

Inspect each full image plus native-resolution crops covering all modules,
labels, connectors, junctions and dense areas. Check layout at intended print
size too. Never claim that a vision model literally inspected every pixel;
the script compares every pixel where alignment is valid, while agents reason
about meaning, style and defects in the displayed evidence. Record concrete
coordinates, crops and observations. Final failures require another candidate
and another three-agent round; earlier failed rounds remain in the record.

`scripts/figure_pixel_audit.py` is an independent CLI:

```sh
python scripts/figure_pixel_audit.py reference.png candidate.png --output audit/pixels --regions audit/regions.json --geometry audit/geometry.json
```

It emits an all-pixel absolute difference for equal native sizes, exact counts
and mean absolute channel difference, native paired crops and declared geometry
findings. Different dimensions produce `SIZE_MISMATCH`, with no implicit resize
or similarity score. Geometry checks can flag box overlaps, centering offsets,
excessive bends, disconnected declared anchors and nonuniform intended flat
fills. Geometry manifests need actual measured positions; merely declaring
ideal boxes cannot certify the raster. Blur, glyph accuracy and real line
continuity still require native visual inspection. Numeric differences are not
quality or aesthetic scores, and a valid adaptation need not be pixel-identical.

## Bundle schema and seven deliverables

`bundle={"plan_sha256": plan["plan_sha256"], "outputs":[...]}` must include
exactly one output per planned style. An output contains `style_id`,
`final_image`, `artifacts`, `generation_record`, and `rounds`.

The seven requested deliverable classes are the final image plus the following
evidence (the executable gate splits the paired comparison/report into separate
keys):

| Deliverable | Required artifact key and format |
| --- | --- |
| Finished high-resolution image | `final_image`, actual raster at >= planned dimensions and DPI |
| Comparative audit, especially both-image validation | `comparison_audit`, readable narrative; `pixel_report`, JSON emitted by the CLI |
| Pixel verification script | `pixel_script`, distributable executable Python CLI |
| Individual component material library | `components_manifest`, JSON `items=[{id,file,meaning}]` |
| Collected available and actually used internet assets | `internet_assets_manifest`, JSON `items=[{id,file,source_url,license,license_url,accessed_at,used,used_in}]`; if empty, `empty_reason` |
| Mapping to the paper's logic | `logic_mapping`, JSON `items=[{id,component_ids,present,explanation}]` |
| Per-component explanation and information audit | `component_audit`, same row fields; covers every requirement and every component |

`logic_mapping` and `component_audit` row `id` values are the locked requirement
IDs, each exactly once. `component_ids` point to existing individual materials.
For user-provided or generated materials, record that provenance in the component
manifest rather than inventing an internet license. Internet `used_in` identifies
actual component IDs; record both unused collected candidates and used assets.

The raster must also preserve the planned `width_mm / height_mm` aspect ratio
within 2%. Meeting the two minimum pixel counts alone does not prevent a
stretched printed figure. If a revised layout changes the canvas proportions,
update the physical dimensions in a new plan and bind the review to that plan.

`generation_record` fields are `tool="image_gen.imagegen"`,
`availability_checked_at`, `availability_evidence` (file), `prompt_file`,
`tool_record` (file), `model_id=null`, `model_selection_supported=false`.

Each round is `{round_id,image_file,reviews:[...]}`. Every review has `role`,
`agent_id`, `candidate_sha256`, `reference_sha256`,
`method="native_resolution_and_paired_crops"`, `dialogue_file`, `checks` (all
role keys as booleans), and `issues` (array). The last round must inspect the
delivered final image; all its checks must pass and all issue lists be empty.
The final pixel report must bind the actual reference and final hashes and
include native paired crops. The gate recomputes every-pixel metrics and crop
contents to reject a report copied from another image.

The receipt becomes stale if any manuscript, reference, catalog, image, crop,
dialogue, tool record, material or deliverable changes. The gate validates
structural evidence and consistency; recorded agent identities and subjective
review results are attestations, not authenticated execution or a scientific
correctness guarantee.
