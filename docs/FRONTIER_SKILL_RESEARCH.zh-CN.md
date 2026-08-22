<!-- research-guard-doc-pair: frontier-skill-research | revision: 2026-08-23.3 -->
# 前沿 Skill 研究与准入

[English](FRONTIER_SKILL_RESEARCH.md) | [简体中文](FRONTIER_SKILL_RESEARCH.zh-CN.md)

## 范围

本契约管理第三方学术 Skill 的发现、本地评估和准入。它是现有
`research_design` 主责工具的类型化子路由，不是另一套安装器、执行器、模型或
顶层工具。领域、目标智能体、harness 和规范主责均由主智能体选择；关键词分类器
或小型路由模型不能替代这一语义判断。

本契约不会声称热门 Skill 必然有效、静态扫描已经证明安全，也不会假定一个智能体
上的结果可以迁移到另一个智能体。搜索排名、stars、安装量和 token 重合只能作为
发现信号或代理证据。
每个保留候选都必须在真实目标智能体与冻结 harness 上接受测试。

## 科学依据

实际机制只吸收了当前一手研究中少量且经过审计的部分：

- [SkillOpt](https://arxiv.org/abs/2605.23904) 支持有界编辑、验证集门禁、被拒编辑
  记忆和最终 heldout 核验。
- [SkillLens](https://arxiv.org/abs/2605.23899) 区分经验生成、提取和消费，并指出
  可能发生负迁移，因此必须在真实目标智能体上评估。
- [Arbor](https://arxiv.org/abs/2606.11926) 支持跨长时任务保存失败分支以及
  artifact—证据链接的持久假设树。
- [HDSO](https://arxiv.org/abs/2606.22330) 支持可审计的假设驱动优化，并显式防止
  从稀疏轨迹学到伪捷径。
- [SLIM](https://arxiv.org/abs/2605.10923) 与
  [SkillOS](https://arxiv.org/abs/2605.06614) 支持按边际贡献保留/退役，以及等待
  延迟证据，而不是默认永久准入。
- [Skill-Inject](https://arxiv.org/abs/2602.20156)、
  [SkillAttack](https://arxiv.org/abs/2604.04989) 与
  [SkillSieve](https://arxiv.org/abs/2604.06550) 支持失败关闭的供应链初筛、
  上下文相关审查和多轮对抗测试。

仓库把实现来源登记为不可变 commit。某篇论文影响了契约，不代表其上游代码会被
执行或复制。

## 可执行流程

按以下顺序使用 `frontier_skill_action`：

1. `plan` 冻结带版本的问题、目标智能体/harness、候选 Skill ID/仓库/commit、
   基线 artifact SHA-256、互不重叠的 train/validation/heldout case ID、指标方向
   与容差、恰好 2–3 轮验证，以及主智能体的选择理由。
2. `record_source` 只接收带可点击 HTTPS 链接和不可变标识的一手论文、实现、
   benchmark 或 specification；每条记录同时保存机制和局限。
3. `register_hypothesis` 建立追加式父子分支，保存预期效果、证伪条件、来源、
   规范主责和交叉功能裁决。
4. `record_trial` 读取项目内受限 JSON artifact。验证轮必须按冻结顺序只追加，
   且协议内每个 `run_id` 必须唯一。代码按冻结指标重新计算效用改善和全部安全
   非退化，不接受调用方自报的 PASS。
5. 所有验证轮通过前 heldout 保持锁定。它只在最后一个已接受 artifact 上执行
   一次，finalize 前的 status 不暴露其结果。
6. `finalize` 强制要求一手论文、实现/specification 来源、精确的冻结验证轮、
   一次通过的 heldout、未改变的 artifact 身份和零安全退化。它返回
   `HUMAN_REVIEW_REQUIRED`，保留拒绝/参考分支，并且不暴露自动 apply 路由。
7. `verify` 重查哈希链和每个 trial artifact；状态或证据一旦漂移，收据立即失效。

整项任务没有任意超时。主智能体持续给出阶段回显并保存 artifact，直到协议完成、
出现已记录的事实阻塞，或用户明确给出预算/时间/停止指令。本地子进程继续遵守
串行、GPU 关闭、512 MiB 的资源契约。

## 安全与准入

隔离扫描读取每个受限文本文件。已知远程 shell、凭据、编码执行、指令覆盖、
审批绕过、隐瞒、敏感数据、隐藏 Unicode 和大范围删除模式都会失败关闭，即使它们
出现在 `SKILL.md` 而非可执行脚本中也一样。扫描还会关联“一个文件中的敏感源”和
“另一个文件中的外发汇”。任何 review finding 都不能静默变成 PASS。

静态扫描只是初筛，不能证明意图无害。动态对抗评估未执行时，收据明确标成
`NOT_RUN`。第三方脚本永不自动执行；来自
[SkillWeaver](https://arxiv.org/abs/2504.07079) 或
[HASP](https://arxiv.org/abs/2605.17734) 的可执行程序合成只保留为参考，因为直接
引入会越过隔离和授权边界。

原有 2–3 轮 Optuna 路由现在把结果明确标为“触发/文件选择代理”。
`domain_skill_action=admit` 还必须取得已 finalize 的前沿协议，并让 candidate
Skill ID、仓库、commit、artifact SHA-256、规范主责和交叉裁决与待准入 Skill
完全一致。准入仍需显式调用；
前沿机制自身不会安装或准入任何 Skill。

## MCP 契约

该路由仍位于 17 个顶层 MCP 工具之一：

```json
{
  "action": "status",
  "project_root": "/project",
  "frontier_skill_action": "plan",
  "frontier_protocol_id": "graph-skill-v1",
  "frontier_selected_by": "main_agent",
  "frontier_selection_rationale": "Evaluate this exact candidate on the frozen target research harness.",
  "frontier_protocol": {
    "research_question": "Does the candidate improve specialist graph research support?",
    "target_agent": "target research agent",
    "target_harness": "project-local frozen harness",
    "baseline_artifact_sha256": "<64 lowercase hex characters>",
    "candidate_identity": {
      "skill_id": "graph-skill",
      "repository": "owner/repository",
      "commit": "<40 lowercase hex characters>"
    },
    "splits": {
      "train": ["train-1"],
      "validation": ["validation-1"],
      "heldout": ["heldout-1"]
    },
    "metrics": [
      {"name": "utility", "direction": "maximize", "kind": "utility", "tolerance": 0.0},
      {"name": "unsafe_rate", "direction": "minimize", "kind": "safety", "tolerance": 0.0}
    ],
    "validation_rounds": 2
  }
}
```

后续调用使用 `record_source`、`register_hypothesis`、`record_trial`、`finalize`、
`status` 或 `verify`。trial 文件必须位于 `project_root` 内，是不超过 2 MiB 的
非符号链接 JSON 文件，并绑定 SHA-256。

## 边界

- 本地测试只证明已记录的目标/harness/case 和指标，不是普适科学有效性结论。
- 来源 URL 与不可变标识证明来源身份，不证明上游每项主张真实或适用于本项目。
- 被拒分支是证据，不等于没有进展；它保留在假设树中，避免后续静默重复失败。
- `HUMAN_REVIEW_REQUIRED` 不等于准入；只有现有显式准入门禁能消费一个精确匹配的
  retained proposal。
- 缺失网络覆盖、不可用的动态评估或用户拒绝的依赖必须保持显式 `NOT_RUN`/阻塞，
  绝不能变成 PASS。
