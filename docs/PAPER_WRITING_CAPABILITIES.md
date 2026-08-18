# 论文写作、协作、审稿与终稿能力全清单

本文档列出 Research Guard 在论文生命周期中的完整能力、触发方式、实际实现、硬约束、依赖和降级边界。它区分“主智能体在 Skill 契约下完成的写作判断”和“本地脚本/MCP 强制执行的验证”，避免把提示词能力误写成程序证明。

## 四种实现状态

| 标记 | 含义 |
|---|---|
| `EXECUTABLE` | 有脚本、MCP 状态、哈希或收据约束，可测试并显式失败。 |
| `AGENT-CONTRACT` | 由主智能体进行语义判断，但必须遵守 Skill 工作流并留下证据。 |
| `OPTIONAL-DEPENDENCY` | 需要 TeX、Lean/Mathlib 或在线服务；缺失时先询问，拒绝安装则明确降级。 |
| `NOT-CLAIMED` | 系统明确不声称能够证明的事项。 |

## 从想法到终稿的 11 种工作模式

这些模式由主智能体根据完整请求显式选择，不用关键词分类器或小模型自动路由。一次通常选择 1–3 个必要模块。

| 模式 | 典型触发 | 主责模块 | 主要产物 | 强制门禁 |
|---|---|---|---|---|
| 全流程写作 | “从研究结果写成论文” | `academic-language-guard` + `paper-audit-guard` | 论文主线、章节草稿、审计收据 | 新方法先撞车；引用有链接；终稿全文审计 |
| 计划 | “规划写作步骤” | 主智能体 + 研究推进契约 | 阶段、检查点、证据清单 | 不设任意总时限；阶段结果持续保存和回显 |
| 大纲 | “给我论文大纲” | `language_assist` venue 子路由 | 证据约束的大纲 | venue/year/track/stage 未核验时不得自造章节 |
| 分节起草 | “写 Introduction/Methods” | 主智能体 + `language_assist` | 与 claim/evidence 对齐的段落 | 不补造结果、数字或引用 |
| 文献综述 / Related Work | “写 Related Work” | `citation_literature` + `language_assist` | 可追溯综述与比较维度 | 每个文献结果保留 DOI/原始记录 HTTPS 链接 |
| 修订 | “按审稿意见修改” | 主智能体 + `reviewer_response` artifact | issue-by-issue 补丁、证据和状态 | 不迎合式改结论；改方法立即废止旧撞车证据 |
| 修订教练 | “告诉我怎样改，不直接改” | 主智能体 | 优先级、风险和补证建议 | 建议与已执行修改分开 |
| 摘要 | “写摘要/双语摘要” | `academic-language-guard` | 结构化摘要 | 数字、因果、范围和不确定性不得漂移 |
| 格式转换 | “转 LaTeX/检查模板” | venue evidence + TeX compile | venue 绑定的 TeX/PDF | 精确官方模板；TeX 缺失只做静态检查且不得声称编译通过 |
| 引用检查 | “检查参考文献/格式” | citation audit + DOI formatter | 身份、格式、claim-support 结果 | DOI 身份正确不等于支持正文主张 |
| rebuttal / disclosure audit | “写 rebuttal/AI 使用声明” | `reviewer_response` + venue evidence | 回复问题板或披露清单 | 遵循当前 venue 政策；未解决项不能伪装为 answered |

## 写作与语言能力

### 1. 论证主线和证据链

- `AGENT-CONTRACT`：先建立 paper spine：研究问题、主张、证据、边界和章节依赖，再写正文。
- `EXECUTABLE`：`paper_audit` 会从 UTF-8 稿件抽取 bibliographic、quantitative、comparative 和 scope claims，并要求逐条 `claim_evidence_items`。
- `EXECUTABLE`：数字证据检查正文值是否实际出现在冻结稿件中，核对百分号、单位、精确匹配或登记的舍入容差。
- `NOT-CLAIMED`：结构完整不证明科学结论正确；终稿仍需选定角色、联网事实和实验/公式验证。

### 2. 非防御性学术语言

- `EXECUTABLE`：识别 imagined-critic disclaimer、disclaimer-first framing、internal reviewer narration、generic throat-clearing、重复 hedge stack 和空泛宣传归因。
- 单个 `may/可能` 不会被机械删除；已登记的认识论限定词、范围边界、伦理披露和实质 limitation 会被保护。
- limitation 和潜在伦理遗漏只生成清单，由用户选择保留、补充或指出已在何处披露；工具不能替用户作伦理判断。
- 任何可能改变含义的改写都要求编辑原稿、重新 plan/analyze，而不是用一条理由豁免。

