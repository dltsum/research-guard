# P28 network-channel recovery

## Issue and scope

GitHub Issue [#6](https://github.com/dltsum/research-guard/issues/6) reported
that the 0.7.0 novelty/collision search could not connect to academic search
websites. The attached run reported transport failures from both arXiv and
Crossref. A transport failure is not a zero-result observation and must keep
the collision gate incomplete.

## Root cause

The source request boundary always selected the configured foreign proxy and
retried that same route. When the local listener accepted a connection but
failed the TLS handshake, no usable route remained even when direct access to
the same official endpoint was available. The failure was therefore in route
recovery, not in source parsing or collision adjudication.

## Implemented contract

- Domestic and loopback requests use an empty `ProxyHandler`, bypassing
  inherited ambient proxy variables.
- Foreign requests try `RESEARCH_GUARD_FOREIGN_PROXY` first (default
  `http://127.0.0.1:7897`).
- A transport-only failure moves to one explicit direct-route recovery path;
  the route name and typed error are written to the evidence attempt record.
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
novelty-coverage tests remain unchanged. Live smoke checks use the official
Crossref and arXiv APIs and report their HTTPS records; they do not turn
network reachability into a novelty or quality claim.
