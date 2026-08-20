# Durable research-progression contract

Use this contract for deep literature searches, idea development, experiments, writing, audits, and other long research work unless the user supplies a time or cost budget.

1. Decompose work into short, independently verifiable stages with explicit inputs, outputs, evidence, and next action.
2. Do not impose an arbitrary whole-task timeout. A timeout may bound one network/process attempt; the main agent decides whether useful work remains.
3. During long work, provide factual progress updates and save stage results, queries, receipts, logs, manifests, hashes, and unresolved items incrementally.
4. Preserve partial attempts with an explicit status. Missing, invalid, not applicable, not run, and unknown completion are different states.
5. After transport loss or stale heartbeat, inspect durable evidence before retrying. Unknown completion is not retry authority.
6. Use append-only revisions or idempotent ledgers where replay could duplicate work or overwrite evidence.
7. Keep resource use within the registered budget. Stream/chunk large corpora and artifacts; never load the whole repository, corpus, TeX tree, or model when a bounded unit is enough.
8. Separate transport, availability, compilation, and local smoke evidence from empirical, quality, causal, novelty, or acceptance claims.
9. Stop when the objective is genuinely complete, the user budget is exhausted, or a real authority/external-state blocker remains. Do not stop merely because a default duration elapsed.
10. Before final delivery, consolidate stage artifacts into a self-contained result and report every unrun or degraded check explicitly.
11. For resource-sensitive multi-stage work, register the main agent's task DAG through `research_design.resource_plan_action`; use the existing serial CPU profiles, record actual resource telemetry where enforced, and never treat host inventory as process entitlement.
