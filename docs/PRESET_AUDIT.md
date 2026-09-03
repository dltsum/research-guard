<!-- research-guard-doc-pair: preset-audit | revision: 2026-09-04.1 -->
# Host-independent preset audit

## Scope

This audit checks the complete Research Guard checkout for settings that could
silently bind a new installation to the machine that built or ran it. The
default scope includes Git-ignored development and evaluation files and
excludes only `.git`. It is a portability/configuration check, not a security or attacker audit.

## Categories

The executable scanner reports concrete user paths, absolute system/volume/UNC
paths, fixed local/private endpoints, ambient proxy reads, hard-coded proxy
URLs, ambient pip/uv index or configuration reads, optional scholarly credential
reads (`ambient_credential_read`), complete host-environment inheritance, workstation font names, and host
locale/time-zone inference.
Every finding is retained with a redacted path/snippet. ZIP members in the
checkout (including ignored evidence and generated release archives) are
inspected within declared size/count limits; tar-family members are inspected
too, while binary or non-UTF-8 members and symlink entries are listed as
skipped. A clean Git checkout may contain zero optional ignored archives; the
fixture tests exercise ZIP/tar member inspection independently. Intentional test fixtures, measured runtime evidence, the
localhost-only optional console, venue-source evidence, the documented
user-command environment, and explicitly optional scholar-service credentials
are classified in `allowed_findings`; they are not silently omitted. Portable
fallbacks such as `Path.home()`, `Path.cwd()`,
explicit environment overrides, measured host facts, bundled/generic fonts,
the explicit project locale, and the serial 512 MiB project policy are listed
separately as `portable_defaults`.

The `mechanism_inventory` section is a coverage ledger independent of the
finding decision. It lists the files and bounded examples that contain path,
platform, locale, font, environment, network client/route, package-index,
credential, subprocess, resource, archive/cleanup, and provenance mechanisms.
Examples retain only a pattern id and source location, never the matched value,
so this ledger cannot become a credential dump. A skipped symlink is visible in
`scan.symlink_entries_skipped`; it is never followed implicitly.

## Allowlist and intentional defaults

The policy is [assets/preset-audit-policy.json](../assets/preset-audit-policy.json).
It deliberately keeps the source tree neutral: no fixed developer path, local
proxy port, ambient scholarly proxy, ambient package index, workstation font,
or host locale/time-zone is an install default. Optional API keys/contact email
are opt-in inputs only; missing credentials preserve anonymous or
`credential_required` behavior. Install locations resolve in
this order: an explicit CLI parameter, the corresponding
`RESEARCH_GUARD_*`/`CODEX_HOME` setting, then the standard per-user fallback.
The Windows and POSIX launchers also honor an explicit
`RESEARCH_GUARD_PYTHON` before looking under the selected Research Guard home.
Only loopback is automatically local; public domain suffixes, including `.cn`,
never infer a user's country. Blank proxy input means direct access; a proxy or
package mirror is used only when the user explicitly supplies it or preserves
an installer-owned configuration. An installed copy may also contain an
installer-generated `.mcp.json` with the selected per-user runtime and plugin
paths; this explicit binding is visible in `allowed_findings`, while the source
checkout declaration remains `${PLUGIN_ROOT}`-based and host-neutral.

On Windows, the release workflow may hydrate the manifest-registered third-party
payloads under `assets/payloads/`. The hydrator verifies each payload's byte count
and SHA-256 before the builder sees it. Vendor paths or environment references
inside those payload archives remain visible as `allowed_findings` because they
are payload evidence, not Research Guard source defaults.

## Execution

Run the full checkout audit from the repository root:

```text
python -X utf8 scripts/preset_audit.py --root . --policy assets/preset-audit-policy.json --output <path-outside-checkout>/preset-audit.json
```

`researchctl preset-audit --project-root <checkout>` and the `research_design`
maintenance route expose the same implementation. The CLI root is required so
an invocation from an unrelated directory cannot silently audit the wrong
checkout. `--no-ignored` is a package-oriented diagnostic and
must not replace the default full audit. Release validation invokes the full
audit before a package can be built or published.

## Evidence and limitations

The receipt reports scanned text files/bytes, ZIP/tar archives and members, skipped
binary or non-UTF-8 files/members, symlink entries, generated audit receipts
skipped to avoid recursive growth, scan errors, violations, allowed findings,
portable defaults, the mechanism inventory, and resource/network/LLM policy
bindings. Skipping a binary, symlink, or oversized archive member is visible in
the receipt; it is never treated as proof that the content is portable. The scanner does not hash source files,
print credentials, infer a user's discipline, or test whether a foreign
network is reachable. A `FAIL` means a concrete finding or policy-binding drift
must be corrected and the audit rerun.

Implementation and tests: [scripts/preset_audit.py](../scripts/preset_audit.py),
[scripts/researchctl.py](../scripts/researchctl.py),
[scripts/mcp_server.py](../scripts/mcp_server.py), and
[tests/test_p29_preset_audit.py](../tests/test_p29_preset_audit.py).
