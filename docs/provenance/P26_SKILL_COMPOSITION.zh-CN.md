<!-- research-guard-doc-pair: p26-skill-composition | revision: 2026-08-23.3 -->
# P26 Skill 组合核验

## 范围与冻结决策

P26 只补一个窄证据缺口：多个已 finalize 的 Skill 各自有效，并不能证明组合后有
额外价值、顺序是否重要，或其能力不会串成有害路径。P26 在现有 `research_design`
主责下增加可选的有序组合矩阵，不新增顶层 MCP 工具、分类器、模型、执行器、
优化器、安装器、准入权限或 apply 路径。

冻结决策要求恰好两个或三个由主智能体选择且已 finalize 的 P24 artifact、全新
case、一个目标顺序与一个不同的对照顺序、utility/safety 指标，以及恰好两次或三次
replicate。每次 replicate 都包含无 Skill、每个单 Skill、目标顺序和对照顺序证据；
所有结果与声明的跨 Skill 路径均保持可见。

## 当前一手来源与实现快照

2026-08-23 检查了当前公共记录：

- [Generative Skill Composition for LLM Agents](https://arxiv.org/abs/2606.32025)
  支持测量 Skill 子集、数量与顺序。
- [Break It Down, Pass It On](https://arxiv.org/abs/2608.20274) 支持对模块化
  迁移与组合做任务级评估。

匿名 GitHub 公共元数据钉住了下列实现快照：

| 仓库 | 不可变 commit | 决策 |
|---|---|---|
| [benchflow-ai/skillsbench](https://github.com/benchflow-ai/skillsbench/tree/9a1f4dd5f7659f75707435da3ce854b6e48321d1) | `9a1f4dd5f7659f75707435da3ce854b6e48321d1` | Apache-2.0 方法来源；大型 payload 保持外置 |
| [oneal2000/SR-Agents](https://github.com/oneal2000/SR-Agents/tree/277fd8d2bbd7d3b81a5cf4ffa6e87e18c7906e4f) | `277fd8d2bbd7d3b81a5cf4ffa6e87e18c7906e4f` | MIT 方法来源；不作为运行时依赖 |
| [simonucl/PolySkill](https://github.com/simonucl/PolySkill/tree/fff8807d7501d93188f9f658f4d0af2f29f35c23) | `fff8807d7501d93188f9f658f4d0af2f29f35c23` | MIT 方法来源；不融合代码 |
| [Limax666/CompoSkill](https://github.com/Limax666/CompoSkill/tree/d7dc9d314f491eaace0b9e7c18e0c21ed3b71577) | `d7dc9d314f491eaace0b9e7c18e0c21ed3b71577` | 仅供参考；未核验到可再分发许可证 |

仓库热度没有被用作正确性、安全或准入证据。实际实现是本地标准库契约，不是上游
实现的副本。

## 基线与实现

首次定向测试按预期以 `ModuleNotFoundError` 失败，因为当时
`skill_composition_core` 尚不存在。第一轮实现通过 11 项核心行为测试，同时暴露一个
缺失的 MCP 路由；接入现有 `research_design` 主责后，P24-P26 共 37 项定向测试
全部通过，且没有增加第 18 个工具。

当前实现会：

- 把每个组件绑定到精确 P24 protocol、finalization、artifact、主责、交叉裁决与
  已占用 case 边界；
- 拒绝 P24 case 泄漏、自动组件选择、相同目标/对照顺序、不完整条件、收据重放、
  artifact 漂移、状态链漂移和变化的 P24 绑定；
- 相对实测最强无 Skill/单 Skill 参照重算 `POSITIVE_COMPOSITION_GAIN`、
  `NO_COMPOSITION_GAIN`、`INTERFERENCE` 与 `SAFETY_REGRESSION`；
- 保留对照分类和顺序效应，不输出分数平均；
- 检测由主智能体声明、带来源定位、符合顺序且跨越至少两个 Skill 的能力路径；
- 只允许限定到精确记录顺序的正向支持，并始终保持
  `universal_claim_allowed=false`、`order_invariant_claim_allowed=false` 与
  `safety_claim_allowed=false`。

## 定向测试与重复 SkillOpt

连续四轮 SkillOpt 全部通过。每轮运行同一组 44 项测试，覆盖 P26 组合、P25
可移植性、P24 前沿评估和 P10 规范 MCP/路由表面，并执行 12 项静态架构门禁。覆盖
正向/无增益/干扰/安全结果、目标与对照顺序效应、目标路径和仅对照路径、精确 P24
绑定、split 泄漏、finalize 前不披露、顺序、重放、来源身份、篡改、真实 MCP
dispatch 以及保持 17 个工具不变。

任务所属进程聚合工作集最大为 236,027,904 字节，低于 536,870,912 字节限制；
没有发生工作集 trim 或 trim failure。本地报告是
`evals/p26-skill-composition-skillopt/report.json`；其封存内容摘要是
`f086c3956f0ee3d4ca356cb1c413c4be5c721de8564be0c15a3876117cacecef`，
文件 SHA-256 是
`74b0a6e7e2b1fa9c11749246b86fa094e4765bda3f7679f6d3e0cab5d79974f9`。
评估日志与本地 SkillOpt JSON 留在本地；确定性 runner、测试、契约和本有界
provenance 报告进入公共包。

另一次全仓库本地运行记录了 83 个 PASS 测试文件和 2 个 FAIL 测试文件。
这两个文件中记录的所有失败都来自实时匿名外源传输：7897 端口接受 HTTP
CONNECT 后，对 Crossref、PubMed、OpenAlex、Europe PMC、DataCite、DBLP、HAL、
DOI、OpenAIRE、Zenodo 或 ClinicalTrials 请求返回 TLS EOF。没有放宽任何断言或
必需来源。因此，本地全套件结果在外部路由成功重跑前仍为 `ACTION_REQUIRED`；
P26 定向门禁和确定性打包门禁的 PASS 证据与之分开保留。

## 打包与发布门禁

P26 已登记为仓库校验、来源安全包和四个平台迁移包的必备文件集。一次发布前
构建生成了全部五种归档变体。重建的 Windows 证明包大小为 305,068,965 字节，
SHA-256 为
`21d167ed53b49546ea1996a60d3e2e512da9337419858ba06dad127f1f7967fb`，随后通过了干净的
重定向用户根安装。已安装验证器报告 17 个 MCP 工具、P26 路由，以及固定的
Pint 0.25.3、SymPy 1.14.0 与 Z3 5.0.0；安装阶段聚合工作集峰值为 342,421,504 字节。

双语登记表把中英文操作契约和本 provenance 对绑定到共享修订、标题、链接和
规范化哈希。最终归档身份只能在本文档对冻结后生成，应进入 Release/CI 收据，
不应写入会改变自身哈希的归档输入。本发布前记录不声称已安装插件刷新、远程推送或
精确 commit CI；它们仍是独立的提交后门禁。仅归档构建成功不等于安装或发布证据。

## 主张边界

这些结果建立本地契约行为、数据流约束、篡改检测、受限重复回归与已登记的打包纳入，
但不证明两篇引用论文、真实场景组合增益、capability edge 覆盖完整性、可利用性、
全局安全、独立模型执行或 venue 录用。`HUMAN_REVIEW_REQUIRED` 不等于准入。缺失
执行、条件、来源、收据或人工复核时必须保持阻塞/`NOT_RUN`，不能转成正向主张。
