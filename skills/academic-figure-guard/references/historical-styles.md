# Historical style provenance and reusable design rules

This catalog was derived from two user-nominated local Codex conversations on 2026-10-19. It records design constraints, not the scientific claims in those conversations.

## Verified sources and counting

Source conversations: `01a11010-bf44-74f2-a68b-a47d80330efd` and `01a10da2-e378-7f52-b71e-19c3f1bace88`.

The source inventory contains **five design families and seven distinct reference layouts**:

| Catalog ID | Layouts | Source role |
| --- | --- | --- |
| fact-transaction | Transaction/attribution overview; controlled-comparison mechanism | Two figures explicitly nominated as the original paper style |
| lin-dashed-modules | Thin colored dashed subsystem architecture | Fig. 1 of a user-supplied reference paper |
| red-blue-modules | Narrow saturated headers and stacked evidence rows | User-attached example, confirmed by the user's answer |
| warm-workspace | Three-column input/persistent-workspace/evaluation cards | User explicitly supplied this as a reference |
| flashtrace | Isometric token comparison; layered mechanism plate | Two references the user explicitly liked |

One later “salmon dashed arrows / magnification” attachment is a smaller rendering of the FACT overview. It is a duplicate design, not a sixth family. Generated candidates, zoomed error screenshots and rejected iterations are not styles. Two FlashTrace layouts share a palette/component family; either layout must be named in the local run, and the unused layout can be an additional variant.

When no new reference is supplied, produce one final for **every verified catalog ID**. This yields five required finals. Do not silently choose the easiest family or count an upscaled duplicate as another style.

## Public catalog and private bindings

The public JSON catalog lives in `assets/style-library/registry.json`. It intentionally has no bound reference images or local absolute user paths. A rendering run must bind its own authorized reference image, SHA256, source thread and source locator. The machine contract requires a readable `reference_file`; a null public template value is not execution evidence.

Original reference images and exact conversation excerpts are retained only in the local deliverable bundle, outside the public repository. The user authorized local reuse for this skill and demonstrations. That authorization does not establish a third-party open-source license or permission to redistribute private papers. Do not copy a full manuscript, screenshots containing unpublished research, or provider responses into a release.

“Verified” here means source identity and visual style were actually inspected. It does not mean legal rights were independently established, that a manuscript's claims are scientifically validated, or that a generated final has passed review.

## Lessons extracted from the feedback

1. **Read the target paper and freeze its information first.** Build a requirement-to-paper-locator-to-component table, including each equation, comparison, input/output and link meaning. A reference describes presentation; it does not authorize importing its scientific claims.
2. **Match the complete design grammar.** Composition, information structure, hierarchy, scale, typography, panel semantics, fill palette, icon rendering and connector grammar must all be specified. Matching a background color alone is insufficient.
3. **Keep a named baseline immutable.** A user-approved baseline remains the base until the user explicitly replaces it. A local improvement or newly generated preview does not change baseline authority.
4. **Respect the requested edit scope.** If the user asks to change the background and one malformed connector, do not redesign the UI, remove colorful internals, change arrow directions, or replace thick arrows with thin ones.
5. **Use generated components when required; assemble without degrading them.** Record tool/model evidence honestly. If the built-in image tool exposes no verifiable model identifier, record “model not exposed”; never claim a requested version was verified. Preserve border context and render text/formulas crisply rather than pasting blurred component screenshots.
6. **Every connector needs a declared meaning.** Distinguish state/data flow, comparison, feedback and magnification leaders. Unexplained red/black dashed lines are failures. Route to the intended ports/corners, normalize widths and heads, and avoid ugly multi-bend routes or clipped paths.
7. **Tight layout still requires readability.** Keep a balanced rectangular silhouette, consistent card spacing, centered text, adequate line spacing and sufficiently large labels at actual publication size. Do not solve empty space by inventing claims, or solve density by silently deleting requirements.
8. **Flat fills and sharp edges require separate checks.** Audit uniformity away from antialiased borders and intended texture, line continuity, edge spread/blur, doubled borders, crop damage, overlap and text centering.
9. **Iterate with three independent reviewers every round.** Review information completeness, reference-style fidelity and visual details separately. Save actual conversations/findings, including disagreements, corrections and residual uncertainty. A fixed source crop cannot substitute for all three reviews.
10. **Limit pixel-check claims.** Exact RGB equality in retained regions only proves those regions were unchanged. It cannot certify the whole figure, semantic correctness, aesthetic similarity, OCR accuracy or absence of overlap. Use whole-canvas and tiled native-scale views, geometric checks and manual reference comparisons together.

The exact feedback excerpts and source-line locators are in the private local evidence bundle. This public document paraphrases the reusable lesson and excludes transcript dumps.

## Acceptance and delivery

Each final requires the seven requested deliverable classes: final figure; reference-versus-final and round-by-round audit records; executable pixel/geometric validation script; separately generated component library; internet-asset library with used/unused distinction and rights/source records; manuscript-logic mapping; and one-by-one component explanations plus requirement audit.

Record a zero-entry internet-asset library truthfully if no external assets were used. Do not invent search, downloads, assets, review dialogue, a model version, publication-quality certification or pixel-perfect style equality.

Quality is established on the actual exported artifact with its hash, not on a convenient preview. Reopening the final export, checking all required information, and completing all three independent reviews remain required even when the code or prior round passed.
