# 来自本地完整交付包的 CiteSpace 配套插件

`citespace-mcp/` 保留项目所有者 `Research_Guard.zip` 完整包中的全部 16 个插件文件
（2026-10-22，773,297,766 字节）。插件声明版本仍为
`0.1.0+codex.20260925085627`，快照另含文档记录的10月21/22日修复；
不能只用清单时间戳识别后续源码快照。本次入库没有重新执行原生制图。

对应历史引擎：**CiteSpace 6.4.R2 Basic**，应用 JAR 为 `CiteSpace-6.4.2.jar`；
配套 Java：**Temurin 22.0.1+8 Windows x64 JRE**。
本地完整包中的软件与运行时目录保持不变。公开目录提供配套实现、测试、Skill 和
自编译的窄接口 Java 适配器，不包含厂商 CiteSpace 应用本体。

## 安装与绑定

1. 使用合法取得的本地引擎与对应 Java 运行时。
2. 创建隔离 Python 环境，安装 `citespace-mcp/requirements.txt`；
   包括 MCP、pyjab，依赖保留各自许可。
3. 为 `.mcp.json` 指定该 Python，并将 `CITESPACE_INSTALL_DIR`、`CITESPACE_JAVA`、
   `CITESPACE_TASK_ROOT` 绑定实际路径。原配置期待同级 `software/`，仓库不会自动下载
   或悄悄替换软件版本。
4. 将插件与 Research Guard 分别加载。许可、账号、邮箱提示由本人完成。
   保留的10月快照默认不会自动提交测试邮箱。
5. 原生运行前阅读插件 README/Skill 和集成说明；旧版自动启动说明为历史记录，
   不是当前授权。

## 分发边界

[官方 FAQ](https://citespace.podia.com/faq) 第2.4节明确将非官方站点分发标为未授权。
尚未取得历史软件在 GitHub 建镜像的许可，因此公开仓库不重新分发厂商软件、研究
PDF或私人任务记录。用户现有的**本地**完整档案不因此删减文件。
公开上传应用本体需要相应再分发授权。

此处代码是所有者的配套插件快照，不授予 CiteSpace、Java 或 pyjab 许可；桥接说明
原样保留。运行时、语料和原生结果证据不能被源码/格式检查替代。
