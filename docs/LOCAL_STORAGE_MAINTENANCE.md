<!-- research-guard-doc-pair: local-storage-maintenance | revision: 2026-08-26.1 -->

# Local storage maintenance

## Scope

This policy keeps a Research Guard source checkout and installed plugin cache small without deleting authoritative releases, Git-tracked conclusions, or evidence needed to interpret a claim. Cleanup is serial, GPU-free, and bounded by the project-wide `512 MiB` owned-working-set limit.

## Classification and retention

| Class | Examples | Required action |
| --- | --- | --- |
| source of truth | tracked source, registries, documentation, final release checksums | keep |
| exact duplicate | repeated download with exact SHA-256 equality to a canonical copy | retain one canonical copy and record the mapping |
| useful but cold | ignored evaluation receipts, snapshots, venue binaries | compress once, test CRC and paths, write `SHA256SUMS.txt`, then remove originals |
| reproducible cache | `build/`, `dist/`, optional payloads, installed-plugin copies | delete after the authoritative release or pinned rehydration manifest is verified |
| raw data whose conclusion is sufficient | superseded isolated installs and probe trees | retain the conclusion, counts, hashes, claim boundary, and recovery source; delete raw copies |

The rule is archive first, delete second. File names, equal byte counts, or similar directory sizes are not deduplication evidence; exact SHA-256 equality is required for file-level deduplication.

## Cleanup workflow

1. Record repository commit, file count, byte count, disk free space, and exact candidate roots.
2. Verify that candidates stay below the admitted repository, plugin-cache, quarantine, or explicit archive root. Never recurse over a user profile or workspace root.
3. Move the unique final release to an archive outside the checkout without recompressing it.
4. Compress cold evidence serially. Test every ZIP entry for CRC failure and reject absolute paths or `..` components.
5. Preserve a bilingual archive README, a compact conclusion ledger, and checksums.
6. Delete only the verified candidates. On Windows, enumerate and remove remaining paths longer than 260 characters explicitly; do not broaden the target.
7. Re-run repository, bilingual-documentation, focused behavior, package, and installed-plugin checks.

## Recovery

Optional Windows payloads are intentionally absent from a small source checkout. Restore them from the pinned manifest with [the hydration script](../scripts/hydrate_release_payloads.py):

```powershell
python -X utf8 scripts/hydrate_release_payloads.py
```

The pinned source, size, and digest contract is in [payload-bootstrap.json](../assets/payload-bootstrap.json). Missing venue binaries remain an explicit `ONLINE_ACQUISITION_REQUIRED` state and are reacquired from the URLs and hashes in `assets/venue-evidence/registry.json`. An offline archive is a convenience, not a second canonical source.

## Verification

A cleanup passes only when all of the following are true:

- the authoritative release hashes are unchanged;
- every cold-evidence ZIP passes CRC and path-safety checks;
- tracked venue registries remain present while ignored binaries are absent;
- repository and installed-plugin behavior still pass without optional payloads;
- a Windows package build fails closed at payload preflight until hydration, rather than silently producing an incomplete package;
- deleted generated roots are absent, and the conclusion ledger reports what is no longer recoverable as raw files.

## Boundaries

Storage cleanup is not new empirical evidence and cannot upgrade a prior research claim. A compressed development receipt remains development evidence. A conclusion-only record is acceptable only for reproducible or superseded raw data whose decision-relevant result, provenance, counts, and hashes have been retained. Credentials, private prompts, provider replies, and user data must never enter a cleanup archive.
