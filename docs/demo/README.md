# 真实逐问交互档案

[下载独立 HTML](https://raw.githubusercontent.com/dltsum/research-guard/main/docs/demo/index.html)，保存为 `index.html` 后在浏览器打开。页面无需服务器、联网、CDN 或 Python；目录、搜索、筛选和证据展开都在本机工作。GitHub 的源码预览不会执行 HTML。

这是实际持续验收记录。当前统计、待测路由、预期拒绝、失败、修复及跳过均以页面原始状态为准；不能把已实测计数当作所有候选通过或科研结论成立。每条记录保留真实问题、执行 agent 原始答复、主审反馈和实际调用回执。独立条件另保留实际读取的输入文件、第一版答案、工作记录及主审逐句审查；不会重建加密宿主消息。

公开副本只对机器路径、本地端点与凭据作脱敏，原件 SHA256 留在回执中。完整本机可见工具事件、原始论文与数据留在本地交付目录，不发布私有推理。`manifest.json` 绑定构建所读本机证据的哈希及页面 SHA256；哈希本身不证明执行身份。

实际验证宿主是 Windows。多个原生 agent 不代表多个操作系统。CiteSpace 的外部伴随工具不可用，按用户授权跳过，没有以其他引擎冒充。功能组件安装不会复制本目录。

## 从已有真实记录重建

使用 Python 标准库执行（`EVIDENCE_ROOT` 须是交付的本机真实验收目录，不能用样例替代）：

```text
python -X utf8 docs/demo/build_demo.py --evidence-root EVIDENCE_ROOT --repository . --template docs/demo/template.html --output LOCAL_OUTPUT
```

构建器只读取既有记录并生成页面，不启动 agent、不调用功能、不推断 PASS、不生成对话或执行回执。`data.json` 是本机构建中间件；为减少重复体积，仓库仅发布已内嵌同一数据的 HTML、manifest、模板和构建器。

文字总览可用 `python -X utf8 docs/demo/build_overview.py --evidence-root EVIDENCE_ROOT --repository .` 从同一队列重建。它分别计数真实调用、待测和跳过；没有调用的外部工具跳过不会计入已测。两种构建都只是记录展示，不替代功能运行。
