<!-- research-guard-doc-pair: harness-compatibility | revision: 2026-09-25.1 -->
# Harness 兼容性

Research Guard 的单个仓库可被多种智能体 harness 直接加载。本文逐一列出各 harness 的安装方式与确切配置片段；对于插件接口尚未完全确认的 harness，给出其他智能体在完成集成前必须自行发现的接口点清单。

仓库的集成面：

- `skills/` —— 五个可移植的 `SKILL.md` 领域技能（跨 harness 通用标准格式）。
- `.mcp.json` —— MCP stdio 服务器 `research-guard`（`scripts/mcp_launcher.py`）。launcher 依次从 `PLUGIN_ROOT`、`CLAUDE_PLUGIN_ROOT` 或 harness 文本替换的 `${...}` 占位符解析插件根目录。
- `hooks/hooks.json` —— SessionStart、UserPromptSubmit、PreToolUse、PostToolUse、Stop 五类回执钩子。POSIX 命令从 `PLUGIN_ROOT` 解析插件根并回退到 `CLAUDE_PLUGIN_ROOT`；`commandWindows` 条目使用 `%PLUGIN_ROOT%`。
- `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json`、`kimi.plugin.json` —— 各 harness 的 manifest，均指向上述同一集成面。

## Claude Code

仓库根目录即是完整的 Claude Code 插件：`.claude-plugin/plugin.json` 加上默认组件布局（`skills/`、`hooks/hooks.json`、`.mcp.json`）。

本地开发安装：

```
claude --plugin-dir /path/to/research-guard
```

或作为个人 marketplace 条目持久安装：

```
claude plugin marketplace add /path/to/parent-directory
claude plugin install research-guard@<marketplace-name>
```

注意：

- 钩子命令假定 PATH 上存在 POSIX `sh`。在 Windows 上，Claude Code 的 Git Bash 环境可满足；钩子随后调用 `hooks/hook.sh`，该脚本自行定位，无需插件根变量。
- `agents/openai.yaml` 是 Codex 专用文件，不是 Claude Code 子代理；Claude Code 会直接忽略非 Markdown 条目。

## Codex

已集成。运行安装器即可：它会把插件复制到 `~/plugins/research-guard`，注册个人 marketplace 并启用：

```
python scripts/install_posix.py      # Linux / macOS
powershell -File install.ps1         # Windows
```

安装器同时会把技能物化到 `~/.codex/skills/research-guard`，并以绝对路径写入 MCP 注册。

## Kimi Code CLI

仓库根目录包含 `kimi.plugin.json`（Kimi 首选的 manifest 文件名，优先级高于 `.kimi-plugin/plugin.json`）。manifest 复用 `skills/`，并以插件根相对路径 `./scripts/mcp_launcher.py` 注册 MCP stdio 服务器。

在 Kimi Code 内从本地检出或 Git URL 安装：

```
/plugins install /path/to/research-guard
/plugins install https://github.com/<owner>/research-guard
/plugins mcp enable research-guard research-guard
```

管理命令：`/plugins info research-guard`、`/plugins enable|disable research-guard`、`/plugins reload`。

尚未确认的接口点（留给后续智能体对照 Kimi 插件文档核实）：

- manifest 的 `hooks` 字段是否接受 Claude 风格的 `SessionStart`/`UserPromptSubmit`/`PreToolUse`/`PostToolUse`/`Stop` 事件及 `matcher` + `command` 条目，以及钩子命令可用的插件根变量是 `${PLUGIN_ROOT}` 还是 Kimi 专有变量。`hooks/hooks.json` 中的可移植 POSIX 回退已覆盖任何"文本替换 `${PLUGIN_ROOT}` 或导出 `CLAUDE_PLUGIN_ROOT`"的 harness；若 Kimi 使用专有变量，只需再加一个回退分支。
- `sessionStart.skill` 是否应指定五个技能之一以便自动激活。

## ZCode（Z.ai GLM harness）

ZCode 支持 stdio、HTTP、SSE 三种 MCP 传输，并可导入为 Claude Code 或 Codex CLI 编写的 MCP 配置。直接指向本仓库的 `.mcp.json`，或手动添加等价条目：

```json
{
  "mcpServers": {
    "research-guard": {
      "command": "python",
      "args": ["-X", "utf8", "/absolute/path/to/research-guard/scripts/mcp_launcher.py"]
    }
  }
}
```

