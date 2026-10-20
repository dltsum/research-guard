# Explicit feature component installation

For interactive acceptance, the main chat dispatches one natural-language
request to the executing agent at a time, beginning with installation. The
agent retains the real command/tool inputs, raw outputs and artifact hashes,
then waits. The main agent reads and checks the response, supplies feedback,
and only then sends the next feature question. Do not outsource the complete
acceptance run to another session. Preserve ordered prompts, actual replies,
checks, defects, fix commits and same-sentence retests. Fix and push confirmed
defects before installing a fresh target from that revision and retrying.
Distinguish positive feature execution, expected refusal, missing implementation,
environmental blocks and not-run steps; transport startup and status alone do
not establish that a component's main function works.

`python -I scripts/component_install.py --list` lists the nine groups from `assets/feature-components.json`. No group is selected by default. Running without `--components` returns `SELECTION_REQUIRED` and performs no copy, download, runtime creation or Codex registration.

Choose only the required groups. Examples:

```text
python -I scripts/component_install.py --components core --target /absolute/isolated/core --create-venv
python -I scripts/component_install.py --components literature --target /absolute/isolated/literature --create-venv
python -I scripts/component_install.py --components writing --target /absolute/isolated/writing --install-python-deps
python -I scripts/component_install.py --components figures,formal --dry-run
python -I scripts/component_install.py --verify --target /absolute/isolated/core
```

Replace paths with the chosen location. `--source` may name another checkout. A component selection is explicit installation authorization for its code only. `--install-python-deps` separately permits pip to install the selected explicitly pinned application dependency closure into the target's `.venv`. The manifest includes the necessary default-extra transitive packages observed for the tested platform; a combined selection takes their deduplicated union. With no such flag, requirements are recorded `REQUIRED_NOT_INSTALLED`, and the runtime uses `-S` to prevent accidentally borrowing host site-packages. `--create-venv` for core/literature creates a bare standard-library environment **without pip**. No payload, bundled Python distribution, TeX, Lean, Mathlib, Java, GUI, reference paper, data export, external Skill or provider API is downloaded by selecting a feature group.

Core and literature use only Python's standard library. Research adds literature; experiments adds research. Writing adds literature and pypdf (one application package). Figures includes matplotlib, numpy, Pillow, pypdf and eight necessary transitive packages (12 application packages). Formal includes Pint, SymPy, Z3 and five necessary transitive packages (eight application packages). Skill Lab adds no third-party Python package. CiteSpace adds literature and networkx (one application package); real CiteSpace remains a separately installed companion plugin and must never be impersonated by local graph analysis. All versions are explicit in `python_requirements`. pip is a separate `ensurepip` bootstrap tool, not an application component requirement; the observed bootstrap version was 26.1.1, and standard-library groups do not acquire pip. Shared files can appear in two components; they are copied once. A shared Python file is not permission to expose every route it defines: runtime route gating must honor the selected groups.

The manifest uses `schema_version: 1`, `components` keyed by stable group id, and each record's `depends_on`, `files`, `modules` and `python_requirements`. File paths are exact relative paths or explicit directory names, never whole-repository defaults. Directory entries are filtered by the manifest's text/source suffix allowlist and exclude caches, development evidence and hidden generated state. Binary payloads are absent from all groups. Symlinks, junctions and path escapes are rejected. Unknown components, dependency cycles, missing declared files and conflicting/unpinned Python requirements fail before creating the target.

`COMPONENT_INSTALL.json` records requested and dependency-resolved groups, source-manifest digest, each installed file's byte size and SHA256, original source digests for generated metadata, interpreter digest, actual dependency installation commands/outputs, dependency status and an integrity digest. `.mcp.json` binds directly to the chosen interpreter and target's MCP server, with no host environment launcher inference. Host plugin registration is deliberately a separate step; copying files does not claim that Codex loaded the plugin or started a new authenticated session.

In an installed receipt and the successful installer response, `copy_bytes` is
the sum of the actual tracked installed files, including generated instructions
and metadata. It excludes the receipt itself and the private venv. The separate
`source_copy_bytes` retains the dry-run source-file total, before generation;
these totals may differ. Generated root/component Skills and README retain the
main-chat one-question-at-a-time protocol, rather than losing it when replacing
the full source Skill with selected-installation instructions.

Installation only accepts a fresh empty target or a byte-verifiable identical previous selection. Repeating the same selection/source is `UNCHANGED`, with zero copies and no pip invocation. Changing groups or changing source uses a **fresh target**, so no removed group or stale Python dependency survives silently. Existing unrelated files, edited installed files and changed receipts are rejected. A pending marker remains if interrupted before final receipt commit; do not treat a partial directory as installed. Preserve it for diagnosis and use a fresh target. The installer does not recursively delete user files or upgrade a global environment.

`--verify` checks the receipt digest, tracked installation files, interpreter identity, unexpected files outside the pruned runtime tree, and the version of every listed application requirement. Because the manifest now explicitly lists the observed default-extra closure, this version check includes all 12 figures packages and all eight formal packages, as well as the one-package writing and CiteSpace closures. The `.venv` tree is not individually file-hashed, and verification does not assert that unlisted extra distributions are absent. It does not prove wheel byte identity, package source safety, scientific correctness, host registration or semantic validity. pip's original installation report retains observed artifact URLs and archive hashes; the installer does not enforce an offline wheel store or `--require-hashes` installation. No network operation is permitted for an unselected group.

Actual fresh closure installation, version-drift refusal/restoration, `pip check`, and a contour render were tested on **Windows amd64, CPython 3.14.5**. The project minimum remains Python 3.11; compatibility with 3.11 here is a `Requires-Python` metadata check, not an executed Python 3.11 test. In particular, contourpy 1.3.3 declares Python >=3.11 and supplied the tested cp314 Windows wheel; contourpy 1.4.0 was not pinned because it requires >=3.12. networkx 3.6.1 excludes Python 3.14.1; the real pip target-version dry-run refusal is not a run of that interpreter. Other operating systems, CPU architectures, Python/ABI versions and optional extras require separate marker/closure and execution validation. Reproducing exact artifacts also requires the compatible wheels and hashes plus base Python/pip identity; these version pins do not establish cross-platform bitwise results.

The top-level receipt `resolved_components` is the installation capability authority used by the MCP runtime. Missing modules or uninstalled routes must return `COMPONENT_NOT_INSTALLED` with a concrete install command; never silently import another component, auto-install a group, or present omitted functionality as having passed validation.

Relative targets are supported. The installer first rejects symlink/junction traversal, then canonicalizes `..` before checking whether the destination lies inside the source checkout. Python subprocesses obtain their environment through `network_config_core.network_environment`; ambient Python, pip/index and proxy settings are removed. No host proxy or package index silently chooses the installation route.

On Windows, the isolated runtime uses an extended absolute path to support pip's nested package/license files without changing the machine's long-path policy. Venv creation and offline `ensurepip` bootstrap are separate recorded commands. Executable paths themselves must still fit the platform's process-launch limits. A failed bootstrap preserves its real diagnostics and pending receipt. UTF-8 output remains readable even when isolated Python ignores host encoding variables.

The receipt's `network_operations` counts network-capable pip installation commands, not individual HTTP requests. Source-only and bare-venv installs record zero; a selected dependency install fetches its explicitly pinned application closure for the recorded environment. Generated README instructions describe inputs, steps, outputs and dependency limits, and `tests/component_smoke.py` provides a real installed stdio test. The full development test suite and unselected feature documentation are omitted.
