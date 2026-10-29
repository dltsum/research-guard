# All-pixel figure fill checks

## Declare every intended surface

Inventory every background/card intended to be flat. Separate deliberate reference
art, photos, gradients and shadows only when supported by the actual design
request; a generated effect is not approval. Retain rich UI and component art.
Do not flatten the entire figure just to pass its background check.

Declare interior `bbox` rectangles in `flat_regions`. Split irregular interiors.
Exclude known text/icons/strokes/antialiasing/shadows with `exclude_boxes` and
`exclusion_reason`; full-candidate coordinates must stay inside that region.
Do not select only clean corners, exclude defects, or claim whole-figure coverage
from a few patches. Review the entire inventory and exclusions against the image.
The checker cannot infer artistic intention or missing inventory entries.

For user-reported crops, first map their visible defect surfaces into the actual
delivered image and measure overlap with the audit scope. A PASS elsewhere is not
evidence for an uncovered complaint. Keep paired same-coordinate before/after
crops and report coverage gaps. On layered repairs, inspect complete component
boundaries and unintended overdraw as well as retained surface interiors; a later
background layer can truncate an earlier rim while all remaining fills pass.

## Execute the pixel scan

Prepare the inventory and exclusion geometry before testing color values. For
scene-derived masks, keep surface IDs and expected RGBA even for fully occluded
surfaces or strokes with no testable interior; mark those explicitly as excluded,
not as measured PASS. Require a partition of unique eligible pixels, justified
exclusions and unaccounted pixels. Unaccounted pixels must be zero before claiming
complete declared coverage. Rectangle totals may double-count overlapping regions;
do not present their sum as a unique whole-image pixel count.

```json
{"flat_regions":[{"id":"card-interior","bbox":[20,20,180,100],
  "max_channel_range":0,"exclude_boxes":[[40,40,100,60]],
  "exclusion_reason":"Known text foreground; border lies outside bbox."}]}
```

```sh
python scripts/figure_pixel_audit.py reference.png final.png --output audit \
  --regions regions.json --geometry geometry.json --require-flat-fills
```

Every eligible pixel, including alpha, is visited. The report contains exact
examined/excluded counts, RGBA minima/maxima/ranges, violation count, bounds and
first coordinates. `max_channel_range=0` requires identical channels throughout
the declared interior. A larger integer tolerance must come from the design
requirement, never be increased after observing failure to conceal the defect.
Optional `expected_rgba` additionally tests the specified color. Without it,
componentwise minima define the allowed channel intervals; they are not an ideal
color or necessarily an observed joint RGBA pixel. Violation counts/locations
refer to this comparison, not automatic labels identifying every artifact pixel.
For an exact-color repair, always provide `expected_rgba`; a uniformly wrong
color can pass uniformity alone. Geometry masks are not inferred by the standard
rectangle CLI. Supply the scene-derived checker with irregular-geometry results,
or decompose them explicitly without selecting pixels by their observed color.

Missing scope is `NOT_RUN`; nonuniformity is `FAIL`; completed successful checks
are `PASS`. `--require-flat-fills` exits 2 for FAIL or NOT_RUN. Comparison-only
legacy calls still emit a report, but cannot supply fill approval. Different
reference/candidate sizes do not prevent candidate fill checking; SIZE_MISMATCH
describes a separate comparison.

## Correct and recheck

On failure, preserve the report and show the region/coordinates. Correct the
affected fill using the authorized image/source workflow, preserving text,
borders, icons and intended UI detail. Scan the corrected final export under the
same expectations and inspect affected semantic/style regressions. Continue
while defects remain and correction is authorized/possible. If blocked, report
the concrete unmet requirement. Never relabel failure as acceptable or claim
the image was repaired merely because the checker was repaired.

Reference audit recomputes fill measurements from actual final pixels and the
declared geometry. Missing/failed checks prevent PASS even if all reviewer
booleans are true; false metrics are rejected. Status reads stored results only;
explicitly reassess old figures without digest or replanning ceremonies.

## Evidence boundaries

Run negative controls for a one-step RGB change, alpha-only change, and a whole
uniform-but-wrong surface. Preserve their detected locations/counts. Test a
modified excluded pixel only in a separately declared full-export comparison;
it is intentionally outside the flat-fill guarantee. Deterministic render replay
checks export consistency, not independent semantic or design correctness.

After repair, repeat the same coverage/color contract on the actual final export
and review preserved icons, document stacks, summary bars, ports and labels.
Keep failed reviews and follow-ups separate. Do not reuse a previous candidate's
approval or remove rich UI design to eliminate texture.

A scoped PASS does not certify unlisted surfaces, intended artwork, semantics,
style or print readability. Pixel measurements supplement actual image review,
not replace it. Unit fixtures test software, not native-agent performance.
Preserve real failures and meaningful positive controls.
