# Research Guard

[English](README.md) | [简体中文](README.zh-CN.md)

Research Guard 是一个可迁移的学术科研 Skill 与 Codex 插件。它把简洁的智能体
指令与可执行 MCP 路由、Hook、哈希收据和失败关闭门禁组合起来，覆盖 idea 探索、
文献检索、实验指标、论文写作、科研作图、公式核验和终稿审计。

它不能证明全局新颖性、科学结论必然正确、论文会被录用或研究质量必然合格。
每一个 PASS 都只对已记录的来源、产物、哈希和实际执行的检查成立。

## 直接复制给 Agent 安装

```text
请从 https://github.com/dltsum/research-guard 安装 Research Guard Skill。
下载与本机平台匹配的 Release 包，用 SHA256SUMS.txt 核验；Windows 执行
scripts/install.ps1，Linux/macOS 执行 scripts/install.sh。验证传统 Skill、
Codex 插件、MCP 服务和核心 Python 运行时后，开启新会话并加载
research-guard。不要自动安装可选的 Git、TeX 或 Lean/Mathlib。某项功能需要
缺失组件时，先向我展示“复用现有环境、系统安装/安装、not_now”及下载和安装
体积，只执行我的明确选择。若选择 not_now，未执行检查必须标记为 NOT_RUN，
不能报告为 PASS。
```

Release 资产：

- Windows x64 离线模块包：
  [research-guard-windows-x64-modular.zip](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-windows-x64-modular.zip)
- Linux x64 虚拟环境包：`research-guard-linux-x64.zip`
- macOS Intel 虚拟环境包：`research-guard-macos-x64.zip`
- macOS Apple Silicon 虚拟环境包：`research-guard-macos-arm64.zip`
- 完整性文件：Windows 离线包使用 `SHA256SUMS.txt`，Linux/macOS 使用
  `SHA256SUMS-posix.txt`

Windows 包仍约 300 MB，因为它携带经审计的核心 Python 运行时。Linux/macOS
包不携带 Windows 二进制，安装器使用系统 Python 创建隔离 venv。精确依赖和
降级规则见 [REQUIREMENTS.md](REQUIREMENTS.md)。

