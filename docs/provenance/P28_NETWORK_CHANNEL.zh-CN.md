<!-- research-guard-doc-pair: p28-network-channel | revision: 2026-09-05.1 -->
# P28 网络通道恢复

## 问题与范围

GitHub Issue [#6](https://github.com/dltsum/research-guard/issues/6) 报告
0.7.0 的新颖性/撞车检索无法连接学术检索网站。附带运行记录显示 arXiv 与
Crossref 均发生传输失败。传输失败不是零结果观察，必须让撞车门禁保持未完成。

## 根因

源码请求边界即使在用户没有配置代理时，也假定存在本地外国源代理
（`127.0.0.1:7897`），随后又重复尝试同一路由。对于位于新加坡或其他没有该监听器
的环境，这会把正常的直连误报为学术源故障。即使代理监听器接受连接但 TLS 握手失败，
在官方端点可以直连时也没有剩余可用路由。因此故障在路由选择/恢复，而不在来源解析
或撞车裁决。

同一个隐式主机假设还出现在学科初始化、Crossref 引用核验、GitHub/SkillsHub 发现、
OpenReview 校准、刊物证据检查、POSIX 依赖安装器和 Lean 引导中。现在这些路径共享一个
小型标准库配置模块。它们只接受显式的、无凭据的
`RESEARCH_GUARD_FOREIGN_PROXY` 或安装器自有的 `network-config.json`；绝不会把环境中的
`HTTP_PROXY`/`HTTPS_PROXY` 值导入保存配置。

共享边界覆盖包内所有出站客户端：新颖性核心（包括 PubMed、PMC、OpenAlex、Semantic
Scholar、Unpaywall、GitHub、IEEE、Web of Science、试验、基金、专利、OSF 与源目录）、
学科 profile、Crossref、OpenReview、领域 Skill 与 Git 发现、刊物证据、CCF/资产/载荷
引导，以及 POSIX/Lean 依赖引导。Python 客户端使用 `route_openers`（或等价的共享
`request_routes` 接缝）；Git 和 Lean 使用相同的显式代理优先、直连恢复策略。每个网络
回执都保留路由名称，因此直连恢复不会被误认为来源级零结果。

## 已实现契约

- 只有 loopback 请求使用自动本地路由和空的 `ProxyHandler`，绕过继承的环境代理变量。
  包括 `.cn` 在内的公开域名不会依据后缀推断国家或用户所在地。
- 公开请求在用户显式配置 `RESEARCH_GUARD_FOREIGN_PROXY` 时优先使用它，随后使用安装器
  保存的选择；未配置时使用直连路由。
- 交互式安装器会询问一次可选代理 URL。回车（或非交互安装）记录直连选择，幂等重新安装/
  更新会保留已有选择。POSIX 与 PowerShell 安装器的显式非交互覆盖参数都是
  `--foreign-proxy URL`。
- 配置代理发生仅限传输的失败时，进入一次明确的直连恢复路径；路由名称与类型化错误会
  写入证据尝试记录。
- HTTP 状态错误和格式错误的载荷不会静默切换路由。
- 同一个检索切片内连续的 DBLP 请求会间隔两秒，符合 [DBLP 公布的建议](https://dblp.org/faq/Am%2BI%2Ballowed%2Bto%2Bcrawl%2Bthe%2Bdblp%2Bwebsite)：
  自动请求之间至少等待一到两秒。429、503 或连接断开仍是类型化失败单元，绝不会变成
  空结果。
- 当一份人工捕获覆盖完整查询计划时，带有 `matched_query_ids` 的导入记录只会重放到
  对应查询单元。为保持向后兼容，未声明查询范围的旧记录仍沿用全查询行为。
- `RESEARCH_GUARD_DISABLE_FOREIGN_DIRECT_FALLBACK=1` 可恢复严格的仅代理模式。
- 所有路由均失败时，抛出的错误会列出尝试过的路由名称和类型化原因，但不会保存代理凭据
  或原始秘密 URL。

## 验证边界

重点回归测试模拟代理 TLS/传输失败后直连成功，验证带路由标签的证据、严格仅代理模式，
并确认所有路由中断仍是类型化的 `SourceTransportError`。现有的限流、loopback 绕过、
适配器和新颖性覆盖测试保持不变。跨平台测试还检查未配置状态、环境代理清理、持久化以及
安装器询问/保留行为。在线 smoke 只使用官方 Crossref 和 arXiv API 并报告 HTTPS 记录；
不会把网络可达性转化为新颖性或质量结论。

2026-09-03，在类似新加坡的直连 smoke 中移除了所有环境代理变量和
`RESEARCH_GUARD_FOREIGN_PROXY`，使用空的临时 `RESEARCH_GUARD_HOME`，并解析为
`foreign-direct`。Crossref 返回一条记录（DOI `10.1007/978-3-031-84300-6_13`），
arXiv 返回一条预印本（`2209.15001v3`）。这证明修正后的未配置路由可以在当前环境访问
官方端点，但这只是传输证据。记录分别为
[`10.1007/978-3-031-84300-6_13`](https://doi.org/10.1007/978-3-031-84300-6_13)
和 [`arXiv:2209.15001v3`](https://arxiv.org/abs/2209.15001v3)。

2026-09-05 的新加坡主机验证尝试了全部 120 个绑定的来源—查询单元，并暴露出两个后续
缺陷：DBLP 未限速的突发请求在前序单元成功后出现 429/503/断连；仅属于一个查询的
11 条 Google Patents 记录被计入全部八个单元。定向测试现已冻结两秒 DBLP 间隔和逐记录
查询范围。这次验证只构成网络与计数证据；DBLP 覆盖未完成时不支持新颖性 PASS。

修复后，同一主机上的独立在线烟测完成了三次 DBLP API 请求；观测到的请求启动间隔为
2.125 秒和 3.375 秒，分别返回 1、0、1 条记录。这验证的是当前可达性与真实限速路径，
不是完整的绑定查询覆盖，也不构成新颖性 PASS。
