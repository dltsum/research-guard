# Interaction design and writing/figure tests

## Original interaction design

The original design is natural-language collaboration with one main agent:
provide a goal and material, let the agent choose the useful component, do the
work, review the actual result, and deliver the files. P0/P5/P6/P8 historical
plans explain the evolution; the current Skill, component interfaces and
2026-10-22 simplification supersede their old mandatory hash/receipt gates.

The main agent reads the complete request, preserves the user's scope and
scientific meaning, chooses useful owners rather than keyword routing, and
asks only for genuinely missing user decisions. Plans, instruction ledgers,
module records and status queries are optional aids, not prerequisites to
editing or finishing. Ordinary file changes do not invalidate a whole project.
Citations, numbers, real compiler executions and actual review findings still
need substantive checking where relevant.

The interactive-acceptance mode is more specific: the main agent gives an
operator one natural-language task at a time, inspects its real reply/output,
gives feedback, then advances. Begin that mode with component installation;
repair a failure and retest the original request in place. Do not replace
actual dialogues with a mock or outsource the entire acceptance sequence.

## Choose the entrypoint

For writing use `$academic-language-guard`; for figures use
`$academic-figure-guard`. The agent calls tools; the user need not fill JSON or
copy internal identifiers/checksums. Natural-language selection also works.

For current source tests, provide the actual checkout and ask the agent to read
its `SKILL.md` and the relevant child Skill. A running installed cache may be
older even with the same version label. Reading new instructions does not
hot-swap an old MCP process. Report the source revision and actual execution
entrypoint; use a fresh session/server for the selected installation.

Install only needed groups with `component_install.py --components writing figures
--target <absolute-directory>`; core is included. Update in the same directory.
Reuse functioning local Python/TeX/Lean; install dependencies only when needed
and authorized. This source change does not reinstall the plugin or edit hook
trust. See [component installation](../references/component-installation.md).

## Test writing

Start with a real paragraph or section:

~~~text
$academic-language-guard
Use my specified Research Guard source checkout. Polish the attached
Introduction and deliver a revised Markdown file with brief substantive edit
notes. Keep numbers, citations, negation, causal strength, uncertainty and
limitations. Do not invent experiments. Use general academic style unless
a specific venue is supplied. Do not turn this into unrelated novelty work.
~~~

For qualified-reference writing, provide experiment records, current outline,
scope/word budget, protected information and an explicit date threshold.
References must meet one qualification alternative: CAS zone 1 with >10
citations; CCF B/A best-paper nomination or higher; or CCF A oral or higher.
Verify dated primary evidence plus object/method/content similarity.

Transfer reasoning rather than wording: cover eleven logic levels, complete
word/sentence/paragraph alignment, whole-paper consistency and the functions
of every reference figure/table. Preserve the user's outline. Obtain three
distinct actual reviews: logic matching, defensive writing and scientific
adequacy. Retain their dialogues/findings and report missing experiments.
Deliver seven classes: revised manuscript, official-kit compiled PDF, missing
experiments/explanations, reference logic analysis, detailed correspondence,
runnable structural logic checker/input, and one actually compiled complete
Lean file when mathematics and a supported local Lean environment apply.

The useful routes are `language_assist` and
`reference_writing_action=plan/register_reference/submit/audit/status`.
Ordinary edits reuse IDs and directories; no checksum, matching receipt or
compulsory replan is needed. `status` reads a saved result, not a fresh review.

For defensive sentences, ask who uses them, what understanding/decision changes,
and what becomes misleading if removed. Remove irrelevant process narration,
calibrate repeated hedges, relocate a useful boundary or retain meaningful
qualifications. Include captions/prefaces. Review-only work proposes edits
without changing source artifacts; internal working notes may still be written.
Check the actual revised text; a structural PASS is not semantic proof.

## Test figures

Supply the original image and, for paper-specific content, the manuscript or
information notes. For reference-guided illustration, use:

~~~text
$academic-figure-guard
Read my supplied paper and reference image. Preserve every requested fact,
label and connector meaning. Improve this figure's layout and legibility
without inventing results. Use the actual available host image tool when
generated assets are appropriate. Keep real information/style/detail reviews,
native comparisons and crops, and deliver the seven requested artifact classes.
~~~

The reference route is `figure_action=reference_plan/reference_audit/reference_status`.
Each review round uses three actual agents for information, style and detail;
complete at least two rounds and repair final findings. Retain dialogues,
paired crops and pixel observations. No supplied reference means using every
verified historical style, not inventing references. Deliver: final image;
review/comparison records; runnable pixel inspection script/results; component
library; used Internet assets with links/licenses (empty if none); paper-logic
mapping; component explanations and requirement-by-requirement information audit.
Do not fabricate independent reviewers or claim unavailable tool/model control.

Exact formal vectors and statistical plots have a separate deterministic route:
`figure_action=plan/render/audit`. Review the actual final-size PNG and export
SVG/PDF/300-DPI PNG. Statistical plots require real raw CSV and correct estimator,
uncertainty, replicate unit and missingness; no generated measurements. A formal
diagram uses explicit nodes/edges. Do not silently turn a requested generated
illustration into that route, or call a raster container an editable vector.

For a venue, consult its current official year/track/stage rules. No venue means
generic publication style. Ordinary edits do not require replan or file digests;
review the changed visual/scientific content. Pixel differences are observations,
not automatic style verdicts. Vector PDF export does not require TeX.

## User decisions and scope

The user owns final direction/title, missing substantive facts, actual
limitation/ethics choices, dependency/provider spending and changed acceptance
criteria. The agent handles routine layout, implementation and relevant checks.
Do not request authorization already given. Review does not authorize source
edits; explicit file boundaries take priority over convenient adjacent changes.

Preserve requested review rounds and acceptance checks, not obsolete bookkeeping.
Reuse useful existing evidence while it supports the current work; rerun for
relevant changes, failures, unresolved concerns, required live facts or explicitly
requested replication. Unknown completion calls for inspecting saved outputs and
logs before replay, not a specially signed receipt. A default elapsed duration
is not a reason to stop before completion.

## Selective upstream integration

Source: [Stop That Shit 0.2.5](https://github.com/lennney/stop-that-shit/tree/0.2.5),
MIT. The change adapts task responsibility, bounded authority, direct solutions,
evidence-driven expansion, evidence reuse and reader-useful prose. It imports
no upstream runtime code, dependency, classifier or new execution gate.

The existing module catalog exposes advisory `work_discipline`; explicit
selection stores the same advice, and `UserPromptSubmit` supplies compact context.
The language Skill reuses protected information and existing reviews rather
than adding a second analyzer. We do not restore removed hash gates, compulsory
ledgers, fixed audit counts for ordinary tasks or automatic state invalidation.
Requested reference-workflow reviews remain intact. These are agent instructions,
not a new runtime permission boundary or measured model-quality improvement.

## Report a test result

Send the exact request, source/installed revision, input files, output directory,
actual observation and expected result. For writing, identify the changed claim,
lost citation or weak paragraph. For figures, identify the panel, label or edge
and attach the actual output PNG. Include actual errors and reviewer findings,
not credentials. Distinguish a broken tool path, wrong scientific meaning and
weak visual quality.
