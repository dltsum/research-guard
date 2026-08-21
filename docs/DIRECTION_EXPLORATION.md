# Local-resource direction exploration

This capability is a typed subroute of `research_design`. It starts only after
the user explicitly authorizes direction finding. It inventories the effective
local CPU, memory, disk, registered process policy, and task profiles; runs
small, frozen pilot checks through the existing managed reproducibility owner;
binds a complete novelty-search receipt for every current candidate revision;
and returns exactly five unranked directions for the user to choose from.

It does not prove global novelty or research validity. A positive result is
reported only as a local coarse signal. “No collision” means no unresolved
collision under the recorded queries, sources, coverage, and date.

## Workflow

Use `action=status` together with one `direction_action`:

1. `plan` requires `direction_authorized_by=user`, an authorization scope,
   research problem, constraints, and a versioned exploration ID. It calls the
   canonical privacy-redacted resource inventory. Inventory is evidence, not
   entitlement. GPU remains unqueried and not admitted.
2. `register` accepts a main-agent-curated pool of 5–15 candidates. Every
   candidate contains a canonical method, falsifier, minimum experiment,
   differentiator, feasibility statement, linked HTTPS prior work, and a
   frozen coarse-test protocol. Rank, score, prestige, winner, and acceptance-
   probability fields are rejected.
3. `activate` registers one exact candidate revision with the canonical novelty
   owner. The main agent then registers the explicit domain route and continues
   the existing collision-search queue until a strict PASS or factual blocker.
4. The main agent registers a fresh user-selected reproducibility plan and runs
   it through the existing managed executor. `record_iteration` accepts only a
   managed PASS whose method hash and declared JSON output match the candidate.
   It recomputes metric improvement or predeclared checks, protocol legality,
   data role, observation count, legal range, artifact hash, and process receipt.
5. `bind_collision` accepts only the current strict signed novelty PASS for the
   exact candidate method hash. Required-source gaps and unresolved collisions
   fail closed. The binding retains clickable literature links.
6. `revise` creates a new method revision. Its positive evidence, collision
   evidence, and active five-choice set start empty; all old attempts and
   reports remain historical. The revised method must be activated, tested, and
   searched again.
7. `finalize` requires exactly five distinct current revisions with at least one
   positive managed pilot and a complete collision binding each. The main agent
   curates the set for coverage but cannot rank it or choose a winner. The
   result is `USER_SELECTION_REQUIRED`.
8. `status` exposes factual gaps. `verify` detects state, resource snapshot,
   method-file, result, collision-report, receipt-file, and choice-set drift.

## Frozen coarse-test contract

Each candidate selects an iteration limit from 1–5. This is a methodological
pilot bound, not a whole-task time limit. A failed candidate can be revised or
replaced within the registered pool; collision search itself retains the
project-wide no-arbitrary-deadline policy.

Two evidence modes are supported:

- `quantitative_delta`: freezes metric ID, unit, maximize/minimize direction,
  minimum effect, legal range, minimum observations, baseline source, data
  role, resource estimate, and protocol checks. The coordinator computes the
  outcome and rejects non-finite or protocol-illegal values.
- `predeclared_checks`: freezes positive criteria and protocol-legality checks.
  Every required Boolean must be present; caller-supplied “positive” labels are
  ignored.

Allowed data roles are `pilot`, `validation`, and `synthetic`. Final-test data
cannot be used for direction selection. Parameter trials inside a frozen range
may share a method revision. A changed mechanism, algorithm, feature set,
parameter range, data contract, evaluation protocol, or tracked method file is
a method revision and therefore requires both checks again.

## Canonical-owner boundary

| Concern | Sole owner | Direction coordinator responsibility |
|---|---|---|
| CPU/RAM/disk/profile inventory | `resource_plan_action=inventory` | Freeze its redacted snapshot and policy hash |
| Local command execution | `research_integrity.execute_reproducibility` | Bind only a managed PASS and declared result artifact |
| Memory enforcement | `resource_guard` | Copy measured receipt; never accept caller telemetry |
| Literature and collision search | `research-novelty-guard` | Bind strict version-matched report and signed receipt |
| Metric optimization after a committed study | `metrics_action` | Do not replace it; coarse screening only |
| Final research direction | user | Present exactly five unranked eligible options |

## Result interpretation

The five options show mechanism, falsifier, minimum experiment, differentiator,
feasibility, all-attempt count, the selected positive pilot artifact and hash,
the collision coverage/report hashes, and clickable linked work. Negative and
crashed attempts remain in the ledger. The output must not call a pilot result
confirmatory evidence, global novelty, a publication guarantee, or an automatic
recommendation.
