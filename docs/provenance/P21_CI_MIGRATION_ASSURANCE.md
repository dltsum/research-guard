# P21 cross-platform migration-assurance audit

Audit date: 2026-08-22. This change addresses a release-evidence gap: the
repository already built Windows x64, Linux x64, macOS Intel, and macOS Apple
Silicon archives, but archive creation alone did not prove that a fresh user
root could install and start the packaged Skill, plugin, runtime, and MCP
surface.

## Current upstream evidence

The implementation uses the official
[`actions/upload-artifact`](https://github.com/actions/upload-artifact)
action. Its current v7 release and `archive: false` input allow CI to retain the
already-built ZIP as the artifact itself instead of wrapping it in a second
ZIP. `retention-days: 3` deliberately keeps this diagnostic asset short-lived;
GitHub documents retention and manual removal in
[Remove workflow artifacts](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/remove-workflow-artifacts).
Durable public installation continues to use signed/tagged GitHub Release
assets and their SHA-256 files.

Open dependency-update proposals were inspected but not merged into P21.
Changing NumPy, Matplotlib, or Pillow also changes the audited Windows offline
runtime and therefore needs a separate supply-chain rebuild and compatibility
audit. Mixing those upgrades into migration verification would make a clean-
install failure ambiguous.

## Overlap and owner audit

| Candidate | Decision | Reason |
|---|---|---|
| Trust successful ZIP creation | Reject | It verifies serialization, not a fresh installation or runtime startup. |
| Add one installer per CI platform | Reject | It duplicates `install.ps1` and `install_posix.py` and risks release/CI drift. |
| Add a generic package manager or container runtime | Reject | It expands dependencies without closing the fresh-user-root evidence gap. |
| Retain every CI package indefinitely | Reject | CI evidence is diagnostic; permanent duplicate assets waste repository storage. |
| Reuse the canonical installers, clean-install each matrix archive, and retain the exact ZIP for three days | Admit | It adds the missing evidence while keeping one installation owner and one archive. |

The new `scripts/test_isolated_install.py` is an assurance coordinator, not a
second installer. It performs bounded ZIP extraction, rejects traversal,
duplicate paths, symlinks, unsupported filesystem entries, excess member count,
and excess expanded size, then invokes the existing platform installer. Both
installation and verification run through `resource_guard.run_managed_install`
under the existing 448 MiB worker + 64 MiB orchestrator allocation. GPU remains
disabled and numerical thread counts remain one.

The packaged `verify_isolated_install.py` now recognizes the canonical Windows
`python.exe`, Windows venv `Scripts/python.exe`, and POSIX `bin/python` layouts.
It still verifies exact Pint, SymPy, and Z3 versions, the first-load dependency
inventory, plugin and traditional-Skill copies, MCP version 0.7.0, and the
unchanged 17-tool surface.

## CI and release contract

Every platform matrix job must complete in this order:

1. validate the source and deterministic public regression;
2. build the platform-specific migration ZIP;
3. clean-install that exact ZIP into a new redirected user root;
4. execute the packaged isolated verifier with the installed interpreter;
5. upload that exact ZIP, without double wrapping, for three days.

The tagged release job repeats the same clean-install proof for the Linux x64
archive before uploading POSIX release assets. macOS archives are not falsely
installed on an Ubuntu runner; their native proofs remain owned by the macOS CI
matrix. POSIX dependency downloads use the explicit Tsinghua PyPI mirror. A
per-process/CI timeout is an operational safety bound, not a research deadline
or permission to claim an incomplete installation as PASS.

## SkillOpt and evidence contract

`scripts/skillopt_ci_migration.py` runs four serial, resource-managed rounds.
Each round combines static ownership/order/security checks with P21, cross-
platform, package, and resource-policy tests. Timestamped results are append-
only under ignored `evals/p21-ci-migration-skillopt/run-*/`; the canonical
ignored `report.json` is only the latest plan artifact. Any static failure,
test failure, resource abort, isolated-install failure, or missing GitHub
artifact is explicit and cannot be converted to PASS.

Executed local and GitHub evidence is recorded after the source, package, and
remote matrix are all frozen; no result is predeclared in this audit.
