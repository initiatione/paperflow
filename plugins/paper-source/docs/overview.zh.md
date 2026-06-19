# Paper Source 中文链路与结构总览

文档权威分工（doc map）见 `docs/paper-source-linkage.md` 顶部；本文档只承担中文导航层，不复制完整 pipeline 事实。

## 一句话定位

Paper Source 是通用论文插件，不默认任何学科方向。它把用户画像/config 和当前问题转成可审计的论文知识流水线：

```text
主题/问题 -> MCP/CLI 检索 -> wiki reference-index 去重 -> 排序候选
-> Paper Wiki 沉淀/更新，或显式 source-staging -> human approval
-> Paper Wiki/Codex/Claude wiki ingest agent -> final-source-review -> record-wiki-ingest
```

完整 8 阶段链路事实、artifact 路径、CLI 语义和安全门见 `docs/paper-source-linkage.md` 的主链路章节；本文档只给继续开发和接手时的地图。

## 核心心智模型

Paper Source 当前分三层工作：

| 层级 | 解决的问题 | 主要能力 | 关键产物 |
| --- | --- | --- | --- |
| 主题纵向层 | 最近有什么新论文、是否漏掉分支、先读哪几篇 | `topic-tracking`、`discover-papers`、`dry-run`、`research-queue` | `_meta/reference-index.json`、`_paper_source/runs/*`、coverage/backlog |
| 单篇证据层 | 这篇论文是否真的读懂、公式/图/表是否保留 | acquire、MinerU、reader、critic、paper-gate | `_paper_source/raw/<slug>/*`、`evidence-index.json`、`claim-support.json` |
| Wiki 沉淀层 | 最终页面里的 claim 能否回溯到原文证据 | `wiki-ingest-handoff`、`wiki-provenance`、`record-wiki-ingest` | `_paper_source/staging/papers/<slug>/*`、`final-source-review.json`、`wiki-ingest-record.json` |

三层分别保证广度、深度和可信回溯。reader/critic 是辅助导航和审计层，不替代 MinerU Markdown 主证据；PDF、figure/formula indexes、images 和 manifest 只在 Markdown 缺失、错误、歧义或视觉证据需要时回退复核，非空原生 TeX（若存在）只是可选交叉核对。

## 用户黄金路径

日常使用优先走这一条路径，不从单个底层命令或旧 handoff artifact 开始：

1. 先检查环境和配置：`doctor --json`，配置缺失时走 `config-setup`。
2. 方向不清楚时先用 `research-grill-me` 形成 Research Brief；方向明确时直接 `discover-papers --query "<topic>" --json`。它会先保留 dry-run evidence，再默认把最多 3 篇 PDF-available primary recommendations 准备到 source-staging；review/survey/meta-analysis 默认保留，只有明确 non-review intent 才排除。
3. 用 `report --run-id <discovery-run-id>` 查看底层排序结果，或直接读取 `discover-papers` JSON 输出里的推荐和 auto-staging 摘要；持续追踪、coverage、backlog 以 `_meta/reference-index.json` 为准，`topic-tracking` 做增量视图。
4. 选中的论文如果已有足够 source evidence，直接交给 Paper Wiki `$paper-research-wiki` 沉淀或更新。
5. 只有需要补 PDF、MinerU、source-staging、approval report 或 `wiki-ingest-brief.json` 时，才显式运行 `prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing`。
6. 如果走 source-staging，从 `briefs/reading-report.md` 看中文审批报告；同意后运行 `record-human-approval` 和 `wiki-ingest-trigger`。
7. 由 Paper Wiki `$paper-research-wiki` 或当前 wiki-capable agent 按 `wiki-ingest-brief.json` 写正式页面和 `final-source-review.json`。
8. 用 `record-wiki-ingest` 回填最终页路径、hash、source review 和可选 Zotero record。

新任务只使用 `wiki-ingest-brief.json` 作为 Paper Source-to-Paper Wiki handoff；不要从 `wiki_deposition_task.json` 或旧别名入口启动正式写入。

## 常用入口

