<!-- research-guard-doc-pair: p29-preset-audit | revision: 2026-09-03.3 -->
# P29 preset-audit implementation record

## Scope

P29 closes the portability issue in which a release could inherit the
developer's home, proxy, package index, runtime, global Git proxy, optional
scholarly credentials, workstation font, or host locale. It covers the complete checkout,
including tracked and ignored files, and scans UTF-8 text inside
bounded ZIP and tar-family members while leaving `.git` out of the scan. Symbolic links
are surfaced as skipped entries rather than followed silently.

## Implementation

The stdlib-only [preset scanner](../../scripts/preset_audit.py) uses a declared
[policy](../../assets/preset-audit-policy.json), redacts evidence, scans release
archives, and separates violations from intentional fixtures/evidence and
portable fallbacks. Install roots, signing-key placement, Windows/POSIX runtime
launchers, Git source transport, scholarly route fallback, optional credential
inputs, font/locale choices, and pip/uv child environments now honor explicit
user choices before portable defaults. All scholarly adapters share one
route resolver so a copied checkout cannot drift into a second proxy policy.
The receipt also carries a mechanism inventory for path/platform/locale/font,
environment, network/index, credential, subprocess, resource, archive/cleanup,
and provenance sites. Inventory examples retain only a pattern id and location;
they never copy matched values.
The route is available through
[`researchctl preset-audit`](../../scripts/researchctl.py) and the existing
`research_design` maintenance surface without adding a top-level MCP tool.

## Verification

The focused P29 suite exercises full-checkout scanning, absolute and escaped
Windows paths, bounded ZIP/tar inspection, generated-receipt handling,
ignored-file scope, MCP routing, package-index/Python-host scrubbing, optional
credential classification, explicit install root/runtime precedence,
signing-key placement, and Git direct-route behavior.
The release validator and both package builders invoke the same audit before
admitting a source tree or archive.

## Boundaries

This is not an attacker or security review. Binary/non-UTF-8 files, symbolic
links, and bounded archive members are counted and listed as skipped; their contents are not
asserted portable. Measured host facts, user-command environment inheritance,
venue evidence, and localhost console bindings are visible classifications,
not hidden exceptions. No source hash or credential is placed in the receipt.
