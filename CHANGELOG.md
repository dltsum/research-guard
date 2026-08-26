# Changelog

All notable release-level changes are recorded here. Development evidence and
optimization details live under `docs/provenance/`.

## Unreleased

- Added a direct source-tree development build mode to the modular/public
  builders and runtime repacker. It emits a small inspection receipt instead of
  copying a version, creating a ZIP, pinning raw components, or calculating
  source-file hashes; release packaging remains an explicit separate mode.
- Unified optional-component `install` and `update` into one idempotent path with
  short per-component receipts, `resume`/`cancel`, and explicit interruption
  state. Added `clean`/`hard-clean` to `researchctl`, the dependency manager,
  POSIX installer, PowerShell installer, and the `research_design` maintenance
  subroute. Cleanup reports released bytes and preserves source, conclusions,
  and installed components.
- Documented the research-development operating boundary: ordinary exploration
  does not trigger a safety/security or attacker audit, unusual repeated checks,
  or fail-fast gates; research evidence checks and observability remain intact.

- Added an optional Skill-portability evidence matrix under the existing
  `research_design` owner. It consumes one exact finalized P24 artifact and
  inherited metric contract; freezes 2-12 explicit model/harness/task cells,
  fresh non-P24 cases, evidence-family dependence, and exactly 2-3 paired
  replicates; preserves positive transfer, no measured gain, negative transfer,
  and safety regression per cell; hides outcomes before finalization; and never
  averages away a failed cell or permits a universal portability claim. It adds
  no top-level tool, classifier, model, executor, installer, apply path, or
  admission authority. Four-round SkillOpt, bilingual operator/provenance
  contracts, four-platform packaging, and isolated-install gates are included.
- Added an academic-frontier Skill research protocol under the existing
  `research_design` owner. It freezes target agent/harness, disjoint
  train/validation/heldout cases, utility and safety metrics, exactly 2-3
  validation rounds, and one locked heldout evaluation; binds all trial files,
  sources, hypotheses, owners, overlap decisions, and candidate artifacts by
  hash; preserves rejected branches; and produces a human-review proposal only.
  Domain-Skill admission now requires this exact target-harness evidence in
  addition to the existing proxy SkillOpt rounds. Quarantine scanning also fails
  closed on dangerous Markdown instructions, hidden Unicode, approval bypass,
  concealment, sensitive-data instructions, and cross-file sensitive-source to
  outbound-sink combinations. No third-party Skill code is executed.
- Added the optional cross-platform Research Console as a separately released
  localhost-only browser add-on. It reuses the installed Codex CLI, Research
  Guard Skill/runtime, plugin status, and 512 MiB aggregate process guard;
  streams NDJSON progress, citations, diagnostics, usage, and resource states;
  supports explicit workspace/sandbox/focus selection, cancellation, and thread
  continuation; explicitly binds and requires the local Research Guard MCP,
  grants automatic approval only to that server, disables every other configured
  MCP for the turn; and adds no model, external API fallback, classifier, MCP tool,
  or core-package bytes. Deterministic packaging, isolated installation,
  security/accessibility/static checks, bilingual operations documentation, and
  core-package exclusion tests are included.
- Added executable instruction adherence under `research_design`: the main
  agent registers atomic multistep requirements, dependencies, acceptance
  criteria, forbidden substitutions, and required evidence before mutation;
  append-only hash-chained state, evidence-drift checks, explicit user-only
  waivers, and the Stop Hook prevent premature completion claims.
- Added constructive numerical audit under `paper_audit`: Pint-normalized,
  source-located linear rational equations/inequalities flow through SymPy and
  Z3, exact marginal legal intervals, and independently rechecked complete
  joint anchors. Marginal intervals are never reported as a jointly feasible
  Cartesian product; unsupported nonlinear/specialist systems fail uncertified.
