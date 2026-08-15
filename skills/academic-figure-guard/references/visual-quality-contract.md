# Final-size scientific-figure quality contract

Apply this contract to the actual current PNG at the planned physical size, not to a design description or an earlier revision.

## Composition

- No text, marker, uncertainty interval, annotation, legend, edge, arrow, node, or panel label may obscure another content-bearing element.
- Use the canvas efficiently, but do not fill space at the cost of hierarchy, legibility, uncertainty visibility, or required whitespace.
- Align text baselines, node rows/columns, panel edges, axes, captions, arrows, and repeated graphical elements consistently.
- Keep margins, gutters, legend offsets, title spacing, and panel spacing balanced at final size.
- Prefer direct labels when they reduce lookup cost without causing collisions. A legend must not cover data.

## Scientific semantics

- Confirm that the geometry, ordering, axes, scales, uncertainty, missingness, transformations, and visual emphasis match the registered scientific claim and source data.
- Color needs a redundant marker, line style, hatch, label, or edge style.
- Never improve composition by removing inconvenient data or uncertainty.

## Venue binding

When a publication target is known, search the exact official venue or journal rules first. Bind venue, year, track, stage, policy URL, figure-rules URL, access time, and extracted rules during planning. A nearby year, related journal, CCF class, exemplar, or remembered convention is not a substitute.

The visual review must explicitly mark `venue_style_conformant=true` when a venue contract is present. This covers only the registered rules; it is not a journal-acceptance guarantee.

## Rerender rule

Every visual check must be true and the unresolved issue list empty. A collision, weak space use, misalignment, clipping, illegibility, or venue mismatch requires a new append-only render; it cannot be waived with prose.
