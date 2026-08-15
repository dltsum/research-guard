# Research Guard

一个可迁移到其他 Agent 的 Windows x64 科研 Skill/插件：从研究想法、文献与
撞车检索，到实验、引用写作、公式核验、科研作图和全文审计。关键约束由 MCP、
Hook、哈希收据和可执行门禁保证，而不是只靠提示词。

> **只有一个安装包。** 例如 **289.5 MiB** 与
> **303,582,309 字节**是同一体积的两种单位写法，不是 30 GB。Lean/Mathlib、
> TeX 安装树等大型环境不进入 Git 或 ZIP；用到且缺失时才询问用户是否安装。

## 直接复制给 Agent 安装

把下面整段发给另一个支持本地文件与命令执行的 Agent：

```text
请安装 Research Guard Skill：https://github.com/dltsum/research-guard
只使用 GitHub Releases 中的 research-guard-windows-x64-modular.zip（约 300 MB），不要把源码 ZIP 当成安装包。下载 SHA256SUMS.txt 并核验 SHA-256，解压后执行 research-guard/scripts/install.ps1。安装完成后验证传统 Skill、Codex 插件、15 个 MCP 工具和离线核心 Python 运行时。不要自动安装任何可选依赖：当某项功能需要缺失的 Git、TeX 或 Lean/Mathlib 时，先向我展示复用现有环境、安装、not_now 三个选择以及下载/安装体积；只有得到我的选择后才能执行。若我选择 not_now，使用该组件声明的降级方案，并把未执行的检查明确标为 NOT_RUN，不能报告为 PASS。
```

