<!-- research-guard-doc-pair: skill-portability | revision: 2026-08-23.1 -->
# Skill 可移植性证据矩阵

[English](SKILL_PORTABILITY.md) | [简体中文](SKILL_PORTABILITY.zh-CN.md)

## 范围

本可选契约用于限定这样一种主张：一个已经完成 P24 的精确 Skill artifact 能从源
目标迁移到其他目标。只有当用户、论文、README 或准入理由提出跨模型、跨 harness
或跨任务可移植性主张时才启动。普通单目标 Skill 评估仍由
`frontier_skill_action` 负责；发现或 finalize 一个 Skill 本身不会自动触发 P25。

该路由是 `research_design.skill_portability_action`。它不新增顶层 MCP 工具、
分类器、模型、执行器、安装器、准入权限或自动 apply 路径。主智能体显式选择
2–12 个目标 cell 并登记理由。核心只消费哈希绑定的外部 trial artifact，永不执行
模型或第三方 Skill。

## 科学依据

设计只对当前一手研究作有界吸收：

- [SkillLens](https://arxiv.org/abs/2605.23899) 指出提取与消费是不同阶段，提取出的
  Skill 可能在消费目标上产生负迁移，因此必须评估目标 cell，不能假定可移植。
- [SkillOpt](https://arxiv.org/abs/2605.23904) 研究跨模型与 harness 的优化和迁移，
  因而需要冻结这些身份并比较同一个 artifact，不能静默重新优化。
- [Workflow-Localized Mechanism Learning](https://arxiv.org/abs/2607.20999)
  支持检验对相近 workflow 的有界迁移，而不是普适结论。
- [SkillRise](https://arxiv.org/abs/2607.26784) 与
  [ReuseRL](https://arxiv.org/abs/2605.31509) 提出了跨任务复用与演化问题，同时也
  强化了逐目标实测的必要性。

2026-08-23 通过 GitHub 公共记录检查并单独钉住了这些实现快照：
[SkillOpt at `bdfdc30a`](https://github.com/microsoft/SkillOpt/tree/bdfdc30a8e17309c06cdbe8449f01bdecc120203)、
[SkillLens at `c5ee10f6`](https://github.com/microsoft/SkillLens/tree/c5ee10f6b566cd2ccf96f7cef115eba59606b01b) 和
[Workflow-Localized Mechanism Learning at `019b7d9e`](https://github.com/xiaolin9595/workflow-localized-mechanism-learning/tree/019b7d9edd6cbc4e971d35443c83d120e5d0b974)。
这些来源只影响协议设计；代码没有被复制或执行。

## 可执行流程

1. 先在精确源目标上 finalize P24。P25 只接收其 Skill ID、仓库、40 字符 commit、
   candidate artifact SHA-256、规范主责、交叉裁决、指标契约、协议哈希和 finalize
   哈希。
2. 调用 `skill_portability_action=plan`。冻结 2–12 个 cell 和恰好 2 或 3 次
   replicate。每个 cell 登记 agent、模型 family/version、harness/version、任务
   范围、executor group、evidence family 和 case ID。模型、harness 或任务维度中
   至少有一个必须真实变化。
3. 使用全新 case。P25 case 不得与 P24 的 train、validation 或 heldout case
   重叠。每个 cell 的全部基线/候选配对 replicate 都使用同一份冻结 case 列表。
4. 至少登记一条当前一手论文和一条钉住不可变 40 字符 commit 的仓库来源。每条
   记录必须包含可点击 HTTPS URL、机制和局限。
5. 提交项目内、不超过 2 MiB 的非符号链接 JSON trial artifact。核心按继承的 P24
   效用/安全指标契约重新计算结果。run ID、baseline 哈希和 candidate 哈希不得重放。
6. finalize 前，status 只报告 `RECORDED_NOT_EXPOSED`，不暴露可能引导后续 cell 的
   分类或指标值。
7. 只有完整 cell × replicate 矩阵存在，且全部 trial 文件和 P24 绑定仍匹配哈希时
   才能 finalize。之后再由人工审查精确的有界主张。

整项任务没有任意超时。主智能体持续回显事实阶段并保存 artifact，直到完成、登记
事实阻塞，或用户明确给出预算/时间/停止指令。本地子进程保持串行、GPU 关闭，并
遵守 512 MiB 任务所属进程聚合资源契约。

## 证据矩阵

每次 replicate 独立分类：

| 分类 | 可执行含义 |
|---|---|
| `POSITIVE_TRANSFER` | 至少一个继承效用指标改善，所有效用指标均未超过容差退化，且全部安全指标非退化。 |
| `NO_MEASURED_GAIN` | 效用和安全均非退化，但没有效用指标超过容差改善。 |
| `NEGATIVE_TRANSFER` | 至少一个效用指标超过容差退化，同时安全仍非退化。 |
| `SAFETY_REGRESSION` | 至少一个继承安全指标退化；它支配该 cell 和整体主张边界。 |

只有全部 replicate 均为正迁移时，cell 才为正。安全退化具有最高优先级；任何负迁移
都必须保留。正迁移与无增益混合时记为 `MIXED_OR_UNCERTAIN`。系统不计算跨 cell
总平均，因此强 cell 不能抹掉失败 cell。

`SUPPORTED_ON_RECORDED_CELLS` 只允许明确列出已记录 cell ID、变化维度和精确
artifact 哈希的主张。`universal_claim_allowed` 永远为 false。只有全部 cell 均为
正迁移且至少存在两个不同 evidence family 时，已支持主张才算得到独立佐证；共享
模型 family 或 executor group 的 cell 被强制归入同一 evidence family；它们不能伪装成独立证据。

## MCP 契约

计划仍位于 17 个顶层 MCP 工具之一：

```json
{
  "action": "status",
  "project_root": "/project",
  "skill_portability_action": "plan",
  "skill_portability_id": "candidate-portability-v1",
  "skill_portability_selected_by": "main_agent",
  "skill_portability_selection_rationale": "Test the exact retained artifact on explicit target cells without universal extrapolation.",
  "skill_portability_protocol": {
    "research_question": "Where does this exact Skill artifact transfer without utility or safety regression?",
    "frontier_protocol_id": "candidate-frontier-v1",
    "source_binding": {
      "artifact_sha256": "<64 lowercase hex characters>",
      "skill_id": "candidate-skill",
      "repository": "owner/repository",
      "commit": "<40 lowercase hex characters>",
      "canonical_owner": "domain-skill",
      "overlap_decision": "fuse_narrow_adapter"
    },
    "replicates": 2,
    "cells": [{
      "cell_id": "target-a",
      "agent_id": "agent-a",
      "model_family": "model-family-a",
      "model_version": "model-version-a",
      "harness": "harness-a",
      "harness_version": "harness-version-a",
      "task_scope": "frozen-target-task-a",
      "executor_group": "executor-a",
      "evidence_family": "evidence-a",
      "case_ids": ["transfer-a-1", "transfer-a-2"]
    }, {
      "cell_id": "target-b",
      "agent_id": "agent-b",
      "model_family": "model-family-b",
      "model_version": "model-version-b",
      "harness": "harness-b",
      "harness_version": "harness-version-b",
      "task_scope": "frozen-target-task-b",
      "executor_group": "executor-b",
      "evidence_family": "evidence-b",
      "case_ids": ["transfer-b-1", "transfer-b-2"]
    }]
  }
}
```

后续使用 `record_source`、`record_trial`、`finalize`、`status` 或 `verify`。最终
收据暴露每个 cell 与 replicate、支持范围、evidence-family 数量、artifact 哈希和
完整性状态。

## 边界

- PASS 只证明契约和 artifact 完整性，不证明 Skill 普遍有效、科学上真实、在全部
  上下文安全，或能迁移到未测试目标。
- `HUMAN_REVIEW_REQUIRED` 不等于自动准入。P25 没有准入效果，也不能修改或安装
  已保留的 P24 artifact。
- artifact 支持的自报执行，不等于本核心独立重执行。producer 与执行收据仍属于
  证据边界。
- 同模型 family 或同 executor 的证据即使标签不同也彼此相关；协议拒绝这种虚假
  独立性表达。
- 缺失来源、cell、replicate、动态执行或证据变化必须保持阻塞/`NOT_RUN`，不能
  转换为可移植性支持。