- Added five focused rounds per capability, four-round combined SkillOpt,
  overlap/admission evidence, bilingual operator documentation, repository and
  package admission, and cross-platform CI coverage while preserving the 17
  top-level MCP tools and 512 MiB aggregate resource contract.
- Rebuilt the English and Simplified Chinese README first screen around one
  copy-paste Agent install request, a complete platform download table, first-
  load dependency behavior, a five-stage workflow, a full capability chooser,
  and explicit claim/resource boundaries.
- Added a text-free, project-generated evidence-lifecycle banner with generation
  provenance, PNG structural/CRC validation, dimensions, digest, size limit, alt
  text, and visual-quality audit.
- Added an executable bilingual-document registry. It binds both members to one
  revision, exact level-two section skeletons, identical links/images, localized
  alt text, required contract tokens, normalized content hashes, and one pair
  hash; unregistered `.zh-CN.md` files now fail closed. Human bilingual review
  remains mandatory because structural checks cannot prove translation quality.
- Added cross-platform migration assurance: every CI matrix job now clean-
  installs the exact archive it built, executes the packaged verifier with the
  installed interpreter, and retains that raw ZIP for three days without
  double wrapping. The release workflow repeats the Linux proof before upload.
- Added a SHA-pinned, streaming CI hydrator for the Windows payloads deliberately
  omitted from Git. It cross-checks the prior tagged archive, archived release
  manifest, and committed payload manifest; the Windows builder now fails before
  packaging when any payload is missing, altered, extra, or unsupported.
- Hardened archive admission against traversal, duplicate/case-colliding paths,
  symlinks, unsupported filesystem entries, excessive members, and excessive
  expansion. Installation remains serial, GPU-off, and bounded by the existing
  448+64 MiB managed-install profile.
- Added four-round P21 SkillOpt and explicit overlap/provenance documentation;
  dependency upgrades remain a separate offline-runtime supply-chain rebuild.
- Added an explicitly user-authorized local-resource direction-exploration
  subroute under `research_design`. It freezes a privacy-redacted resource
  snapshot, coordinates 5-15 unranked candidate revisions, accepts only managed
  reproducibility PASS artifacts, recomputes pilot positivity and protocol
  legality, and binds strict complete collision-search receipts with HTTPS links.
- Added an exact-five user-choice gate. Any method, protocol, parameter-range,
  or tracked-file revision makes old pilot and collision evidence ineligible and
  invalidates the active choice set while preserving every historical attempt.
- Compared AI-Scientist, RD-Agent, autoresearch, and Optuna; retained only the
  complementary loop/ledger semantics and added no model, GPU route, scheduler,
  second executor, automatic ranker, or new top-level MCP tool.
- Nested managed tests reuse the registered runtime low-water only when the
  caller kept the default admission threshold. Explicit stricter thresholds
  remain binding, and resource-guard aborts are retained as failed attempts.

## 0.7.0 - 2026-08-21

- Added Windows x64, Linux x64, and macOS x64/arm64 launch, installation,
  resource-telemetry, packaging, and CI contracts. Windows retains the audited
  offline runtime; POSIX platforms use an isolated Python 3.11+ venv.
- Added hash-bound experiment-metric planning, independent-run CSV analysis,
  protocol range checks, validation-only constrained/Pareto comparison, and
  user-owned weighted ranking under the existing `research_design` tool.
- Expanded education research and added a separate educational-technology
  profile with official literature, venue-discovery, method-standard, data,
  measurement, multilevel, psychometric, learning-analytics, privacy,
  accessibility, and fairness boundaries.
- Split the project entry documentation into content-equivalent English and
  Simplified Chinese READMEs.
- Added a narrow `resource_plan_action=execute` binding for the one READY
  `managed_standard` task. It accepts only a fresh user-selected
  `reproducibility_run_id`, delegates to the existing integrity executor, and
  automatically records aggregate working-set telemetry, measured duration,
  output hashes, plan hash, and execution hash. Caller-reported telemetry can no
  longer complete a linked task.
