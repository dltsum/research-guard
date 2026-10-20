# Qualified-reference writing contract

Use this workflow when the user asks to learn the logic of a qualified recent
reference, adapt the user's existing paper within its established outline, and
deliver a detailed cross-paper logic audit. The agent performs the research,
reading, writing, compilation and actual reviews. The production module checks
the registered evidence and deliverables; its acceptance does not establish
semantic equivalence or scientific truth.

## Start from the user's evidence and outline

Read the experiment records and existing draft before searching. Identify the
research object, method and content, the observations actually supported, the
unmeasured quantities and material limitations. Freeze ordered outline IDs,
titles and heading levels; name the sections to revise, protected information
and whole-draft word budget. Explain a consistency change or justified no-change
for every existing section. Do not turn a local revision into a different paper,
invent an experiment, add unexplained distribution parameters, or hide a genuine
limitation while removing defensive prose.

`publication_date_min` must be explicit and no earlier than 2025. For example,
`2025-01-01` includes publications in 2025; `2026-01-01` implements a strict
"after the end of 2025" interpretation. Record which interpretation the user
intends. Check the actual publication date against primary evidence; a future
publication date is not evidence that a work is already published.

## Three alternative qualification routes

A candidate is eligible only if it meets the frozen date threshold and at least
one row below. The rows are alternatives, not three simultaneous requirements.

| Route | Required facts | Primary evidence to preserve |
| --- | --- | --- |
| CAS | CAS zone 1 **and citation count > 10** | Actual partition edition; dated citation-count provider and exact record; 10 is insufficient, 11 satisfies the numerical condition |
| CCF award | CCF B or A **and** best-paper nomination or higher | Exact CCF list edition; actual best-paper/best-student-paper nomination or award record |
| CCF oral | CCF A **and** oral or plenary oral presentation | Exact CCF list edition; actual presentation classification |

Keep a credential-free HTTPS primary-record URL, local captured evidence,
specific source locator and timezone-aware `checked_at` for identity,
publication date and every claimed qualification. The module records hashes of
the actual evidence files and detects later changes. It cannot infer that a
locally written assertion is true, establish venue reputation, authenticate an
award, or turn a citation-provider name into a verified count. Read the records
and retain the acquisition trace. If evidence is missing, research another
candidate or report the gap; do not fill an oral/award field from reputation.

Assess `research_object`, `research_method` and `research_content` similarity
separately. Each needs an experiment anchor, reference-paper anchor and a
specific explanation. A close mechanism or suitable information structure is
more useful than a generic statement that the papers share a topic. Qualification
does not itself demonstrate suitability.

## Seven requested delivery classes

These are the user's seven classes. Supporting manifests and audit records do
not replace them, and the conditional seventh class is not silently made an
unconditional installation requirement.

1. **Rewritten text.** Deliver the complete revised draft with the existing
   outline titles, order and levels unchanged. Check the whole paper even when
   only selected sections are revised. Claims, evidence, uncertainties,
   quantities, symbols and parameter meanings must remain faithful to the
   user's work.
2. **Conference paper-kit PDF.** Resolve the exact venue, year, track and stage
   using current official sources. Use that kit, compile the actual source,
   retain command/log and source/PDF/kit hashes, and inspect the exported PDF.
   A valid PDF container or venue-looking title does not prove kit compliance.
3. **Experiments or explanations still needed.** For each reference logic gap,
   identify the required experiment or explanation and mark it `needed` or
   `provided` truthfully. Preserve absent experiments as gaps rather than
   inventing measurements or stating a planned experiment has run.
4. **Reference-paper logic analysis.** Explain how the reference builds its
   question, claims, mechanisms, evidence, figures/tables and limitations, and
   where that logic fits or fails to fit the user's paper. Reuse rhetorical
   functions rather than copying the author's sentences.
5. **Detailed word/sentence/paragraph logic correspondence.** Deliver the
   readable matching document and machine-readable alignment manifest. Cover
   all eleven levels below, both texts in full, protected information, explicit
   logical relations and every reference figure/table's function.
6. **Formal logic verification script.** Deliver the exact standalone
   `scripts/writing_logic_verify.py`, not a script that prints PASS. Run it
   against the delivered manifest and texts and retain its actual result.
   Here "formal" describes the registered spans/edge constraints; the script
   does not prove semantic equivalence or scientific validity.
7. **Conditional Lean file.** If the paper contains mathematical reasoning and
   the local environment has Lean, deliver one whole-manuscript `.lean` file,
   actually compile it, bind the result to that file's hash and remove unproved
   `sorry`/`admit`/axiom shortcuts. The proof formalization must also match the
   paper's actual statements. If Lean is unavailable, retain the real
   environment inventory and report `NOT_RUN_UNAVAILABLE`; do not invent a
   proof or install a large environment without the user's choice.

In addition, deliver the **logic matching audit document**, containing the
actual dialogue/feedback and resulting corrections from three different actual
agents. These accompanying audits do not replace delivery class 7.

Internally, `artifacts` registers `draft`, `formatted_pdf`, `supplements`,
`reference_logic`, `detailed_alignment`, `logic_script`, `alignment_manifest`
and `compile_receipt`. The manifest and compile receipt are supporting evidence
for the seven classes, not an alternative list of user deliverables. Figure and
table counterparts, claim evidence, whole-paper consistency actions, kit
evidence and conditional Lean evidence are separate bundle fields.

