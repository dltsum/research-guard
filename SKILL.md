---
name: research-guard
description: Install explicitly selected research components, then run evidence-bound literature, research design, experiments, reference-guided writing, scientific figures, formula verification, Skill experiments, or CiteSpace companion workflows. Use for multistep research work requiring traceable tool calls, reproducible artifacts, and independent agent review.
---

# Research Guard

Input: a natural-language research request, selected component IDs, a fresh
installation directory, and paper, experiment, data or reference files.
Output: requested research artifacts, source-bound receipts, actual execution
records, and explicit unresolved checks.

## Install only the requested groups

Read [the complete installation prompt](INSTALL_PROMPT.md) and
[component installation](references/component-installation.md). Run:

```sh
python -I -X utf8 scripts/component_install.py --list
python -I -X utf8 scripts/component_install.py --components literature --target <fresh-absolute-path> --dry-run
python -I -X utf8 scripts/component_install.py --components literature --target <fresh-absolute-path> --create-venv
python -I -X utf8 scripts/component_install.py --target <installed-path> --verify
```

No selection means no installation. `core` is mandatory for any selected group.
Use `--install-python-deps` only when the selected group requires third-party
packages and the user authorizes that installation; it creates an isolated venv.
Never substitute the legacy all-in-one runtime for a selected installation.
Exact pinned requirements and file closures are in `assets/feature-components.json`.

| ID | Capability | Automatically includes | External needs |
|---|---|---|---|
| core | Instruction contracts, method state, capability selection, receipts | — | Python 3.11+, standard library |
| literature | Sources, novelty, publications, citations, text evidence | core | Current scholarly sources for online claims |
| research | Ideas, hypotheses, candidates, experiments, strategies | literature | Research inputs |
| experiments | Metrics, resource tasks, direction iterations | research | Actual experiment results; selected execution environment |
| writing | Academic language, reference logic, paper audit, venue evidence | literature | pypdf; current official evidence; optional TeX |
| figures | Data figures, reference style, pixel comparison, image integrity | core | Matplotlib, NumPy, Pillow, pypdf; host ImageGen for generated assets |
| formal | Formula contracts, units, symbolic/SMT and numerical checks | core | Pint, SymPy, Z3; explicitly selected Lean profile |
| skill-lab | Skill discovery, quarantine, portability, composition, evolution | core | Genuine model/execution capability for behavioral experiments |
| citespace | Knowledge records, local networks, companion workflow | literature | NetworkX; historical free CiteSpace + Java + original MCP for native runs |

Start the actual stdio server using generated `.mcp.json`. `tools/list` exposes
installed routes; omitted routes return `COMPONENT_NOT_INSTALLED`. Installing
the CiteSpace group does not validate its Java engine. Installing formal does
not establish Mathlib or Lean availability. Platform packaging is reusable;
each host must support the actual execution, MCP, subagent and image capabilities.

## Execute and retain evidence

For interactive acceptance, the main chat owns the sequence. Give the executing
agent one natural-language feature request per turn, including installation as
the first interaction. The agent performs that request, retains actual calls,
responses and artifacts, then waits. The main agent inspects the result and
gives feedback before the next question. Never delegate the whole acceptance
job to another session. Repair defects or missing implementations, test and
push the fix, reinstall from that revision in a fresh target and retry the
original sentence. Keep failed attempts, reviewer feedback and retests in an
append-only chronological transcript with component/action indexes. Startup,
schemas, status and refusal checks do not substitute for core feature examples.

1. Read the selected group's installed Skill only when needed. The main agent
   chooses one to three semantic modules using `select_research_modules`; a
   keyword router or small model must not make the scientific choice.
2. Register a multistep instruction contract. Preserve every requested output,
   acceptance criterion and unresolved blocker. A changed method invalidates
   prior novelty evidence; register and search the complete updated method.
3. Use actual inputs and tool calls. Retain natural-language prompts, selected
   routes, exact parameters, raw responses, process exits, source times,
   hashes, artifacts, reviewer identities, feedback and retest records.
4. Keep user-owned scientific choices explicit. Do not invent observations,
   citations, eligibility, image content, engine output or proof results.
5. Distinguish successful execution, correct refusal, historical replay,
   unavailable external services and checks not run. A receipt proves only its
   recorded scope. Finish independent work while preserving blockers.

## Feature contracts

Literature and design follow installed `research-novelty-guard` and
`research-design-guard` Skills. Online outages remain visible. Replaying saved
source evidence does not refresh a novelty or citation-count claim.

Writing follows `skills/academic-language-guard/SKILL.md` and its reference-writing
contract. Read experiment records before finding eligible references published
in 2025 or later; eligibility is the user's alternative journal/conference
criteria, supported by dated evidence. Preserve the existing outline and map
logic from words through sentences, paragraphs and sections to the entire paper.
Preserve the reference's figure/table functions. Use three distinct real agents
for logic matching, defensive-writing and scientific audits; deliver all seven
contract outputs: draft, official-kit PDF, missing experiments, reference
analysis, fine-grained match analysis, verification script, and a single
compilable Lean file when applicable and supported by the local profile.

Figures follow `skills/academic-figure-guard/SKILL.md`. Read the paper, preserve
the required information, and adapt the reference's visual grammar to it. Use
the host's current ImageGen capability for requested assets. Every generation
round has three distinct real agents audit information, style and visual
details with side-by-side/crop evidence. Deliver final image, audits/comparisons,
pixel script, component library, internet asset library with provenance,
paper-logic mapping, and per-component explanations/information checklist.
Without a user reference, use every available historical style in the installed
catalog; missing references stay explicit.

Formal checks report Lean, Pint, SymPy, Z3 and numerical checks separately.
No `sorry`, `admit`, unexplained axioms or unsupported parameters. An Init-only
`lean-basic` proof must not be reported as a Mathlib manuscript proof.

CiteSpace follows `skills/citespace-frontier/SKILL.md`; use the original companion
MCP and a legally usable historical free engine. Preserve native display/export
evidence and explain native/export count differences. NetworkX output cannot
substitute for native CiteSpace execution.

## Delivery and platform validation

Deliver the Skill itself, README, dependency/platform/usage instructions,
at least two input runs and original records allowing others to judge results.
A second verified platform is a separate bonus, never inferred from portable
file layout. `references/full-workflow-legacy.md` retains the full workflow for
existing all-in-one installations; its release instructions do not override
selected installations.