- Revalidated frozen reproducibility plan and execution hashes before launch and
  during status synchronization. Managed reproducibility PASS now requires the
  registered 384+128 MiB resource profile and measured duration. Network-bound
  execution and user disk-write budgets fail closed where full enforcement or
  telemetry is unavailable.
- Hardened the canonical process guard so non-finite or non-positive attempt
  timeouts are rejected before child creation instead of disabling the safety
  bound through `NaN` comparison behavior.
- Added no-replay interruption reconciliation for linked managed stages. A
  valid final integrity receipt is adopted into the task state; without one,
  `execute` returns `RECEIPT_INSPECTION_REQUIRED` and launches no child process.
- Added a typed `research_design.resource_plan_action` route for privacy-redacted
  resource inventory, main-agent-selected task DAGs, serial profile admission,
  user-owned download/disk/time/cost budgets, durable stage transitions, and
  hash-bound expected artifacts.
- Reused the existing 512 MiB process guard, dependency manager, and LLM
  delegation contract. GPU remains disabled; host inventory is not treated as
  process entitlement; missing estimates remain unknown; unknown completion
  requires receipt inspection before resolution or replay.
- Added a dedicated `managed_install` allocation of 448 MiB worker plus 64 MiB
  orchestrator. A real isolated installation of the rebuilt Windows archive
  passed at 433,209,344 bytes aggregate working set without raising the 512 MiB
  total task-owned limit.
- Compared Snakemake, Nextflow, Dask, Ray, and three local Skills; retained only
  complementary DAG/admission/checkpoint semantics and did not add a distributed
  scheduler, model, automatic retry escalation, or top-level MCP tool. Four
  SkillOpt rounds passed with a peak aggregate working set of 202,522,624 bytes.
- Added a hash-bound `research_design.delegation_action` contract for LLM-assisted
  research. It defaults to one serial native entry/economy subagent at low
  reasoning, uses main-agent local fallback when unavailable, and rejects silent
  external-API fallback. External providers require explicit user authorization
  or a registered cross-provider protocol; same-host/same-model subagents are not
  represented as independent reviewers.

## 0.6.4 - 2026-08-16

- Added an explicit, optional active AI-reviewer adaptation route under the
  existing `paper_audit` multiplexer. It binds current official venue guidance,
  complete manuscript candidates, and hash-bound evaluations from the same
  panel of at least two distinct reviewer models.
- Added a variance-penalized selector that optimizes normalized panel score,
  permits the unchanged baseline to win, and freezes citations, numbers,
  formulas, and critical limitations, ethics, risk, criticism, and negative-
  result paragraphs.
- Kept active score optimization separate from the default defensive
  `ai_robustness` audit. Neither route predicts acceptance probability, hides
  reviewer instructions, or fabricates prestige signals.
- Added current primary-record evidence for rhetoric effects, reviewer-guideline
  design, and title/style sensitivity, plus four passing P18 SkillOpt rounds.

## 0.6.3 - 2026-08-16

- Added a hash-bound AI-reviewer robustness audit under the existing
  `paper_audit` multiplexer. It blocks hidden reviewer instructions, prompt
  injection, score-targeted paraphrase selection, and prestige manipulation,
  while separately reporting presentation, critical-topic, metadata, and
  cross-model/rerun sensitivity without predicting acceptance.
- Added a primary-record evidence registry for recent AI-reviewer research and
  a complete manuscript-writing/review capability map covering non-defensive
  language, Nature-accessible prose, textual-artifact revision, translation,
  venue writing, citations, rebuttal, formulas, experiments, figures, and final audit.
- Removed automatic figure-role routing. The main agent now selects 2-3 roles;
  exact venue figure rules are freshness-bound, and final-size review explicitly
  gates occlusion, space use, alignment, margins/gutters, and venue conformance.
