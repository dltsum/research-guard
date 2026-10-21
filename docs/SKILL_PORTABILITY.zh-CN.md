<!-- research-guard-doc-pair: skill-portability | revision: 2026-10-22.1 -->
# Skill 迁移评估

[English](SKILL_PORTABILITY.md) | [简体中文](SKILL_PORTABILITY.zh-CN.md)

只有要回答“在另一模型、harness 或任务上是否仍有效”时，才使用这个可选实验。
它不妨碍普通 Skill 安装与使用，也不要求传文件摘要或执行收据的校验码。

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

## 使用流程

1. 用 `skill_portability_action=plan` 按 P24 协议 ID 和 Skill 的 ID/仓库/版本定位
   源实验，说明目标 cell 的模型、harness、任务和 case。迁移比较至少有一个真实变化维度。
2. `replicates` 默认 1，可选 1–10；数量由任务决定。目标 case 与源实验开发/评估数据分离。
3. 保存支持协议的论文和实现来源。实际运行后提交结果 JSON 的路径、run ID、case 和指标。
   不需要 `artifact_sha256`、baseline/candidate run 摘要或执行收据摘要。
4. `finalize` 按已选择的 cell × replicate 汇总；缺失运行仍然缺失。
   `status` 显示已记录的进度，`verify` 不会因普通文件或说明文字编辑而拒绝继续。

## 结果含义

每次比较保留 `POSITIVE_TRANSFER`、`NO_MEASURED_GAIN`、`NEGATIVE_TRANSFER`
或 `SAFETY_REGRESSION`。强 cell 不能用平均分抹掉失败 cell。相同模型或执行器
的重复结果不能伪装成跨来源独立证据；未测目标不能写成已支持。

这是记录外部实际运行的评估器，核心不会自己执行模型或第三方 Skill。
字段样例见 [简化流程](../references/skill-lab-workflow.md) 和
[无摘要回归样例](../tests/test_simplified_skill_lab.py)。
