# 可直接交给智能体的安装与使用提示词

选择所需组件即可；可在同一安装目录更新，无需提供任何哈希、指纹或签名。

```text
请从 https://github.com/dltsum/research-guard 下载源码，按需安装 Research Guard。
本次选择：[core / literature / research / experiments / writing / figures / formal / skill-lab / citespace，可多选]
安装目录：[新的安装路径，或已有 Research Guard 安装目录]
研究输入：[实际需求，以及论文、实验记录、CSV 或参考图等文件]

读取 SKILL.md 和 assets/feature-components.json，然后运行：
python -I -X utf8 scripts/component_install.py --list
未填写选择时只列出选项，不默认全部安装。

core：MCP、指令、研究状态、资源和依赖信息；标准库即可。
literature：文献、查新、出版信息、引用、文本证据和台账；带入 core。
research：候选想法、假设、研究和实验策略；带入 literature。
experiments：指标、统计、CPU复现和资源任务计划；带入 research。
writing：学术语言、参考论文逻辑写作、审稿和会议信息；带入 literature；pypdf。
figures：数据图、参考风格作图和图像审阅；带入 core；matplotlib、numpy、Pillow、pypdf。
formal：量纲、代数、约束和数值核验；带入 core；Pint、SymPy、Z3。
skill-lab：专业 Skill 发现、迁移、组合和实验；带入 core；标准库即可。
citespace：知识台账、文献网络和 CiteSpace 伴随工作流；带入 literature；networkx。
Lean、TeX、Java、CiteSpace 和宿主图像/模型能力按实际任务单独使用，选组不会下载它们。

用 --dry-run 查看计划，然后执行：
python -I -X utf8 scripts/component_install.py --components <选择> --target <安装目录>
需要安装第三方包时加 --install-python-deps，只安装所选组的依赖到该目录的 .venv。
已有可用 Python 环境可以直接使用，或通过 --python <解释器> 指定。
仅需标准库的独立环境时加 --create-venv；它不安装 pip。
最低 Python 为 3.11。以 pip 实际安装和模块实际导入结果判断依赖是否可用。

更新源码、改变组件或补装依赖时，在同一目录重跑安装命令即可。
安装器更新自己管理的源码；保留额外用户文件，不递归清空目录或修改全局 Python。
中断后可在同目录重试。不要向无关的非空目录覆盖安装。
COMPONENT_INSTALL.json 和 .mcp.json 是普通配置；无需文件摘要、解释器摘要或回执签名。
启动和日常功能调用不进行全目录或环境锁定核验，修改本地文件后可直接继续使用。
只有排障时才运行一次可选诊断：
python -I -X utf8 scripts/component_install.py --verify --target <安装目录>
诊断只检查文件存在、解释器可用和依赖能否导入，不要求版本完全相等。

从安装目录的 .mcp.json 启动真实 stdio MCP，执行 initialize、tools/list 和当前任务的
tools/call。未选功能应说明 COMPONENT_NOT_INSTALLED，不自动下载其他组。
传统 Skill 读取安装目录的 SKILL.md；宿主支持 Skill/MCP 时按其实际配置载入。
已有 TeX、Git、Lean 项目直接使用，无需先登记或切到某个固定 Lean/Mathlib 版本。
缺少依赖时，只补装任务所需的最小环境。CiteSpace 只用合法可运行的历史免费版本；
找不到时明确跳过，不能把本地图分析冒充 Java 引擎结果。

需要逐功能交互验收时，主会话一次给执行智能体一句当前请求，安装作为第一条。
执行智能体返回真实参数、原始结果和产物后等待；主会话读取结果、给反馈，再问下一条。
不将整项测试托管给另一个 session。发现 bug 就修复、推送、更新安装，以原句重测。
保留原始失败、反馈、修复和重测，不强制生成哈希清单或重复审计回执。
使用至少两类实际输入完成样例；功能调用成功不替代研究结论正确。

作图遵循 academic-figure-guard：阅读论文、保留用户要求的信息、匹配参考图风格，
按用户要求完成多轮三角色审阅和七类交付。不要添加无关的安装或哈希门禁。
写作遵循 reference-writing-contract：阅读实验记录、核对参考论文资格，保持已有大纲和
参考行文逻辑、表图功能对应，完成逻辑/防御性写作/科学性三角色审阅及约定文件。
实际缺失的实验、资格、图表或证明应列明，不得编造以凑齐交付。

交付可使用的 Skill、运行说明、真实输入/结果/交互记录和未完成项。
```
