<!-- research-guard-doc-pair: research-console-ui | revision: 2026-08-23.3 -->
# 可选 Research Console 可视化界面

[English](https://github.com/dltsum/research-guard/blob/main/docs/RESEARCH_CONSOLE_UI.md) | [简体中文](https://github.com/dltsum/research-guard/blob/main/docs/RESEARCH_CONSOLE_UI.zh-CN.md)

## 范围

Research Console 是一个可选、仅限本机 localhost 的浏览器界面，用于在
对话 Codex 时使用已安装的 Research Guard Skill。它单独发布为
`research-guard-ui-addon.zip`，明确不进入任何 Research Guard 核心包，也
不会改变 17 个顶层 MCP 工具。

附加包只包含小型标准库 HTTP 服务、静态 HTML/CSS/JavaScript 和受控的
Codex CLI 桥接层，不捆绑模型、核心插件、Python 运行时、TeX、Lean、外部
LLM API 客户端或自动领域分类器。仍由主 Codex 阅读用户的完整请求并选择
必要的 Research Guard 模块。界面中最多三个可见的关注项是用户显式偏好，
不是小模型路由器。

## 安装与启动

先安装并启用 Research Guard 核心插件。下载
[research-guard-ui-addon.zip](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-ui-addon.zip)
和 [SHA256SUMS-ui.txt](https://github.com/dltsum/research-guard/releases/latest/download/SHA256SUMS-ui.txt)，
核对压缩包摘要，解压后使用核心安装所登记的 Python 执行其中的
`install.py`。安装器会核验每个打包文件、复用核心的 `psutil`、检查 Codex
及 Research Guard 是否已启用，通过 Codex 的机器可读输出检查必需的各服务
MCP 控制，并建立按版本隔离的当前用户安装目录。它不会下载任何内容。

可以直接把下面这段话交给 Agent：

```text
安装 Research Guard Release 中的可选 Research Console。根据
SHA256SUMS-ui.txt 核验 research-guard-ui-addon.zip，使用已安装 Research
Guard 核心登记的 Python 运行 install.py，为我选择的工作区启动界面，并
把 localhost 地址给我。不要安装另一个模型，也不要调用外部 LLM API。
```

安装后的手动启动方式：

```powershell
python "$HOME/.research-guard/addons/research-console/0.1.0/launch.py" --workspace "C:\path\to\research"
```

```sh
python3 "$HOME/.research-guard/addons/research-console/0.1.0/launch.py" --workspace "/path/to/research"
```

`launch_command` 不会把安装器进程的当前目录写入命令。请提供
`--workspace <project>` 或设置 `RESEARCH_GUARD_WORKSPACE`；两者都没有时返回
`WORKSPACE_REQUIRED`，不会静默绑定主机检出目录。程序只输出 URL，请用户手动打开；
程序不控制浏览器，`--open` 选项和浏览器自动化均被刻意移除。

准确的宿主要求与降级行为以
[REQUIREMENTS.md](https://github.com/dltsum/research-guard/blob/main/REQUIREMENTS.md)
为准。

## 交互模型

工作区、沙箱、语言和最多三个关注项始终可见；默认项是“让 Codex 判断”。
新对话轮次使用 `codex exec --json`，继续对话时复用返回的 Codex thread
标识。提示词通过标准输入传递，不出现在进程参数里。NDJSON 会随时展示
助手消息、活动、引用、诊断、资源采样、用量、完成状态和事实性失败状态。

每一轮都会枚举已配置的 MCP 服务，禁用 `research-guard` 以外的全部服务，
并显式绑定已安装插件声明的本地 stdio 命令。Research Guard 服务会被标为
required，初始化失败时整轮启动即失败。只有该服务获得 Codex 已记录的
`default_tools_approval_mode = "approve"`；这是范围受限的非交互审批，不会修改
全局审批策略，也不是危险沙箱绕过。任务依赖其他 MCP 服务时，应改用完整 Codex
客户端。各服务审批与 required 配置键见
[Codex 配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)。

这一轮次式设计遵循 Codex 已记录的
[非交互 JSONL 与续接接口](https://learn.chatgpt.com/docs/non-interactive-mode)。
更完整的 [Codex App Server](https://learn.chatgpt.com/docs/app-server) 才是由
客户端管理审批、结构化用户输入请求和完整会话历史的官方深度集成接口。
0.1 版明确不实现这套更大的双向协议，而保持为小型可选控制台。

系统没有整项任务超时。运行中的轮次会持续发出心跳和进度，直到 Codex
完成、用户点击停止、浏览器断开、资源门禁终止所拥有的进程树，或 Codex
报告失败。阶段性结果保持可见；除非用户给出时间或预算限制，否则由主
Agent 判断研究覆盖何时完成。

宿主可能拥有超过 Codex 预加载容量的 Skill 描述。因此，桥接层先核验已
安装插件，再把已安装 `SKILL.md` 的精确路径写入紧凑且可见的本轮上下文；
私有子进程环境还会为本地 MCP 启动器携带插件根目录。系统不会把所有模块
提示词粘贴到每轮对话里。

## 安全与隐私

服务只绑定随机端口上的 `127.0.0.1`。每个 API 请求必须携带当次启动随机
生成的 token。token 最初位于 URL fragment，随后移入浏览器
`sessionStorage`，且只通过同源自定义请求头发送。服务拒绝外部 Origin，
并返回严格的内容安全策略、frame、referrer、MIME、permissions 和跨源
响应头。

界面不使用远程脚本、字体、分析服务、外部 API 或 HTML 注入。引用通过
安全 DOM 节点创建，只有 `https://` 目标可点击。桥接层会从显示的诊断中
清除常见凭据和用户主目录前缀。UI 服务不写入提示词和回答；浏览器持久化
仅限工作区/thread 元数据及本地偏好。Codex 与所选 Research Guard 模块
仍遵循各自已经说明的持久化边界。

界面只提供 `read-only` 和 `workspace-write` 沙箱，绝不提供危险绕过模式。
恢复已有 Codex thread 时，会保留该会话建立时的沙箱与工作目录。

启动专用控制台，仅代表用户授权本地 Research Guard MCP 服务为本次提交任务
自动执行调用。这些工具仍执行各自的证据、依赖同意、资源和工作区契约；控制台
不会自动下载依赖，也不会把失败门禁改写成 PASS。其他已配置 MCP 服务会在本轮
被禁用，而不是被自动批准。

## 资源行为

Research Console 复用已安装的 `assets/resource-policy.json`：同一时间只有
一个活动轮次；禁用 GPU；数值线程数固定为一；UI 服务及其所拥有后代进程
的聚合工作集最多为 512 MiB；空闲物理内存至少保留 512 MiB；采样间隔为
10 ms。发生越界时，系统终止所拥有的 Codex 进程树并报告错误，绝不报告
PASS。

附加包不做后台索引或自动模型推理，只在用户提交消息后启动 Codex，并提供
显式停止按钮。512 MiB 限制针对任务拥有的进程，不针对整个操作系统；宿主
资源清单也不代表某轮对话一定能够容纳。

## 打包与发布

确定性附加包构建器输出一个压缩包和一个校验文件。清单绑定附加包版本、
核心兼容范围、Python/Codex/`psutil` 要求、文件哈希、资源策略、安全边界
和压缩包大小。如果归档超过 25 MiB，或包含核心 MCP 服务、插件清单、
payload 归档、模型或运行时，构建会失败。

核心包构建器按白名单选择文件，并排除整个 `addons/` 目录。CI 分别证明
两个方向：UI 归档可以安装，同时所有核心归档不含 UI。可选 Release 资产
不会改变核心包的校验记录。

## 维护者工作流

维护中的源码位于
[addons/research-console](https://github.com/dltsum/research-guard/tree/main/addons/research-console)。
每次行为变更都必须：

1. 同步更新这对中英文文档并刷新登记哈希；
2. 串行运行 UI 单元、HTTP、安全、可访问性、桥接、打包和隔离安装测试；
3. 在核心资源门禁下多轮运行附加包 SkillOpt；
4. 以无头浏览器截图检查桌面与窄屏视觉效果；
5. 证明核心包仍然排除 `addons/`；以及
6. 重建确定性归档并发布其校验值。

Release 流程与维护检查记录于
[CONTRIBUTING.md](https://github.com/dltsum/research-guard/blob/main/CONTRIBUTING.md)。

## 已知边界

- UI 是传输和可观测界面，不是独立审稿人、证据来源、科学验证器或完成证明。
- 0.1 版不会呈现 Codex App Server 的审批或结构化用户输入请求。需要新增
  交互审批的任务必须转到完整 Codex 客户端继续；UI 绝不会自动接受或绕过。
- 它要求可工作的已登录 Codex CLI，以及已安装并启用的 Research Guard
  插件。如果任何一项不可用，附加包会在预检时显式失败，不会静默切换到
  外部 API。
- 浏览器关闭导致流断开时，只取消当前拥有的轮次；重放前仍须检查 Codex
  侧的持久收据。
- 页面中的引用只是便捷链接；文献身份、来源定位和主张支持仍由 Research
  Guard 的文献及引用门禁负责。
- 任何不可用的核验都保持为 `NOT_RUN`，绝不报告 PASS。
- 可访问性检查和视觉审查可以减少界面缺陷，但不能证明普适可访问性。
