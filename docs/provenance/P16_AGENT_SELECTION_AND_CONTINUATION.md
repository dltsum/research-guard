# P16 explicit-selection and continuation verification

Date: 2026-08-15

Status: **PASS**

## Accepted change

- Semantic ownership belongs to the main agent. Runtime code contains no
  keyword field classifier, automatic module router, automatic method-change
  detector, or automatic paper-review role selector.
- Code registers one to three explicit modules, an explicit domain, and two or
  three explicit audit roles; it rejects unknown IDs, overlaps, missing
  rationale, and non-main-agent selections.
- Collision search persists every source-query unit and has no research
  deadline. `IN_PROGRESS` requires a factual user update and continuation.
- Required-unit failure returns `ACTION_REQUIRED`. Final `BLOCKED` status needs
  a hash-bound main-agent decision covering every failed required unit.
- Public MCP tools contain no ambiguous generic `timeout` property. Network
  attempt and owned child-process boundaries are named separately and cannot
  establish research completion.

## SkillOpt evidence

Four serial rounds passed the P16 behavioral and static gates. Each round ran
eight tests and verified ten static contract conditions. No semantic selector
was optimized or reintroduced.

| Round | Result | Peak owned working set |
|---:|---|---:|
| 1 | PASS | 175,718,400 bytes |
| 2 | PASS | 180,998,144 bytes |
| 3 | PASS | 180,408,320 bytes |
| 4 | PASS | 178,499,584 bytes |

Maximum observed owned working set was 180,998,144 bytes, below the
536,870,912-byte limit. The aggregate ignored development receipt is stored at
`evals/p16-skillopt/report.json`; its SHA-256 is
`a3e0357e970f4fcc71ffcb1d03ed34ab2fde0db60af63164128f6297b770c4c4`.
