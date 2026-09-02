# P28 network-channel recovery

## Issue and scope

GitHub Issue [#6](https://github.com/dltsum/research-guard/issues/6) reported
that the 0.7.0 novelty/collision search could not connect to academic search
websites. The attached run reported transport failures from both arXiv and
Crossref. A transport failure is not a zero-result observation and must keep
the collision gate incomplete.

## Root cause

The source request boundary assumed a local foreign proxy (`127.0.0.1:7897`)
even when the user had not configured one, then retried that same route. For a
user in Singapore or any other environment without that listener, this made a
normal direct connection look like an academic-source outage. When a listener
did accept a connection but failed the TLS handshake, no usable route remained
even when direct access to the same official endpoint was available. The
failure was therefore in route selection/recovery, not in source parsing or
collision adjudication.

The same implicit host assumption also appeared in discipline initialization,
Crossref citation verification, GitHub/SkillsHub discovery, OpenReview
calibration, venue evidence checks, the POSIX dependency installer, and the
Lean bootstrap. Those paths now share one small standard-library configuration
module. They accept only an explicit credential-free
`RESEARCH_GUARD_FOREIGN_PROXY` or the installer-owned `network-config.json`;
they never import ambient `HTTP_PROXY`/`HTTPS_PROXY` values into saved
configuration.

## Implemented contract

- Domestic and loopback requests use an empty `ProxyHandler`, bypassing
  inherited ambient proxy variables.
- Foreign requests use `RESEARCH_GUARD_FOREIGN_PROXY` first when it is
  explicitly configured, then the saved installer choice; otherwise they use
  a direct route.
- Interactive installers ask once for an optional proxy URL. Enter (or a
  non-interactive install) records a direct choice, while an existing choice
  is preserved on idempotent reinstall/update. `--foreign-proxy URL` is the
  explicit non-interactive override on POSIX and PowerShell installers.
- A transport-only failure on a configured proxy moves to one explicit
  direct-route recovery path; the route name and typed error are written to the
  evidence attempt record.
- HTTP status errors and malformed payloads do not silently change routes.
- `RESEARCH_GUARD_DISABLE_FOREIGN_DIRECT_FALLBACK=1` restores strict
  proxy-only behavior for deployments that require it.
- If all routes fail, the raised error lists the attempted route names and
  typed causes without persisting proxy credentials or raw secret URLs.

## Verification boundary

The focused regression simulates proxy TLS/transport failure followed by a
successful direct request, verifies route-labelled evidence, checks strict
proxy-only mode, and confirms that an all-route outage remains a typed
`SourceTransportError`. Existing rate-limit, domestic-bypass, adapter, and
novelty-coverage tests remain unchanged. Cross-platform tests additionally
check unset configuration, ambient-proxy scrubbing, persistence, and installer
prompt/preserve behavior. Live smoke checks use the official
Crossref and arXiv APIs and report their HTTPS records; they do not turn
network reachability into a novelty or quality claim.

On 2026-09-03, a Singapore-like direct smoke removed all ambient proxy
variables and `RESEARCH_GUARD_FOREIGN_PROXY`, used an empty temporary
`RESEARCH_GUARD_HOME`, and resolved `foreign-direct`. Crossref returned one
record (DOI `10.1007/978-3-031-84300-6_13`) and arXiv returned one preprint
(`2209.15001v3`). This confirms that the corrected unset route can reach the
official endpoints in this environment; it is transport evidence only. The
records are [`10.1007/978-3-031-84300-6_13`](https://doi.org/10.1007/978-3-031-84300-6_13)
and [`arXiv:2209.15001v3`](https://arxiv.org/abs/2209.15001v3).
