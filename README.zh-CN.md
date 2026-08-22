<!-- research-guard-doc-pair: readme | revision: 2026-08-23.3 -->
# Research Guard

[English](README.md) | [简体中文](README.zh-CN.md)

![Research Guard 证据生命周期：idea、文献、方法门禁、分析与完成审计的论文](assets/readme/research-guard-evidence-lifecycle.png)

Research Guard 是一个可迁移的学术科研 Skill 与 Codex 插件。它用可执行 MCP
路由、Hook、哈希收据和失败关闭门禁，覆盖从 idea 探索、文献检索到实验指标、
论文写作、科研作图、公式核验、审稿和发布的完整路径。

它**不能**证明全局新颖性、科学结论必然正确、论文会被录用或研究质量必然合格。
每一个 PASS 都只对已记录的来源、产物、哈希和实际执行的检查成立。

## 从这里开始

| 我想要…… | 从这里开始 |
|---|---|
| 让 Agent 自动安装并完整核验 | 把下面的请求原样复制给 Agent |
| 自己安装 | 使用下方带校验和的手动命令 |
| 安装前先判断是否适合 | 查看“选择能力”和对应文档 |

### 直接复制给 Agent 安装

```text
请从 https://github.com/dltsum/research-guard 安装 Research Guard Skill。
下载与本机平台匹配的 Release 包，对照发布的校验文件核验；Windows 执行
scripts/install.ps1，Linux/macOS 执行 scripts/install.sh。验证传统 Skill、
Codex 插件、MCP 服务、Hook 和核心 Python 运行时后，提醒我开启新会话并加载
research-guard。不要自动安装可选的 Git、TeX 或 Lean/Mathlib。某项请求需要
缺失组件时，先展示 reuse-existing、install-system/install 和 not_now，以及
下载体积和安装后体积；只执行我的明确选择。若我选择 not_now，未执行检查必须
报告为 NOT_RUN，绝不能报告为 PASS。
```

