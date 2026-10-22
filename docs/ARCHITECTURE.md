# Architecture and enforcement boundaries

## Canonical owners

| Owner | Scope | Checks and records |
|---|---|---|
| `research-novelty-guard` | publication and extended-source discovery, substantive collision review | source attempts, coverage and actual mechanism comparisons |
| `research-design-guard` | optional instruction/task plans, discipline profiles, research design, hypotheses, experiments, metrics, reproducibility, domain Skills, frontier/portability/composition studies, knowledge and research artifacts | declared requirements, task IDs and paths, split controls, actual execution results and saved progress |
| `paper-audit-guard` | manuscript ingestion, citations, claims, statistics, record health, mathematics, code, experiments and optional reviewer studies | source locators, claim support, numerical checks, available compilers and actual reviewer outputs |
| `academic-language-guard` | editing, translation, paper logic and reference-based writing | protected meaning, narrative logic, user-selected venue requirements and writing audits |
| `academic-figure-guard` | statistical/vector graphics and reference-based scientific illustrations | source data, actual renders, information coverage, style and visual detail |

Capabilities reuse the existing top-level MCP tools; the installed component
set determines which tools are exposed. Citation and figure operations belong
to `paper_audit`, research coordination routes to `research_design`, and
venue evidence to `language_assist`. Optional owner selection helps complex
work; it is not a registration requirement before ordinary research or editing.

## Frontier Skill research boundary

`research_design.frontier_skill_action` records an optional evaluation of a
Skill on a specified target agent and harness. Ordinary installation and use
do not require this study. The main agent supplies the field, target, cases,
metrics, and overlap owner.

A study declares Skill ID/repository/version, disjoint train/validation/heldout
cases, and utility/safety metric semantics. Validation rounds default to one
and accept 1–10 when the task calls for replication. Sources retain clickable
primary records and implementation identities. Hypotheses retain mechanisms,
falsifiers, sources, owners, and retain/reject/reference decisions.

Trials are bounded project-local JSON records. The core recomputes utility
improvement and safety non-regression rather than accepting supplied PASS
labels. Heldout execution follows accepted validation and is kept separate
from tuning. Finalization requires the declared observations and sources,
retains failed branches, and returns `HUMAN_REVIEW_REQUIRED`. It neither
executes third-party code nor applies a proposal.

The domain-Skill optimizer is a trigger/file-selection proxy, not target-agent
performance evidence. Admission may use a matching finalized study when the
task requests one, but installation does not require an optimization campaign.
Current staged-content scanning detects known instruction risks; it is static
triage and does not establish dynamic adversarial safety. See the
[frontier Skill contract](FRONTIER_SKILL_RESEARCH.md).

## Skill portability boundary

`research_design.skill_portability_action` is an optional follow-on for a
cross-model, cross-harness, or cross-task transfer claim. It reuses a finalized
frontier study's Skill identity, owner, metrics, and occupied case IDs. It does
not require copied file digests or signed execution records.

The main agent declares 2–12 target cells, fresh cases, model/harness versions,
executor groups, and evidence families. At least one target dimension varies.
Paired replicates default to one and accept 1–10. The core recomputes
`POSITIVE_TRANSFER`, `NO_MEASURED_GAIN`, `NEGATIVE_TRANSFER`, or
`SAFETY_REGRESSION` from the inherited metrics. Finalization requires the
declared matrix and sources. It preserves negative results and cell-level
scope instead of averaging away failures or permitting a universal claim.

Shared model families or executor groups share an evidence family; correlated
runs cannot be relabeled independent. Independent corroboration requires
distinct evidence families. The core records external execution evidence and
does not independently rerun it. Status reads saved progress. Explicit verify
can check relevant files when needed. See the
[Skill portability contract](SKILL_PORTABILITY.md).

## Skill composition boundary

`research_design.skill_composition_action` is an optional study of joint
value or order over two or three finalized frontier components. It uses
component IDs and identities, declared target/control orders, fresh cases,
metrics, and source-located capability edges.

Replicates default to one and accept 1–10. Each contains no-Skill, individual
Skill, target-order, and control-order conditions with actual run provenance.
No component or run digest is needed. The core recomputes
`POSITIVE_COMPOSITION_GAIN`, `NO_COMPOSITION_GAIN`, `INTERFERENCE`, or
`SAFETY_REGRESSION` against the strongest no-Skill/single-Skill reference.
It reports order effects separately and retains each replicate.

