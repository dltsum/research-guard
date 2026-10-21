# 文档维护

行为变更时同步维护中英文说明，按含义自然翻译，不要求标题、措辞或篇幅机械一致。
`assets/documentation-parity.json` 只作为配对文件索引。

`python -X utf8 scripts/documentation_parity.py` 是可选的健康检查，确认登记文档
能够读取且非空；缺失的本地链接报告为提示。编辑内容、增加文档、更换图片或标题
不需要刷新摘要、revision 标记、token 表或来源封条。
旧 `--refresh-hashes` 参数保留为无写入的兼容别名。

对照实际功能检查说明和例子。历史测试记录保留为历史，不能当作新版本已验证的证明。
新的操作说明使用当前安装和工作流程。
