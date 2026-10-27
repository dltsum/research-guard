# CiteSpace 科研工作流（Codex 插件）

本地交付更新（2026-10-22）：本包另带未修改的6.4.R2软件和配套Java。
安装位置可通过CITESPACE_INSTALL_DIR指定。首次启动的条款、邮箱及账号验证
交给用户完成，默认启动流程不再自动提交测试邮箱；下文旧版自动启动描述为历史记录。
`.mcp.json` 不再绑定原电脑路径；需使用已有且安装了 requirements.txt 依赖的 Python。
宿主不支持展开 PLUGIN_ROOT 时，用上层 configure_citespace.py 生成解压后的本机配置，
再由用户自行导入。生成配置不会注册账号或替宿主安装插件。

**自然语言研究需求 → 文献调研 → 数据审计 → 真实 CiteSpace 制图 → 图谱和原文回读 → 分析报告。**

需求理解和解释由 Codex 完成；网络构建由本机 CiteSpace 完成。
插件同时提供自动触发的 `citespace-research` skill 和 MCP 接口。

## 直接使用

安装后新开一个 Codex 会话，例如说：

> 用 CiteSpace 分析这个文件夹里的 WoS 数据，关注自我调节学习和反馈。
> 先调研相关概念，做关键词共现与文献共被引，回到代表性论文解释图谱，给我报告。

也可以给其他主题、目录、年份和分析问题，不再固定为 `01-LA`。
在同一个持续会话内串行完成；不要在分析运行中重装/停掉 MCP。

本机安装命令：`codex plugin add citespace-mcp@personal`。

## 新工作流接口

| 阶段 | 接口 | 实际功能 |
|---|---|---|
| 调研 | `citespace_search_literature` | Crossref 检索/精确 DOI 核对，保存检索回执；可与 Codex Web 搜索配合 |
| 审计 | `citespace_prepare_research` | 检查 WoS 字段、年份、重复和冲突；保存哈希并创建独立运行 |
| 项目 | `citespace_activate_research` | 备份原生项目列表、保留旧项目，正常重启空闲软件并处理已验证启动弹窗 |
| 配置 | `citespace_configure_research` | 设置并回读项目路径、年份、节点类型、k、链接与剪枝 |
| 运行 | `citespace_start_research` / `citespace_poll_research` | GO 前落盘；匹配完成对话框；请求原生导出并验证稳定 GraphML |
| 回读 | `citespace_analyze_graph` | 原生节点/边/频次，明确标记的派生结构指标和节点 CSV |
| 关系 | `citespace_graph_neighborhood` | 读取指定节点的真实邻接边、权重和邻居；不只看排行榜 |
| 原文 | `citespace_read_evidence` | 分页读取源记录；`doi:10.x/...` 精确找到论文而不是只找到引用它的文章 |
| 资料 | `citespace_record_research_sources` | 追加后续细读资料，分配稳定证据 ID |
| 附件 | `citespace_read_research_artifact` | 有界读取原生文本输出，供核实突现结果等 |
| 原生图 | `citespace_capture_research_view` | 仅捕获属于该运行的 CiteSpace 结果窗口，不截其他应用 |
| 一致性 | `citespace_verify_native_counts` | Codex 读图后核对原生 N/E 与 GraphML，保留不一致记录 |
| 收尾 | `citespace_finish_research_view` | 保存截图，正常关闭已完成图窗和对应 Control Panel |
| 报告 | `citespace_write_research_report` | 生成带实际指标、原文证据索引的 Markdown、独立 HTML、SVG |
| 恢复 | `citespace_research_state` | 读取持久状态；提交结果未知时不盲目重放 |

原来的十个低层接口继续保留兼容；其中标明 fixed/01-LA 的接口仍只用于旧项目。
通用分析应使用上述研究工作流。

## 已验证及重要边界

- 在真实 6.4.R2 Basic 中完成 Reference 与 Keyword 两类分析，不是 mock。
- 第一组 2016—2026：1643 条原记录，按年份纳入 1557 条；共被引导出 267 节点/980 边。
- 关键词原生界面为 152 节点/1059 边，自动 GraphML 为 152 节点/1000 边。
  **此差异已由截图核对并写入报告。导出图的密度/度数不能冒充完整原生图指标。**
  尚未把此版本的完整原生网络导出问题修复为一个经过验收的自动接口。
- 历史版本曾测试自动推进本地邮箱界面；本交付的默认启动流程已取消该行为，
  许可、邮箱及账号验证必须由用户本人完成。底层兼容接口不得用于代办这些操作。
- 15 项本地测试覆盖重复冲突、缺字段、损坏记录、坏 GraphML、路径越界、
  已提交运行拒绝重放、缺失指标、报告证据 ID 等。