Declared capability edges are checked for order-respecting paths that cross
Skills from a sensitive source to an effectful terminal. A target-order path
blocks a positive claim; a control-only path remains visible. This is static
triage over declared edges, not proof of exploitation or safety. Positive
claims remain limited to the measured components, target, cases, metrics,
evidence families, and order. Universal, order-invariant, and safety claims
remain disallowed. See the [composition contract](SKILL_COMPOSITION.md).

## Direction-exploration boundary

`research_design.direction_action` begins with explicit user authorization
and coordinates existing resource, experiment, and literature owners. It
records a resource snapshot, candidate methods, bounded pilots, and collision
findings without creating another executor or automatic selector.

Use the saved method ID and actual result paths. Parameter trials can share a
method revision. A substantive change to mechanism, data, or evaluation scope
requires reassessing affected conclusions; an ordinary file edit does not
reset work or require a new registration.

The finalizer accepts the user-selected number of eligible directions from
1–20, preserves neutral registration order, supplies literature links, and
returns `USER_SELECTION_REQUIRED`. A local positive pilot is only a coarse
signal. Collision conclusions remain limited to the sources, coverage, and
date actually checked. See [direction exploration](DIRECTION_EXPLORATION.md).

## Resource-aware planning boundary

`research_design.resource_plan_action` optionally records resources, a task
DAG, execution order, and stage outcomes. The main agent supplies the task
split; simple single-response work needs no task plan.

The planner delegates execution to the existing reproducibility owner. It
uses declared argv, inputs, outputs, runtime, and requested checks rather than
fingerprints. The resource guard owns spawned-process limits. Host CPU/RAM/disk
inventory describes available resources, not task authorization. Native
subagent resources remain host-managed.

Budgets and network authority stay explicit. Missing telemetry remains unknown.
After a transport loss, inspect the linked persisted execution result before
replay so an uncertain command is not silently run twice. A recorded completed
stage is reconciled without rerunning it; absence of a final result does not
prove failure or authorize a retry. Replanning preserves prior progress.
See [resource-aware task planning](RESOURCE_AWARE_TASK_PLANNING.md).

## LLM-assistance delegation boundary

The host agent makes real subagent calls; the MCP server records the plan and
result. Prefer a native subagent where available, or main-agent local work
when the host provides none. Do not claim a subagent ran from a planned call.

External providers require explicit user authorization. Completed units retain
the readable artifact path, actual execution mode, and provider identity.
Same-host or same-model agents are not independent providers merely because
they are separate calls. No artifact fingerprint or signed receipt is required.
See [subagent delegation](SUBAGENT_DELEGATION.md).

## Discipline initialization

The static registry supplies broad and specialized source routes. For an
unregistered field, an explicitly selected initializer performs bounded
discovery against official public sources and saves reusable profile records.

OpenAlex, Crossref, and DOAJ support anonymous journal discovery; humanities
also uses book, edition, and catalog sources. A catalog record does not prove
primary-source relevance. Discovery order is not venue quality ranking.

Reuse saved profiles. Status does not reopen all evidence files; explicit
verify can check relevant source paths. Ordinary edits do not invalidate
collision work. Reassess affected coverage when the field or scientific claim
changes. See [discipline support](DISCIPLINE_SUPPORT.md).

## Main-agent semantic selection

The main agent reads the request and chooses helpful owners, sources, and
reviewer roles. Hooks provide compact reminders, not keyword classification or
a mandatory registration barrier. Optional `select_research_modules` and
domain-selection records can document a complex task's rationale.

The legacy `classify_domain` name records an explicit main-agent choice; it
does not run an automatic classifier. Use audit roles appropriate to the task.
Reference writing and reference illustrations retain the user's explicitly
requested three real auditors.

## Instruction-adherence boundary

`research_design.instruction_action` is an optional ledger for complex
requirements. It can record acceptance criteria, dependencies, actual file
paths, result values, source links, and manual checks. Direct writing, editing,
and experiments do not require a contract before beginning.

Events preserve progress without file fingerprints, state chains, or message
checksums. Ordinary edits can continue under the same IDs and paths. Only
explicit user direction can waive a user requirement; higher-authority and
factual constraints still apply. Status reads recorded work and optional verify
checks relevant evidence. Stop hooks are nonblocking reminders, not completion
authority.

Substantive method changes require revisiting the conclusions they affect.
Previous searches remain historical evidence; a normal file change does not
trigger a complete collision search or force re-registration.

