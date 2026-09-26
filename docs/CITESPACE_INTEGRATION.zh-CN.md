<!-- research-guard-doc-pair: citespace-integration | revision: 2026-09-26.4 -->
# CiteSpace 集成

当用户希望探索某个领域的前沿热点、技术爆发点或合作结构时，Research Guard 与配套的 **citespace-mcp** 插件协同工作。Research Guard 提供范围分析、证据纪律与报告能力；citespace-mcp 驱动本机 CiteSpace 应用并返回真实图谱。双方都不重新实现对方的能力，也绝不会把虚构图谱当作 CiteSpace 结果呈现。

## 配套插件提供什么

- 一个 MCP server(`citespace`)，暴露 `citespace_*` 工具：通用启动/控制工具，以及 `citespace_prepare/activate/configure/start/poll/analyze` 研究工作流工具、证据回读、来源登记与报告撰写。
- 一个内置的窄接口 Java Access Bridge 适配器，在不使用浏览器自动化的前提下完成已验证的 CiteSpace Basic 启动流程。
- 一个描述完整研究循环的 `citespace-research` 技能。Research Guard 的 `citespace-frontier` 技能在其之上增加了 Research Guard 范围分析阶段和"保持图谱展示不关闭"规则。

## 前置条件

- 本机 CiteSpace 安装（插件已验证的引擎是 Windows 上的 CiteSpace 6.4.R2 Basic）以及插件包声明的配套 Java 运行时。
- 已为你的 harness 安装 citespace-mcp 插件（形如 `citespace-mcp-workflow-<版本>_codex.<日期>.zip` 的发布 ZIP)。
- 文献语料：UTF-8 编码的 WoS 全记录 `.txt` 导出。如果没有合适导出，流程会在产出精确检索策略与所需导出字段后停止——绝不伪造被引参考文献数据。

## 与 Research Guard 并排安装

两个插件都是普通 MCP 插件，可以共存；各 harness 分别加载它们：

- **Claude Code**：在 Research Guard 插件之外再执行 `claude --plugin-dir /path/to/citespace-mcp`，或从个人 marketplace 安装两者。
- **Codex**：通过 Codex 的插件安装流程安装发布 ZIP;Research Guard 仍由它自己的安装器安装。
- **Kimi Code CLI**:`/plugins install /path/to/citespace-mcp`（该包携带 Codex 格式清单；Kimi 读取同一 `.mcp.json` 与 `skills/` 布局）。

安装后确认两个 server 都能应答：Research Guard 工具（`research_design` 等）与 `citespace_*` 工具必须对 agent 同时可见，然后才能开始前沿分析循环。

## 前沿分析循环（agent 侧）

1. 用 Research Guard 确定范围：重述问题，用前沿组件分析可选的论文寻找范围，并按研究目的选择节点类型（Reference = 共被引知识基础，Keyword = 主题/爆发点，Author/Institution/Country = 合作网络）。
2. 诚实地建立语料：`citespace_search_literature` 与 Web 搜索用于发现与来源核查；真实网络使用真实的 WoS 导出。
3. 按顺序驱动研究工作流工具，保留 `run_id`。
4. 先验证（`citespace_analyze_graph` → `citespace_capture_research_view` → `citespace_verify_native_counts`）再解读；计数不一致必须在报告中显著标注。
5. 用 `citespace_read_evidence` / `citespace_graph_neighborhood` 为每个论断提供依据，登记外部来源，撰写带证据索引的报告。
6. 交付产物（GraphML、节点 CSV、报告、run_id),**并保持原生可视化窗口为用户打开**。

## 保持图谱展示不关闭

`citespace-frontier` 技能禁止在工作完成时关闭图谱展示：不调用 `citespace_finish_research_view`、不关窗口、截图后不杀应用。`citespace_capture_research_view` 始终使用 `close_after=false`。何时关闭窗口由用户决定。如果必须为新运行拆除旧运行，那只发生在 `citespace_activate_research` 内部，它绝不会杀死正在进行的分析。

## 失败处理

无法识别的对话框、缺失的 WoS 数据、Basic 节点上限失败、原生与导出计数不一致，都会阻断对应步骤并保留状态。恢复从 `citespace_research_state(run_id)` 开始；`citespace_launch` 是通用启动恢复入口。已完成运行的参数或语料绝不会被悄悄更改。

## 已验证功能运行（2026-09-26）

通过真实 MCP stdio 传输对真实 CiteSpace 6.4.R2 Basic 端到端验证（run_id `20260926T162748_6792685a`、`20260926T163906_6ac84fda`）：列出 26 个工具声明（回执 `00_tools_list.json`）；01-LA WoS 语料（1019 条合格记录，2020-2025，Keyword，k=4）导出 94 节点 / 485 边 GraphML，原生界面显示 N=94、E=513——该差异已通过 `citespace_verify_native_counts` 登记，导出图的密度/度数仅描述导出图。截图使用 `close_after=false`，图谱窗口由独立常驻会话保持打开供用户查看（经验证：随临时 shell 退出的 MCP 客户端会带走应用，面向用户的展示必须由活得比测试更久的会话持有——且第一个 detached 持有会话本身约 17 分钟后也静默死亡，因此会话寿命有限，交付时必须核验窗口仍存活，不得假定）。分步回执：CiteSpace 任务工作区 `plugin_workflow_validation/functional_20260926/`。

多维度扩展（2026-09-26 晚）：在同一语料上追加两次真实运行展示更丰富的分析维度——Reference 共被引（run `20260926T192058_3d44cf40`，128 节点 / 429 条导出边）与 Keyword（run `20260926T192212_8a6eb60d`，94 节点 / 485 条导出边）——回执 `showcase_reference.json` / `showcase_keyword.json`。经随附 JAB 桥验证的显示窗口自动化要点：合并显示窗口标题为 `CiteSpace: Display Merged - (c) ...`（须前缀匹配，对短前缀做精确匹配会失败）；其工具栏暴露 60 个可访问元素，含命名按钮 `Show/Hide Citation/Frequency Burst`，点击可无误往返——但若该 run 从未执行 burstness 检测，切换不产生任何像素变化，突发环叠加须先在 CiteSpace 中运行突发检测。截图前须将窗口置前（`ShowWindow(SW_RESTORE)` + `SetForegroundWindow`）再抓取其矩形区域，否则抓到的是最上层窗口。
