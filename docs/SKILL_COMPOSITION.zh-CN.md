<!-- research-guard-doc-pair: skill-composition | revision: 2026-10-22.1 -->
# Skill 组合评估

[English](SKILL_COMPOSITION.md) | [简体中文](SKILL_COMPOSITION.zh-CN.md)

这个可选实验回答“所选组合与顺序是否带来实测收益”，不限制普通组件安装与使用。
组件、顺序、目标和指标由任务决定，不由热度或关键词自动选择。

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

## 使用流程

1. `skill_composition_action=plan` 按 P24 协议 ID 和 Skill ID/仓库/版本选取
   两个或三个研究组件，不需要产物摘要。保存目标顺序、不同的对照顺序与新 case。
2. 选择 utility 与 safety 指标；`replicates` 默认 1，支持 1–10，由任务选择。
3. 需要研究能力组合风险时，保存组件能力边的实际来源定位。记录支持协议的参考来源。
4. 实际运行无 Skill、每个单独 Skill、目标组合与对照顺序。在结果 JSON 中提供
   `run_id`、case、条件和指标；无需组件摘要、run 摘要或签名执行收据。
5. `finalize` 分别保留各次重复、顺序与路径分析。`status` 读取记录；可选 `verify`
   检查相关文件，不重算状态链，也不会因普通文件编辑而使工作失效。

## 结果含义

比较结果可以是 `POSITIVE_COMPOSITION_GAIN`、`NO_COMPOSITION_GAIN`、
`INTERFERENCE` 或 `SAFETY_REGRESSION`。只测一个顺序不能声称所有排列有效。
能力路径只表示声明边上的筛查结果，不证明安全或可利用性。

缺失条件或运行不能补成成功；本核心记录外部试验，不自行执行模型或第三方 Skill。
详见 [简化流程](../references/skill-lab-workflow.md) 和
[无摘要回归样例](../tests/test_simplified_skill_lab.py)。
