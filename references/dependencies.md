# Dependencies

Use the component installer for a small installation. See
[component installation](component-installation.md) and the repository's
`INSTALL_PROMPT.md`. Core and literature use the Python standard library.
Only selected groups bring in third-party packages. Existing Python packages
can be used; `--install-python-deps` installs the selected requirements into
the installation's private `.venv`.

Normal startup and scientific work use actual files, imports and executables.
They do not require a signed installation receipt, exact environment snapshot,
interpreter fingerprint or repeated setup audit. Local source changes,
compatible package updates and extra user files are allowed. Update the same
installation by rerunning the component installer.

Existing Git and TeX on PATH can be used directly. A local Lean project can be
selected through `RESEARCH_GUARD_LEAN_RUNTIME`; `RESEARCH_GUARD_LAKE` can name its
Lake executable. No fixed Lean/Mathlib version or registered compiler receipt is
required. The actual compilation determines whether the requested imports work.
`RESEARCH_GUARD_TEX` can select a TeX executable explicitly.

Optional installation is a separate action, only needed when an environment is
missing. The dependency manager can reuse existing tools or install a selected
component on Windows. A requested install downloads only missing named payloads.
Existing payloads are reused; ordinary ZIP reading and executable startup report
unusable files. Downloads can resume using URL and byte-range information without
content digests. Neither loading the Skill nor listing dependencies installs
Git, TeX, Lean, a GUI, reference papers or model weights.

The legacy all-in-one Windows release contains Python and optional installer
payloads. POSIX legacy installers create a venv from system Python. These remain
available for existing users, while component selection avoids downloading the
whole bundle. Maintainers can unpack missing Windows payloads from a local
release ZIP or fetch them with `scripts/hydrate_release_payloads.py`. Release
metadata describes files; it does not impose a byte-for-byte installation lock.

`dependency_manager.py inventory` and `need COMPONENT` report available tools,
missing environments and installation choices. `install`/`update`, `resume` and
`cancel` support explicit setup. `not_now` records a decision to skip installation;
it does not claim that a missing compiler ran. Dependency receipts are useful
setup records, not prerequisites for using an available local program.

Additional parser adapters, SciPy/statsmodels, ASReview, provider APIs and native
CiteSpace remain external integrations. Use them only for the requested task
and report actual unavailable capability. Local graph analysis cannot stand in
for the original CiteSpace engine. An existing license or access requirement
still applies to the external service or program itself.

Cleanup stays within task-owned generated paths and skips symlinks and Windows
junctions. It preserves source files, research conclusions and installed tools.
Process resource limits remain in `assets/resource-policy.json`: managed work
runs serially on CPU within the configured owned-process memory budget. These
limits apply to spawned process trees; the shared parent's RSS is only observed.
They protect execution resources and do not lock source files or environment
versions. Requested development tests actually run; old cached test receipts
do not substitute for a new test result.