## Eleven levels and exact coverage

| Manifest level | Audit question |
| --- | --- |
| `section_internal` | Does each section build its intended question, evidence and conclusion? |
| `between_subsections` | Do subsections establish the same justified progression? |
| `within_subsection` | Are the subsection's moves complete and properly ordered? |
| `between_paragraphs` | Are paragraph transitions justified and information-preserving? |
| `within_paragraph` | Does each paragraph build a coherent evidence-bound move? |
| `between_sentences` | Do sentence relations preserve support, contrast and limitations? |
| `within_sentence` | Are conditions, quantifiers, causal strength and referents preserved? |
| `between_words` | Does the complete token correspondence preserve the intended information? |
| `long_range_correspondence` | Are distant definitions, promises, results and conclusions consistent? |
| `wording_style` | Does the adaptation preserve suitable style without copying wording or strengthening claims? |
| `total_word_count` | Does the complete draft fit the frozen budget? |

Offsets use Python Unicode `[start,end)` character indices. Word units are
Latin/number tokens or individual CJK characters; this is not language-independent
linguistic segmentation. Equations and other scripts still need explicit
protected information and the scientific/math audit. Sentence/paragraph units
are deterministic parsing approximations and require human interpretation.

The verifier requires complete text scopes. Word, sentence and paragraph rows
must map individual canonical units on both sides, cover every counted token,
and avoid duplicate source/target pairs. One-to-many or many-to-one associations
use distinct rows and pairs where justified; they are not a demand for equal
word counts between languages. Keep the same explicit allowed logical edge sets
and acyclic `precedes` relations. Matching declared edges does not establish
that the sentences actually express those relations.

For every reference figure/table, register its ID, type, source locator and
logical function. Provide exactly one distinct target identity, actual local
artifact, caption, preserved-function explanation and target evidence anchor.
Do not invent results merely to imitate a reference's experimental figure.
If the user's evidence cannot support a counterpart, report the missing
experiment/explanation and keep the delivery unresolved.

Set each mapping's `status` to `provided` or `missing` (omission retains the
legacy `provided` interpretation). A `missing` entry may point to an honest
gap record; it remains `FIGURE_TABLE_COUNTERPART_REQUIRED:<reference_id>` and
cannot satisfy delivery. A nonempty file or explanation alone does not prove
that a visual preserves the reference's function; the actual logic and
scientific reviewers must inspect it.

For mathematical content, `contains_math=true` requires an explicit availability
record. The default `lean.lean_profile` is `mathlib`, using the registered pinned
Mathlib runtime. An existing pinned standalone Init environment can instead use
`lean.lean_profile="lean-basic"` with its explicit `runtime_root`; the installer
inventory is rehashed, the one whole file must import only Init and disable
autoImplicit, and the actual compiler runs again. A historical receipt alone
does not replace that run. Unavailable registration is reported as
`NOT_RUN_ENVIRONMENT_REQUIRED`, never as absence of mathematical reasoning.
Init-only compilation proves only the supplied statements in that file; the
scientific review must still check that they cover the actual manuscript claims.

Run the standalone script with:

```text
python writing_logic_verify.py alignment.json --project-root PROJECT --output logic-result.json
```

Exit 0 means the registered structural checks passed. It is not a verdict on
semantic equivalence, scientific adequacy, originality or venue compliance.

## Three actual agents and a current draft

Use three distinct actual agent IDs, preserving each original dialogue and
feedback. Do not write three invented reviewer personas or reuse test-fixture
attestations as real reviews. Review the exact qualified reference and draft
hashes. If the author is also one reviewer, disclose that authorship; different
agent IDs using the same model do not demonstrate cross-model validation.

- `logic`: all eleven levels, frozen outline, whole-paper consistency and
  figure/table functions.
- `defensive`: no disclaimer-first framing, imagined critics or hedge stacks;
  preserve material limitations and do not strengthen claims.
- `scientific`: verified reference qualification and claim support, no invented
  results, defined mathematical symbols and parameters, no data-unjustified
  distribution parameters, explicit missing experiments, supported visuals and
  explicit mathematical-reasoning presence assessment.

All checks are explicit booleans with actual issue lists. An issue or failed
check keeps the case `CORRECTION_REQUIRED`; fix the draft or evidence and ask
for renewed reviews of the new hashes. File names and agent-ID strings cannot
authenticate that a conversation occurred; the workflow requires actual host
tool traces and review content, not just structurally valid JSON.

`status`/`verify` report `REPLAN_REQUIRED` for changed experiment/reference/
qualification evidence and `RESUBMIT_REQUIRED` for changed delivered artifacts
or audit dialogues. Do not carry an old PASS onto a changed draft. Treat PASS as
evidence-bound workflow acceptance with recorded attestations; it remains
explicitly **not a semantic proof**.

## Production route

Use the existing `language_assist` tool; this workflow does not add a top-level
tool. Subroute values are `plan`, `register_reference`, `submit`, `audit`,
`status`, `verify`, with `reference_writing_action` and `writing_id`.
Pass `writing_contract` to plan, `writing_reference` to qualification,
`writing_bundle` to submit and `writing_reviews` to audit. Always inspect the
actual return: `NOT_ELIGIBLE`, `DELIVERABLES_REQUIRED`, `CORRECTION_REQUIRED`
and stale-evidence states are meaningful outcomes, not reasons to invent
missing files or change a frozen constraint.
