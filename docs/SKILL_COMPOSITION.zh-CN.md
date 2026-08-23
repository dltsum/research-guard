<!-- research-guard-doc-pair: skill-composition | revision: 2026-08-23.1 -->
# 证据限定的 Skill 组合

[English](SKILL_COMPOSITION.md) | [简体中文](SKILL_COMPOSITION.zh-CN.md)

## 范围

当主智能体要组合两个或三个已经 finalize 的精确 P24 Skill 产物，并对它们的联合
价值或顺序提出主张时，才启用这个可选契约。普通单 Skill 使用不会触发它。组件、
目标顺序、对照顺序、目标 agent/model/harness/task、指标、case 和理由都必须由
主智能体选择；分类器、小模型或仓库热度不得代选。

调用 `research_design` 的 `skill_composition_action=plan`。每个组件必须绑定精确的
P24 protocol、Skill ID、仓库、不可变 commit、产物 SHA-256、canonical owner 与
overlap decision。组合 case 必须全新，并与所有组件 P24 的 train、validation、
heldout 切分互斥。

## 科学依据

[Generative Skill Composition for LLM Agents](https://arxiv.org/abs/2606.32025)
支持测量 Skill 子集、数量和顺序，而不是假设 Skill 越多越好。
[Break It Down, Pass It On](https://arxiv.org/abs/2608.20274) 提供了当前证据：模块化
分解与迁移需要任务级评估，不能依赖名称级兼容性。

实现比较固定到
[SkillsBench](https://github.com/benchflow-ai/skillsbench/tree/9a1f4dd5f7659f75707435da3ce854b6e48321d1)、
[SR-Agents](https://github.com/oneal2000/SR-Agents/tree/277fd8d2bbd7d3b81a5cf4ffa6e87e18c7906e4f)、
[PolySkill](https://github.com/simonucl/PolySkill/tree/fff8807d7501d93188f9f658f4d0af2f29f35c23)
和仅供参考的
[CompoSkill](https://github.com/Limax666/CompoSkill/tree/d7dc9d314f491eaace0b9e7c18e0c21ed3b71577)。
这些来源只支持协议设计，不能证明某个本地组合有用或安全。由于没有核验到可再分发
的仓库许可证，本项目不复制 CompoSkill 的代码或内容。

## 可执行流程

1. 每个组件先通过 P24 finalize，再由主智能体以 `selected_by=main_agent` 选择恰好
   两个或三个组件，并写明理由。
2. 冻结一个目标顺序和一个不同排列的 `control_order`；冻结全新 case、至少一个
   utility 指标、至少一个 safety 指标，以及恰好两次或三次 replicate。
3. 为每个精确产物声明带来源定位的 capability edge。支持的节点覆盖敏感来源、
   中间载荷与有副作用的终点；系统不会推断未声明能力。
4. 用 `record_source` 记录可点击的当前来源。finalize 至少需要一篇一手论文和一个
   带不可变 40 字符 commit 的仓库来源。
5. 每次 replicate 提交一个项目内 JSON 产物，使用相同 case 和组件哈希，并包含
   以下精确条件：`baseline`、每个 `single.<skill_id>`、`ordered` 与
   `control_order`。每个条件都要有唯一的 run SHA-256 和 execution-receipt
   SHA-256。
6. 调用 `finalize`，再调用 `verify`。finalize 前状态为
   `RECORDED_NOT_EXPOSED`；最终输出始终为 `HUMAN_REVIEW_REQUIRED`。

核心只记录外部产生的产物，永不运行模型或第三方 Skill。除非用户指定时间或预算，
整个任务没有任意截止时间；主智能体持续回显带链接阶段结果，并判断登记证据何时完整。

## 证据与路径结果

每次 replicate 都把目标顺序与实测最强的无 Skill/单 Skill 参照比较，并分类为
`POSITIVE_COMPOSITION_GAIN`、`NO_COMPOSITION_GAIN`、`INTERFERENCE` 或
`SAFETY_REGRESSION`。对照顺序单独分类，顺序效应始终可见，不做跨 replicate
分数平均。

声明的 capability graph 也分别按目标与对照顺序分析。一个顺序合法的路径必须跨越
至少两个 Skill，从敏感来源经声明的 bridge edge 到达有副作用终点。目标顺序路径会
拦截正向组合主张；仅对照顺序存在的路径继续显示并要求人工复核，但不会改写精确目标
顺序的测量。这只是对主智能体声明且带来源定位边的筛查：它不合成攻击，也不证明安全
或可利用性。

仅当每次 replicate 都取得正向组合增益、没有安全退化且没有声明的目标顺序路径时，
`scoped_claim_allowed=true`。即便如此，主张也只适用于精确产物、case、目标、指标、
evidence family 与顺序。任何状态下都保持 `universal_claim_allowed=false`、
`order_invariant_claim_allowed=false` 与 `safety_claim_allowed=false`。

## MCP 契约

现有 `research_design` 主责通过下列子操作提供能力，不新增顶层工具：

| 子操作 | 必需的组合字段 | 结果 |
|---|---|---|
| `plan` | `skill_composition_id`、protocol、`skill_composition_selected_by=main_agent`、理由 | 冻结且哈希绑定的协议 |
| `record_source` | ID、类型、标题、HTTPS URL、不可变 ID、机制、局限 | 追加式来源记录 |
| `record_trial` | 项目内 JSON 产物路径 | 记录产物与执行收据；隐藏结果 |
| `finalize` | 完整的来源与 replicate 矩阵 | 逐 replicate/顺序/路径结果及 `HUMAN_REVIEW_REQUIRED` |
| `status` | Composition ID | 不提前泄漏结果的当前证据 |
| `verify` | Composition ID | 状态、P24 绑定与产物完整性结果 |

协议与产物均为追加式。P24 finalization、protocol、case 边界或 trial 文件一旦变化，
核验就会失败，而不会静默重新绑定。

## 边界

- 该路由只限定一个精确的有序组合主张，不准入、安装、应用、优化或执行任何 Skill。
- 仓库热度、触发词重合和单次成功运行都不是组合证据。
- 对照顺序只是一项比较，不证明已经测试所有排列。
- capability edge 必须带来源定位，但完整性仍需人工复核；获得授权时还应另做动态
  对抗评估。
- CPU 串行执行、GPU 关闭，任务所有进程的总工作集上限为 `512 MiB`
  （`536,870,912` 字节）。
- 缺少外部执行、来源或最终收据时只能是 `NOT_RUN` 或 `ACTION_REQUIRED`，绝不为
  PASS。
