# 可直接交给智能体的安装与验收提示词

将下面整段复制到一个新会话。在“本次选择”填写需要的组；留空时只列选项，不安装。各组共享必要核心文件，未选择的作图、写作、数学、CiteSpace 或 Skill 实验代码不会一起复制。

```text
请从 https://github.com/dltsum/research-guard 下载源码并安装 Research Guard。
本次选择：[填写 core / literature / research / experiments / writing / figures / formal / skill-lab / citespace，可逗号多选]
安装目录：[填写一个新的绝对路径]
研究输入：[填写自然语言需求，以及论文/实验记录/CSV/参考图等实际文件]

先读取根 SKILL.md 和 assets/feature-components.json，运行
python -I -X utf8 scripts/component_install.py --list。
解释以下组选项、自动带入的组、Python 依赖和外部能力，再按本次选择操作；
未填写选择时请列出选项供我选择，不默认全部安装。

core：指令契约、证据状态、主智能体选路、资源及依赖信息；标准库即可。
literature：来源目录、查新、出版信息、引用、文本证据与研究台账；带入 core。
research：候选想法、假设、实验和研究策略；带入 literature。
experiments：指标分析、方向迭代与资源任务计划；带入 research。
writing：学术语言、参考论文逻辑写作、审稿与会议信息；带入 literature；pypdf。
figures：数据图、参考图风格契约、逐像素比较及三角色审计；带入 core；
         matplotlib、numpy、Pillow、pypdf。ImageGen 使用宿主真实图像能力。
formal：单文件公式契约、Pint/SymPy/Z3 和数值构造核验；带入 core；
        pint、sympy、z3-solver。Lean 是独立外部运行时。
skill-lab：专业 Skill 隔离、发现、可迁移性、组合与演化实验；带入 core；
          含优化执行的工作另需 Optuna/真实模型能力，缺少时明确说明。
citespace：知识台账、本地文献网络和 CiteSpace 伴随工作流；带入 literature；
          networkx。本地网络分析不等于 CiteSpace Java 引擎运行；
          还需要可合法运行的历史免费引擎、相应 Java 和原伴随 MCP。
          不安装最新收费版，不绕过旧版许可或过期限制。

用 --dry-run 输出真实文件和精确版本依赖。确认本次选择后执行：
python -I -X utf8 scripts/component_install.py --components <选择> --target <新目录> --create-venv
若本次选择需要第三方 Python 包，并且我已允许安装最小环境，增加
--install-python-deps；该选项只安装所选组需要的精确版本到该目录的 .venv。
不需要 pip 的组不创建带 pip 的环境，也不借用宿主 site-packages。
缺少 Python 时先说明最低 Python 3.11 和平台能力；不得下载整套科研运行时冒充最小安装。

安装后运行 --verify，保存 COMPONENT_INSTALL.json、.mcp.json、精确命令与完整返回。
从所选目录的 .mcp.json 启动真实 stdio MCP，执行 initialize、tools/list、tools/call。
不得只展示界面或只读源代码声称功能可用。先列出本次已安装路由；
未安装功能应返回 COMPONENT_NOT_INSTALLED，不应偷偷下载或继续调用。
传统 Skill 读取所选目录的 SKILL.md；Codex/Claude Code 等平台按其实际
支持的 Skill/MCP 配置载入。若当前宿主不能热加载，允许用已记录的 stdio
客户端真实调用，并明确写清接口类型，不能声称已完成宿主原生挂载。

请用至少两种实际输入完成研究任务，例如论文节选与实验 CSV。
每个展示功能保留自然语言需求→主智能体选择→实际工具参数与返回→
产物→另一智能体反馈→修复与复测。区分正常成功、正确拒绝和未运行。
网络检索保留下载时间、原始响应和来源；离线历史重放只能证明已有证据可重放，
不能刷新实时查新、引用量或收录状态。

额外环境按实际需求最小安装：基础 Lean 样例用显式 lean-basic profile，
只验证 Init 范围，不能称 Mathlib 已安装；TeX 用已登记可用编译器和官方 paper kit；
CiteSpace 只接受真实旧版引擎运行输出。外部服务不可用时保留原始错误和 NOT_RUN，
继续完成可独立运行的项目并列出未满足项，不能用手写仿真替代原引擎。

作图时遵循已安装 academic-figure-guard：保留用户信息、参考图风格与论文适配性，
多轮生成，每轮信息完整度/风格/细节三个不同智能体审计；按契约交付七类文件。
写作时遵循 reference-writing-contract：先读实验记录，核对2025年以来候选的
期刊分区与引用或CCF/奖项/oral资格，锁定已有大纲与原文逻辑、表图功能对应，
三个不同智能体审计逻辑/防御性写作/科学性；交付七类文件与可审查匹配记录。
不得为凑齐实验、表图、资格、像素审计或 Lean 证明而编造材料。

最后交付 Skill 本体（SKILL.md、按需 references/scripts/assets）、README、
两类输入的原始测试记录、平台与依赖说明、运行命令、结果判据及未满足项。
只把当前实际跑过且证据完整的功能列为演示成功。
```

精确版本以 `assets/feature-components.json` 为准。安装器不修改全局 Python、PATH、宿主凭据或已有安装；同来源同选择重复执行返回 `UNCHANGED`。改变选择、来源或依赖安装方式使用新目录。`--verify` 检查回执、文件、解释器和已安装的顶层依赖版本；没有运行科学任务时，不能把安装校验当作研究结论验证。
