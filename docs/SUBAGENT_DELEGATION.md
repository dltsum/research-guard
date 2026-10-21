# Native-subagent-first LLM assistance

Research Guard uses host-native subagents before external LLM APIs. This avoids
provider transport and account dependencies while keeping model assistance
explicit and auditable.

## Trigger

When a research step needs recorded model assistance, the main agent may call `research_design` with `action=status`, `delegation_action=plan`, a stable
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
provider-model ID. The record identifies the task and actual execution mode.
No artifact checksum or signed receipt is required. Ordinary edits do not
invalidate completed work. Optional `delegation_action=verify` checks that the
recorded artifact is available inside the project and that execution was
actually recorded; it does not compare the file with historical byte hashes.

This mechanism governs Research Guard workflows. It is not a claim that the MCP
process can itself launch host subagents or intercept unrelated provider tools.