| 平台 | Release 包 |
|---|---|
| Windows x64，内含经审计 Python 运行时 | [research-guard-windows-x64-modular.zip](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-windows-x64-modular.zip) |
| Linux x64，隔离 venv | [research-guard-linux-x64.zip](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-linux-x64.zip) |
| macOS Intel，隔离 venv | [research-guard-macos-x64.zip](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-macos-x64.zip) |
| macOS Apple Silicon，隔离 venv | [research-guard-macos-arm64.zip](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-macos-arm64.zip) |
| 完整性记录 | [SHA256SUMS.txt](https://github.com/dltsum/research-guard/releases/latest/download/SHA256SUMS.txt) · [SHA256SUMS-posix.txt](https://github.com/dltsum/research-guard/releases/latest/download/SHA256SUMS-posix.txt) |
| 可选本机浏览器 UI，支持全部平台 | [research-guard-ui-addon.zip](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-ui-addon.zip) · [SHA256SUMS-ui.txt](https://github.com/dltsum/research-guard/releases/latest/download/SHA256SUMS-ui.txt) |

Windows 包仍约 300 MB，因为它携带经审计的核心运行时。Linux 与 macOS 使用
受支持的系统 Python 创建隔离 venv。精确的 Python/非 Python 依赖、下载体积、
安装后体积、复用规则和真实降级行为见 [REQUIREMENTS.md](REQUIREMENTS.md)。
可视化 UI 是独立的小型附加包，绝不会进入核心/最小包。

首次加载时，Agent 应当：

1. 展示可用能力组和当前可复用的依赖；
2. 只有用户请求的能力确实需要某个缺失组件时才询问；
3. 可以降级完成时保留任务，但必须明确命名降级，所有省略的检查保持
   `NOT_RUN`。

### 手动安装并核验校验和

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

macOS 未安装 GNU coreutils 时，用 `shasum -a 256` 替代 `sha256sum`。每个安装器
都逐文件核验 `RELEASE_MANIFEST.json`，全程串行、禁用 GPU，并安装到用户目录。
main 分支的每个平台 CI 任务还会构建并净安装对应归档，然后在
[CI 工作流](https://github.com/dltsum/research-guard/actions/workflows/ci.yml)
中提供 3 天已验证 CI 归档。

## 约束链如何工作

首页图对应插件实际执行的五阶段契约：

多步骤请求第一次修改项目前，主智能体先把完整请求拆成原子要求，并登记验收条件、
依赖、必需证据和禁止替代项。追加式台账会在任何强制项待完成、证据变化或缺乏支持
时拦截过早 Stop/完成声明；它不替代主智能体的语义判断。

1. **界定 idea。** 主智能体显式选择领域和少量真正相关的模块；关键词分类器和
   小型路由模型不替代这一语义选择。
2. **建立证据地图。** 文献路由查询对应的公共与已注册学术来源，保存定位信息，
   并输出可点击的 HTTPS DOI 或原始记录链接。
3. **冻结并保护方法。** 方法、领域档案、查询计划和跟踪产物全部绑定哈希。任何
   实质方法/档案修改都会使旧收据失效，并强制完整重跑撞车检索。
4. **执行并核验。** 实验、指标、代码、公式、数字和图片使用相互独立的可执行
   检查，并明确资源与协议边界。
5. **审计论文。** 主智能体每次只选择 2–3 个相关审计角色，effort 最高为
   `high`，并分别报告事实、主张、limitations 和尚未完成的核验。

图片本身不包含科研主张或公式；生成提示和视觉检查记录保存在
[asset-provenance.json](assets/readme/asset-provenance.json)。

## 选择能力

| 你可以这样说 | 会启动什么 | 不可削弱的结果 |
|---|---|---|
| “把我要求的每一步都完成，并证明已经完成。” | `instruction_action=register`、原子要求台账、带证据状态转换和最终核验 | 已登记要求不能静默消失；证据变化使 PASS 失效；只有用户能豁免；事实阻塞移交绝不等于完成 |
| “探索这个 idea，检查是否与已有工作撞车。” | 显式领域选择、idea 探索、多来源新颖性检索 | 每条结果带 HTTPS DOI/原始记录链接；方法或领域档案一改，旧收据作废并完整重查 |
| “找文献并写 Related Work。” | 文献发现、主张—证据映射、引用审计、学术写作 | 引用必须有原始记录链接和来源定位；文献身份与是否支持主张分开核验 |
| “设计研究并分析实验指标。” | 假设/实验注册、`metrics_action=plan`、描述分析、约束比较 | 冻结单位、估计目标、缺失、合法范围、数据切分和候选预算；最终测试集不能调参或选型 |
| “按我现有资源规划这个项目。” | 使用 `resource_plan_action=inventory`、串行 DAG、检查点和 `resource_plan_action=execute` 的资源感知任务规划 | 宿主清单不是进程配额；GPU 禁用；未知估算与完成状态不得伪造；只采用用户给出的预算 |
| “我授权你结合本地资源寻找科研方向。” | 通过 `direction_action` 启动经授权的本地资源科研方向探索 | 每个当前修订都要有受管正向粗测和严格带链接撞车收据；向用户返回恰好五个未排名选项 |
| “优化这些实验配置。” | 可行性约束、Pareto 前沿、可选用户加权排序 | 只比较验证集上真实运行的候选；权重和参考尺度属于用户；不自动选赢家 |
| “协助教育学或教育技术学方向的研究。” | ERIC 等公共来源、领域方法、数据源和会议期刊发现 | 保留学生/班级/教师/学校/机构层级；实时核验精确 venue/year/track/stage |
| “写作或审计这篇论文。” | paper spine、引用写作、venue 证据、代码/实验核验、2–3 角色审计 | 联网事实、数字、代码、实验和证据分别核验；角色 effort 最高为 `high` |
| “降低防御性、Nature 化、减少模板痕迹。” | 非防御性语言、修辞检索、翻译、自然化改写 | 不删除必要不确定性、limitations、伦理、风险、批评或负结果 |
| “核验全文公式并给出合法参数值。” | Lean 逻辑、Pint 量纲、SymPy 等价、Z3 可满足性、`numerical_action=construct` | 建模带来源方程/不等式；分别报告边际合法区间和联合可行锚点；符号必须定义并实际使用；Lean 未运行只能报 `NOT_RUN` |
| “编译 LaTeX/检查顶会模板。” | 精确 venue 证据、模板审计、TeX 编译 | 静态检查不能冒充 PDF 编译通过；必须取得当年精确 venue/year/track/stage 官方说明 |
| “做统计图、向量图或架构图。” | 数据绑定的 SVG/PDF/PNG 和最终尺寸视觉审计 | 哈希绑定源数据；检查遮挡、空间利用、对齐、边距、字号和对应刊物风格 |
| “按审稿意见修改或写 rebuttal。” | 意见台账、证据绑定修改、回复信 | 每条意见都有状态和证据；不承诺未完成工作，不预测录用 |
| “主动迎合 AI 审稿人优化得分。” | 可选的主动 score-aware adaptation | 用户显式开启；固定多模型面板和同一量表评估完整候选；冻结引用、数字、公式和必要披露 |
| “检查稿件是否操纵 AI 审稿人。” | 独立 AI-reviewer robustness 模式 | 拦截隐藏指令和虚假 prestige；报告模型敏感性但不做得分优化 |
| “让 LLM 协助这个科研步骤。” | 原生 subagent 优先的 LLM 委派 | 默认一个串行入门/经济型 subagent、低推理；不可用时本地完成；外部 API 必须有明确例外和收据 |
| “为新领域找专业 Skill。” | GitHub/SkillsHub 发现、隔离、2–3 轮 SkillOpt、交叉审计 | 未通过来源、安全和准入审计前不执行远程 Skill |
| “审计代码、实验或科研图像。” | 复现收据、协议合法性、完整性取证、图像审计 | 传输、容量、本地 smoke 和退出码不得被静默提升为科学或因果证据 |

论文生命周期的逐项清单见
[PAPER_WRITING_CAPABILITIES.md](docs/PAPER_WRITING_CAPABILITIES.md)。

## 科研生命周期与强制门禁

- **指令遵循。** 主智能体在修改项目前把多步骤请求拆成哈希绑定的原子台账。依赖、
  验收条件、禁止替代、文件/收据证据、用户显式豁免和完成声明权限都是可执行状态。
  待完成或漂移证据会拦截 Stop；事实 `BLOCKED` 只允许阻塞移交。
- **文献与撞车检索。** 检索没有任意整任务时限。带链接阶段持续保存并回显；只在
  记录的覆盖完成、事实阻塞已保存，或用户明确给出时间/预算/停止指令时结束。
  所有文献输出都带可点击 HTTPS 链接。
- **实验指标。** 方案冻结指标角色、方向、单位、估计目标、聚合、合法范围、缺失
  策略、优化集、最终测试集和候选预算。分析器只接受独立运行级 UTF-8 CSV，拒绝
  协议外数值，并禁止最终测试集参与选择。聚类、纵向、复杂抽样、参与者级、IRT
  和定性数据必须交给对应专业模型，不能静默摊平。
- **资源感知执行。** 多阶段任务使用带版本、哈希绑定的串行 DAG。每次只执行一个
  READY 受管任务；外部/LLM 工作绑定收据；缺失最终证据记为 `UNKNOWN`，不能成为
  自动重试授权。
- **写作与 venue。** 章节名、布局、格式、科研图和叙事必须先实时获取精确
  venue/year/track/stage 的官方证据。引用绑定原始记录和支持主张的定位。
- **语言。** 非防御性、Nature 化、翻译、措辞、会议写作和自然化模块保留科研上
  必要的不确定性。limitations 与可能的伦理遗漏转化为显式用户决策清单。
- **公式与正向数值审计。** Lean、Pint、SymPy、Z3 和数值行为是五个独立结果。
  正向路由把带来源的线性方程/不等式规范化，推导精确边际合法区间，并提出完整的
  联合可行锚点；每个锚点都要重查全部登记约束和论文协议。边际区间绝不能冒充整体
  可行的笛卡尔积；未使用、未定义、非法或混淆参数不能取得 PASS。
- **作图与图像。** 输出绑定源数据和产物哈希，并在最终尺寸检查遮挡、空间利用、
  对齐、沟槽、字号、可访问性以及刊物当前规范。
- **论文审计。** 角色池覆盖引用支持、数字、公式、代码/复现、实验/统计、语言/
  venue、图像完整性、OpenReview 校准和可选 AI 审稿模式。每次只选择 2–3 个
  角色，避免触发过载。

Research Guard 保持 17 个顶层 MCP 工具。新增能力都进入规范主责工具的类型化
子路由，避免功能交叉造成重复触发或接口膨胀。

## 依赖与可核验降级

Release 包含传统 Skill、Codex 插件、MCP 服务、Hook、核心 Python 运行时契约，
以及确定性核验所需的全部源码。插件加载本身绝不会触发可选组件安装。

| 可选组件 | 用途 | 缺失或拒装时 |
|---|---|---|
| Git | 专业 Skill 获取和仓库来源核验 | 保留发现结果；远程 Skill 准入/安装保持 `NOT_RUN` |
| TeX 发行版 | 真实 venue 模板编译 | 只做静态源码检查；绝不声称 PDF 编译通过 |
| Lean + Mathlib | 定理级逻辑核验 | Lean 报 `NOT_RUN`；Pint、SymPy、Z3 和协议数值仍分开报告 |
| 网络/私有索引 | 时效文献、venue 和订阅来源覆盖 | 保留已完成公共结果，并明确列出缺失来源覆盖 |

依赖管理器优先复用通过核验的现有环境；安装前展示预计下载体积和安装后体积；
只接受用户的 `reuse`、`install` 或 `not_now` 选择。国内源可直接使用，国外源可
使用用户配置的代理。缺失组件绝不能转化为 PASS。

## 平台与资源契约

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

Windows 使用 Job Object；Linux 与 macOS 使用独立进程组和 `psutil` 进程树遥测。
越界时只终止本任务拥有的进程树，数值运行时固定单线程。CI 分别核验 Windows
x64、Linux x64、macOS x64 和 macOS arm64；“归档构建成功”本身不构成安装证据。

## 可选可视化 Research Console

Research Console 是单独安装、仅限 localhost 的浏览器科研工作台，用来通过
已安装的 Research Guard Skill 与 Codex 对话。它显示活动工作区与沙箱，允许
用户显式选择不超过三个关注项，实时输出进度、引用与资源遥测，支持停止和
thread 续接；语义模块选择仍由主 Codex Agent 完成。
专用轮次会禁用除显式绑定且强制启动的 Research Guard 以外的全部 MCP 服务。
仅这个本地服务获得自动审批；系统不会修改全局审批策略，也不使用危险绕过。

它不捆绑模型、外部 LLM API 客户端、核心运行时、TeX 或 Lean，而是复用已
安装的 Codex 登录、Research Guard 核心 Python 与 512 MiB 聚合资源策略。
缺失前置条件时预检会显式失败，不会触发未获批准的下载或 API 降级；核心包
测试还会证明其中不存在任何 `addons/` 文件。

下载 [research-guard-ui-addon.zip](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-ui-addon.zip)，
核验 [SHA256SUMS-ui.txt](https://github.com/dltsum/research-guard/releases/latest/download/SHA256SUMS-ui.txt)，
并阅读 [Research Console 安装、安全、资源与维护指南](docs/RESEARCH_CONSOLE_UI.md)。

## 文档

所有声明为双语的文件都登记在
[documentation-parity.json](assets/documentation-parity.json)。CI 强制核验成对
文件、共享修订、完整二级章节骨架、链接集合、图片集合及可访问性，以及规范化
内容哈希；任何未登记的 `.zh-CN.md` 也会被拒绝。这能保证配对维护和结构一致，
但不会虚构“机器已经证明翻译质量”。

- [Documentation maintenance policy](docs/DOCUMENTATION_POLICY.md) · [中文维护策略](docs/DOCUMENTATION_POLICY.zh-CN.md)
- [依赖与安装](REQUIREMENTS.md)
- [架构](docs/ARCHITECTURE.md)
- [跨学科支持](docs/DISCIPLINE_SUPPORT.md)
- [教育学/教育技术学支持](docs/EDUCATION_SUPPORT.md)
- [论文写作与审计全清单](docs/PAPER_WRITING_CAPABILITIES.md)
- [指令遵循与正向数值审计](docs/INSTRUCTION_AND_NUMERICAL_CONTRACT.zh-CN.md) · [English contract](docs/INSTRUCTION_AND_NUMERICAL_CONTRACT.md)
- [时间与持续执行策略](docs/TIME_AND_CONTINUATION_POLICY.md)
- [原生 subagent 优先的 LLM 委派](docs/SUBAGENT_DELEGATION.md)
- [资源感知任务规划](docs/RESOURCE_AWARE_TASK_PLANNING.md)
- [经授权的本地资源方向探索](docs/DIRECTION_EXPLORATION.md)
- [跨平台迁移保障](docs/provenance/P21_CI_MIGRATION_ASSURANCE.md)
- [第三方声明](THIRD_PARTY_NOTICES.md)
- [安全策略](SECURITY.md)

## 开发

```sh
python -m pip install --disable-pip-version-check -r requirements-dev.txt
python -X utf8 scripts/documentation_parity.py
python -X utf8 scripts/validate_repository.py
python -X utf8 scripts/run_incremental_tests.py --pattern "test_documentation_parity.py" --suite docs
python -X utf8 scripts/build_modular_package.py --platform linux-x64 --output dist/research-guard-linux-x64.zip
```

修改已登记的双语文档时，要同时编辑两份文件，执行
`python -X utf8 scripts/documentation_parity.py --refresh-hashes`，人工检查配对，
然后再运行验证。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

源码 checkout 不包含大型审计 payload、缓存 venue 页面、模板和论文 PDF，因此
不是 Windows 离线 Release 安装包。

## 许可证

Research Guard 使用 [MIT License](LICENSE)。所含或引用的第三方组件保留各自
许可证，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
