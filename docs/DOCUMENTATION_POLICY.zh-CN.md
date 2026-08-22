<!-- research-guard-doc-pair: documentation-policy | revision: 2026-08-22.1 -->
# 双语文档维护

[English](../README.md) | [简体中文](../README.zh-CN.md)

## 范围

只有英文路径和简体中文路径都登记在
[assets/documentation-parity.json](../assets/documentation-parity.json) 时，
Research Guard 才把该文档声明为双语。这个清单就是项目作出的全部双语承诺；
英文的内部来源记录或机器契约不会被静默标记成“已有翻译”。

每一对已登记文档使用唯一 pair id 和相同的修订标记。可发布源码树中的每一个
`.zh-CN.md` 文件都必须且只能属于一个配对。

## 强制维护流程

已登记配对中的任意一份文件发生变化时：

1. 在同一个聚焦变更中同时编辑英文和简体中文文件；
2. 除非有意修改配对清单，否则保持相同的二级章节顺序、公共链接目标和图片目标；
3. 进行人工双语审阅，检查含义、术语、遗漏、命令正确性、主张边界和自然语言质量；
4. 同时更新两份文档和清单中的共享修订标记；
5. 两份文件均完成审阅后，才执行
   `python -X utf8 scripts/documentation_parity.py --refresh-hashes`；
6. 人工检查生成的清单差异；
7. 执行 `python -X utf8 scripts/documentation_parity.py`，并运行
   [CONTRIBUTING.md](../CONTRIBUTING.md) 中的仓库与回归验证。

刷新命令只更新规范化内容哈希；它不会翻译、批准或静默修复任意一份文档。

## CI 强制核验什么

可执行验证器
[scripts/documentation_parity.py](../scripts/documentation_parity.py) 会检查：

- 清单 schema、唯一 id、安全相对路径和完整配对覆盖；
- 两份文件均存在，且 pair/revision 标记完全一致；
- 两种语言都具有清单声明的完整二级章节骨架；
- Markdown 链接目标完全相同，图片目标完全相同；
- 本地化 alt text 非空，以及本地图片的存在性、尺寸、宽高比、体积上限、来源记录
  和登记摘要；
- 必需的公共 token 与语言专属 token；
- 规范化内容哈希与组合配对哈希；
- 不存在未登记的 `.zh-CN.md` 文件。

负向测试和仓库级测试见
[tests/test_documentation_parity.py](../tests/test_documentation_parity.py)。

## CI 不会声称什么

结构一致不等于语义等价。章节、链接、图片、token 和规范化内容哈希一致，不能证明
译文准确、完整、自然或适合目标读者；这些判断必须由人工双语审阅完成。CI 只报告
它实际执行的核验，绝不会把结构 PASS 冒充为语言质量 PASS。

同理，README 图片只是方向引导，不是科研主张的证据。图片来源和视觉审计不能证明
科学结论正确。

## 新增双语配对

创建两份文档，在
[assets/documentation-parity.json](../assets/documentation-parity.json) 中新增一个
配对记录，声明完整的二级章节映射和必要的非语言 token，并在两份文件中加入相同的
pair/revision 标记。若共享图片，还要声明尺寸、宽高比、体积、来源与摘要契约。随后
刷新哈希、增加聚焦的正向/负向测试，并在发布前完成人工审阅。
