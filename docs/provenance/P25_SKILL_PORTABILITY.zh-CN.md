<!-- research-guard-doc-pair: p25-skill-portability | revision: 2026-08-23.1 -->
# P25 Skill 可移植性核验

## 范围与冻结决策

P25 只补一个窄证据缺口：P24 在一个冻结目标上评估一个精确 Skill artifact，但按
设计不能证明它能迁移到另一个模型、harness 或任务。P25 在现有
`research_design` 主责下增加可选目标 cell 证据矩阵。只有提出可移植性主张时才
触发；它不新增顶层 MCP 工具、分类器、模型、执行器、安装器、准入权限或 apply
路径。

冻结决策是：复用已 finalize 的 P24 身份与指标契约；冻结 2–12 个显式目标 cell
和恰好 2 或 3 次配对 replicate；禁止复用 P24 train/validation/heldout case；保留
逐 cell 结果；暴露 executor/evidence-family 依赖；禁止普适外推。核心只记录受限
外部 JSON artifact，不执行第三方代码或模型。

## 当前一手来源与实现快照

2026-08-23 检查了当前一手记录：

- [SkillLens](https://arxiv.org/abs/2605.23899) 支持目标消费测试和显式负迁移结果。
- [SkillOpt](https://arxiv.org/abs/2605.23904) 支持冻结目标模型/harness 身份，并比较
  一个未改变的 artifact。
- [Workflow-Localized Mechanism Learning](https://arxiv.org/abs/2607.20999)
  支持对相近 workflow 做有界迁移测试。
- [SkillRise](https://arxiv.org/abs/2607.26784) 和
  [ReuseRL](https://arxiv.org/abs/2605.31509) 提出跨任务复用问题，但不能自动成为
  未测试目标的证据。

匿名 GitHub 公共元数据钉住了这些 MIT 仓库：

| 仓库 | 不可变 commit | 决策 |
|---|---|---|
| [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt/tree/bdfdc30a8e17309c06cdbe8449f01bdecc120203) | `bdfdc30a8e17309c06cdbe8449f01bdecc120203` | 方法来源；不作为运行时依赖 |
| [microsoft/SkillLens](https://github.com/microsoft/SkillLens/tree/c5ee10f6b566cd2ccf96f7cef115eba59606b01b) | `c5ee10f6b566cd2ccf96f7cef115eba59606b01b` | 目标消费来源；不融合代码 |
| [xiaolin9595/workflow-localized-mechanism-learning](https://github.com/xiaolin9595/workflow-localized-mechanism-learning/tree/019b7d9edd6cbc4e971d35443c83d120e5d0b974) | `019b7d9edd6cbc4e971d35443c83d120e5d0b974` | 有界迁移来源；不执行 |

搜索热度没有被用作正确性或准入证据。实际收纳的是本地契约，不是上游实现副本。

## 基线与实现

修改前的 `evals/incremental-tests/p25-baseline-missing-portability/` 按预期失败：
`skill_portability_core` 尚不存在。其任务所属进程聚合工作集峰值为 125,759,488
字节。第一轮实现暴露两个集成缺陷——校验报错顺序和 MCP 路由缺失——并保持 FAIL。
修正时没有削弱任何断言；随后
`evals/incremental-tests/p25-core-round-2/` 中 P10 路由、P24 前沿和 P25 可移植性
三组全部通过。

当前实现会：

- 消费精确 finalize 的 P24 artifact、主责、交叉裁决、哈希、源 case 与指标契约；
- 冻结模型/harness/任务变化、executor group、evidence family、case 和有序
  replicate；
- 按继承的效用/安全容差重算 `POSITIVE_TRANSFER`、`NO_MEASURED_GAIN`、
  `NEGATIVE_TRANSFER` 与 `SAFETY_REGRESSION`；
- finalize 前隐藏结果，且永不输出跨 cell 总平均；
- 拒绝 case 泄漏、run 哈希重放、artifact 漂移、状态链漂移、虚假独立性、不完整
  矩阵和变化的 P24 绑定；
- 只在全部 cell 为正时允许限定到已记录 cell 与精确 artifact 的主张，并保持
  `universal_claim_allowed=false`。

## 定向测试与重复 SkillOpt

文档接入后的定向集成运行了覆盖 P25、P24 和规范 P10 MCP/路由表面的 31 项测试，
全部通过。测试包含 2/3 replicate 路径、正迁移/无增益/负迁移/安全退化、P24 split
泄漏、finalize 前不披露、来源与身份、顺序、重放、篡改、虚假独立性、不完整矩阵、
真实 MCP dispatch 和保持 17 个工具不变。

连续四轮 SkillOpt 全部通过。每轮运行同一组 31 项测试和 13 项静态架构门禁。任务
所属进程聚合工作集最高为 231,432,192 字节，低于 536,870,912 字节限制；没有发生
工作集 trim 或 trim failure。本地报告为
`evals/p25-skill-portability-skillopt/report.json`；其封存内容摘要是
`a77e8af507f4793444f89a23c24ecd294d01e658d3612bd481891a90e27ffde4`，
文件 SHA-256 是
`04212fcbbf51bd969279864283ce63ce9458b391202aa71c5ff33b61ac381373`。
评估日志保留在本地；确定性 runner、测试、契约和本有界报告进入公共包。

## 打包与发布门禁

P25 已成为仓库校验、来源安全包、四个平台迁移包和隔离安装核验的必备文件集。CI
与 Release workflow 同时运行 P24 和 P25 套件。双语文档登记表把中英文操作契约和
本 provenance 对绑定到共享修订、标题、链接和规范化哈希。

最终包、隔离安装、已安装插件、远程推送和精确 commit CI 证据只有在对应阶段实际
通过后才登记；仅归档构建成功不等于安装或发布证据。

## 主张边界

这些结果建立本地契约行为、数据流约束、篡改检测、双语/打包纳入和重复回归状态，
但不证明任何上游论文主张、普适 Skill 可移植性、独立模型执行、科学有效性、全局
安全或 venue 录用。`HUMAN_REVIEW_REQUIRED` 不等于准入。缺失执行、来源覆盖、
cell 或 replicate 必须保持阻塞/`NOT_RUN`，不能转成支持证据。