```powershell
python scripts\orchestrator.py doctor --json
python scripts\orchestrator.py config-status --vault <vault> --json --include-values --include-runtime
python scripts\orchestrator.py discover-papers --query "<topic>" --max-results 20 --vault <vault> --json
python scripts\orchestrator.py discover-papers --query "<topic>" --max-results 20 --vault <vault> --no-auto-stage --json
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
| `research-grill-me` | 研究方向不清、需要 Research Brief 或 deep-research prompt | 不绕过 discovery、staging、approval gate |
| `paper-discovery` | 单轮检索、query plan、排序、报告 | 不维护长期主题账本 |
| `topic-tracking` | 持续追踪、net-new、coverage/backlog | 不替代底层检索 |
| `paper-ingest` | 已选论文进入 raw、MinerU、source-staging、handoff | 不写最终 Obsidian 页面 |
| `mineru-paper-parser` | PDF -> Markdown/images/manifest，可选非空原生 TeX | 不做学术判断 |
| `wiki-provenance` | 最终页 claim support 和 evidence route | 不替代源论文重读 |
| `wiki-setup` | 初始化、检查、修复、重置 paper wiki vault | 不检索论文、不写最终知识页 |
| `run-lifecycle` | 清理 `_paper_source/runs` 过渡态 | 不删 raw/staging/final wiki |
| `zotero-sync` | 写本地 record-only Zotero sidecar；发现阶段 Zotero dedupe 由 dry-run/discover-papers 只读完成 | Paper Source 不执行外部 Zotero 写入，正式 sync/apply 属于 Paper Wiki |
| `skill-aware-evolve` | 基于证据提出受控优化 | 不直接改用户配置 |
| `paper-source-paper-deposition` | 清理或转接历史 `wiki_deposition_task.json` 残留 | 新任务不要用它启动正式写入 |

## 文献 Wiki 七类页面契约

正式知识沉淀继续保留 7 类研究页面：`references/` 单篇证据页，`concepts/` 方法/理论/术语页，`derivations/` 推导与理论复建页，`experiments/` 复现与实现判断页，`synthesis/` 跨论文综合页，`reports/` 低负担阅读入口页，`opportunities/` 创新机会页。

page-family/frontmatter 的人读 canonical 是 Paper Wiki `plugins/paper-wiki/rules/wiki-writing-standard.md`。Paper Source 只在这里保留索引，不复制完整字段清单。

正式页 frontmatter 至少覆盖 `title`、`category`、`page_family`、`tags`、`aliases`、`sources`、`summary`、`provenance`、`base_confidence`、`lifecycle`、`lifecycle_changed`、`tier`、`created`、`updated`。record 前的研究审阅字段包括 `theory_reconstruction`、`formula_derivation`、`figure_table_evidence`、`novelty_type`、`implementability`、`reproducibility_risk`、`research_gap`、`cost_level`。

Paper Wiki `$paper-research-wiki` 是正式论文 wiki 写入和维护的用户级入口；`wiki-ingest-brief.json` 是 canonical Paper Source-to-Paper Wiki handoff。`wiki_deposition_task.json` 只作为历史残留清理对象，新任务不要生成或依赖它。

## 安全边界

- `discover-papers` 是自然语言发现默认入口，会写高层 run、底层 discovery run 和可选 auto-staging run；默认最多准备 3 篇 PDF-available primary recommendations 到 source-staging，但不写 approval、wiki-ingest trigger/record 或 Paper Wiki 正式页。
- `dry-run` 是底层 evidence/debug 入口，只写 `_paper_source/runs` 和 `_paper_source/reviews` provider cache；已沉淀 backlog 以 `_meta/reference-index.json` 为准。
- `prepare-ranked` 是显式 source-staging 入口，不写最终 wiki。
- agent-mediated wiki ingest 前必须有 `human-approval.json`。
- final wiki agent 写页面前必须读目标 vault contract。
- final wiki 页面必须保留 provenance，不把推断写成源论文事实。
- `record-wiki-ingest` 只记录完成态，不改最终页。
- token、API key、MinerU token 不写入报告、文档或配置预览。
- 安装 cache 不是源码开发位置。

## 推荐阅读顺序

开发者第一次接手时按这个顺序读：

1. 本文档：先建立整体地图。
2. `docs/paper-source-linkage.md`：理解主链路契约和安全门。
3. `docs/structure.md`：定位源码模块和 artifact。
4. `docs/workflow.md`：确认安装后的用户级短命令。
5. 相关 skill 的 `SKILL.md` 和 `references/`：只读当前任务需要的部分。

真正执行论文流程时按这个顺序看 artifact：

1. `_paper_source/runs/<run-id>/report.md`
2. `_paper_source/runs/<run-id>/rank.json`
3. `_paper_source/raw/<slug>/metadata.json`
4. `_paper_source/raw/<slug>/parse-record.json`
5. `_paper_source/raw/<slug>/reader/claim-support.json`
6. `_paper_source/raw/<slug>/critic/critic-quorum.json`
7. `_paper_source/staging/papers/<slug>/briefs/reading-report.md`
8. `_paper_source/staging/papers/<slug>/wiki-ingest-brief.json`
9. `final-source-review.json`
10. `_paper_source/raw/<slug>/wiki-ingest-record.json`
