# Contributing

Thank you for improving Research Guard. Changes to research gates require
evidence proportional to their scientific and safety impact.

## Development setup

Use Python 3.11 or newer on Windows x64, Linux x64, or macOS x64/arm64. Install
the exact development set:

```sh
python -m pip install -r requirements-dev.txt
```

Run changed tests first, then the incremental P10-P14 suite:

```sh
python scripts/run_incremental_tests.py --pattern "test_p10_*.py" --pattern "test_p11_*.py" --pattern "test_p12_*.py" --pattern "test_p13_*.py" --pattern "test_p14_*.py" --suite pull-request
```

Each test file runs in a serial 384 MiB worker and receives a hash-bound
receipt. A contract change invalidates the relevant receipts automatically.

## Bilingual documentation

Every document declared bilingual is registered in
`assets/documentation-parity.json`. Edit both members in one focused change,
preserve their declared section/link/image structure, and complete human
bilingual review. Then refresh the normalized content hashes deliberately:

```sh
python -X utf8 scripts/documentation_parity.py --refresh-hashes
python -X utf8 scripts/documentation_parity.py
python -X utf8 scripts/run_incremental_tests.py --pattern "test_documentation_parity.py" --suite docs --no-resume
```

The refresh command does not translate or approve text. Inspect both documents
and the manifest diff before commit. Any unregistered `.zh-CN.md`, missing pair
member, section/link/image drift, empty image alt text, asset/provenance mismatch,
or stale hash fails repository validation. See
`docs/DOCUMENTATION_POLICY.md` and `docs/DOCUMENTATION_POLICY.zh-CN.md`.

## Non-negotiable boundaries

- Do not weaken method-change invalidation, complete collision reruns, source
  hyperlink requirements, exact-locator checks, or first-load user selection.
- Do not convert a local run, exit code, bibliographic lookup, or capacity
  check into a novelty, quality, causal, or reproducibility claim.
- Keep one canonical owner for overlapping capabilities and no more than 17
  top-level MCP tools without a separately accepted architecture change.
- Literature adapters must return official HTTPS record URLs and expose
  unavailable or subscription-only routes explicitly.
- Discipline profiles must distinguish static routing, live discovery,
  index-membership evidence, and venue quality. Humanities/history additions
  must cover non-journal forms and primary-source provenance.
- Do not add ambient PATH execution. Compilers and optional tools require a
  validated, registered dependency receipt.
- Keep task-owned memory at or below 512 MiB, one worker, one scientific
  thread, and no GPU.
- Keep every registered bilingual document pair synchronized. Structural CI is
  a maintenance backstop, not a substitute for human translation review.

## Adding an upstream or component

Record the official URL, license, immutable revision, architecture, resource
cost, overlap owner, and admission decision. Compare at least three credible
implementations when available. Forks are discovery evidence, not correctness
evidence. Third-party code is not executed during comparison.

Run bounded SkillOpt with frozen train, validation, and held-out cases. A
candidate configuration must pass under its own hash-bound test environment
before it can replace the active configuration.

## Pull requests

Keep changes focused. Include the test receipt or command, explain any new
network or dependency boundary, update public documentation, and complete the
pull-request checklist. Never attach credentials, private papers, provider
responses, or unreleased research data.
