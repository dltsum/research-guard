<!-- research-guard-doc-pair: preset-audit | revision: 2026-09-03.3 -->
# 与主机无关的预设审计

## 范围

本审计检查完整的 Research Guard 检出目录，寻找会把新安装悄悄绑定到构建机或运行机的设置。默认范围包含 Git 忽略的开发、评估和发布归档文件，只排除 `.git`。这是可移植性与配置检查，不是安全或攻击者审计。

## 类别

可执行扫描器报告具体用户路径、绝对系统/卷/UNC 路径、固定本地或私有端点、环境代理读取、硬编码代理 URL、环境 pip/uv 索引或配置读取、可选学术凭据读取（`ambient_credential_read`）、完整主机环境继承、工作站字体名称，以及主机语言环境/时区推断。每条发现都保留经过脱敏的路径与片段。检出目录中的 ZIP 与 tar 系列归档成员（包括忽略的证据和生成的发布归档）会在声明的大小与数量上限内检查；二进制、非 UTF-8 成员和符号链接会明确列为跳过。

明确的测试夹具、测量运行证据、仅绑定 localhost 的可选控制台、刊物源证据、有文档说明的用户命令环境和显式可选学术凭据会记录在 `allowed_findings` 中，而不会静默忽略。`Path.home()`、`Path.cwd()`、显式环境覆盖、测量的主机事实、内置或通用字体、显式项目语言以及串行 512 MiB 项目策略等可移植回退单独记录在 `portable_defaults` 中。

`mechanism_inventory` 是独立于违规判定的覆盖台账，列出包含路径、平台、语言环境、字体、环境变量、网络客户端/路由、包索引、凭据、子进程、资源、归档/清理和溯源机制的文件及有限示例。示例只保留模式 ID 与源码位置，不保留匹配值，因此不会变成凭据转储。跳过的符号链接会在 `scan.symlink_entries_skipped` 中显示，绝不会被隐式跟随。

## 允许项与有意默认值

策略文件是 [assets/preset-audit-policy.json](../assets/preset-audit-policy.json)。它要求源代码保持中立：开发者固定路径、本地代理端口、环境学术代理、环境包索引、工作站字体和主机语言/时区都不能成为安装默认值。可选 API 密钥或联系邮箱只接受用户主动提供；缺失凭据时保持匿名或 `credential_required` 行为。安装位置按以下顺序解析：显式 CLI 参数、对应的 `RESEARCH_GUARD_*`/`CODEX_HOME` 设置、标准的每用户回退。Windows 与 POSIX 启动器也会先使用显式的 `RESEARCH_GUARD_PYTHON`，再查找所选 Research Guard home 下的运行时。只有当前进程的 loopback 端点自动视为本地；包括 `.cn` 在内的公开域名后缀绝不推断用户所在国家。空代理输入表示直连；代理或包镜像只有在用户显式提供或保留安装器配置时才使用。

## 执行

在仓库根目录运行完整审计：

```text
python -X utf8 scripts/preset_audit.py --root . --policy assets/preset-audit-policy.json --output <检出目录之外的路径>/preset-audit.json
```

`researchctl preset-audit --project-root <checkout>` 与现有 `research_design` 维护路由使用同一实现。CLI 必须显式提供根目录，避免从无关目录调用时静默审计错误的检出目录。`--no-ignored` 仅用于面向包的诊断，不能替代默认的全量审计。发布校验会在构建或发布包前执行全量审计。

## 证据与限制

回执报告扫描的文本文件与字节数、ZIP/tar 归档及成员、跳过的二进制或非 UTF-8 文件/成员、符号链接、为避免递归增长而跳过的生成审计回执、扫描错误、违规项、允许发现、可移植默认值、机制台账，以及资源/网络/LLM 策略绑定。跳过二进制、符号链接或超出大小的归档成员会在回执中明确显示，绝不被视为内容可移植的证明。扫描器不计算源文件哈希、不输出凭据、不推断用户学科，也不测试外部网络是否可达。`FAIL` 表示必须修复具体发现或策略绑定漂移后重新审计。

实现与测试见：[scripts/preset_audit.py](../scripts/preset_audit.py)、[scripts/researchctl.py](../scripts/researchctl.py)、[scripts/mcp_server.py](../scripts/mcp_server.py) 和 [tests/test_p29_preset_audit.py](../tests/test_p29_preset_audit.py)。
