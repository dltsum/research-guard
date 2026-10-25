---
name: research-guard
description: Research workflows for literature, study design, experiments, reference-guided writing, scientific figures, formula checks and Skill experiments. Install only the needed component groups and retain actual sources, outputs and agent feedback.
---

# Research Guard

Read the user's papers, notes, data and references, then perform the requested
task with the relevant installed component. Use a short plan for complex work.
Plans, instruction ledgers and status commands are optional aids; do not require
them before editing a file, answering, or completing a task. Do not ask for
hashes, signed receipts, repeated verification or a fresh installation directory.

Complete the requested result and necessary consequences within explicit user
boundaries. Review or explanation alone does not authorize source edits. Prefer
existing owners to optional mechanisms; finish when the requested acceptance
is met and no in-scope blocker remains. See the
[interaction and writing/figure test guide](docs/INTERACTION_AND_TESTING.md).

## Install selected components

Read [the installation prompt](INSTALL_PROMPT.md) when installation is needed.

```sh
python -I -X utf8 scripts/component_install.py --list
python -I -X utf8 scripts/component_install.py --components literature writing --target <absolute-directory>
```

Use the same directory for updates. Add `--create-venv` for an isolated Python
environment and `--install-python-deps` when selected packages are needed and
installation is authorized. Reuse functioning local Python, TeX and Lean.
`--verify` is an optional diagnostic for missing files/imports.
Start the actual stdio server with the generated `.mcp.json`.

| Group | Work | External needs |
|---|---|---|
| core | Task routing and research records | Python 3.11+ |
| literature | Sources, novelty, citations and text evidence | Scholarly source access for current claims |
| research | Ideas, hypotheses, experiments and strategies | Research inputs |
| experiments | Metrics, task execution and direction exploration | Data and the selected execution environment |
| writing | Language, reference logic, venue formatting and paper review | pypdf; TeX for a compiled PDF |
| figures | Data plots, reference styles, image review and pixel comparisons | Matplotlib, NumPy, Pillow; host ImageGen |
| formal | Units, symbolic/SMT, numerical and Lean checks | Only the engines actually needed |
| skill-lab | Skill installation, behavioral evaluation, portability and composition | A real agent for behavioral runs |
| citespace | Knowledge networks and native CiteSpace companion | Historical free CiteSpace, Java and its MCP for native runs |

No selection installs nothing; dependencies between selected groups are included
automatically. See [component details](references/component-installation.md).

## Research work

Choose the useful routes based on the task. Record source URLs, file paths,
observations, commands and outputs. Internal record identifiers require no
copying back by the user. Ordinary source or figure edits can be followed by
another run using the same IDs and directories.

Keep factual checks tied to the work: citations must support claims, numerical
values must agree with data, and a proof or compiler result must come from an
actual run. A status query reads the previous result; it does not silently rerun
experiments or certify newly edited inputs. Recompute when current results are
needed. Preserve prior measurements and make clear which run produced them.

Run checks once for the affected behavior. Repeat only after a relevant change,
a failure, an unresolved concern, or an explicit request for replication. Do not
run the same regression in several rounds to fill a checklist, rescan unchanged
files for receipt hashes, or reinstall a functioning component to inspect it.

Do not turn a literature search into a prerequisite for unrelated writing or
editing. For an explicit novelty task, read the recorded search and discuss
actual collisions and source coverage. A changed scientific question may need
a new search; a file edit alone does not invalidate the project.

## Writing and figures

Writing follows [the writing Skill](skills/academic-language-guard/SKILL.md).
Read experiment records, find references under the user's dated eligibility
criteria, preserve the given outline and transfer the reference's logic through
words, sentences, paragraphs, sections and the whole paper. Preserve the
reference's figure/table functions. Use three distinct real agents for logic,
defensive-writing and scientific reviews when that workflow is requested.
Deliver the revised manuscript, official-kit PDF, missing experiments or
explanations, reference logic analysis, detailed correspondence analysis,
verification script, and a single compilable Lean file when applicable and a
local Lean environment is available. Report actual unresolved scientific gaps.

Figures follow [the figure Skill](skills/academic-figure-guard/SKILL.md).
Read the paper and preserve every requested piece of information. Match the
reference's design grammar, adapt its layout to the paper and use current host
ImageGen for requested generated assets. Each requested review round uses
three real agents for information, style and details, with comparison images
and crops. Deliver the final image, review/comparison records, pixel script,
component library, used internet assets with source links, paper-logic mapping,
and per-component explanations/information checklist. If no reference is
provided, use each available historical style in the installed catalog.

## Interactive testing and delivery

When the user requests an interactive acceptance trace, the main agent gives
the operator agent one natural-language request per turn, inspects the actual
result and gives feedback before proceeding. Begin with component installation.
Repair a failure, update in place and retest the original request. Retain the
prompts, actual tool calls, replies, feedback and resulting files. Do not hand
the complete job to another session or substitute a mock interface.

Deliver the Skill, README, platform/dependency/usage instructions and requested
run records. Distinguish executed, failed, skipped and unavailable work. Native
CiteSpace output must come from the native engine; a local network plot is a
separate capability. Do not invent successful executions, citations or proofs.