main 分支的每个平台 CI 任务还会构建并净安装对应的精确归档，然后在
[工作流运行](https://github.com/dltsum/research-guard/actions/workflows/ci.yml)
中提供原始 ZIP，作为 3 天已验证 CI 归档。它是短期迁移证据，不能替代长期
Release 资产及其校验文件。

## 手动安装

Windows x64：

```powershell
$release = 'https://github.com/dltsum/research-guard/releases/latest/download'
Invoke-WebRequest "$release/research-guard-windows-x64-modular.zip" -OutFile research-guard.zip
Invoke-WebRequest "$release/SHA256SUMS.txt" -OutFile SHA256SUMS.txt
$expected = ((Get-Content SHA256SUMS.txt | Where-Object { $_ -match 'research-guard-windows-x64-modular.zip' }) -split '\s+')[0].ToLowerInvariant()
$actual = (Get-FileHash research-guard.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 mismatch: $actual" }
Expand-Archive research-guard.zip -DestinationPath research-guard-release
powershell -NoProfile -ExecutionPolicy Bypass -File .\research-guard-release\research-guard\scripts\install.ps1
```

Linux x64 或 macOS：

```sh
# ASSET 取 research-guard-linux-x64.zip、research-guard-macos-x64.zip
# 或 research-guard-macos-arm64.zip。
curl -fLO "https://github.com/dltsum/research-guard/releases/latest/download/$ASSET"
curl -fLO https://github.com/dltsum/research-guard/releases/latest/download/SHA256SUMS-posix.txt
grep " $ASSET$" SHA256SUMS-posix.txt | sha256sum -c -
unzip "$ASSET" -d research-guard-release
sh research-guard-release/research-guard/scripts/install.sh
```

macOS 未安装 GNU coreutils 时，用 `shasum -a 256` 替代 `sha256sum`。安装器
会逐文件核验 `RELEASE_MANIFEST.json`，全程串行、禁用 GPU，并安装到用户目录。

## 一眼看懂怎么用

| 你可以这样说 | 主能力 | 强制边界 |
|---|---|---|
| “探索这个 idea，检查是否与已有工作撞车。” | 显式领域选择、idea 探索、多来源新颖性检索 | 每条结果带 HTTPS DOI/原始记录链接；方法或领域档案一改，旧收据作废并完整重查 |
| “找文献并写 Related Work。” | 文献发现、主张—证据关系、引用审计、学术写作 | 引用必须有 DOI/原始记录链接和定位；文献身份与是否支持主张分开核验 |
| “设计实验并分析指标。” | 假设/实验注册、冻结指标方案、描述分析、约束比较 | 分析单位、估计目标、缺失、合法范围、数据切分和候选预算全部哈希绑定；最终测试集不能调参或选型 |
| “按现有 CPU、内存、磁盘、网络和时间规划任务。” | 主智能体选择的资源 DAG、串行档案、阶段检查点和续跑收据 | 宿主机清单不是进程配额；GPU 禁用；未知估算与完成状态不得伪造；只采用用户明确给出的预算 |
| “我授权你结合本地资源寻找科研方向。” | 隐私化资源盘点、受管粗测迭代、逐修订撞车核验、恰好五个选择 | 只有用户授权后启动；每项都要有正向本地粗测和严格带链接撞车收据；方法一改两类证据同时失效；智能体不得排名或选赢家 |
| “优化这些实验配置。” | 可行性约束、Pareto 前沿、可选用户加权排序 | 只比较验证集上已运行候选；权重和参考尺度由用户决定；结果仍为 `USER_SELECTION_REQUIRED` |
| “协助教育学/教育技术学研究。” | ERIC 等来源路由、方法与数据源、会议期刊发现 | 保留学生/班级/教师/学校/机构层级；写作前实时核验具体 venue/year/track/stage |
| “写作或审计这篇论文。” | paper spine、引用写作、语言、venue 证据、2–3 角色审计 | 联网事实、数字、代码、实验和证据分别核验；角色 effort 最高 `high` |
| “降低防御性、Nature 化、减少模板痕迹。” | 非防御性语言、修辞检索、翻译、自然化改写 | 不删除必要不确定性、limitations、伦理、风险、批评或负结果 |
| “核验全文公式。” | Lean、Pint、SymPy、Z3、数值/协议检查 | 五类结果分报；符号必须定义且实际使用；Lean 未运行只能报 NOT_RUN |
| “编译 LaTeX/检查顶会模板。” | 精确 venue 证据和 TeX 编译 | 静态检查不能冒充 PDF 编译通过；必须有当年具体官方说明 |
| “做统计图、向量图或架构图。” | 数据绑定的 SVG/PDF/PNG 和最终尺寸审计 | 哈希绑定源数据；检查遮挡、空间、对齐、边距、字号和对应刊物风格 |
| “按审稿意见修改/rebuttal。” | 意见台账、证据绑定修改、回复信 | 每条意见有状态和证据；不承诺未完成实验，不预测录用 |
| “主动迎合 AI 审稿人优化得分。” | 可选的主动 score-aware adaptation | 用户显式开启；同一多模型面板和量表评全部完整候选；冻结引用、数字、公式和必要披露 |
| “检查稿件是否操纵 AI 审稿人。” | 独立的鲁棒性审计 | 拦截隐藏指令和虚假 prestige；报告模型敏感性但不做得分优化 |
| “让 LLM 协助这个科研步骤。” | 原生 subagent 优先的委派协助 | 默认一个入门/经济型 subagent、低推理；不可用时由主智能体本地完成；外部 API 必须有用户/协议例外和哈希收据 |
| “为新领域找专业 Skill。” | GitHub/SkillsHub 发现、隔离、2–3 轮 SkillOpt、交叉审计 | 未通过来源、安全和准入审计前不执行远程 Skill |

论文生命周期的逐项清单见
[docs/PAPER_WRITING_CAPABILITIES.md](docs/PAPER_WRITING_CAPABILITIES.md)。

## 经授权的本地资源科研方向探索

用户明确授权“寻找方向”后，现有 `research_design` 工具启用带收据的
`direction_action` 工作流：

1. `plan` 冻结规范的隐私化 CPU、内存、磁盘和执行档案快照。资源清单不等于
   可以占用全部宿主机资源；执行仍为串行、单线程、CPU-only，GPU 禁用。
2. `register` 保存主智能体整理的 5–15 个候选，但拒绝 rank、score、prestige
   和 winner。每个候选冻结方法、证伪条件、最小实验、差异点、可行性、HTTPS
   先行工作、数值合法范围、数据角色、资源估算和 1–5 次粗测协议。
3. `activate`、`record_iteration`、`bind_collision` 分别复用规范方法注册器、
   受管复现实行器、内存门禁和撞车搜索；调用方自报“正向”或自报遥测不能通过。
4. 方法、协议、参数范围或跟踪文件一改，当前正向粗测、撞车证据和五选集合同时
   失效；旧的负向/失败尝试和报告继续作为只追加历史保存。
5. `finalize` 只接受恰好五个合格的当前修订，按中性的注册顺序展示，给出可点击
   文献链接并返回 `USER_SELECTION_REQUIRED`；智能体不能替用户选最终方向。

“正向”只表示在冻结粗测协议下重新计算得到的本地初步信号，不是确认性证据；
“不撞车”只表示在已记录的来源、查询、覆盖和日期下没有未解决撞车。详见
[docs/DIRECTION_EXPLORATION.md](docs/DIRECTION_EXPLORATION.md)。

## 实验指标分析与优化

指标能力位于现有 `research_design` 的类型化子路由，不增加顶层工具：

1. `action=status, metrics_action=plan` 冻结主/次/诊断/安全指标、方向、单位、估计目标、
   聚合、合法范围、缺失策略、优化集/最终测试集和候选预算。
2. `metrics_action=analyze` 读取项目内 UTF-8 CSV，只接受独立运行级数据；拒绝
   重复、缺失、非有限值和协议外数值，绑定数据哈希，并输出各配置汇总和明确
   标注为描述性的基线差异。冻结的最终测试集必须保存在独立封存产物中；分析器
   只要检测到该 split 的任何一行就会拒绝继续。
3. `metrics_action=optimize` 在冻结优化集应用约束，输出可行集和 Pareto 前沿。
   最终测试集不参与选择。只有用户提供权重和参考尺度后才允许标量排序。
4. 聚类、纵向、复杂抽样、参与者级、IRT 和定性数据返回
   `SPECIALIST_ANALYSIS_REQUIRED`；核心引擎不会把它们强行摊平成独立行。

## 教育学与教育技术学

二者是独立领域档案。教育学覆盖随机/准实验、多层与纵向模型、调查、心理测量
与 IRT、定性研究、设计型研究和证据综合。教育技术学额外覆盖学习分析、过程
挖掘、EDM/AIED、CSCL、HCI/可用性、知识追踪、公平、隐私、可访问性和算法
影响审计。

官方发现入口包括 [ERIC](https://eric.ed.gov/)、
[AERA](https://www.aera.net/Events-Meetings/Annual-Meeting)、
[ISLS](https://www.isls.org/)、[AIED](https://iaied.org/conferences)、
[EDM](https://educationaldatamining.org/conferences/)、
[LAK](https://www.solaresearch.org/events/lak/) 和
[EC-TEL](https://ea-tel.eu/ec-tel-conference)。方法依据包括
[IES SEER](https://nces.ed.gov/use-work/standards-excellence-education-research-seer)
和 [WWC 手册](https://ies.ed.gov/ncee/wwc/Handbooks)；公共数据入口包括
[NCES DataLab](https://nces.ed.gov/datalab/onlinecodebook/)、
[PISA](https://www.oecd.org/en/about/programmes/pisa/pisa-data.html) 与
[UNESCO UIS](https://www.uis.unesco.org/en/data)。

这些只是发现和方法入口，不是排名，也不授权系统自动照搬格式。章节、布局、
模板和叙事仍须实时核验具体 venue/year/track/stage 的官方材料。详见
[docs/EDUCATION_SUPPORT.md](docs/EDUCATION_SUPPORT.md)。

## 核心保证

- 主智能体显式选择领域、1–3 个科研模块和 2–3 个审计角色；关键词分类器和
  小模型不做这些语义决策。
- 撞车检索没有任意的整任务时限。它保存带链接的阶段结果并持续回显，只在完整
  覆盖、已保存事实阻塞或用户明确给出时间/预算/停止指令时结束。
- 所有文献与引用输出都带可点击 HTTPS 链接。
- 推荐章节名、布局、格式或叙事前，必须取得具体 venue/year/track/stage 证据。
- 公式分别报告 Lean 逻辑、Pint 量纲、SymPy 等价、Z3 可满足性和协议内数值行为。
- 科研图绑定源数据/输出哈希，并做最终尺寸视觉审计。
- limitations 和可能的伦理遗漏作为用户决策清单，不静默删除不确定性。
- 可选依赖按需询问；拒装会记录明确降级，未执行检查绝不变成 PASS。
- 需要 LLM 协助时，默认串行启用一个入门/经济型原生 subagent，推理强度为 `low`。若宿主不提供 subagent，则由主智能体本地继续，绝不静默改用 API。外部供应商例外必须由用户授权并绑定哈希；同宿主/同模型 subagent 不算独立审稿人。
- 经授权的方向探索只有在五个当前修订分别取得受管正向粗测和严格带链接撞车
  收据后，才会返回恰好五个未排名选项；最终选择始终属于用户。

## 资源与跨平台契约

| 边界 | 限制 |
|---|---:|
| 支持平台 | Windows x64；Linux x64；macOS x64/arm64 |
| 任务所有进程的总 RSS/工作集 | 512 MiB |
| 普通 worker / orchestrator | 384 MiB / 128 MiB |
| 安装 worker / orchestrator | 448 MiB / 64 MiB |
| Lean worker / orchestrator | 464 MiB / 48 MiB |
| 并行 worker | 1 |
| GPU | 禁用 |
| 启动/运行期最低空闲内存 | 768 MiB / 512 MiB |

Windows 使用 Job Object；Linux/macOS 使用独立进程组和 `psutil` 进程树遥测。
越界时只终止本任务拥有的进程树。数值运行时固定为单线程。

## 开发

```sh
python -m pip install --disable-pip-version-check -r requirements-dev.txt
python -X utf8 scripts/validate_repository.py
python -m unittest tests.test_experiment_metrics tests.test_education_profiles -v
python -X utf8 scripts/build_modular_package.py --platform linux-x64 --output dist/research-guard-linux-x64.zip
```

源码仓库不包含大型审计 payload、缓存 venue 页面、模板和论文 PDF，因此源码
checkout 不是 Windows 离线 Release 安装包。

## 目录

```text
.codex-plugin/   插件清单
assets/          来源、学科、依赖和 venue 注册表
hooks/           显式选择与方法变更的确定性后备门禁
scripts/         MCP 服务、门禁、安装器、分析器和打包器
skills/          渐进披露的聚焦 Skills
tests/           确定性回归与契约测试
docs/            功能、架构、来源和领域文档
```

项目保持 17 个顶层 MCP 工具；新增能力进入其规范主责工具的类型化子路由，避免
触发冲突和接口膨胀。

## 文档

- [依赖与安装](REQUIREMENTS.md)
- [架构](docs/ARCHITECTURE.md)
- [跨学科支持](docs/DISCIPLINE_SUPPORT.md)
- [教育学/教育技术学支持](docs/EDUCATION_SUPPORT.md)
- [论文写作与审计全清单](docs/PAPER_WRITING_CAPABILITIES.md)
- [时间与持续执行策略](docs/TIME_AND_CONTINUATION_POLICY.md)
- [原生 subagent 优先的 LLM 委派](docs/SUBAGENT_DELEGATION.md)
- [资源感知任务规划](docs/RESOURCE_AWARE_TASK_PLANNING.md)
- [经授权的本地资源方向探索](docs/DIRECTION_EXPLORATION.md)
- [跨平台迁移保障](docs/provenance/P21_CI_MIGRATION_ASSURANCE.md)
- [第三方声明](THIRD_PARTY_NOTICES.md)
- [安全策略](SECURITY.md)

## 资源感知任务规划

你可以直接说：“按照我当前的 CPU、内存、磁盘、网络和时间预算规划这项科研任务。”
该能力位于现有 `research_design` 的类型化子路由，不增加顶层工具：

1. `resource_plan_action=inventory` 只读采集经过隐私处理的 CPU、内存、磁盘、
   资源策略和执行档案；不把宿主机资源误写为当前进程可用配额，也不探测网络或宣称 GPU 可用。
2. `resource_plan_action=plan` 校验由主智能体选择的任务 DAG、依赖、预期产物、
   资源档案、可选依赖，以及用户明确给出的下载、磁盘、时间或费用预算。
3. `resource_plan_action=execute` 只执行绑定到全新、用户选定复现计划的下一个
   `managed_standard` 任务。命令仍由既有科研完整性执行器拥有；规划器自动记录真实内存、
   时长、产物、计划哈希和执行哈希。
4. `resource_plan_action=record` 保存由其他模块执行的阶段状态和产物哈希；调用方自报的
   遥测不能完成已绑定的复现任务。没有最终收据时记为 `UNKNOWN`，不能据此自动重试。
5. `status` 只给出下一个可执行任务和事实阻塞；`verify` 检测策略、状态、转换记录、
   产物和关联执行凭据漂移。

简单的一次性回答不需要启动该规划器。多阶段任务保持单进程、单数值线程和 GPU 禁用；
缺失估算必须保持未知，整项任务只有在用户明确给出时间预算时才有截止边界。
`UNKNOWN` 必须先检查持久化收据才能解除或重放。主智能体负责选择每个任务的语义和档案，
不使用关键词分类器或小模型替代判断。受管绑定仅允许离线任务；由于尚未完整测量进程树
磁盘写入，存在用户磁盘写入预算时会拒绝执行，绝不拿产物大小冒充磁盘 I/O。

## 许可证

Research Guard 使用 [MIT License](LICENSE)。所含或引用的第三方组件保留各自
许可证，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
