# research-guard 多 Harness 兼容计划（2026-09-24）

## 目标
research-guard 兼容 cc(Claude Code)/codex/dsh/zcode/kimicode/workbuddy/openclaw 等 harness；
对不能确定兼容方式的 harness，给出接口必要解释+修改说明供其他智能体自行修改；安装命令中给出引导。

## 步骤
1. [x] 摸底本仓现有集成面（.codex-plugin/SKILL.md/hooks/agents/MCP launcher/install.sh+ps1）
2. [x] 调研各 harness 插件/技能/MCP 接口格式（并行研究 agent）
3. [x] 确定每个 harness 的兼容策略：直接支持（加 manifest/配置模板）vs 文档引导
4. [x] 实现兼容层（新 manifest/配置模板/安装器选项）
5. [x] 写 docs/HARNESS_COMPATIBILITY.md（中英双语，含不确定 harness 的接口解释+修改说明）
6. [x] README + 安装命令引导（parity 哈希刷新）
7. [x] 测试（validate_repository + 新增兼容性测试）+ 推 main（8d958dc；官方 runner github-ci 33 文件 PASS）
8. [x] 同步 PORTFOLIO/记忆

## 约束
- 规则 2/3：最小改动，不动现有 codex 集成
- README 双语改动后必须跑 scripts/documentation_parity.py --refresh-hashes
- 新文档对需登记 assets/documentation-parity.json（或放 docs/ 单语避免 parity 膨胀——调研后定）
