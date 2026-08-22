# P23 Optional Research Console UI

Date: 2026-08-23

## Registered objective

Provide an optional cross-platform visual interface that lets a user hold
turn-oriented Codex conversations through the installed Research Guard Skill.
The UI must be absent from every core/minimal archive, remain separately
installable and maintainable, add no external LLM API or automatic field model,
preserve the 17-tool MCP surface, enforce the existing 512 MiB aggregate
resource contract, and have bilingual operator documentation.

## Interface evidence

- The official [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
  documents `codex exec --json` as a JSONL event stream, saved CLI
  authentication, read-only/workspace-write sandbox selection, and session
  resume by identifier.
- The official [Codex App Server](https://learn.chatgpt.com/docs/app-server)
  identifies app-server as the deep integration protocol for authentication,
  history, approvals, and streamed agent events. Stable stdio is newline-
  delimited JSON; WebSocket transport is experimental. This is the appropriate
  future owner if Research Console later needs interactive approval requests.
- The official [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
  documents per-server MCP `required`, `enabled`,
  `default_tools_approval_mode`, and per-tool approval settings. The admitted
  bridge uses these server-scoped controls rather than a global approval or
  dangerous bypass.
- Local preflight on 2026-08-23 verified `codex-cli 0.144.5`, stdin prompts,
  `exec --json`, specific-session `exec resume`, explicit sandbox selection,
  and machine-readable plugin/MCP inventories. The final read-only HTTP smoke
  emitted a completed `research-guard/list_research_modules` MCP activity,
  returned `RG_UI_MCP_OK 15`, exited successfully, and peaked at 396,423,168
  aggregate owned bytes. Two upstream TLS disconnect events were preserved and
  recovered before completion rather than hidden.

The earlier machine-oriented documentation helper returned HTTP 403. No claim
is based on that failed probe; the current official pages and actual local CLI
help are the admitted interface evidence.

## Architecture and overlap audit

| Candidate | Decision | Reason |
|---|---|---|
| Add an MCP-hosted UI to the core plugin | Reject | It would couple UI bytes and lifecycle to the minimal install and blur the existing canonical MCP owners. |
| Direct OpenAI/other LLM API browser client | Reject | It creates a second authentication, credential, provider, cost, and external-blocking path. |
| TypeScript Codex SDK web service | Reject for 0.1 | It introduces Node/package dependencies and a second runtime for a small optional console. |
| Full Codex App Server client | Defer | It is the correct owner for rich approvals and structured user input, but implementing and auditing the bidirectional protocol is materially larger than this optional turn console. |
| Inherit every host MCP server | Reject | The live smoke reached 541,609,984 owned bytes and crossed the 512 MiB contract. |
| `--ignore-user-config` without an explicit MCP binding | Reject | It reduced memory but removed the callable Research Guard tools, so it could not enforce the intended workflow. |
| Explicit Research Guard MCP plus global approval bypass | Reject | Global authorization would exceed the dedicated console's scope and weaken the user's sandbox boundary. |
| Python standard-library localhost server plus `codex exec --json` bridge | Admit | It reuses installed Codex authentication, JSONL/resume contracts, core Python and `psutil`, while keeping a small deterministic add-on and no new research owner. |

No existing Research Guard component was duplicated. Research Guard MCP tools
still own research design, novelty, evidence, writing, formulas, figures,
experiments, and audits. The add-on owns only presentation, request validation,
Codex process control, event normalization, and local resource display.

## Implemented contract

- Source boundary: `addons/research-console/`; core builders do not whitelist
  `addons/` and package tests inspect archives for absence.
- Distribution: deterministic `research-guard-ui-addon.zip` plus
  `SHA256SUMS-ui.txt`; no runtime/model/core archive may be embedded; archive
  ceiling is 25 MiB.
- Install: full manifest file-set, size and SHA-256 verification; safe and case-
  unique paths; core 0.7.0+ and logged-in/enabled Codex plugin preflight;
  versioned per-user target; no download; altered installations are not
  overwritten.
- Runtime: one Codex turn, prompt over stdin, no whole-task timeout, heartbeat
  and incremental NDJSON, thread continuation, explicit Stop, read-only or
  workspace-write sandbox, and no dangerous bypass.
- MCP isolation: enumerate configured servers; disable every non-Research Guard
  server; explicitly bind the installed canonical local stdio command; require
  successful startup; and apply automatic approval only to that server. The
  exact installed `SKILL.md` path is placed in the compact visible turn context.
- Selection: default main-agent semantic judgment or at most three visible
  user-selected focus preferences; no keyword or small-model classifier.
- Security: loopback bind, per-launch token in fragment/session storage and a
  same-origin custom header, origin rejection, strict response headers, no
  external static asset/analytics/API, safe DOM rendering, HTTPS-only clickable
  links, diagnostic secret/home-path filtering, and no server-side transcript
  persistence.
- Resources: reuse installed policy; GPU disabled; scientific threads fixed to
  one; UI server and owned descendants capped at 512 MiB aggregate working set;
  at least 512 MiB free memory; 10 ms sampling; resource breach terminates only
  the owned process tree and cannot PASS.

## Verification matrix

The focused suite covers request normalization, bounded focus selection,
workspace/sandbox/thread validation, command construction, prompt privacy,
plugin/version/MCP/resource preflight, safe rejection of MCP identifiers that
cannot be overridden, server-scoped MCP approval and isolation, JSONL
normalization, diagnostic redaction,
concurrent-start exclusion, resource-abort behavior, HTTP authentication and
origin rejection, security headers, streamed chat, static accessibility and
responsive contracts, safe citation DOM creation, deterministic packaging,
core-package exclusion, isolated idempotent installation, and rejection of
unregistered package files.

### Final local evidence

- The final focused add-on suite passed all 24 tests, including a deterministic
  regression that closes all three process pipes even when the first close
  raises `BrokenPipeError`. The final four-round packaging-fix SkillOpt run is
  `evals/p23-research-console-ui/run-20260822T205901Z/report.json`, status
  `PASS`, report SHA-256
  `952e854abf53b0738a365b7b517a28df0bcbfc1e6e8fd5ed83a69d2551481076`.
  Its four peak owned working sets were 156,180,480, 155,181,056, 170,065,920,
  and 162,131,968 bytes; no resource trim failed.
- Desktop 1440x1000 and compact 500x900 full-page screenshots were regenerated
  under `evals/p23-research-console-ui/` and inspected for overlap, clipping,
  alignment, space use, typography, and control visibility. The first compact
  inspection exposed a clipped third quick-action button. The final CSS wraps
  those actions responsively; the second compact inspection has no clipped or
  overlapping control. `agent-browser doctor --offline --quick` itself hung in
  a local Chromium `--version` probe and was terminated by exact owned PIDs;
  that failed path is not evidence. Installed Playwright produced the admitted
  localhost screenshots.
- The resumable offline repository suite passed 79 of 79 selected test files.
  Real Lean compilation separately passed 6 of 6 tests in 247.557 seconds and
  peaked at 467,247,104 owned bytes with 264 successful working-set trims and
  zero trim failures. Live source tests are not claimed as PASS: the configured
  `127.0.0.1:7897` proxy accepted the connection but failed TLS handshakes for
  Crossref, OpenAIRE, Zenodo, and ClinicalTrials, and the failure receipts remain
  under `evals/incremental-tests/p23-research-console-final/`.
- The actual local conversation smoke completed
  `research-guard/list_research_modules`, returned `RG_UI_MCP_OK 15`, and peaked
  at 396,423,168 owned bytes. Its two transient upstream TLS-disconnect events
  remained visible before recovery. This verifies the turn transport and local
  Research Guard MCP call, not scientific correctness or live-source coverage.
- The final deterministic `research-guard-ui-addon.zip` is 128,544 bytes,
  contains 15 fixed-timestamp `ZIP_STORED` entries and no core archive, and has
  SHA-256
  `c9e4a4a52f3ae0eae64a33c6450fdd987cffca658893d9aa0185b27606c9dc74`.
  Stored entries deliberately trade roughly 81 KiB for byte-identical archives
  across OS/Python/zlib implementations. Its extracted installer passed both
  `INSTALLED` and idempotent `ALREADY_INSTALLED` paths in the focused package
  suite.
- Repository validation passed 97 required files and 306 text files, preserved
  four registered bilingual pairs, and reported 7,307,492 bytes of GitHub source.
  Plugin validation passed, and the installed local cache now reports enabled
  version `0.7.0+codex.20260822211557`. A new Codex session is required to load
  that cachebuster.

Several pre-publication CI failures were retained and repaired rather than hidden.
The first macOS Intel run exposed a race in which the resource monitor could
terminate Codex before stdin delivery; closing that broken pipe then prevented
stdout/stderr reclamation under Python 3.14 `ResourceWarning` enforcement. The
bridge now reports early stdin closure structurally and closes each pipe
independently. A later Ubuntu run completed all build and isolated-install gates
but exposed that `actions/upload-artifact@v7` with `archive: false` accepts one
file only; the archive and checksum are now retained as two exact-file
artifacts. Finally, comparison of the Linux CI archive with the Windows local
archive showed identical member hashes but different Deflate bytes, so the
builder and regression contract now require `ZIP_STORED` members.
The next Windows matrix run then stopped because its SHA-pinned payload
bootstrap still described a superseded 303,733,735-byte v0.7.0 core asset. The
current 304,934,228-byte Release asset and the local verified archive both
reported SHA-256
`dc48c186e6240763fbec37d27000e9ee17e46a6b1ff2cca557833dc59a98065a`;
only then was the bootstrap repinned. A real four-payload hydration and
cross-manifest audit passed for 303,001,850 extracted bytes at 69,410,816 peak
owned bytes, after which the exact temporary copies were removed. The
four-round P21 rerun at
`evals/p21-ci-migration-skillopt/run-20260822T211036Z/report.json` passed with
report SHA-256
`0132f29992acc7c29c248355d3dd706d937d071d5abd1ddfe802bb2bec464637`.

Remote CI, commit, and public Release-asset evidence are appended only after
their URLs are independently verified. Until then, `p23.publish` remains
`ACTION_REQUIRED`; local implementation checks do not imply publication.

## Claim boundary

The UI does not prove novelty, source support, scientific correctness, resource
fitness, completion, accessibility, or security. Version 0.1 intentionally
auto-approves only calls to the locally installed Research Guard MCP server;
its executable gates remain authoritative. It does not render Codex App Server
approval or structured user-input requests. A task requiring shell escalation,
another MCP server, or a new structured approval must continue in a full Codex
client; the add-on never changes the global approval policy or exposes a
dangerous bypass.
