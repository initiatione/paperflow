# EPI 中文链路与结构总览

本文档给继续开发者、使用 EPI 的 agent、以及需要审查最终 wiki 沉淀质量的人一个中文总览。它把插件结构和完整工作流放在同一张地图里，方便快速判断“下一步该用哪个 skill / CLI / artifact”。

权威分工如下：

- `docs/epi-linkage.md`：主链路维护契约，任何流程语义变化都要同步。
- `docs/structure.md`：源码目录、模块职责、vault artifact 和发布边界。
- `docs/workflow.md`：安装后日常使用的短入口。
- 本文档：中文导航层，解释 EPI 如何从主题跟踪走到单篇论文阅读，再走到带 provenance 的 wiki 沉淀。

## 一句话定位

EPI 是一个 Codex 本地插件，用于把“持续关注某个研究方向”转成可审计的论文知识流水线：

```text
主题/问题 -> 增量检索 -> 排序与去重 -> PDF 采集 -> MinerU 解析
-> source-first reader -> critic gate -> staging evidence package
-> human approval -> wiki ingest agent (Claude/Codex/other)
-> final-source-review -> record-wiki-ingest -> 后续检索/综合/演化
```

它不替用户完成完整科研项目，也不固定某一学科方向。研究方向、正负关键词、venue prior、最终 wiki 结构和语言风格都来自用户配置、当前请求和目标 vault contract。

## 核心心智模型

EPI 不是只有“一个 slug 跑完一条管道”。当前设计分三层：

| 层级 | 解决的问题 | 主要能力 | 关键产物 |
| --- | --- | --- | --- |
| 主题纵向层 | 我持续关注的方向最近有什么新论文、有没有漏掉分支、先读哪几篇 | `topic-tracking`、`dry-run`、`research-queue`、coverage/backlog | `_runs/*`、`research-queue.json`、主题 coverage/backlog 说明 |
| 单篇证据层 | 这篇论文是否真的读懂了，公式/图/表有没有被保留下来 | acquire、MinerU、reader、critic、paper-gate | `_raw/papers/<slug>/*`、`reader/evidence-map.json`、`critic/critic-report.json` |
| Wiki 沉淀层 | 最终页面里的 claim 能否回溯到原文证据 | `wiki-ingest-handoff`、`wiki-provenance`、`record-human-approval`、`record-wiki-ingest` | `_staging/papers/<slug>/*`、`final-source-review.json`、`wiki-ingest-record.json` |

这三层分别保证广度、深度和可信回溯：

- 广度：多 query variants、多来源、去重、topic backlog、coverage gap、systematic-review snowballing。
- 深度：不只读摘要，必须保留 PDF、MinerU Markdown、TeX、图片、manifest、reader evidence 和 critic。
- 可信回溯：最终 wiki 页不能只写结论，还要把 source-grounded、metadata-only、inferred、unsupported 等证据层保留下来。

## 工作流总链路

### 0. 安装诊断与配置

入口：

```powershell
python scripts\orchestrator.py doctor --json
python scripts\orchestrator.py config-status --vault <vault> --json --include-values --include-runtime
```

职责：

- 检查插件结构、skill bundle、模板和 wrapper 是否可用。
- 检查 paper-search MCP/CLI、MinerU、Zotero 等外部能力是否配置。
- 区分插件结构错误和外部依赖 warning。
- 首次配置或修改配置必须走 `config-setup` skill，一次只问一个问题，最终确认前不运行写配置命令。

配置分两层：

- 研究画像配置：`<vault>/_meta/epi-config.yaml`。
- 本机 runtime 依赖：用户级 EPI runtime 配置，只记录命令路径和 env-file 路径，不保存 token 明文。

### 1. 主题跟踪与论文发现

入口：

```powershell
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 20 --vault <vault> --json
python scripts\orchestrator.py report --run-id <run-id> --vault <vault>
```

职责：

- 根据用户画像、当前 query、positive/negative keywords、domains 和 venue prior 生成 `query-plan.json`。
- 多 query variants 检索后合并候选，进行 DOI/arXiv/title/library 去重。
- 默认排除 review/survey/meta 类综述，除非用户明确要综述。
- 给出 `paper_type`、`quality_gate`、`quality_tier`、`ranking_rubric`、`ranking_confidence`。
- 输出可扫读的推荐清单，而不是让用户读 raw JSON。

关键产物：

```text
<vault>/_runs/<run-id>/query-plan.json
<vault>/_runs/<run-id>/search-record.json
<vault>/_runs/<run-id>/normalized.json
<vault>/_runs/<run-id>/rank.json
<vault>/_runs/<run-id>/report.md
<vault>/_runs/<run-id>/report.json
<vault>/_runs/<run-id>/run-state.json
<vault>/_runs/index.json
<vault>/_runs/research-queue.json
```

