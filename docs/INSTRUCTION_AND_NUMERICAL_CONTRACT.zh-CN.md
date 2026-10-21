<!-- research-guard-doc-pair: instruction-and-numerical | revision: 2026-10-22.1 -->
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

需要追踪复杂任务时，可选用 `instruction_action=register` 保存请求原文、
任务 ID、要求、依赖和预期交付；普通任务无需先登记合同。

`record` 保存实际进度、文件路径、JSON 状态、来源链接或检查说明。无需文件摘要、
状态链或签名收据；普通文件编辑不会让已完成工作失效。JSON 执行结果仍需与所声称
的状态一致，未完成的步骤不能当作完成。

用户明确豁免某项要求时，用 `waive` 保存决定与理由，无需用户消息的校验码。
`status` 显示保存的进度，`verify` 可生成当前检查报告。Stop Hook 只作提醒，
不以登记、摘要或收据缺失阻断会话。

## 正向数值审计

先使用 `audit_features.constructive_numerical=true` 规划论文审计，并选择
`methodology_statistics` 或 `formal_math_lean`，然后调用
`numerical_action=construct`。一般审计不要求固定角色数量、特定选择者标签或
达到最低字数的理由。

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
| `PASS` | 已记录的要求完成 | 允许 |
| `ACTION_REQUIRED` | 尚有工作未完成 | 仅提醒，不拦截 |
| `USER_DECISION_REQUIRED` | 尚需用户决定 | 仅提醒，不拦截 |
| `BLOCKED` | 禁止；只能事实性移交阻塞 | 允许移交，但绝不转换为 PASS |
| `NOT_CERTIFIED` | 禁止 | 数值结果保持未解决 |

指令事件保存实际进度，不建立摘要链；Stop Hook 不重新扫描全部文件。
正向数值记录保存完整输入 manifest、求解器输出和进程资源遥测，无需收据哈希。
使用同一 audit ID 提交更新后的约束，会执行更新后的 manifest 并替换该审计的
已保存结果。

## 边界与降级

- 指令台账无法自动得知所有隐含验收条件。主智能体必须拆解完整请求；代码负责
  阻止已经登记的项目被静默丢弃。
- HTTPS 证据项只证明登记了一个定位；仍需由相应文献/引用路由核验身份和主张支持。
- 人工检查是声明式人类/智能体证据，不是独立可执行证明。
- 认证区间当前只覆盖线性有理约束。非线性、超越函数、随机、混合类别或专业协议
  模型会显式返回不支持/未认证，而不会生成启发式“合格锚点”。
- 正向构造路由不执行论文数值模型。应把合法锚点交给边界/极限/溢出模型审计，
  以核验当前模型行为。提供模型文件路径即可，无需模型校验码。
- 按实际问题选择数学通道。声称 Lean 通过时，必须使用可用且兼容的运行环境
  实际编译提供的文件，无需固定版本登记或收据链。读取历史状态不会编译修改后
  的源文件；检查修改时直接重跑 `lean_check`，并如实报告缺少环境或编译失败。
  量纲检查需要单位引擎；普通写作与独立 Lean 检查不因此强制安装 Pint。