- 最终同一个 MCP 会话连续完成两组 2020—2025 / k=4 的真实分析：
  Reference 导出 128 节点/429 边，Keyword 导出 94 节点/485 边；
  包括自动收起上一张图、回收已退出的自有 JVM、再次启动并处理弹窗。
- 自动导入目前支持 UTF-8 WoS 全记录文本。没有合法可用的文献数据时，会说明缺失内容；
  不把零散搜索结果伪装成完整引文语料，也不自动访问需付费权限的数据库。
- Basic 的实际节点容量限制仍保留。参数需调整时另开运行并保留原因与旧结果。
- 聚类/时间线的界面自动操作尚不在本版本验收范围。Q、轮廓值、中心性和突现强度
  只有在相应真实产物中核实后才可报告；配置默认零值不算计算结果。
- SVG 用真实导出边重绘，明确标为环形布局，不声称是原生聚类图；原生截图另存。
- 证据 ID 校验保证可追溯，不代替 Codex 对论据与结论关系的审查。

### 2026-10-21 公开元数据兼容性修复

源码工作流准备文件使用 `FN ISI Export Format` 表示交换语法，不表示数据来自 WoS。
输入来源、原文件头和转换说明另外保存在审计记录中；不得把 OpenAlex 元数据称为
WoS 原厂导出。其他格式仍须另建可追溯、独立验证的转换器，不在通用导入器中猜字段。

本次公开限定示例发现：tag 解析器通过并不保证本机原生扫描成功。仅修改文件头的
对照仍失败；在另存真实 DT、明确缺失 SO 的空结构标记并采用已验证字段顺序后，
同三条记录获得原生 Qualified Records=3、N=80/E=202。原数据与失败对照均保留，
不把这个组合修复说成已分离验证的唯一原因。正式77篇图的结果以各自运行回执为准。

原生窗口捕获已加入有界、可恢复的线程 DPI awareness，避免高缩放屏幕截图被裁切。
不修改系统 DPI、不截其他应用。上述修改位于源码目录；**不代表已安装插件缓存已更新**。

## 运行目录与恢复

`CITESPACE_TASK_ROOT/workflow_runs/<run_id>/` 包含：

- `manifest.json`、`events.jsonl`：需求、参数、状态、动作记录。
- `data_audit.json`、`data/`、`records.jsonl`：来源哈希、纳排、隔离输入及原文索引。
- `verified_settings.json`、`completion_dialog.json`：实际界面读回证据。
- `project/`：CiteSpace 原生输出；旧项目不被覆盖。
- `graph_parsed.json`、`graph_summary.json`、`nodes.csv`：结构化回读。
- `sources.json`、`reports/<version>/`：调研出处和版本化报告。

若状态是 `submitted` 或 `export_requested`，先轮询/核对产物，不重复 GO。
空闲软件、非空目录或命令返回成功，都不能单独证明完成。

## 本机绑定与依赖

Windows 安装：`C:\Program Files (x86)\CiteSpace`。
`.mcp.json` 复用现有隔离 Python 环境；`CITESPACE_TASK_ROOT` 是工作流存储根目录，
不是只允许那个主题的数据目录。移到其他电脑需调整 Python/存储路径及 CiteSpace 安装，
安装 `requirements.txt`，并配置项目内 JAB marker。当前压缩包是本机插件包，
不含 CiteSpace 软件、虚拟环境、文献数据或账号凭据。

依赖 `mcp==2.2.0`、`pyjab==1.1.7`（及其 Pillow/pywin32 传递依赖）。
pyjab 使用 GPL-2；包中不再分发其第三方源码/二进制。
桌面交互使用 Java Access Bridge；启动邮箱/确认直接通过本机 Swing EDT 操作控件，
不依赖前台焦点，不发送键盘输入，不使用浏览器自动化。
切换项目先关闭已完成图窗并执行 File > Exit；若 Java Access Bridge 留下后台 JVM，
只回收本工具创建、已核对空闲且所有 CiteSpace 窗口均已退出的那个子进程。
公开检索只发送检索词/DOI，不上传整个本地语料库。

为解决原捆绑运行时无法载入 `instrument.dll` 的问题，本机已另备经过 SHA-256
核对的 Temurin **22.0.1+8 JRE**，与原应用的 Java 22.0.1 版本对应。
`CITESPACE_JAVA` 指向该运行时，直接启动**原安装目录中未修改的 CiteSpace-6.4.2.jar**。
没有修改 CiteSpace 二进制、授权检查或系统 Java；堆上限设为 1024 MiB，串行运行。
`bridge/startup-agent.jar` 是随插件提供的自编译小型控件适配器，源码一并提供，
只接受已验证的启动表单填写与确认两种动作。构建和运行时来源见 `bridge/README.md`。

官方说明：[CiteSpace FAQ](https://citespace.podia.com/faq)。
本机行为以保存的实测证据为准，不把新版网页功能误当成 6.4 已有能力。