`topic-tracking` 是这一层的外层 skill。它负责回答：

- 上次之后有哪些 net-new 论文？
- 哪些候选已经在库里，不该重复推荐？
- 当前主题覆盖了哪些方法族、benchmark、应用场景和高被引簇？
- backlog 里先读哪几篇最划算？
- 系统综述模式下是否需要 forward/backward snowballing？

### 2. 采集、解析与 raw 留痕

入口：

```powershell
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault> --json
python scripts\orchestrator.py parse-paper --slug <slug> --vault <vault>
```

职责：

- 对 ranked papers 执行 PDF 下载或本地复制。
- 失败时写清楚 `failure_class`、`retryable`、`recovery_hint`，避免把 403/502 误判为论文不存在。
- 调用 MinerU 生成 Markdown、TeX、images、manifest。
- 对已完整解析的论文使用 `--skip-existing`，避免补跑时浪费预算。

关键产物：

```text
<vault>/_raw/papers/<slug>/paper.pdf
<vault>/_raw/papers/<slug>/metadata.json
<vault>/_raw/papers/<slug>/acquire-record.json
<vault>/_raw/papers/<slug>/parse-record.json
<vault>/_raw/papers/<slug>/mineru/paper.md
<vault>/_raw/papers/<slug>/mineru/paper.tex
<vault>/_raw/papers/<slug>/mineru/images/*
<vault>/_raw/papers/<slug>/mineru/mineru-manifest.json
<vault>/_raw/papers/<slug>/run-state.json
```

解析保真度应当对用户可见。对公式密集、图表密集或方法细节重要的论文，reader 和 wiki agent 不能只读 `paper.md`，还必须检查 TeX、图片、manifest，并在必要时回到 PDF。

### 3. Source-First Reader

入口通常由 `advance-paper`、`advance-ranked`、`ingest-one` 或 redo 命令内部触发。

reader 不是最终知识库页面，而是降低阅读负担的证据导航层。它必须以源论文为中心：

- `paper.pdf`
- `metadata.json`
- `mineru/paper.md`
- `mineru/paper.tex`
- `mineru/images/*`
- `mineru/mineru-manifest.json`

三角色输出：

- `nature-sci-editor`：创新性、叙事价值、scope caveat。
- `peer-reviewer`：方法、实验、baseline、metric、benchmark、复现条件。
- `senior-domain-researcher`：理论启发、实验思路、可迁移知识点、应进入 wiki 的概念。

关键产物：

```text
<vault>/_raw/papers/<slug>/reader/reader.md
<vault>/_raw/papers/<slug>/reader/editorial-summary.md
<vault>/_raw/papers/<slug>/reader/technical-reading.md
<vault>/_raw/papers/<slug>/reader/research-notes.md
<vault>/_raw/papers/<slug>/reader/figures.md
<vault>/_raw/papers/<slug>/reader/reproducibility.md
<vault>/_raw/papers/<slug>/reader/implementation-ideas.md
<vault>/_raw/papers/<slug>/reader/evidence-map.json
<vault>/_raw/papers/<slug>/reader/claim-support.json
```

`claim-support.json` 必须区分：

- `source-grounded`：源论文直接支持。
- `metadata-only`：只来自标题、摘要、DOI、venue、year 等元数据。
- `inferred`：agent 基于证据做出的推断。
- `unsupported`：没有足够证据，不能进入最终页当作事实。

### 4. Critic 与 Paper Gate

critic 是进入 staging 和最终 wiki 的硬边界。无 critic pass，不进入默认 wiki ingest 路径。

critic 组成：

- `paper-quality-critic`
- `parse-quality-critic`
- `reader-quality-critic`
- `editorial-significance-critic`
- `peer-review-methods-critic`
- `domain-fit-critic`

关键产物：

```text
<vault>/_raw/papers/<slug>/critic/critic-report.json
<vault>/_raw/papers/<slug>/critic/critic-quorum.json
<vault>/_raw/papers/<slug>/critic/research-decision.json
<vault>/_raw/papers/<slug>/critic/reader-revision-plan.json
<vault>/_raw/papers/<slug>/critic/reproduction-plan.json
```

只读状态面板：

```powershell
python scripts\orchestrator.py paper-gate --slug <slug> --vault <vault> --json
```

`paper-gate` 判断下一步是：

- 修复 reader / parse / metadata。
- 等待 human approval。
- 允许 wiki ingest agent 接手。
- 已经记录 final wiki ingest 完成态。

### 5. Staging Evidence Package

critic pass 后才生成 staging。staging 是给最终 wiki agent 的证据包，不是最终页面。