- Added durable research-progression defaults for staged checkpoints, progress
  feedback, append-only evidence, unknown-completion recovery, and user-owned
  time/budget stopping.
- Completed four passing P17 SkillOpt rounds. Peak aggregate task-owned working
  set was 173,150,208 bytes, below the 536,870,912-byte limit.

## 0.6.2 - 2026-08-15

- Removed automatic keyword/small-model selection of disciplines, research
  modules, method-change labels, and paper-audit roles. The main agent now makes
  each semantic choice explicitly; executable code validates and hash-binds it.
- Replaced monolithic novelty-search timing with persistent source-query work
  units, linked stage updates, explicit retries, and no wall-clock research
  deadline.
- Required-source failures now return `ACTION_REQUIRED`. Only the main agent's
  explicit factual-blocker decision, full coverage, or a user-supplied budget or
  stop instruction can end an incomplete search.
- Renamed public operation bounds to `attempt_timeout_seconds` and
  `process_timeout_seconds`, audited every remaining timeout boundary, and
  completed four passing P16 SkillOpt rounds under the 512 MiB resource policy.

## 0.6.1 - 2026-08-15

- Consolidated end-user installation on the single approximately 300 MB
  Windows x64 modular archive and removed the custom source ZIP from releases.
- Added a first-screen copy-paste Agent installation request, deterministic
  checksum-verified manual commands, trigger examples, and a complete root
  dependency document.
- Replaced the global first-load optional-dependency block with executable,
  on-demand `reuse`, `install`, and `not_now` decisions.
- Added receipt-bound degraded TeX and formula paths. Declined TeX performs
  static checks only; declined Lean runs Pint, SymPy, Z3, and protocol-numeric
  checks but cannot produce a final formula or manuscript PASS.

## 0.6.0 - 2026-08-15

- Added seven broad and fourteen specialized discipline profiles, including
  humanities/history contracts for books, editions, archives, catalogs, and
  primary-source discovery.
- Added automatic, bounded first-use initialization for unregistered fields
  through current anonymous OpenAlex, Crossref, and DOAJ routes.
- Bound field registry, live profile, and source evidence hashes into the
  novelty plan so profile changes force a complete collision rerun.
- Added a typed `research_design.discipline_action` subroute while preserving
  all 15 top-level tools and legacy action enums.
- Completed four accepted P14 SkillOpt rounds and fixed multi-owner conflict
  evaluation across every selected router module.
- Added publication governance, support, discipline documentation, and a
  GitHub tag-release workflow.

## 0.5.0 - 2026-08-14

- Added separate Lean, Pint, SymPy, Z3, and protocol-admitted numerical formula records.
- Added official OpenReview review calibration without acceptance prediction.
- Added hash-bound scientific-image integrity audit and expert per-flag review.
- Bundled Pint, SymPy, and z3-solver into the offline core runtime while preserving the 512 MiB serial/no-GPU contract.

- Prepared the project for a public GitHub repository.
- Replaced whole-suite execution with serial, hash-resumable test and SkillOpt
  units under a 512 MiB task-owned memory ceiling.
- Added standard 384+128 MiB and Lean 464+48 MiB working-set profiles, with
  descendant accounting, 10 ms sampling, and Lean working-set trimming.
- Added hash-bound candidate configuration testing before SkillOpt admission.
- Converted package creation to bounded, streaming workers.

## 0.4.0 - 2026-08-14

- Added structured paper ingestion, claim-evidence graphs, extended collision
  families, preregistration, statistical recomputation, managed
  reproducibility, human-only active review, and record-health monitoring.
- Added a modular Windows x64 migration package with first-load component
  selection and an offline core runtime.
- Preserved five canonical Skills, 15 MCP tools, exact literature hyperlinks,
  mandatory method-change invalidation, Lean formula checks, venue evidence,
  academic figures, language safeguards, and multi-role paper audit.
