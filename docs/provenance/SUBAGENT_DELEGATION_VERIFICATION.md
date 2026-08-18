# Native-subagent delegation verification

Date: 2026-08-18

Research Guard admits the existing `research_design` typed subroute with an
executable native-subagent-first plan and hash-bound completion receipt. It
rejects prompt-only preference, silent external-API fallback, and a new
top-level MCP tool.

The default contract is one serial entry/economy/lowest-capable native subagent
at low reasoning. Medium requires a recorded escalation rationale. If the host
has no subagent, the main agent performs the work locally. External APIs require
the user's explicit provider authorization or a registered cross-provider
protocol plus user authorization.

The focused suite covers five adversarial cases: default selection, unavailable
subagent fallback, unauthorized external API, authorized and hash-bound external
exception, excessive reasoning/path escape/tampering, plus MCP surface
preservation. Repeated SkillOpt evidence is generated locally under
`evals/subagent-delegation-skillopt/` and intentionally excluded from releases.

The MCP does not claim to launch host subagents or intercept unrelated provider
connectors. The host agent executes the plan; the hook exposes the contract and
the MCP validates provenance and artifacts.

## SkillOpt result

Four serial rounds passed all six behavioral tests and eight static gates. The
default-path test also executes a successful native-subagent receipt and checks
the explicit `NOT_CROSS_PROVIDER` label.
Peak aggregate task-owned working sets were 171,167,744; 173,613,056;
176,205,824; and 179,277,824 bytes, below the 536,870,912-byte limit. The
content-level report SHA-256 is
`b7f8120f4261c15674b3397f682c03c01e4f491403b3a865763ffabeb1a5ce64`.
