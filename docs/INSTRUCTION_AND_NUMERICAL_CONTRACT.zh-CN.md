<!-- research-guard-doc-pair: instruction-and-numerical | revision: 2026-08-22.1 -->
# 指令遵循与正向数值审计

[English](INSTRUCTION_AND_NUMERICAL_CONTRACT.md) | [简体中文](INSTRUCTION_AND_NUMERICAL_CONTRACT.zh-CN.md)

本契约说明 Research Guard 的两项可执行能力。语义判断仍由主智能体完成；本地
代码负责保存已选择的要求并核验结果证据。完整工作流见
[Research Guard Skill](../SKILL.md) 和
[论文写作能力矩阵](PAPER_WRITING_CAPABILITIES.md)。

## 范围

- `research_design.instruction_action` 保护主智能体显式选择的多步骤用户要求。
- `paper_audit.numerical_action` 建模并审计带来源定位的线性有理约束系统。
- 两者都复用现有 17 个顶层 MCP 工具，并遵守 512 MiB、串行、禁用 GPU 的
  进程契约。
- 两者都不能替代 system/developer/安全约束、科学判断、实时联网核验、Lean
  定理检查或数值模型执行。

## 指令遵循

多步骤任务第一次修改前，主智能体调用 `instruction_action=register`，登记：

- 一个稳定的合同 ID 和完整用户请求的哈希；
- 原子要求的 `mandatory`、验收条件、依赖、必需证据类型和禁止替代项；
- `instruction_selected_by=main_agent` 与具体的拆解理由。

带证据的状态转换使用 `instruction_action=record`。证据类型被有意限制为：项目内
文件哈希、指定状态路径等于登记值的 JSON 收据、可点击 HTTPS 证据定位，以及
显式人工检查清单。文件或收据改变后状态变为 `evidence_invalid`。用户豁免使用
`instruction_action=waive`、`instruction_selected_by=user`，并提供该明确用户消息
的 SHA-256。

台账不会覆盖历史。已经满足的证据一旦漂移，该项会重新变为活动状态，并允许提交
新的带证据事件；当依赖项证据无效时，下游项目不能继续使用其旧 `satisfied` 标签。

只有 `instruction_action=verify` 能签发完成 PASS 收据；其输出包含
`completion_claim_allowed=true`。简单单轮回答免登记，因为是否属于多步骤任务
必须由主智能体结合完整上下文判断，不能交给关键词分类器。

## 正向数值审计

先使用 `audit_features.constructive_numerical=true` 规划论文审计，并在 2–3 个
角色中选择 `methodology_statistics` 或 `formal_math_lean`，然后调用
`numerical_action=construct`。

manifest 可声明 1–32 个实数或整数变量。每个变量都要有 Pint 单位、协议来源、
用途和可选开/闭边界，并且必须实际出现在 1–64 条结构化线性方程或不等式中。
每条关系都登记独立来源、有理系数、系数单位和右侧单位。零系数、未声明变量、
非线性语法、量纲不匹配以及仿射/偏移单位换算都会显式失败。

结果分开保留四类记录：

1. Pint 量纲归一化；
2. SymPy 规范线性关系，以及等式系统的秩/RREF；
3. Z3 的 SAT/UNSAT/UNKNOWN，以及 UNSAT core 或精确投影边界；
4. 对每个完整锚点进行精确有理数协议复核。

每个合法区间都标记为
`marginal_projection_subject_to_all_registered_constraints`。边际区间不保证其
笛卡尔积可行。`joint_anchors` 是在全部约束下构造的完整赋值，随后再次独立检查
边界、整数类型、每条关系的精确 slack，以及 binary64 溢出/下溢风险。这些是
联合可行锚点；它们只是设计点，不是观测结果、最优解或自动参数建议。

## MCP 示例

指令登记复用现有 `research_design` 工具：

```json
{
  "action": "status",
  "project_root": "/project",
  "instruction_action": "register",
  "instruction_contract_id": "revision-v1",
  "instruction_request_text": "Implement and verify both requested features.",
  "instruction_scope": "This multistep implementation and release.",
  "instruction_selected_by": "main_agent",
  "instruction_selection_rationale": "The complete request contains two implementation deliverables and one release proof.",
  "instruction_requirements": [
    {
      "id": "implementation",
      "text": "Implement the executable routes.",
      "kind": "deliverable",
      "mandatory": true,
      "acceptance_criteria": ["Project-local implementation artifacts exist."],
      "required_evidence_kinds": ["file"],
      "forbidden_substitutions": ["Do not replace code with prompt text."],
      "depends_on": []
    }
  ]
}
```

数值变量和关系使用精确结构化值：

```json
{
  "action": "status",
  "project_root": "/project",
  "numerical_action": "construct",
  "numeric_constraint_manifest": {
    "audit_id": "protocol-v1",
    "protocol_id": "methods-v1",
    "source": "Methods pp. 3-4",
    "anchor_count": 3,
    "variables": [
      {
        "name": "duration",
        "type": "real",
        "unit": "second",
        "minimum": 0,
        "minimum_inclusive": false,
        "maximum": 10,
        "source": "Methods p. 3",
        "purpose": "duration allocated to one protocol run"
      }
    ],
    "constraints": [
      {
        "id": "budget",
        "source": "Methods Eq. 2",
        "relation": "<=",
        "terms": [{"variable": "duration", "coefficient": 1}],
        "rhs": {"value": 10, "unit": "second"}
      }
    ]
  }
}
```

## 证据与停止状态

| 状态 | 能否声称完成 | Stop 行为 |
|---|---|---|
| `PASS` | 只有当前核验收据存在时允许 | 允许 |
| `ACTION_REQUIRED` | 禁止 | Stop Hook 拦截 |
| `USER_DECISION_REQUIRED` | 禁止 | 用户决定前由 Stop Hook 拦截 |
| `BLOCKED` | 禁止；只能事实性移交阻塞 | 允许移交，但绝不转换为 PASS |
| `NOT_CERTIFIED` | 禁止 | 数值结果保持未解决 |

指令事件追加写入并组成哈希链；Stop Hook 会重新哈希已登记文件和 JSON 收据。
正向数值记录绑定完整输入 manifest、求解器输出、进程资源遥测和收据哈希。使用
同一 audit ID 提交不同约束会被拒绝。

## 边界与降级

- 指令台账无法自动得知所有隐含验收条件。主智能体必须拆解完整请求；代码负责
  阻止已经登记的项目被静默丢弃。
- HTTPS 证据项只证明登记了一个定位；仍需由相应文献/引用路由核验身份和主张支持。
- 人工检查是声明式人类/智能体证据，不是独立可执行证明。
- 认证区间当前只覆盖线性有理约束。非线性、超越函数、随机、混合类别或专业协议
  模型会显式返回不支持/未认证，而不会生成启发式“合格锚点”。
- 正向构造路由不执行论文数值模型。应把合法锚点交给现有哈希绑定的边界/极限/
  溢出模型审计，以核验模型行为。
- 只要任务涉及定理或公式逻辑，Lean 仍是独立的全文要求。
