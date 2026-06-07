# EPI 中文链路与结构总览

文档权威分工（doc map）见 `docs/epi-linkage.md` 顶部；本文档只承担中文导航层，不复制完整 pipeline 事实。

## 一句话定位

EPI 是通用论文插件，不默认任何学科方向。它把用户画像/config 和当前问题转成可审计的论文知识流水线：

```text
主题/问题 -> 增量检索 -> 排序与去重 -> PDF 采集 -> MinerU 解析
-> source-first reader/critic -> staging evidence package
-> human approval -> PRW/Codex/Claude wiki ingest agent
-> final-source-review -> record-wiki-ingest
```

完整 8 阶段链路事实、artifact 路径、CLI 语义和安全门见 `docs/epi-linkage.md` 的主链路章节；本文档只给继续开发和接手时的地图。

## 核心心智模型

EPI 当前分三层工作：

| 层级 | 解决的问题 | 主要能力 | 关键产物 |
| --- | --- | --- | --- |
| 主题纵向层 | 最近有什么新论文、是否漏掉分支、先读哪几篇 | `topic-tracking`、`dry-run`、`research-queue` | `_epi/runs/*`、`_epi/reviews/*`、coverage/backlog |
| 单篇证据层 | 这篇论文是否真的读懂、公式/图/表是否保留 | acquire、MinerU、reader、critic、paper-gate | `_epi/raw/<slug>/*`、`evidence-index.json`、`claim-support.json` |
| Wiki 沉淀层 | 最终页面里的 claim 能否回溯到原文证据 | `wiki-ingest-handoff`、`wiki-provenance`、`record-wiki-ingest` | `_epi/staging/papers/<slug>/*`、`final-source-review.json`、`wiki-ingest-record.json` |

三层分别保证广度、深度和可信回溯。reader/critic 是辅助导航和审计层，不替代 `paper.pdf`、MinerU Markdown、TeX、images 和 manifest。

## 常用入口

```powershell
python scripts\orchestrator.py doctor --json
python scripts\orchestrator.py config-status --vault <vault> --json --include-values --include-runtime
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 20 --vault <vault> --json
python scripts\orchestrator.py report --run-id <run-id> --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault> --json
python scripts\orchestrator.py research-queue --vault <vault> --json
python scripts\orchestrator.py paper-gate --slug <slug> --vault <vault> --json
python scripts\orchestrator.py wiki-ingest-handoff --slug <slug> --vault <vault> --json
python scripts\orchestrator.py record-human-approval --slug <slug> --approved-by <name> --scope run-wiki-ingest-agent --vault <vault> --json
python scripts\orchestrator.py record-wiki-ingest --slug <slug> --page <final-page.md> --approved-by <name> --source-review <final-source-review.json> --vault <vault> --json
```

## Skill 分工

| Skill | 何时使用 | 边界 |
| --- | --- | --- |
| `config-setup` | 首次配置、修改 profile/runtime/确认门 | 不跑论文流程 |
| `paper-discovery` | 单轮检索、query plan、排序、报告 | 不维护长期主题账本 |
| `topic-tracking` | 持续追踪、net-new、coverage/backlog | 不替代底层检索 |
| `paper-ingest` | 已选论文进入 raw、MinerU、source-staging、handoff | 不写最终 Obsidian 页面 |
| `mineru-paper-parser` | PDF -> Markdown/TeX/images/manifest | 不做学术判断 |
| `wiki-provenance` | 最终页 claim support 和 evidence route | 不替代源论文重读 |
| `wiki-setup` | 初始化、检查、修复、重置 paper wiki vault | 不检索论文、不写最终知识页 |
| `run-lifecycle` | 清理 `_epi/runs` 过渡态 | 不删 raw/staging/final wiki |
| `skill-aware-evolve` | 基于证据提出受控优化 | 不直接改用户配置 |

## 文献 Wiki 七类页面契约

正式知识沉淀继续保留 7 类研究页面：`references/` 单篇证据页，`concepts/` 方法/理论/术语页，`derivations/` 推导与理论复建页，`experiments/` 复现与实现判断页，`synthesis/` 跨论文综合页，`reports/` 低负担阅读入口页，`opportunities/` 创新机会页。

page-family/frontmatter 的人读 canonical 是 PRW `plugins/PRW/rules/wiki-writing-standard.md`。EPI 只在这里保留索引，不复制完整字段清单。

正式页 frontmatter 至少覆盖 `title`、`category`、`page_family`、`tags`、`aliases`、`sources`、`summary`、`provenance`、`base_confidence`、`lifecycle`、`lifecycle_changed`、`tier`、`created`、`updated`。record 前的研究审阅字段包括 `theory_reconstruction`、`formula_derivation`、`figure_table_evidence`、`novelty_type`、`implementability`、`reproducibility_risk`、`research_gap`、`cost_level`。

PRW `$paper-research-wiki` 是正式论文 wiki 写入和维护的用户级入口；`epi-paper-deposition` 只作为 EPI `wiki_deposition_task.json`、旧 handoff 和 record provenance 的 compatibility adapter，旧名 `epi-wiki-deposition` 只是兼容 alias。

## 安全边界

- `dry-run` 只写 `_epi/runs` 和 `_epi/reviews`。
- `prepare-ranked` 默认停在 source-staging，不写最终 wiki。
- agent-mediated wiki ingest 前必须有 `human-approval.json`。
- final wiki agent 写页面前必须读目标 vault contract。
- final wiki 页面必须保留 provenance，不把推断写成源论文事实。
- `record-wiki-ingest` 只记录完成态，不改最终页。
- token、API key、MinerU token 不写入报告、文档或配置预览。
- 安装 cache 不是源码开发位置。

## 推荐阅读顺序

开发者第一次接手时按这个顺序读：

1. 本文档：先建立整体地图。
2. `docs/epi-linkage.md`：理解主链路契约和安全门。
3. `docs/structure.md`：定位源码模块和 artifact。
4. `docs/workflow.md`：确认安装后的用户级短命令。
5. 相关 skill 的 `SKILL.md` 和 `references/`：只读当前任务需要的部分。

真正执行论文流程时按这个顺序看 artifact：

1. `_epi/runs/<run-id>/report.md`
2. `_epi/runs/<run-id>/rank.json`
3. `_epi/raw/<slug>/metadata.json`
4. `_epi/raw/<slug>/parse-record.json`
5. `_epi/raw/<slug>/reader/claim-support.json`
6. `_epi/raw/<slug>/critic/critic-quorum.json`
7. `_epi/staging/papers/<slug>/briefs/reading-report.md`
8. `_epi/staging/papers/<slug>/wiki-ingest-brief.json`
9. `final-source-review.json`
10. `_epi/raw/<slug>/wiki-ingest-record.json`