## Long-running search continuation

Collision search saves queries, sources, links, errors, attempts, and progress
incrementally. A scheduling slice can return `IN_PROGRESS` and continue from
its checkpoint. It does not require raw-file or progress digests.

Incomplete required coverage remains `ACTION_REQUIRED`. Retry affected
failures, supply admissible evidence, or record the factual blocker. Attempt
timeouts protect a transport or owned process; they do not establish research
completion. Respect actual user budgets and stop instructions.

Writing, experiments, audits, and research preserve partial results, factual
progress, and distinct missing/invalid/not-run/unknown states. Inspect uncertain
execution outcomes before replay. See the [continuation policy](TIME_AND_CONTINUATION_POLICY.md)
and [research progression contract](../references/research-progression-contract.md).

## Evidence and hyperlink rule

Every literature-producing path must return a clickable `https://` DOI or
primary-record link. DOI metadata verification establishes bibliographic
identity only; it does not show that a source supports a claim. Claim support is
checked separately by the manuscript claim-evidence ledger.

Current external facts such as venue rules, corrections/retractions, dataset
licenses, benchmarks, and software versions require live verification. Saved source records identify what was checked and when; they do not prove
that the external fact remains current.

## Venue hierarchy

1. Current official venue policy and template: hard layout/format authority.
2. Award or high-quality paper: descriptive headings and narrative observations
   for that paper only.
3. CCF A/B catalog: venue discovery and classification only.

No lower level can authorize rules belonging to a higher level. Missing exact
venue/year/track/stage evidence returns `ONLINE_ACQUISITION_REQUIRED`.

## Formula and experiment boundary

Formula assistance uses exactly one manuscript-wide Lean file, disables
implicit undeclared parameters, maps each formula to an ID, and checks that
every registered parameter is legal and used. Formula changes require another
full-file Lean check.

`paper_audit.numerical_action` complements—not replaces—the five-channel formula
audit. It accepts only source-located linear rational systems over declared real
or integer variables. Pint rejects dimensional and affine-conversion errors;
SymPy records canonical relations and equality rank/RREF; Z3 records
SAT/UNSAT/UNKNOWN and tracked cores. For satisfiable systems it derives each
variable's exact marginal projection with open/closed endpoint semantics and
constructs complete joint anchors. Every anchor is rechecked with exact
rationals against every bound, integer type, equation/inequality, and binary64
risk. Marginal intervals are never a claim that their Cartesian product is
feasible. Nonlinear, stochastic, categorical, or specialist systems remain
explicitly uncertified rather than receiving heuristic anchors.

Code/experiment review reads current raw results, configurations, scripts, and
paper claims. It checks result existence, ground-truth provenance, dead paths,
aggregation, seeds, scope, and reported numbers. Passing code execution alone
is not an empirical or scientific-quality claim.

## Macro-first paper spine

`language_assist.spine_action` can organize a local observation into a
paper-level argument. It records the macro problem, unifying mechanism,
abstraction, cross-context predictions and falsifiers, source-linked evidence,
and title options. It is useful when developing the paper's contribution,
not mandatory before ordinary line editing.

An optional collision link connects the existing novelty owner's substantive
comparison to the declared method. Nearby work creates a differentiation
obligation rather than automatically shrinking the question. Method revisions
preserve earlier analyses and require reassessing affected claims, without
copy-back digests or forced complete searches.

Metric plans record methods, experiments, splits, ranges, and candidate budgets.
Analysis reads actual data and checks missingness, duplicate run IDs, and
protocol suitability. Optimization uses its declared split; final TEST remains
outside candidate selection. Scalar ranking needs user-owned weights/scales.
Specialist designs require suitable analyses rather than a generic metric
claim. Ordinary edits and reuse of IDs do not require recreating the plan.

## Optional Research Console boundary

`addons/research-console/` is a separately built presentation adapter. It is
not a canonical research owner and adds no MCP tool, hook, agent, classifier,
model, evidence store, or scientific PASS state. Its only stateful boundary is
one local Codex CLI turn plus browser-local workspace/thread preferences.

The browser sends a validated request to a `127.0.0.1` standard-library HTTP
server. The server verifies the installed/enabled Research Guard plugin and its
resource policy, places the exact installed `SKILL.md` path in a compact visible
context, passes the plugin root privately for the MCP launcher, and sends that
context plus the user's text to `codex exec --json` over standard input. The main Codex agent still owns
semantic module selection; explicit UI focus choices are bounded to three and
never invoke a keyword classifier.

