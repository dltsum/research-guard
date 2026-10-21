# Reference-guided scientific illustration

Read the manuscript, identify its actual contribution, and list every fact the user
requires in the figure. Preserve the supplied reference's composition, hierarchy,
information structure, component drawing style, colors, typography, connector
style, box meaning and visual semantics. Adjust only to present the paper's actual
information. Do not delete requested information or invent empirical results.

Use `figure_action=reference_plan/reference_audit/reference_status` when structured
tracking is useful. Provide paths to the manuscript, reference, final images and
review material. A bundle may use `{"outputs": [...]}` without a plan digest.
Normal source, image, crop or dialogue edits do not require replanning or checksum
updates. Check actual files and review the affected content.

Use the latest image tool actually available. Record its real prompt/output and
model-selection limits. It may generate separate components for assembly; inspect
the assembled final image. Without a supplied reference, use every verified style
in `assets/style-library/registry.json` and read `historical-styles.md` for their
design guidance. Locate the actual available reference files; do not substitute
fabricated historical references.

Each review round uses three actual agents: information completeness, style
matching and detail quality. Inspect the final image at native resolution and
useful paired reference crops. Address blur, uneven fills, broken lines, awkward
multi-bend connectors, overlap, incorrect typography and misalignment. Preserve
actual dialogues and feedback across multiple rounds. Use ordinary image paths
and reviewer roles; no candidate/reference checksum needs to be supplied.

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
