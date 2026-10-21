# Component installation

Use Python 3.11 or later. Run `python -I scripts/component_install.py --list`
to list the nine groups. No selection means no installation or download.

```text
python -I scripts/component_install.py --components core --target /path/to/research-guard
python -I scripts/component_install.py --components writing --target /path/to/research-guard --install-python-deps
python -I scripts/component_install.py --components figures,formal --dry-run
```

Selection brings in the required shared groups. Core and literature use the
standard library; research adds literature; experiments adds research. Writing
adds pypdf; figures adds matplotlib, numpy, Pillow, pypdf and their dependencies;
formal adds Pint, SymPy and Z3 and their dependencies; CiteSpace adds literature
and networkx. Skill Lab adds no third-party Python package. The dependency
declarations are in `assets/feature-components.json`.

`--install-python-deps` installs the selected Python requirements into a private
`.venv`. Without it, the chosen Python can use its existing packages. Use
`--python /path/to/python` to choose an interpreter, or `--create-venv` for a
bare private environment. Installing a component does not download TeX, Lean,
Mathlib, Java, GUI programs, reference papers or a bundled Python distribution.

`COMPONENT_INSTALL.json` records selected groups, file paths, the interpreter and
actual installation commands. `.mcp.json` starts that interpreter and the MCP
server directly. These are ordinary editable configuration files: there is no
receipt signature, interpreter fingerprint or per-file digest gate. Existing
receipts with old digest fields remain readable; those fields are ignored.

Rerun the same command with the same target to update source files, add selected
groups or finish dependency installation. The source files belonging to the
installation are updated. Explicitly deselected groups lose their package-owned
files. Other user files are preserved. An interrupted installation can be retried
in the same directory. An unrelated nonempty directory is not overwritten.
Paths must stay within the chosen installation; symlink or junction traversal
and source/target nesting are rejected.

Ordinary startup and tool calls do not recheck every file, environment version,
compiler or receipt. A missing package reports its actual import error. An
unselected feature reports `COMPONENT_NOT_INSTALLED`. To diagnose an installation
once, run `python -I scripts/component_install.py --verify --target /path/to/research-guard`.
This checks required files are present and dependencies import; local edits,
extra files, compatible package updates and interpreter updates do not invalidate
the installation. No diagnostic pass is required before normal work.

Existing Git, TeX and local Lean projects can be used directly without a
registration receipt or a fixed Lean/Mathlib version. For a custom environment,
set `RESEARCH_GUARD_TEX`, `RESEARCH_GUARD_LEAN_RUNTIME` or `RESEARCH_GUARD_LAKE`.
The requested compilation checks whether its actual imports work. Explicit
optional installation fetches only missing payloads. Existing files are reused;
ZIP reading and executable startup report unusable payloads. No digest needs
to be supplied. Cleanup still stays within task-owned paths and skips links.

`tests/component_smoke.py` runs actual MCP initialize and tools/list requests.
For a functional example, send a real tools/call with project inputs and inspect
its result. Installation and startup are not scientific-result acceptance.
When interactive acceptance is requested, give the executing agent one request
at a time, preserve the real answer and outputs, then provide feedback before
the next request. Keep failures and same-request retests after repairs.