Before each turn, the bridge enumerates Codex MCP configuration, disables every
server except Research Guard, and explicitly rebinds the installed plugin's
canonical local stdio command. That server is required and receives per-server
automatic tool approval; no global approval policy or dangerous bypass is used.
This keeps non-interactive Research Guard calls functional without authorizing
unrelated MCP servers or coupling their memory to the UI process tree.

The bridge streams normalized NDJSON, filters diagnostics, and owns exactly one
Codex child tree. It reuses the core 512 MiB aggregate working-set/512 MiB free-
memory/10 ms sampling contract, one numerical thread, and GPU-off environment.
Resource breach, browser disconnect, user cancellation, or non-zero Codex exit
is an explicit failed turn. There is no whole-research timeout.

The UI add-on has its own archive, manifest, isolated installer, focused tests,
and optional release asset; a checksum file is not required. Both core builders whitelist their
inputs and exclude `addons/`; therefore installing or cloning the core does not
implicitly install the UI. See [the maintained UI contract](RESEARCH_CONSOLE_UI.md).

## Cross-platform runtime boundary

The source MCP entrypoint is shell-neutral. Windows x64 releases retain the
audited offline Python runtime and Job Object process ownership. Linux x64 and
macOS x64/arm64 releases create an isolated Python 3.11+ venv and use a process
group plus `psutil` descendant telemetry. Every platform keeps the same 512 MiB
aggregate owned-task limit, serial execution, one-thread numerical defaults,
and GPU-off policy. Optional Windows payload installers never run on POSIX;
POSIX reuses a validated host dependency or records an explicit degradation.

For source development, the builders expose an explicit `development` mode
that reads the current checkout in place and returns a lightweight receipt; it
does not copy a version, hydrate third-party payloads, pin raw components, or
hash every source file. `release` remains the opt-in archive path. Lifecycle
maintenance uses one short transaction per component/path: `install` and
`update` are aliases, while `resume`, `cancel`, `clean`, and `hard-clean` leave
durable source/results and installed components visible. This boundary is for
research velocity and observability, not a security/threat-model audit.

## Research-artifact contracts

- Paper Card: exactly Sections 01-16, verified primary-record URL, and explicit
  page/structure/source-limited locator mode.
- Systematic review: frozen protocol, DOI/arXiv/OpenAlex-style dedup keys,
  recomputed flow counts, and only `selected_by=user` inclusion decisions.
- Experiment log: readable source files and measurements with units, parameters,
  anomalies and separate interpretations. Measurement times may be unknown.
- Reviewer response: every atomic issue has a status; answered issues require
  evidence; unresolved author input blocks delivery.

## P12 integrity receipts

- Ingestion accepts compact native text/PDF extraction or a normalized
  Docling/GROBID/MinerU/Marker output. Every block requires locator provenance;
  source paths and parser output are recorded.
- Claim-evidence graphs separate support, refutation, and insufficiency.
  Literature/registry evidence requires a clickable primary record. Literature
  evidence is bound to an ingested block; local and registry excerpts must
  occur in a readable UTF-8 source extract. Insufficiency alone
  cannot satisfy a claim, and refutation without support is reported as
  `CLAIMS_REFUTED` rather than a generic PASS.
- Preregistration freezes the declared analysis contract; changes append a
  user-selected deviation instead of altering history.
- Statistical PASS covers only successfully recomputed APA-like reports.
- Reproducibility runs execute the declared command under the resource guard
  and evaluate exit code, output existence and requested content checks.
  External submissions remain review-required; managed execution can report
  PASS after actual success. Edited commands, inputs and existing output paths
  can be reused without environment fingerprints or digest checks. Logs retain
  execution history. Parent RSS is observed; limits cover the spawned tree.
- Active review ranks only undecided records and cannot assign inclusion.
- Crossref update relations preserve prior snapshots. Material updates require
  review of affected claims. Saved reports remain historical results; ordinary
  metadata or deposit-timestamp changes do not invalidate the whole audit.

## Trust model

The plugin does not claim global proof of novelty, correctness, accessibility,
venue acceptance, or research quality. PASS is bounded to the recorded source
inputs, artifacts and actual checks. Status reads recorded results; explicit
execution or submission evaluates current content without digest-seal gates.
