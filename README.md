# Research Guard

[English](README.md) | [简体中文](README.zh-CN.md)

Research Guard is a set of installable research Skills with executable MCP tools
for literature, study design, experiments, writing, figures and mathematical
checks. Use only the component groups needed for the task.

## Install and use

```sh
git clone https://github.com/dltsum/research-guard.git
cd research-guard
python -I -X utf8 scripts/component_install.py --list
python -I -X utf8 scripts/component_install.py --components literature writing --target <absolute-directory>
```

Start the MCP server using the generated `.mcp.json`, then make a natural-language
request. Update by running the installer against the same directory. A venv is
optional (`--create-venv`); install selected Python packages with
`--install-python-deps` if needed. Reuse existing Python, TeX and Lean environments.
`--verify` is an optional missing-file/import diagnostic.

The [installation prompt](INSTALL_PROMPT.md) explains selection, dependencies and
interactive testing. [SKILL.md](SKILL.md) is the agent entry point.

## What changed on 2026-10-22

Normal research work no longer requires hash parameters, signed receipts,
repeated full-file verification, a new install directory after edits, or a
mandatory register/verify sequence before writing files or completing a reply.
Hooks give short reminders and do not block editing or stopping. Build and
installation use readable files and actual dependencies rather than digest seals.
Documentation edits need no hash refresh or exact heading/token correspondence.

Source links, real computation and requested scientific reviews remain useful
parts of the research itself. Status commands report recorded runs. Explicit
reruns consume the current files and report the actual new result.

[Details and actual runs](docs/SIMPLIFICATION_20261022.md)。

## Component groups

| ID | Functions |
|---|---|
| `core` | Task routing, research records and optional instruction tracking |
| `literature` | Source search, novelty comparison, citations, ingestion and evidence graphs |
| `research` | Ideas, strategy, hypotheses and experiment design |
| `experiments` | Metrics, execution plans, managed reruns and direction exploration |
| `writing` | Academic language, reference logic, paper review and venue-kit formatting |
| `figures` | Data plots, reference-guided figures, image reviews and pixel comparisons |
| `formal` | Units, symbolic/SMT checks, numerical models and actual Lean compilation |
| `skill-lab` | Install Skills, evaluate behavior, study transfer/composition and propose improvements |
| `citespace` | Knowledge graphs, local networks and the native CiteSpace companion route |

Selected groups include their dependencies; no selection installs nothing.
Omitted routes report the missing component. Third-party engines and host agent
or image capabilities must actually be available for those functions.
See [component installation](references/component-installation.md) and
[requirements](REQUIREMENTS.md).

## Writing and figure deliverables

Reference-guided writing reads experiment notes, finds eligible papers using
dated sources, preserves the supplied outline and maps the reference's logic
to the manuscript. The requested three agent reviews cover logic matching,
defensive writing and scientific validity. Deliverables are the manuscript,
official-kit PDF, missing-experiment/explanation list, reference logic analysis,
fine-grained correspondence analysis, verification script and, when applicable,
a compilable single-file Lean proof using the local environment.

Reference-guided figures preserve all requested information and match the
reference design. Each requested round uses three actual agents for information,
style and visual details. Deliver the final figure, reviews and image comparisons,
pixel script, component assets, used internet assets with links, paper-logic
mapping and a per-component information audit. Without a reference, use each
available style in the installed historical catalog.

## Actual interactive records

[Download the offline interactive archive](https://raw.githubusercontent.com/dltsum/research-guard/main/docs/demo/index.html)
and read its [record/rebuild notes](docs/demo/README.md). It shows installation,
individual user questions, actual agent replies, parent feedback and repair
retests. The archive is the earlier 2026-10-21 run, not a new run of today's code.
Its recorded outcomes include 170/176 routes invoked, 43 defects repaired and
retested, and six CiteSpace routes explicitly skipped. Unresolved writing gaps
and a composition result of `NOT_DEMONSTRATED` remain visible.

For new acceptance work, request one feature at a time. The operator executes it,
the parent gives feedback, and failures are fixed and retested in place. At least
two real input examples, dependency/platform notes and original call records let
other people install the Skill and judge the result.

## Further documentation

- [Source policy](skills/research-novelty-guard/references/source-policy.md)
- [Research design](skills/research-design-guard/SKILL.md)
- [Writing](skills/academic-language-guard/SKILL.md)
- [Figures](skills/academic-figure-guard/SKILL.md)
- [Skill experiments](references/skill-lab-workflow.md)
- [Optional browser console](docs/RESEARCH_CONSOLE_UI.md)
- [Harness compatibility](docs/HARNESS_COMPATIBILITY.md)
- [CiteSpace integration](docs/CITESPACE_INTEGRATION.md)

Portable file layout does not by itself establish a second-platform execution
result. Report the actual platform, inputs, outputs and checks that were run.