### 3. “去 AI 痕迹”的合规实现

- `EXECUTABLE`：检查聊天残留、knowledge-cutoff 表述、模板化开场、机械均匀结构、空泛评价和 assistant process residue。
- 检查结果只叫“文本模式”，不推断作者身份，也不声称通过 AI 检测器。
- `AGENT-CONTRACT`：修订目标是具体、自然、证据贴合和作者声音一致；拒绝固定句长、同义词替换、故意错字和检测器规避。
- `NOT-CLAIMED`：无法保证任何 AI 检测器给出某个分数，也不帮助隐瞒应披露的 AI 使用。

### 4. Nature-accessible 表达

- `AGENT-CONTRACT`：可选择 `nature-accessible` 写作配置：概念先解释、减少不必要术语与缩写、句子直接、标题可被跨学科读者理解、避免把宣传语当贡献。
- 该配置来自 Nature Portfolio 的一般写作建议，不是所有 Nature 旗下期刊的统一格式。写作时必须同时核验目标刊物的精确 author instructions：[Nature Portfolio writing guidance](https://www.nature.com/nature-portfolio/for-authors/write)、[Nature editorial criteria](https://www.nature.com/nature/for-authors/editorial-criteria-and-processes)。
- `EXECUTABLE`：限定词、数字、引用、limitations 和披露仍受 language/paper gates 约束，不能为了“更像 Nature”而强化主张。
- `EXECUTABLE`：若是具体刊物、文章类型或格式，必须登记 exact venue/year/track/stage 官方 policy/template receipt；缺资料先联网，不得自动发明章节和布局。

### 5. 翻译

- `EXECUTABLE`：源文和译文同时哈希绑定；检查数字、百分比、引用、URL、代码标识符、LaTeX refs、术语表、否定、因果和不确定性。
- 丢失 `not/不`、`may/可能`、引用、数字或约定术语会 BLOCKED。
- 翻译中的 limitation/伦理线索仍进入用户决策清单。

### 6. 修辞 RAG 与作者声音

- `EXECUTABLE`：rhetorical card 只保存来源链接、定位、段落功能、证据放置、转折关系和短验证片段，不保存整段论文或全文模板。
- 检索一次返回 2–4 张卡；复用“结构动作”，不复制措辞或做同义改写。
- `AGENT-CONTRACT`：若用户提供至少三篇自己的已发表文章，可总结稳定的组织习惯和术语偏好；不得模仿未授权作者，也不得覆盖当前证据边界。

## venue、顶会与排版

- `EXECUTABLE`：精确键为 venue + year + track + stage；相邻年份、相近会议、CCF 分级或一篇高分文章都不能替代当前官方规则。
- `EXECUTABLE`：内置若干 venue profile 和 CCF A/B 发现目录；缺失目标时返回 `ONLINE_ACQUISITION_REQUIRED`，主智能体继续搜索官方 policy/template 和源定位的 exemplar evidence。
- 官方 policy/template 决定页数、匿名、章节、图表和文件要求；award/high-score papers 只用于描述叙事习惯，不能升级为硬规则。
- `OPTIONAL-DEPENDENCY`：TeX 可编译时记录引擎、退出码、日志和产物；缺失时先询问复用/安装/not_now。静态检查不能称为“模板编译通过”。
- `AGENT-CONTRACT`：顶会协作包括大纲、逐节草稿、claim-to-section 映射、revision patch、caption/table wording、rebuttal 和终稿一致性。

## 引用与 Related Work

- 任何文献检索、撞车、写作引用和论文分析输出都必须给可点击 HTTPS DOI、arXiv、出版社、会议论文集或正式原始记录链接。
- 引用身份、格式和主张支持分开核验。Crossref DOI metadata 可验证身份；正文 claim support 必须使用源定位证据。
- Related Work 不按“作者 A 做了 X、作者 B 做了 Y”堆砌；主智能体按方法假设、证据、数据、边界或失败模式组织比较。
- 新增或改动方法后，旧 novelty receipt 立即失效；先重新撞车搜索，再写 novelty/related-work 论述。
- 伪造、无法解析或与主张无关的引用会失败，不因引用格式正确而放行。

## 公式、数字、代码和实验

- 全文公式使用单个 Lean 文件；`autoImplicit false`；每个公式和参数登记 purpose、used_by 和实际使用；禁止 `sorry/admit/axiom/unsafe`、非法、无用或混淆参数。
- 五个通道分别报告：Lean 逻辑、Pint 量纲、SymPy 代数、Z3 约束可满足性、数值/协议边界。某通道未运行不等于 PASS。
- 数值模型脚本必须哈希绑定；每个极限、溢出和边界用例先证明处于论文冻结协议允许范围。
- 代码/实验角色检查 raw results、数据来源/许可、配置、seed、聚合、表格重算、dead path、评估范围和版本。
- 任何已报告数字变化都会要求重审正文、表格、图、公式范围、舍入和 OCR 可见标签；旧收据失效。

## 科研作图与图像完整性

- `EXECUTABLE`：统计图绑定原始 CSV、估计量、不确定性、replicate unit、missing policy、预登记排除和 seed；输出 SVG/PDF/300-DPI PNG、spec、manifest 和复现脚本。
- `EXECUTABLE`：禁止数据图调用生成式图片、装饰性 3D、彩虹色、双轴、截断柱状图基线、静默删行和自动突出 `Ours`。
- 主智能体显式选择 2–3 个 figure roles；图工具不再根据关键词自动选择。
- final-size visual review 必须逐项确认：文字可读、无裁切、legend/uncertainty 清楚、颜色有冗余编码、语义准确、panel hierarchy、无文字/线条/点/图例遮挡、空间利用平衡、文字与线条对齐、margin/gutter 平衡。
- 有目标刊物时，plan 必须绑定 30 天内核验的官方 figure policy/rules URL 和具体规则；visual review 额外要求 `venue_style_conformant=true`。
- “最大化利用空间”不是把画布塞满，而是在最终物理尺寸下减少无意义空白，同时保留层级、可读性、标注与必要留白。
- 科研图像完整性审计检查原图/处理图/拼图来源、声明的变换、元数据、像素 clipping、图/区域近重复；自动信号只表示 `REVIEW_REQUIRED`，不推断造假。专家必须在原分辨率逐条结案。

## 三套审稿相关接口

### A. 2–3 角色全文审计

主智能体从 venue fit、methodology/statistics、domain literature、interdisciplinary impact、adversarial logic、formal math、code/experiment、OpenReview calibration、scientific-image integrity 和 AI-reviewer robustness 中只选 2–3 个必要角色，effort 最高 `high`。每个角色必须提交 findings 与 numeric checks；联网事实、数字、公式、代码、实验和引用分别核验。

### B. OpenReview 审稿校准

- 使用官方公共 API v2 forum/note 记录，保留可点击 forum URL。
- 比较评审类别覆盖、证据具体性和遗漏，不用关键词频率冒充严重度。
- fixture 只能测试接口，不能关闭真实校准。
- `NOT-CLAIMED`：不预测接收、不模拟某位审稿人、不把历史评分当本稿概率。

### C. reviewer response / rebuttal

- `research_design` 的 `artifact_type=reviewer_response` 保存 venue、decision type、response mode、字数限制和问题板。
- 每条意见都有 issue ID、reviewer、raw anchor、状态、response 和 evidence links；没有证据不能标 `answered`。
- `needs_user_input` 和 unresolved 项会阻断终稿；修订创建新 artifact/version，不覆盖旧记录。
- 回应批评时先回答事实和补证，再解释边界；不得通过删除 limitations、夸大贡献或承诺未做实验来“显得积极”。

## AI 审稿：可选主动适配与鲁棒性审计

### 最近研究告诉了我们什么

| 研究 | 观察 | 本项目如何使用 |
|---|---|---|
| [LLM-REVal](https://arxiv.org/abs/2510.12367) | 报告了与文本特征、作者来源和批判性表述有关的评分差异。 | 作为公平性暴露；绝不删除批判、风险或 limitation。 |
| [How Can Rhetoric Reward-Hack AI Reviewers?](https://arxiv.org/abs/2608.08975) ([DOI](https://doi.org/10.48550/arXiv.2608.08975)) | 4,200 篇全文控制实验中，evidence framing 与 novelty stance 的正负差异最大，scope framing 次之；递归和 reviewer-guided 重写没有稳定额外收益。 | 主动模式优先测试证据、创新和范围框架；跨模型评价并对波动惩罚，不假定策略稳定迁移。 |
| [TitleTrap](https://aclanthology.org/2025.eval4nlp-1.10/) ([DOI](https://doi.org/10.18653/v1/2025.eval4nlp-1.10)) | 只改变标题形式也可能改变部分 LLM 评分；branded colon title 往往较高，疑问标题有时降低严谨性判断。 | 主动模式可生成真实、venue-compliant 的 branded/plain 标题候选并实测；鲁棒模式只报告敏感性。 |
| [Evaluating Reviewer Guideline Design](https://arxiv.org/abs/2607.22553) ([DOI](https://doi.org/10.48550/arXiv.2607.22553)) | 官方会议审稿指南产生的自动评审与人类判断更一致；严格 rubric 化反而可能降低表现。 | 优化必须绑定当前官方审稿指南，但保持整体叙事，不能关键词堆砌。 |
| [Paraphrasing Adversarial Attack](https://arxiv.org/abs/2601.06884) | 报告同义改写搜索可改变 LLM reviewer 分数，并存在模型偏好。 | 主动模式允许显式候选搜索，但要求语义/证据保护与同一跨模型面板；鲁棒模式仍拒绝候选字段。 |
| [When Your Reviewer is an LLM](https://arxiv.org/abs/2509.09912) | 大规模比较报告 LLM/human 行为差异、校准和 prompt-injection 风险。 | 至少用多运行/多模型观察敏感性；单一评分不作为质量或接收概率。 |
| [Justice in Judgment](https://aclanthology.org/2026.findings-acl.14/) ([DOI](https://doi.org/10.18653/v1/2026.findings-acl.14)) | 控制元数据实验报告 affiliation/seniority 等偏差暴露。 | 在协议允许时建议匿名；拒绝添加或突出 prestige signal。 |
| [20K ICLR review randomized study](https://arxiv.org/abs/2504.09737) | 研究 LLM feedback 对评审具体性、可行动性和 rebuttal 互动的影响。 | 用于评审完整性/可行动性清单，不用于预测本稿评分。 |
| [Style Over Substance](https://aclanthology.org/2025.coling-main.21/) ([DOI](https://doi.org/10.18653/v1/2025.coling-main.21)) | 一些 evaluator 对风格瑕疵的惩罚可能超过事实错误，并建议多维评分。 | 单列 factuality/evidence/clarity 等维度，禁止聚合高分掩盖事实退化。 |
| [Turning Bias into Bugs](https://openreview.net/forum?id=7g23tYAIDC) | 黑盒 style edit 在多种 LLM judge 上可人为抬分。 | 用作候选搜索与模型特异性的边界证据；隐藏指令、欺骗和事实改变仍禁止。 |

这些研究支持“对特定 AI reviewer 配置进行主动适配”这一可选功能，但不支持跨模型、跨 venue 的稳定录用配方。因此系统只对用户显式指定、哈希绑定的 reviewer panel 做局部优化，并同时报告迁移边界。

任何需要 LLM reviewer 协助的步骤，先由 `research_design.delegation_action`
登记。默认使用一个入门/经济型原生 subagent、`low` 推理和串行执行；不可用
时由主智能体本地完成，不静默切换外部 API。同宿主或同模型 subagent 不能
冒充独立多模型面板。只有用户明确点名外部供应商，或注册协议确实要求跨供应商
身份且用户授权后，才能进入外部 API 例外；每次输出均绑定项目内产物哈希。

### A. 主动适配优化（可选，用户显式启用）

触发示例：“主动优化这篇稿子，让 AI 审稿人更容易给高分”。主智能体必须先向用户展示该模式；只有用户选择后才能提交 `selected_by=user`。

1. `review_action=ai_optimize_plan`
   - 提供 versioned `ai_optimization_id`、基线 `paper_files` 和 `optimization_goal=maximize_ai_reviewer_score`；
   - 强制联网核验最新修辞实验、官方 guideline 实验与 TitleTrap，输出原始 HTTPS 链接；
   - 绑定精确 venue/year/track/stage 的官方 policy、reviewer guideline、核验时间和加权 criteria；
   - 输出 evidence framing、novelty stance、scope framing、title presentation、reviewer navigation、language polish 六类候选方向。
2. `review_action=ai_optimize_register`
   - 注册 1–8 个完整候选稿及其变更维度；
   - 候选稿的引用、数字、公式和含 limitation/伦理/风险/批评/负面结果的段落必须与基线一致；
   - 隐藏文本、直接 reviewer 指令和伪造 prestige 直接失败；
   - 返回每个候选稿的输入哈希和官方 rubric 哈希。
3. 用相同 panel 评分
   - 基线和每个候选稿必须由同一组至少两个 reviewer models、相同 prompts、相同量表与相同官方 criteria 评价；
   - 每条记录绑定 run/model/prompt/input/rubric/review-output hash，并分别给 overall 与所有 criterion 分数；
   - 每次评价明确提交 `meaning_preserved=true` 与 `evidence_preserved=true`，否则失败。
4. `review_action=ai_optimize_select`
   - 可执行 selector 使用 `normalized mean - 0.5 × population standard deviation`，再以官方加权 rubric、worst-panel score 和较小改动面作为 tie-break；
   - 允许选择基线，即没有稳健提升时不强行选改写稿；
   - 选中稿应用后，受影响的 novelty、citation、language、formula、experiment、figure 和全文收据全部重跑；
   - 新一批使用新的 versioned ID，不设任意总时限，由用户预算或无稳健增益决定停止。

这是主动迎合特定 AI reviewer panel 的真实评分优化，不应再描述为单纯 robustness。结果仍不是接收概率，也不能保证迁移到其他模型、prompt、venue 或人类审稿人。

### B. 鲁棒性审计（不优化）

调用 `paper_audit`，令 `review_action=ai_robustness`，提供：

- `ai_review_audit_id`；
- UTF-8 `paper_files`；
- 至少三条刚联网核验、与内置 primary-record registry 对齐的 `ai_review_online_evidence`；
- 可选的至少两个 `model_evaluations`，每条绑定 run/model/prompt/input hash、score 和原始量表。

结果分开报告：

1. `manipulation_integrity`：隐藏/直接 reviewer 指令、prompt injection、零宽字符；
2. `presentation_sensitivity`：只做标题形式观察，不建议刷分；
3. `critical_topic_fairness`：保护 risk/ethics/limitation/negative result；
4. `metadata_bias_exposure`：身份和 prestige 暴露；
5. `model_specificity`：归一化跨模型/重复运行 spread，缺数据明确 `NOT_TESTED`。

鲁棒模式输入中出现 score-targeted variant/rank/selected/optimization target 仍会被拒绝；这些字段只能进入用户显式选择的 `ai_optimize_*` 流程。PASS 只表示当前哈希稿件未检出被禁操纵且证据刚完成核验，不表示论文高质量、公平审稿或录用概率。

## 终稿全量审计顺序

1. 冻结稿件、参考文献、代码/原始结果、图表和协议哈希。
2. 方法若有任何变化，先使旧撞车证据失效并完成新 novelty receipt。
3. 完成 citation identity 与 claim-support，所有文献输出含 HTTPS 链接。
4. 完成 language review；limitation/伦理清单由用户决定。
5. 若涉及公式，完成 Lean + Pint + SymPy + Z3 + numerical/protocol 五通道。
6. 若涉及实验，完成 raw/code/config/seed/recomputation/dead-path/evaluation-scope 审计。
7. 每张图通过 programmatic export audit 和 final-size visual review；目标刊物规则已绑定。
8. 按用户选择完成 AI-reviewer active adaptation；按需完成 OpenReview calibration、scientific-image integrity 和 AI-reviewer robustness。
9. 2–3 个角色提交 findings、numeric checks、在线来源与逐 claim 证据。
10. TeX/PDF 编译或明确降级，复核页数、匿名、交叉引用、caption、表格和 supplementary files。
11. `paper_audit verify=PASS` 后才能称终稿通过；任何被跟踪文件变更都会失效。

## 不会做的事

- 不伪造引用、数字、结果、实验、审稿意见或 venue 规则。
- 不把 OpenReview、LLM reviewer 或文本检测器输出当作接收概率。
- 主动模式可以围绕证据、novelty、scope、真实标题、导航和语言表现生成候选并按 AI reviewer 分数选择；不允许关键词堆砌、隐藏文本、prompt injection、伪造身份/名校信号或用高分掩盖事实退化。
- 不自动删除 limitation、伦理披露、失败、风险、批判性陈述或必要的 `may/可能`。
- 不声称静态 TeX 检查等于编译、自动图像 flag 等于学术不端、引用身份等于 claim support、风格相似等于作者身份。
