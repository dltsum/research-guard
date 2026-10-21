<!-- research-guard-doc-pair: frontier-skill-research | revision: 2026-10-22.1 -->
# 前沿 Skill 研究

[English](FRONTIER_SKILL_RESEARCH.md) | [简体中文](FRONTIER_SKILL_RESEARCH.zh-CN.md)

这是需要比较 Skill 科研效果时使用的可选实验。普通安装和使用无需先做 P24，
也不用登记文件摘要、状态链或签名收据。直接说清要完成的工作即可。

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

## 使用流程

1. `frontier_skill_action=plan` 保存问题、目标智能体与 harness、候选 Skill
   的 ID/仓库/版本、数据切分和指标。`validation_rounds` 可选，默认 1，支持 1–10。
2. `record_source` 保存论文、实现或规范来源的链接、版本、机制与适用范围。
3. `register_hypothesis` 保存要测试的机制、预期效果和证伪条件。
4. 实际运行后用 `record_trial` 读取结果 JSON，提供 `run_id`、case ID 和指标。
   无需基线或候选产物的校验码。代码根据指标计算改善与安全退化。
5. 需要独立评估的实验仍将 heldout 与开发数据分离，按任务选择的轮次完成。
6. `finalize` 汇总实测证据与拒绝分支；未运行、失败或证据不足保持原状态。
   `status` 读取记录，`verify` 可检查相关产物是否可读；普通文件编辑不会触发摘要失效。

## 安装与科研评估分开

`domain_skill_action=admit` 在实际内容安全扫描通过后即可安装到选定领域。
触发优化和 P24 均为可选；未做目标智能体评估时标记 `NOT_EVALUATED`，
不把“可以安装”说成“已经证明有效”。优化轮次由任务决定，不再强制重复两三次。

若提供 `frontier_protocol_id`，会附上相应评估记录，按候选 ID、仓库与版本定位，
无需来回传产物摘要。静态扫描只做内容初筛，第三方脚本不会因安装而自动执行。

## 示例

“安装图研究相关组件，读取我的实验记录，找一个适合的领域 Skill。先直接使用，
若要比较其效果，再在独立测试样本上与原流程各运行一次，并保留实际结果。”

详细字段和可运行的无摘要样例见 [简化流程](../references/skill-lab-workflow.md)
与 [回归样例](../tests/test_simplified_skill_lab.py)。本地结果只支持已测目标、
case 和指标，不自动推出普适效果。