将 `/absolute/path/to/research-guard` 替换为检出位置。技能是可移植的 `SKILL.md` 文件；若 ZCode 的技能加载器要求特定目录，把 `skills/research-design-guard`（及其余四个）复制或软链到该处。

## WorkBuddy（腾讯）

WorkBuddy 从 `~/.workbuddy/mcp.json` 读取 MCP 服务器，从 `~/.workbuddy/skills/` 加载 Claude 风格技能。

1. 把五个技能目录复制（或软链）到 `~/.workbuddy/skills/`。
2. 合并进 `~/.workbuddy/mcp.json`：

```json
{
  "mcpServers": {
    "research-guard": {
      "command": "python",
      "args": ["-X", "utf8", "C:/path/to/research-guard/scripts/mcp_launcher.py"]
    }
  }
}
```

## OpenClaw

OpenClaw 在 `~/.openclaw/openclaw.json` 中配置 MCP 服务器；JSON 结构与上文相同。两条安装路线：

1. **直接添加 MCP 条目** —— 把 `research-guard` 服务器（见 ZCode 片段）加入 `openclaw.json`。
2. **经 babelfish 导入插件** —— OpenClaw 的 `babelfish` 插件可导入 Claude Code 与 Codex 插件：

```
openclaw plugins install npm:@openclaw/babelfish
```

然后把本仓库作为 Claude Code 插件（`.claude-plugin/plugin.json`）或 Codex 插件（`.codex-plugin/plugin.json`）导入；babelfish 会转译技能、钩子与 MCP 注册。

## DSH（DeepSeek Harness）及其他未确认 harness

DSH 的插件接口尚无法从公开来源确认（只能访问到 dsh.directory 等插件市场列表站）。与其猜测，不如给出集成智能体必须在目标 harness 官方文档或源码中发现的接口点清单，以及每一点确认后 Research Guard 的对接方式：

1. **MCP stdio 注册** —— 找到 harness 存放 MCP 服务器定义的位置（JSON 文件、CLI `mcp add` 命令或 UI）。注册：command 为 `python`，args 为 `["-X", "utf8", "<absolute-repo-path>/scripts/mcp_launcher.py"]`。launcher 不需要任何环境变量；当 `~/.research-guard/runtime/python` 存在时会 re-exec 进已安装运行时，否则在进程内校验依赖。
2. **技能加载** —— 找到 harness 的技能/提示包目录或 manifest 字段。`skills/` 下五个目录各自是自包含的 Claude 标准 `SKILL.md` 技能；复制过去，或在 manifest 中指向 `./skills/`。
3. **钩子事件** —— 找到 harness 的生命周期钩子机制，并映射这五个事件：会话开始（`SessionStart`，matcher `startup|resume|clear|compact`）、处理每条用户输入前（`UserPromptSubmit`）、文件修改或 shell 工具调用前后（`PreToolUse`/`PostToolUse`，matcher `Bash|apply_patch|Edit|Write`）、代理停止前（`Stop`）。每个钩子条目运行一条命令，超时 15 秒；POSIX 用 `sh "<repo>/hooks/hook.sh"`，Windows 用 `"<repo>\scripts\hook.cmd"`。两个脚本均自行定位，harness 提供的任何插件根变量仅用于找到脚本。钩子通过 stdin/stdout JSON 通信，格式与 Claude Code 定义完全一致；若 harness 使用不同的线路格式，写一个薄适配层把 JSON 原样转发给 `hooks/guard_hook.py` 即可。
4. **插件 manifest** —— 若 harness 需要自己的 manifest 文件，参照 `kimi.plugin.json`：`name`、`version`、`description`、`author`、`license`、`skills: "./skills/"`，以及第 1 点的 `mcpServers` 映射。

若任何一点无法满足，停下并报告 harness 缺少哪个接口，不要静默降级 —— 钩子与 MCP 服务器在设计上都是 fail-closed 的。

## 验证安装

无论使用哪个 harness，都通过 MCP 服务器验证：

1. 调用 `research_design` 工具并传 `{"action": "status"}`；健康的安装会返回当前 ledger 状态 JSON。
2. 调用 `frontier_analysis` 并传 `{"frontier_analysis_action": "status"}`，确认分析模块已加载。
3. 若钩子已激活，提交任意输入不应出现 `DEPENDENCY_MISSING` 输出；出现该错误说明 Python 运行时缺失，应重新运行 `scripts/install.sh` / `install.ps1`。
