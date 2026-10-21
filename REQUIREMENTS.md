# Requirements

Research Guard uses Python 3.11 or later and a host agent that can read files
and run commands. MCP uses standard-library JSON-RPC over stdio; Node.js and an
MCP SDK are not required. Select the groups you need with
[`scripts/component_install.py`](scripts/component_install.py). The complete
copy-and-run prompt is in [`INSTALL_PROMPT.md`](INSTALL_PROMPT.md).

| Group | Included shared groups | Python dependencies |
|---|---|---|
| core | — | Standard library |
| literature | core | Standard library |
| research | literature | Standard library |
| experiments | research | Standard library |
| writing | literature | pypdf |
| figures | core | Matplotlib, NumPy, Pillow, pypdf and their dependencies |
| formal | core | Pint, SymPy, Z3 and their dependencies |
| skill-lab | core | Standard library |
| citespace | literature | NetworkX |

The install requirements are declared in
[`assets/feature-components.json`](assets/feature-components.json). They record
the project's current dependency choices. Actual imports and function calls
determine usability; normal operation does not compare installed versions with
an environment lock. Existing Python environments are supported. Add
`--install-python-deps` to create or reuse the installation's private `.venv`
and install only the selected requirements. Source updates and component
changes can use the same installation directory.

`COMPONENT_INSTALL.json` records selected groups, paths, interpreter and setup
commands. `.mcp.json` starts that interpreter directly. Old digest fields are
ignored; no file, interpreter or receipt fingerprint is needed. Local source
edits, extra user files and compatible interpreter/package updates do not
invalidate the installation. `--verify` is an optional one-shot diagnostic of
file presence and dependency imports, not a startup prerequisite.

## Optional local tools

| Tool | Needed for | Ordinary use |
|---|---|---|
| Git | Remote repository acquisition and optional Lean installation | Use an existing executable on PATH, or explicitly install portable Git |
| TeX | Compiling the requested manuscript and official paper kit | Use an available TeX compiler, optionally selected by `RESEARCH_GUARD_TEX` |
| Lean / Mathlib | Compiling the proof or imports required by a task | Use the local project and Lake executable; no fixed release or registration receipt is required |
| Image generation | Creating or editing raster artwork | Use the host's actual available image tool |
| Native CiteSpace | Original CiteSpace analyses | Requires its real companion MCP, a usable historical free engine and appropriate Java |

Use `RESEARCH_GUARD_LEAN_RUNTIME` for an existing Lean project and
`RESEARCH_GUARD_LAKE` for its Lake executable. The Lean installer has selectable
`Toolchain` and `MathlibRevision` parameters; its defaults are installation
choices, not restrictions on existing projects. A proof importing Mathlib
needs Mathlib available to that project; an Init-only sample does not establish
that Mathlib works. No missing scientific result is replaced with a setup
receipt or a simulated external program.

Loading a Skill does not install optional programs. Existing programs work
without registration. When an installation is actually requested, only the
missing selected environment is acquired. Research Guard does not silently
run a privileged system package manager. Separate licenses, credentials and
subscription access remain requirements of the external program or service.

## Optional UI and legacy bundles

The Research Console is a separate optional add-on under
`addons/research-console`. It needs a local browser, available Python with
psutil, a logged-in Codex CLI and an enabled Research Guard plugin. It includes
no model, Node framework, scientific runtime or TeX/Lean environment. The
installer accepts normal local edits and updates the existing add-on version.

Legacy all-in-one release archives remain available for existing users.
Windows bundles Python and installer payloads; POSIX uses system Python and a
venv. Component installation is the smaller default. Release metadata lists
files and sizes without imposing a content-digest gate. ZIP read errors,
missing executables and failed actual imports still produce ordinary errors.
Building a Windows legacy archive needs its actual payload files, which can be
unpacked from a local ZIP or fetched by `scripts/hydrate_release_payloads.py`.

## Development and execution

Development dependencies are in
[`requirements-dev.txt`](requirements-dev.txt). Install them only for the
development work being performed:

```text
python -m pip install --isolated --disable-pip-version-check --index-url https://pypi.org/simple -r requirements-dev.txt
```

Builders support `--mode development` to inspect the current source without
creating a ZIP. Requested incremental tests actually run and record their
outputs; historical cached results do not replace a new run. Cross-platform
compatibility claims must reflect the platform actually tested.

Managed work retains the configured CPU, concurrency and memory limits in
[`assets/resource-policy.json`](assets/resource-policy.json). Existing defaults
use one CPU worker and a 512 MiB task-owned working-set budget, with separate
profiles for installation and Lean. The limit applies to the spawned process
tree; parent-process RSS is recorded and does not block execution after imports
or previous work. Resource limits do not lock source bytes
or environment versions. Cleanup is restricted to task-owned generated paths
and skips links; no user-wide directory is recursively cleared.

Scientific inputs and outputs belong in the selected project's work directory.
Retain the real source material, method, commands, result and any requested
review record. Additional parser backends, advanced statistics and provider
APIs are optional task-specific integrations, not default installation costs.

For licenses, see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