关键产物：

```text
<vault>/_staging/papers/<slug>/references/<slug>.md
<vault>/_staging/papers/<slug>/concepts/<slug>-concept.md
<vault>/_staging/papers/<slug>/synthesis/<slug>-synthesis.md
<vault>/_staging/papers/<slug>/reports/<slug>-reading-report.md
<vault>/_staging/papers/<slug>/wiki-ingest-brief.json
<vault>/_staging/papers/<slug>/promotion-plan.json
```

默认阅读入口是轻阅读报告：

- `Quick Take`
- `What To Read If You Only Have 5 Minutes`
- `Reading Trust Status`
- `Role-Specific Notes`
- `Theory And Experiment Ideas`
- `Evidence Map`
- `Suggested Wiki Routes`
- `Figure / Table Skim`
- `Reproducibility Caveats`

### 6. Wiki Ingest Handoff 与人类批准

只读 handoff：

```powershell
python scripts\orchestrator.py wiki-ingest-handoff --slug <slug> --vault <vault> --json
```

前置批准：

```powershell
python scripts\orchestrator.py record-human-approval --slug <slug> --approved-by <name> --scope run-wiki-ingest-agent --vault <vault> --json
```

`record-human-approval` 只在当前 gate 无 failure checks 且唯一待办为 `human-approval` 时写入：

```text
<vault>/_staging/papers/<slug>/human-approval.json
```

这个 artifact 是“允许外部 wiki ingest agent 写最终页”的机器可验证证据。没有它，`wiki-ingest-handoff` 不应显示 `ready_for_agent=true`，`record-wiki-ingest` 也不能事后补登记。

批准后继续触发当前 agent：

```powershell
python scripts\orchestrator.py wiki-ingest-trigger --slug <slug> --vault <vault> --json
```

`wiki-ingest-trigger` 会写：

```text
<vault>/_staging/papers/<slug>/wiki-agent-trigger.json
```

它不是后台自动拉起 Claude/Codex 的进程，也不写最终页；它把“当前 agent 可以开始按目标 vault contract、wiki-provenance 和 source-first closure 写 wiki”的指令、路径、checklist 和 final-source-review 合同固化下来。用户读完轻阅读报告后再次触发 `@EPI`，EPI 可以先看 `research-queue --bucket ready_to_promote --actions`，若 gate 已批准就执行 `wiki-ingest-trigger`，然后由当前 Claude/Codex/其他 wiki-capable agent 进入最终 wiki 写入。

### 7. Final Wiki Ingest 与 Provenance

最终 Obsidian/LLM Wiki 页面由 wiki ingest agent 写，不由 EPI 的固定 promotion 脚本决定路径。执行器可以是 Claude、Codex 或其他 wiki-capable agent，但必须先读取目标 vault contract：

```text
<vault>/AGENTS.md
<vault>/_meta/agent-operating-contract.md
<vault>/_meta/schema.md
<vault>/_meta/taxonomy.md
<vault>/_meta/directory-structure.md
```

最终页必须满足：

- 读源论文 Markdown、TeX、图片、manifest 和必要时 PDF。
- 不把 reader summary 当作原文替代品。
- 每条重要 claim 保留支持状态。
- 页面内保留 evidence address 或能回到 `reader/evidence-map.json` 的路线。
- 对公式、图、表、实验结论、SOTA/优于 baseline 等高风险断言做 source-first 复核。
- 写出 `final-source-review.json`，记录源工件 hash、公式复核、图表复核、PDF fallback 决策和 final page provenance。

`wiki-provenance` skill 专门约束这一层。它的目标是防止半年后查询 wiki 时，把 agent 的推断误当成源论文事实。

### 8. 完成态记录、Zotero 与后续查询

完成态记录：

```powershell
python scripts\orchestrator.py record-wiki-ingest --slug <slug> --page <final-page.md> --approved-by <name> --source-review <final-source-review.json> --vault <vault> --json
```

`record-wiki-ingest` 不写最终页。它只做审计记录：

- 重新检查 `paper-gate`。
- 验证 pre-write `human-approval.json` 存在。
- 要求 `--approved-by` 与批准 artifact 完全一致。
- 验证最终 Markdown 页在目标 vault 内，且不在 `_raw`、`_staging`、`_runs`、`.obsidian` 等内部目录。
- 验证 `final-source-review.json` 中的 source-first closure。
- 记录最终页路径、sha256、source review 和 approval。

关键产物：

```text
<vault>/_raw/papers/<slug>/wiki-ingest-record.json
<vault>/_staging/papers/<slug>/wiki-ingest-record.json
<vault>/_raw/papers/<slug>/zotero-record.json
```