- 仓库地址：[github.com/dltsum/research-guard](https://github.com/dltsum/research-guard)
- 单一安装包：[下载最新 Windows x64 模块包](https://github.com/dltsum/research-guard/releases/latest/download/research-guard-windows-x64-modular.zip)
- 完整依赖表：[REQUIREMENTS.md](REQUIREMENTS.md)

## 手动安装（Windows x64）

```powershell
$release = 'https://github.com/dltsum/research-guard/releases/latest/download'
Invoke-WebRequest "$release/research-guard-windows-x64-modular.zip" -OutFile research-guard.zip
Invoke-WebRequest "$release/SHA256SUMS.txt" -OutFile SHA256SUMS.txt
$expected = ((Get-Content SHA256SUMS.txt | Where-Object { $_ -match 'research-guard-windows-x64-modular.zip' }) -split '\s+')[0].ToLowerInvariant()
$actual = (Get-FileHash research-guard.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 mismatch: $actual" }
Expand-Archive research-guard.zip -DestinationPath research-guard-release
powershell -NoProfile -ExecutionPolicy Bypass -File .\research-guard-release\research-guard\scripts\install.ps1
```

安装器会校验包内 `RELEASE_MANIFEST.json`，离线安装核心运行时，并注册传统
Skill 与 Codex 插件。安装完成即可进行核心科研工作；首次加载只展示功能与依赖
清单，不要求一次性配置所有组件，也不会自行下载或启动编译器。

## 一眼看懂怎么用

直接对 Agent 说自然语言即可，Hook 会把请求路由到最多 2–3 个模块：

| 你可以这样说 | 自动触发的能力 | 关键约束 |
|---|---|---|
| “分析我的研究领域并查一下这个 idea 是否撞车” | 领域识别、文献路由、查新 | 每条结果有 HTTPS 链接；方法一改立即作废旧收据并重查 |
| “帮我找论文并写 Related Work” | 文献检索、引用核验、学术写作 | 文献与引用强制给 DOI/原始记录超链接 |
| “审计这篇论文/实验/代码” | 2–3 角色全文审计 | 联网事实、数字、代码、实验和证据分别核验 |
| “核验全文公式” | Lean、Pint、SymPy、Z3、数值协议 | 五类结果分开；Lean 缺失时先询问，拒装则降级且不能最终 PASS |
| “编译这份 LaTeX/检查顶会模板” | TeX 编译与 venue evidence | TeX 缺失时先询问；拒装只做静态检查，不声称 PDF 已验证 |
| “做统计图、向量图或架构图” | 数据绑定的科研绘图 | 输出 SVG/PDF/PNG、源数据哈希与最终尺寸审计 |
| “深入这个新领域并找专业 Skill” | GitHub/SkillsHub 检索、隔离、2–3 轮 SkillOpt | 缺 Git 时先询问；拒装只保留发现能力，不准入远程 Skill |

可选依赖的选择与降级不是口头约定：`dependency_manager.py` 与
`research_design.dependency_action` 会返回机器可读状态、精确体积、选择命令和
降级边界。详情见 [REQUIREMENTS.md](REQUIREMENTS.md)。

Research Guard is also a traditional Skill and a Codex plugin for
evidence-bounded academic research. It combines concise agent instructions with
executable MCP routes, hooks, hash-bound receipts, and fail-closed gates.

## Why it exists

Research workflows often fail at the boundaries: a changed method keeps an old
novelty result, a citation resolves but does not support the claim, an equation
introduces an unused symbol, or a successful program exit is mistaken for a
valid experiment. Research Guard keeps these boundaries explicit and
machine-checkable.

It does **not** prove global novelty, paper correctness, venue acceptance, or
research quality. Every PASS is limited to the recorded sources, artifacts,
hashes, and checks.

## Core guarantees

- Detects the research field and routes literature work across publications,
  patents, trials, grants, datasets, software, and preregistrations as required.
- Covers seven broad and fourteen specialized discipline profiles. An
  unregistered field automatically receives a bounded, hash-bound first-use
  profile from official public sources; the user is warned that initialization
  may take several minutes.
- Treats history and humanities as more than journal search by tracking books,
  chapters, editions, reviews, archives, catalogs, and primary-source evidence.
- Invalidates the novelty receipt after every registered method change and
  blocks progress until the complete collision search is rerun.
- Returns a clickable HTTPS DOI or primary-record link for every literature,
  citation, and collision item.
- Separates bibliographic identity from claim support through exact source
  locators and claim-evidence relations.
- Supports immutable preregistration/deviation records, statistical
  recomputation, resource-bounded reruns, human-only review decisions, and
  correction/retraction monitoring.
- Selects only 2-3 audit roles at effort no higher than `high`.
- Reports five formula records separately: one manuscript-wide Lean proof file,
  Pint dimensional compatibility, SymPy algebraic equivalence under declared
  assumptions, Z3 parameter satisfiability, and hash-bound numerical
  boundary/limit/overflow tests admitted by the paper protocol.
- Calibrates review coverage from official public OpenReview API v2 records
  without predicting acceptance, and flags scientific-image provenance,
  duplicate, metadata, and pixel evidence for expert review without alleging fraud.
- Requires exact venue/year/track/stage evidence before recommending headings,
  layout, formatting, or narrative style.
- Produces data-bound statistical figures and editable vector diagrams with
  source and output hashes.
- Presents limitations and possible ethics omissions as decision checklists;
  it does not silently remove uncertainty.

See [the architecture](docs/ARCHITECTURE.md) for ownership and enforcement
boundaries, and [discipline support](docs/DISCIPLINE_SUPPORT.md) for the current
field matrix and public catalogs.

## Source checkout

The Git repository intentionally excludes binary payloads larger than GitHub's
normal source limit, cached venue pages, template archives, and paper PDFs.
Those assets remain in the hash-verified modular release.

End users should download the release artifact above. `git clone` is a small,
development-only source checkout and deliberately cannot run `install.ps1`
without a built `RELEASE_MANIFEST.json` and audited payloads; cloning never
downloads a 30 GB dependency tree.

For development:

```powershell
python -m pip install -r requirements-dev.txt
python scripts/run_incremental_tests.py --pattern "test_p10_*.py" --pattern "test_p11_*.py" --pattern "test_p12_*.py" --pattern "test_p13_*.py" --pattern "test_p14_*.py" --suite local-development
```

Verified test files are recorded individually and are resumed only when their
contract hash still matches. Use `--no-resume` for a deliberate clean run.

## Resource contract

Research Guard does not need 6 GiB for its own work. All optimizer, regression,
packaging, compiler-validation, and managed reproduction work is serialized:

| Profile / boundary | Limit |
|---|---:|
| Total task-owned aggregate working set | 512 MiB |
| Standard worker process tree | 384 MiB |
| Standard orchestrator/installer | 128 MiB |
| Lean worker process tree | 464 MiB |
| Lean orchestrator | 48 MiB |
| Parallel workers | 1 |
| Machine headroom before start | 768 MiB |
| Machine low-water abort | 512 MiB |
| GPU | disabled |

A Windows Job Object owns each worker tree; a 10 ms monitor sums the physical
working set of every owned process and terminates only that tree on a limit or
machine low-water violation. Lean gets more of the same 512 MiB envelope and
trims reclaimable working sets above 384 MiB, trading speed for memory.
Scientific runtimes use one thread. Test files and SkillOpt rounds write atomic,
hash-bound receipts, so work proceeds in small units instead of repeatedly
loading the entire suite.

## Repository layout

```text
.codex-plugin/      Codex plugin manifest
agents/             Skill UI metadata
assets/             discipline/source catalogs, schemas, licensed assets, payload manifests
hooks/              deterministic prompt-time routing and invalidation
references/         on-demand agent references
scripts/            MCP server, executable guards, installers, tests and builders
skills/             five focused Skills with progressive disclosure
tests/              deterministic P0-P14 regression suites
docs/               architecture, upstream audit, provenance and development logs
.github/            CI, issue forms and pull-request template
SKILL.md             traditional Skill bootstrap and mandatory invariants
```

The plugin keeps 15 top-level MCP tools. New capabilities are admitted as typed
subroutes under a canonical owner instead of expanding the surface indefinitely.

## Build artifacts

Build a developer integrity archive (this is not an end-user install asset):

```powershell
python scripts/build_public_package.py --output dist/research-guard-source.zip
```

Build the complete, hash-manifested migration artifact on a release workstation
where the audited payloads are present:

```powershell
python scripts/build_modular_package.py --output dist/research-guard-windows-x64-modular.zip
```

Both builders run inside the 384 MiB worker limit and stream files. The modular
builder refuses archives above 1 GiB.

## Evidence, dependencies, and provenance

- [Complete installation requirements](REQUIREMENTS.md)
- [Dependency and first-load model](references/dependencies.md)
- [Architecture and trust boundaries](docs/ARCHITECTURE.md)
- [Cross-discipline support and initialization](docs/DISCIPLINE_SUPPORT.md)
- [Original and additional upstream audit](docs/UPSTREAM_AUDIT.md)
- [P12 component registry](docs/provenance/P12_COMPONENT_REGISTRY.json)
- [P13 release-final verification report](docs/provenance/P13_RELEASE_VERIFICATION.md)
- [P14 cross-discipline and release verification](docs/provenance/P14_DISCIPLINE_AND_RELEASE.md)
- [P12 overlap audit](docs/provenance/P12_OVERLAP_AUDIT.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

Anonymous scholarly routes are preferred where an official public interface
exists. Domestic sources are accessed directly; the local port 7897 proxy is
used only for unavailable foreign routes. Subscription indexes and other
non-anonymous systems require user-supplied official exports and never accept an
arbitrary web page as registry evidence.

## Contributing and security

Read [CONTRIBUTING.md](CONTRIBUTING.md) before changing a gate, source adapter,
or canonical owner. Report vulnerabilities according to
[SECURITY.md](SECURITY.md). Project decisions follow [GOVERNANCE.md](GOVERNANCE.md),
and usage questions follow [SUPPORT.md](SUPPORT.md). Never submit papers, credentials, private provider
responses, or unreleased research data to an issue.

## License

Research Guard is available under the [MIT License](LICENSE). Included and
referenced third-party components retain their own licenses; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
