# Explicit feature component installation

`python -I scripts/component_install.py --list` lists the nine groups from `assets/feature-components.json`. No group is selected by default. Running without `--components` returns `SELECTION_REQUIRED` and performs no copy, download, runtime creation or Codex registration.

Choose only the required groups. Examples:

```text
python -I scripts/component_install.py --components core --target /absolute/isolated/core --create-venv
python -I scripts/component_install.py --components literature --target /absolute/isolated/literature --create-venv
python -I scripts/component_install.py --components writing --target /absolute/isolated/writing --install-python-deps
python -I scripts/component_install.py --components figures,formal --dry-run
python -I scripts/component_install.py --verify --target /absolute/isolated/core
```

Replace paths with the chosen location. `--source` may name another checkout. A component selection is explicit installation authorization for its code only. `--install-python-deps` separately permits pip to resolve and install the selected pinned Python requirements into the target's `.venv`. With no such flag, requirements are recorded `REQUIRED_NOT_INSTALLED`, and the runtime uses `-S` to prevent accidentally borrowing host site-packages. `--create-venv` for core/literature creates a bare standard-library environment **without pip**. No payload, bundled Python distribution, TeX, Lean, Mathlib, Java, GUI, reference paper, data export, external Skill or provider API is downloaded by selecting a feature group.

Core and literature use only Python's standard library. Research adds literature; experiments adds research. Writing adds literature and pypdf. Figures adds matplotlib, numpy, Pillow and pypdf. Formal adds Pint, SymPy and Z3. Skill Lab adds no third-party Python package. CiteSpace adds literature and networkx; real CiteSpace remains a separately installed companion plugin and must never be impersonated by local graph analysis. Shared files can appear in two components; they are copied once. A shared Python file is not permission to expose every route it defines: runtime route gating must honor the selected groups.

The manifest uses `schema_version: 1`, `components` keyed by stable group id, and each record's `depends_on`, `files`, `modules` and `python_requirements`. File paths are exact relative paths or explicit directory names, never whole-repository defaults. Directory entries are filtered by the manifest's text/source suffix allowlist and exclude caches, development evidence and hidden generated state. Binary payloads are absent from all groups. Symlinks, junctions and path escapes are rejected. Unknown components, dependency cycles, missing declared files and conflicting/unpinned Python requirements fail before creating the target.

`COMPONENT_INSTALL.json` records requested and dependency-resolved groups, source-manifest digest, each installed file's byte size and SHA256, original source digests for generated metadata, interpreter digest, actual dependency installation commands/outputs, dependency status and an integrity digest. `.mcp.json` binds directly to the chosen interpreter and target's MCP server, with no host environment launcher inference. Host plugin registration is deliberately a separate step; copying files does not claim that Codex loaded the plugin or started a new authenticated session.

Installation only accepts a fresh empty target or a byte-verifiable identical previous selection. Repeating the same selection/source is `UNCHANGED`, with zero copies and no pip invocation. Changing groups or changing source uses a **fresh target**, so no removed group or stale Python dependency survives silently. Existing unrelated files, edited installed files and changed receipts are rejected. A pending marker remains if interrupted before final receipt commit; do not treat a partial directory as installed. Preserve it for diagnosis and use a fresh target. The installer does not recursively delete user files or upgrade a global environment.

`--verify` checks the receipt digest, every installed file, interpreter identity, unexpected package files and installed direct dependency versions. It does not prove every transitive package's source safety, scientific correctness, host registration or semantic validity. pip's actual report is retained when dependencies are installed; dependency resolution may include necessary transitive packages of selected requirements. No network operation is permitted for an unselected group.

The top-level receipt `resolved_components` is the installation capability authority used by the MCP runtime. Missing modules or uninstalled routes must return `COMPONENT_NOT_INSTALLED` with a concrete install command; never silently import another component, auto-install a group, or present omitted functionality as having passed validation.

Relative targets are supported. The installer first rejects symlink/junction traversal, then canonicalizes `..` before checking whether the destination lies inside the source checkout. Python subprocesses obtain their environment through `network_config_core.network_environment`; ambient Python, pip/index and proxy settings are removed. No host proxy or package index silently chooses the installation route.

On Windows, the isolated runtime uses an extended absolute path to support pip's nested package/license files without changing the machine's long-path policy. Venv creation and offline `ensurepip` bootstrap are separate recorded commands. Executable paths themselves must still fit the platform's process-launch limits. A failed bootstrap preserves its real diagnostics and pending receipt. UTF-8 output remains readable even when isolated Python ignores host encoding variables.

The receipt's `network_operations` counts network-capable pip installation commands, not individual HTTP requests. Source-only and bare-venv installs record zero; a selected dependency install can fetch necessary transitive dependencies. Generated README instructions describe inputs, steps, outputs and dependency limits, and `tests/component_smoke.py` provides a real installed stdio test. The full development test suite and unselected feature documentation are omitted.
