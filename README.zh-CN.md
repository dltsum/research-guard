# Research Guard

[English](README.md) | [简体中文](README.zh-CN.md)

Research Guard 是可以按功能组安装的科研 Skill，提供文献、研究设计、实验、
写作、科研作图和数学检查的真实 MCP 工具。按任务安装需要的组件即可。

## 安装与使用

```sh
git clone https://github.com/dltsum/research-guard.git
cd research-guard
python -I -X utf8 scripts/component_install.py --list
python -I -X utf8 scripts/component_install.py --components literature writing --target <absolute-directory>
```

使用生成的 `.mcp.json` 启动 MCP，然后直接用自然语言提出任务。
更新时继续安装到同一目录。需要隔离环境时加 `--create-venv`；
所选功能缺少 Python 包时加 `--install-python-deps`。已有 Python、TeX、Lean
可以直接复用。`--verify` 只是可选的缺失文件和依赖导入诊断。

[完整安装提示词](INSTALL_PROMPT.md) 说明组件选择、依赖和交互式验收。
[SKILL.md](SKILL.md) 是智能体入口。

## 2026-10-22 简化

正常科研工作不再要求用户提交哈希参数、签名回执、重复扫描整组文件、
修改后另建安装目录，或先登记合同再 verify 才能写文件、结束回复。
Hook 改为简短提示，不阻止编辑和结束。安装和构建检查文件是否可用及实际依赖，
不再依赖摘要封条。修改文档无需刷新哈希，也无需保持标题、token 机械对应。

来源链接、真实计算和用户要求的科研审计继续服务于具体任务。
status 读取已有运行记录；显式重跑才使用当前文件重新计算并报告新结果。

[改动与真实运行记录](docs/SIMPLIFICATION_20261022.md)。

## 功能组

| ID | 功能 |
|---|---|
| `core` | 任务路由、科研记录和可选指令跟踪 |
| `literature` | 文献检索、查新对比、引文、文档解析和证据图谱 |
| `research` | 研究想法、策略、假设和实验设计 |
| `experiments` | 指标分析、执行计划、真实复跑和研究方向探索 |
| `writing` | 学术表达、参考论文逻辑、论文审计和会议模板排版 |
| `figures` | 数据图、参考风格附图、图像审计和像素比较 |
| `formal` | 量纲、符号/SMT、数值模型检查和真实 Lean 编译 |
| `skill-lab` | 安装 Skill、行为实验、迁移/组合研究和改进建议 |
| `citespace` | 知识图谱、本地网络和原生 CiteSpace 伴随路线 |

安装器自动补齐所选组的依赖；不选择就不安装。未安装的路线会提示缺少组件。
原生引擎、宿主智能体与图像能力按实际可用情况执行。
详见[组件安装说明](references/component-installation.md)和[依赖说明](REQUIREMENTS.md)。

## 写作与作图交付

参考论文写作先读实验记录，按用户的时间和资格条件找论文，保留已有大纲，
将参考文章的逻辑映射到全文。按要求由三个真实智能体分别审计逻辑匹配、
防御性写作和科学性。交付文稿、正式 paper kit PDF、待补实验/解释、
参考逻辑分析、细粒度对应分析、验证脚本，以及适用且本机支持时可编译的单文件 Lean。

参考图作图保留所有指定信息并匹配参考设计。每轮按要求由三个真实智能体检查
信息、风格和细节。交付成品、审计和两图比较、像素脚本、组件素材、
已用网络素材及来源、论文逻辑表，以及逐组件解释和信息审计表。
没有参考图时，使用安装包历史目录里每一种可用风格。

## 真实交互记录

[下载离线交互档案](https://raw.githubusercontent.com/dltsum/research-guard/main/docs/demo/index.html)，
并查阅[记录和重建说明](docs/demo/README.md)。其中包含安装、逐条问题、
实际智能体回答、主智能体反馈和修复重测。档案记录的是 2026-10-21 的运行，
不是今天代码的新运行：170/176 条路线已调用，43 个缺陷修复重测，
六条 CiteSpace 路线明确跳过。写作缺口和组合研究 `NOT_DEMONSTRATED` 如实保留。

新的验收逐功能逐句进行：执行智能体完成一项，主智能体给反馈，再进入下一项；
发现问题直接修复、同目录更新并重测。交付至少两种真实输入、平台依赖说明及原始调用，
使其他人能够安装、运行并判断结果。

## 进一步说明

- [来源政策](skills/research-novelty-guard/references/source-policy.md)
- [研究设计](skills/research-design-guard/SKILL.md)
- [写作](skills/academic-language-guard/SKILL.md)
- [作图](skills/academic-figure-guard/SKILL.md)
- [Skill 实验](references/skill-lab-workflow.md)
- [可选浏览器界面](docs/RESEARCH_CONSOLE_UI.zh-CN.md)
- [平台兼容](docs/HARNESS_COMPATIBILITY.zh-CN.md)
- [CiteSpace 集成](docs/CITESPACE_INTEGRATION.zh-CN.md)

可移植的目录结构本身不代表已完成第二个平台的运行验证。
报告实际平台、输入、输出和真正执行过的检查。
