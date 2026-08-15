# Governance

Research Guard is maintained as an evidence-bound research infrastructure
project. The repository owner, `@dltsum`, is the initial maintainer and release
sign-off authority. Additional maintainers may be added after sustained,
reviewed contributions.

## Decisions

Routine fixes use pull-request review and documented test evidence. Changes to
hard gates, canonical ownership, the 15-tool MCP surface, dependency execution,
network access, resource limits, or PASS semantics require an architecture note
and explicit maintainer approval.

When proposals conflict, decisions prioritize:

1. scientific claim boundaries and user control;
2. credential, privacy, and artifact safety;
3. deterministic evidence and reproducibility;
4. a small, comprehensible public interface;
5. performance within the frozen resource envelope.

Silently weakening a gate is never an acceptable compatibility strategy.

## Releases

Releases use semantic versioning. Each release must pass repository validation,
focused and whole-plugin regression, Skill/plugin validators, package manifest
verification, and isolated-install checks. Tags use `vMAJOR.MINOR.PATCH` and
must match `CITATION.cff`, the plugin manifest's base version, and the changelog.

The GitHub source archive excludes binary payloads and mutable research data.
The separately attached Windows modular archive is the migration artifact and
must stay below 1 GiB with a verified `RELEASE_MANIFEST.json`.

## Security and conduct

Security reports follow [SECURITY.md](SECURITY.md). Community behavior follows
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Maintainers may remove public content
that exposes credentials, private papers, provider responses, identities, or
unreleased research data.
