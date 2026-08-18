# Native-subagent-first LLM assistance

Research Guard uses host-native subagents before external LLM APIs. This avoids
provider transport and account dependencies while keeping model assistance
explicit and auditable.

## Trigger

Before a research step that would otherwise call an LLM API, the main agent
calls `research_design` with `action=status`, `delegation_action=plan`, a stable
task ID/type/summary, `delegation_selected_by=main_agent`, and the host's actual
`subagent_available` value.

The executable default is:

- one native subagent;
- entry, economy, or lowest-capable model tier;
- `low` reasoning;
- serial execution;
- no external API permission.

`medium` reasoning requires a recorded escalation rationale. The default path
rejects `high`, `xhigh`, `max`, and `ultra`.

## Fallback and exceptions

If the host cannot provide a native subagent, the plan returns
`LOCAL_FALLBACK_REQUIRED`: the main agent performs the bounded work locally.
It does not silently switch to an API.

An external API is allowed only when:

1. the user explicitly requested a named provider/model; or
2. a registered evaluation protocol genuinely requires cross-provider identity;
3. `external_selected_by=user` and a rationale are recorded.

Subagents may prepare prompts or analyze returned evidence, but repeated calls
to the same model or same-host subagents do not satisfy an independent
multi-model/cross-provider protocol.

## Completion receipt

After execution, call `delegation_action=submit` with the planned execution
mode, executor ID, project-local artifact, and applicable tier/effort or external
provider-model ID. The receipt binds the current plan and artifact SHA-256.
`delegation_action=verify` rereads every current artifact and fails if it moved,
changed, disappeared, escaped the project root, or no current receipt exists.

This mechanism governs Research Guard workflows. It is not a claim that the MCP
process can itself launch host subagents or intercept unrelated provider tools.