后续查询和综合依赖这些元数据。EPI 自身的 `wiki-query` 只是 legacy manifest/index 视角；真正的跨论文综合、带引用检索和 provenance round-trip 需要目标 wiki skills 消费 final page metadata、claim support 和 evidence route。

## 插件源码结构

```text
<plugin-root>/
  .codex-plugin/
    plugin.json
  docs/
    overview.zh.md
    epi-linkage.md
    structure.md
    workflow.md
    progress.md
    config.md
    evaluation.md
    privacy.md
    terms.md
  scripts/
    orchestrator.py
    init_paper_wiki.py
    build/epi/*.py
  skills/
    config-setup/
    wiki-setup/
    paper-discovery/
    topic-tracking/
    mineru-paper-parser/
    paper-ingest/
    wiki-provenance/
    run-lifecycle/
    zotero-sync/
    skill-aware-evolve/
  templates/
  metric-packs/
  vendor-notices/
  coverage/
```

职责边界：

- `.codex-plugin/plugin.json`：marketplace 元数据和 skill 入口声明。
- `docs/`：用户与维护者可读的契约层。
- `scripts/orchestrator.py`：插件公开 wrapper，用户和 skill 调 CLI 时使用。
- `scripts/build/epi/`：实际 Python 实现。
- `skills/`：Codex skill 入口，保持短小，复杂策略拆到 `references/`。
- `templates/`：ranking、filter、interest、routing、critic checklist 示例。
- `metric-packs/`：插件开发质量环使用的评估指标。
- `coverage/`：发布评估需要时刷新的 coverage artifact。

## 主要 Skill 分工

| Skill | 何时使用 | 不负责什么 |
| --- | --- | --- |
| `config-setup` | 首次配置、修改 profile、runtime 或确认门 | 不跑论文流程 |
| `wiki-setup` | 初始化、检查、修复、重置目标 paper wiki vault | 不检索论文、不写最终知识页 |
| `paper-discovery` | 单轮检索、query plan、排序、报告 | 不维护长期主题账本 |
| `topic-tracking` | 持续追踪、增量发现、coverage/backlog | 不替代底层检索/ranking |
| `mineru-paper-parser` | PDF 到 Markdown/TeX/images/manifest | 不做学术结论判断 |
| `paper-ingest` | 单篇 raw -> reader -> critic -> staging -> handoff | 不直接写最终 Obsidian 页面 |
| `wiki-provenance` | 审查最终页 claim support 和 evidence route | 不替代源论文重读 |
| `run-lifecycle` | 清理 `_runs` 过渡态 | 不删 raw/staging/final wiki |
| `zotero-sync` | 本地 Zotero sidecar 记录 | 默认不调用外部 Zotero API |
| `skill-aware-evolve` | 基于证据提出受控优化 | 不直接改用户配置或绕过验证 |

## 常用命令速查

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

## 安全边界

- `dry-run` 只写 `_runs`。
- `prepare-ranked` 停在 raw/MinerU parse，不进入 reader/critic/staging。
- 无 critic pass，不进入默认 wiki ingest handoff。
- agent-mediated wiki ingest 前必须有 `human-approval.json`。
- final wiki agent 写页面前必须读目标 vault contract。
- final wiki 页面必须保留 provenance，不把推断写成源论文事实。
- `record-wiki-ingest` 只记录完成态，不改最终页。
- legacy `promote-to-wiki` 只保留兼容用途，不是默认路径。
- token、API key、MinerU token 不写入报告、文档或配置预览。
- 安装 cache 不是源码开发位置，源码修改应在插件源码包内完成并通过发布/安装流程进入 cache。

## 推荐阅读顺序

开发者第一次接手时按这个顺序读：

1. 本文档：先建立整体地图。
2. `docs/epi-linkage.md`：理解主链路契约和安全门。
3. `docs/structure.md`：定位源码模块和 artifact。
4. `docs/workflow.md`：确认安装后的用户级短命令。
5. 相关 skill 的 `SKILL.md` 和 `references/`：只读当前任务需要的部分。

真正执行论文流程时按这个顺序看 artifact：

1. `_runs/<run-id>/report.md`
2. `_runs/<run-id>/rank.json`
3. `_raw/papers/<slug>/metadata.json`
4. `_raw/papers/<slug>/parse-record.json`
5. `_raw/papers/<slug>/reader/claim-support.json`
6. `_raw/papers/<slug>/critic/critic-quorum.json`
7. `_staging/papers/<slug>/reports/<slug>-reading-report.md`
8. `_staging/papers/<slug>/wiki-ingest-brief.json`
9. `final-source-review.json`
10. `_raw/papers/<slug>/wiki-ingest-record.json`
