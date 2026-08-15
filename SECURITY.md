# Security policy

## Supported versions

Security fixes target the latest published release. Older development
snapshots and third-party tools referenced only for comparison are not
supported runtime components.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting or a private security advisory
for the repository. Do not open a public issue containing an
exploit, credential, private paper, provider response, local path, or research
dataset. If private reporting is unavailable, contact a maintainer through a
private channel listed on the repository and disclose only the minimum needed
to establish impact.

Include the affected version, entrypoint, expected boundary, observed
behavior, minimal reproduction, and whether any secret or private research
artifact may have been exposed. Maintainers should acknowledge a complete
report within seven days, validate it in an isolated environment, and
coordinate disclosure after a fix is available.

## Security boundaries

Research Guard treats imported Skill code as untrusted, stages it in
quarantine, and does not execute it during discovery or overlap review.
Anonymous network adapters accept only credential-free HTTPS endpoints.
Subscription exports and manual imports are hash-bound and must point to an
official record host. Release installation verifies every file against the
manifest before registration.
