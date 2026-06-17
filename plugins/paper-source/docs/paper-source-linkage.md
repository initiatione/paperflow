# Paper Source 插件链路说明

本文档是 Paper Source 插件的主链路说明和维护契约。Paper Source 是用户可见名，machine-facing name 是 `paper-source`；Paper Wiki 是 sibling wiki 插件的用户可见名，machine-facing name 是 `paper-wiki`。旧别名不再作为用户入口、路由触发条件或新 artifact 合同。Paper Source 的核心目标是：按用户画像/config 衍生高质量论文收集 -> Obsidian/LLM Wiki 知识沉淀 -> 轻阅读负担的阅读报告。它是通用学术论文插件，不默认任何学科方向；AUV、机器人、AI、医学等词只能来自用户配置、当前请求、Research Brief 或 agent 显式传入的 query variants / domain focus terms / structured agent query plan。它不是从 0 到完成投稿的自动科研工作台，也不默认生成大型复现实验 agenda；复现只作为短小的验证线索。

## 维护契约

每次修改或优化 Paper Source 插件，都必须同步更新本文档。需要更新的变化包括：CLI 命令、dry-run/ingest/critic/staging/promotion/rollback/redo/wiki-query/wiki-ask/evolution 链路、生成物路径、JSON 字段、Markdown 报告结构、Wiki 页面类型、安全边界、人类确认门、配置流程、技能说明、模板、ranking/critic 规则和阅读报告侧重点。若一次改动确实不影响链路，提交说明应写明无需更新本文档的原因。

配套文档（唯一 doc map / 权威分工）：

- `docs/overview.zh.md`：中文总览入口，把插件结构、主题纵向层、单篇管道和 wiki provenance 闭环放在同一张地图里。
- `docs/structure.md`：当前插件目录、CLI 模块、技能、模板、vault artifact 和测试边界。
- `docs/progress.md`：当前开发进度、已验证信号、未完成工作和下一步发布前检查。
- `docs/config.md`：首次使用和修改配置时的聊天式引导话术，是 `config-setup` skill 的话术来源。
- `docs/workflow.md`：给用户和安装副本看的短流程入口，避免把完整链路文档塞进日常提示。

## 目标边界

Paper Source 服务论文知识摄取，而不是替用户完成完整科研闭环。

- 发现：按用户研究画像、关键词、venue prior、来源和 ranking 规则找到值得读的论文。
- 留痕：保存 PDF、元数据、non-authoritative retrieval preview、MinerU Markdown/images/manifest、非空原生 TeX（若存在）、可选 reader/critic、source-staging handoff 和 run-state。
- 审查：reader/critic 是按需导航和审计层；默认 fast-ingest 不跑，reviewed-ingest 加 reader，audited-ingest 加 critic。
- 沉淀：默认 fast-ingest 生成中文审批报告和 wiki-ingest handoff；最终 Obsidian/LLM Wiki 页面由 agent 按 vault contract 从源论文蒸馏、合并和写入。
- 轻读：用户默认从 `_paper_source/staging/papers/<slug>/briefs/reading-report.md` 开始，必要时再看 reader、evidence map 或原文。

## Obsidian Wiki 规则来源模型

规则来源必须分成三层，不允许混成一个 schema：

- Obsidian syntax layer：`kepano/obsidian-skills` 是 properties/frontmatter、wikilinks、Markdown links、embeds、callouts、tags、math、bases/canvas 的格式权威。
- Paper Wiki paper-evidence layer：Paper Wiki / Paper Source 合同负责论文证据包、正式页家族、claim provenance、公式推理链、图表证据卡、页面关系维护、evidence tier 和 `final-source-review.json` / `record-wiki-ingest` readiness。
- Local vault governance layer：目标 vault 的 `AGENTS.md` 和 `_meta/*` 负责本库 taxonomy、页面归属、staged writes、QMD scope、迁移和 legacy retirement；样例 vault 或上游仓库只能作参考，不能替代目标 vault contract。

Paper Source 不能把 Obsidian Wiki 写入规则简化成“调用本机 `llm-wiki` / `wiki-ingest` 两个 skill”。这两个 skill 只是本机执行适配器；真正的构建和写入规则必须按优先级解析：

1. 当前用户指令：本次任务目标、语言、写入边界和安全要求。
2. 目标 vault `AGENTS.md`：用户个性化约定、领域词汇、写作风格和安全边界。
3. 目标 vault `_meta/agent-operating-contract.md`。
4. 目标 vault `_meta/schema.md`、`_meta/taxonomy.md`、`_meta/directory-structure.md`：最终路由、页面类型、标签、链接、staged writes、合并/拆分策略。
5. Paper Wiki 插件包（目录 `plugins/paper-wiki`）：面向用户的一体化论文 wiki 助手，提供 `$paper-research-wiki`，支持提取 Paper Source 论文、检测 wiki 库、更新 wiki 库和 `重link`，并在内部执行 source-first provenance、七类正式页面、staged review、paper lint、cross-link/relink 和 Paper Source handoff 消费。
6. `initiatione/obsidian-wiki-dev` 的 `liuchf/wiki-skills` 分支：个性化 multi-vault contract、QMD 只是检索辅助、Markdown vault 是 source of truth。
7. `Ar9av/obsidian-wiki`：agent-mediated LLM Wiki 架构、manifest/index/log/hot、provenance、先搜索/合并再创建页面。
8. `kepano/obsidian-skills`：Obsidian syntax authority，负责 properties/frontmatter、wikilinks、Markdown links、embeds、callouts、tags、math、bases/canvas 等格式约定。
9. 本机 `llm-wiki` / `wiki-ingest` / `obsidian-markdown`：按上述规则执行的本地 helper/adapters，不覆盖目标 vault contract。

`wiki-ingest-brief.json` is the canonical Paper Source-to-Paper Wiki handoff; `wiki_deposition_task.json` is historical cleanup only, not a new-task entrypoint.
Paper Wiki `$paper-research-wiki` 是 canonical 执行层。external wiki skills are optional helpers / policy references, not runtime required dependencies.

因此 `wiki-ingest-brief.json` 必须包含 `wiki_rule_source_model`，记录 `resolution_order`、`must_read_before_final_write`、`write_contract_requirements` 和 `execution_agent_policy`。`execution_agent_policy` 必须明确 Claude、Codex 或其他 wiki-capable agent 都可以作为最终执行器，只要遵守同一套 target vault contract、source-first review、人类批准和 final-source-review gate。`paper-gate` 要把这些字段纳入 `wiki-ingest-brief` 检查，避免 Paper Source 退化成固定脚本、单一 skill 默认规则或单一 agent 默认规则。

page-family/frontmatter 的人读 canonical 是 Paper Wiki `plugins/paper-wiki/rules/wiki-writing-standard.md`；Paper Source 文档只保留执行入口和最小索引，执行层常量仍在 `wiki_contracts.py` 中用于 gate 校验。

## 主链路

### 1. 初始诊断与配置

入口：`doctor`、`config-status`、`config-setup` skill、`init-config`、`propose-config-update`、`apply-config-update`。

职责：检查插件结构、模板、技能目录、默认 vault、`paper-search` CLI、MinerU 命令、`MINERU_TOKEN` 和 Paper Source vault 配置。外部依赖缺失只提示 warning，插件结构缺失才 error。用户初次使用或修改配置时必须走 `config-setup` skill：一次只问一个问题，每步说明影响、推荐值和参考方向，不把字段名直接丢给用户，不一次性输出完整默认配置；最终确认前不得运行 `init-config` 或 `apply-config-update`。skill-aware evolution 不直接改用户配置。

配置分两层：研究画像、关键词、预算、Zotero、可选 `grok_search` 补充检索策略和人工确认门属于目标 vault 的 `_paper_source/meta/paper-source-config.yaml`；paper-search、Grok、MinerU、EasyScholar、provider key env file 和 CLI/MCP 命令属于本机工具 runtime，写入 `%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json`。根 `_meta/` 只保留 wiki skill 需要读取的 vault contract 文件，例如 schema、taxonomy 和 directory structure。runtime.json 只记录 `paper-search` MCP command/args、可选 `grok-search-rs MCP` command/args/env-file、CLI fallback、MinerU 命令、EasyScholar env file 和 provider env file 路径，不保存 token 明文。默认和推荐做法是把 provider env file 放在同一个用户级插件 runtime 目录下，例如 `paper-search-providers.env`、`grok-search.env`、`mineru.env`、`easyscholar.env`；runtime.json 不能依赖开发源码 checkout、项目 `.env` 目录、vault 内部 `_paper_source`、临时目录或版本化 plugin cache。命令字段应是 PATH 上的安装命令、全局工具路径、解释器路径或用户级 runtime wrapper，不能指向开发目录中的辅助脚本。`runtime_config.py` 在 doctor、paper-search discovery/download、optional Grok supplemental discovery 和 MinerU parse 前自动加载它，并且只补缺失的环境变量；显式进程 env 永远优先。`runtime_config.py` 同时生成 `path_policy`，`doctor --json` 以 `runtime_path_policy` check 暴露 runtime 路径越界和开发 checkout 依赖。

### Paper Source 内部仓库结构

Paper Source 在 vault 中只有一个内部写入根：`_paper_source/`。新初始化和迁移后的 vault 不再创建顶层 `_raw`、`_staging`、`_runs`、`_quarantine` 或 `_evolution`。这些旧目录只作为迁移来源存在，可用 `paper-source-repository-migrate --preview --json` 预览，用 `paper-source-repository-migrate --json` 收拢到 `_paper_source/`。

`_paper_source/README.md` 是给 AI/agent 的导航入口，`_paper_source/manifest.json` 是机器可读目录和统计索引，`_paper_source/policies/retention.json` 是仓库清理策略。Obsidian graph 应忽略 `_paper_source/`；正式图谱页只应由 wiki skill 写到 `references/`、`concepts/`、`derivations/`、`experiments/`、`synthesis/`、`reports/`、`opportunities/` 等正式目录。默认初始化采用 lean 结构，只预建核心 source/handoff/config/policy 目录；运行、缓存、临时、隔离和 evolution 目录由实际 workflow 按需创建。

- `_paper_source/raw/<slug>/`：PDF、metadata、`paper-search-read-preview.txt`、MinerU Markdown/images/manifest、非空原生 TeX（若存在）、reader、critic 和论文级 run-state。
- `_paper_source/staging/papers/<slug>/`：source-reader、reading-report、canonical `wiki-ingest-brief.json`、human approval、trigger、final-source-review 和 record sidecars。
- `_paper_source/staging/wiki-batches/pending/wiki-batch-ingest-brief.json`：wiki skill 的多论文批量沉淀交接包。
- `_paper_source/meta/`：Paper Source config、config history、run lifecycle、raw cleanup、migration、wiki reset、formal-page snapshots 和 repository maintenance manifests。
- `_paper_source/policies/retention.json`：自动清理阈值和 lifecycle 上限；默认总量预算为 3000 files / 1 GiB，用来尽早暴露 `_paper_source` 体量压力并触发维护产物清理。默认不删除 `_paper_source/raw` 原始论文源文件，但会限制 terminal run dirs、`_paper_source/meta/run-lifecycle`、`_paper_source/meta/raw-cleanup`、`_paper_source/meta/repository-maintenance`、`_paper_source/meta/migrations`、`_paper_source/meta/wiki-reset`、`_paper_source/meta/formal-page-snapshots` 和 `_paper_source/tmp-manual-pdfs` 的累计数量。

按需结构：

- `_paper_source/runs/`：dry-run、batch、record、dashboard、research-queue 和 workflow reports；运行时创建，不作为空壳预建。
- `_paper_source/cache/`：EasyScholar 等可再生成缓存；缓存不能替代原论文证据。
- `_paper_source/tmp/`、`_paper_source/tmp-manual-pdfs/`：临时下载和人工补 PDF 入口，只保留最近少量文件；成功进入 raw source bundle 后不应长期堆积。
- `_paper_source/quarantine/`：失败、隔离或不应推荐的论文工件；只有发生 identity mismatch 或隔离事件时创建。
- `_paper_source/evolution/`：受控 skill/profile/template evolution proposals；只有 vault-local 证据必须绑定到演化提案时创建，空壳不属于默认结构。

### 2. 论文发现与排序

入口：`dry-run`。单次运行证据写 `_paper_source/runs/<run-id>/`，provider resume/cache 写 `_paper_source/reviews/<review-id>/`；长期文献 backlog 和去重 source of truth 是 wiki `_meta/reference-index.json`。`dry-run` 不下载 PDF，不调用 MinerU，不写 raw/staging/compiled wiki。

关键产物：

- `_paper_source/runs/<run-id>/normalized.json`
- `_paper_source/runs/<run-id>/rank.json`
- `_paper_source/runs/<run-id>/report.md`
- `_paper_source/runs/<run-id>/report.json`
- `_paper_source/runs/<run-id>/run-state.json`
- `_paper_source/runs/index.json`
- `_paper_source/runs/research-queue.json`

### Review Sessions And Default Resume

`dry-run` now writes both `_paper_source/runs/<run-id>/` and `_paper_source/reviews/<review-id>/`. `_paper_source/runs` remains the single-invocation evidence record; `_paper_source/reviews` is a resumable provider cache, not the user-facing literature backlog. A repeated `dry-run --query "<topic>"` with the same normalized query, query plan, source routing, profile, filters, ranking inputs, and EasyScholar setting resumes by default from the matching review session and skips provider calls. Use `--refresh` to force a new provider search and update the review session. Use `--no-resume` only for debugging.

Each review session stores `state.json`, `query-plan.json`, `candidates.json`, `shortlist.json`, `fetch_plan.json`, `coverage.json`, and `provider-cache/query-*.json`. These files prevent context compaction or terminal interruption from causing repeated provider requests. Deposited-paper dedupe and topic backlog should read `_meta/reference-index.json` first.

### Discovery Evidence First, Web Verification Second

Paper Source 论文推荐必须先有 Paper Source run/candidate artifact：fresh `dry-run`、resumed review session、已有 `search-record.json` / `report.json` / `rank.json`，或用户直接给出的 DOI/arXiv/title seed。需要检索新候选时，source route 先走 `paper_search_mcp.search_papers` / configured source adapters；可选 `grok-search-rs MCP` 只作为 Paper Source discovery workflow 内部的 supplemental recall，用 targeted 或 parallel 补 paper-search provider/source gap，不替代 paper-search。Firecrawl、generic web search、publisher search 和 GitHub search 只能在候选身份已经存在后做 targeted verification，不得作为 primary discovery provider，也不得把 Firecrawl/web-only result set 说成 Paper Source recommendation。重复主题默认先检查 `_meta/reference-index.json`，再检查 `_paper_source/reviews/<review-id>/` 或最近 `search-record.json`，通过 wiki dedupe、resume、`report --run-id` 或已有 artifact 继续；只有 explicit freshness、documented recall gap 或用户要求时才 `--refresh`。有代码的论文中，GitHub/repository search 是 reproducibility/code evidence verification，不是 paper identity discovery。

ranking 必须同时给机器信号和低阅读负担解释：

- `research_mode`：`targeted-discovery`、`quick-brief`、`lit-review`、`systematic-review`、`fact-check` 或 `guided`，用于说明本次 discovery 的意图路线。
- `ranking_signals`：topic、venue、citation、freshness、PDF/code、benchmark、reproducibility、negative keyword penalty。
- `paper_classification` / `paper_type`：按 title/abstract 给出 method、system、benchmark、dataset、field-trial、theory、survey、application、reproducibility 或 unknown，并附 confidence/evidence。
- `ranking_rubric`：relevance、method_rigor、evidence_sufficiency、reproducibility、source_confidence 维度和 `ranking_confidence`。
- `ranking_protocol`：`selection_policy`、advance/review 决策、正负关键词、reasons/cautions、editorial/peer-review/domain/reproducibility lens。默认 `balanced_high_quality` 允许高质量 review-candidate 继续进入准备队列；`strict_advance` 保留旧的严格推进行为；`code_required` 只在用户明确要求公开代码时使用。
- `ranking_rationale`：一句话推荐、用户兴趣匹配、Nature/Sci editor、peer reviewer、senior domain researcher 三角色短评，以及建议进入 wiki 的页面类型。

当用户是在对话中要求“找最新/高质量论文”时，`paper-discovery` skill 应优先运行 `discover-papers`，不应只转述 `report.md`、`rank.json` 或 raw dry-run report。`discover-papers` 会先运行并留存 Paper Source dry-run 证据，再按 `report.json.session_recommendations` 生成对话框中的“推荐优先看”清单，并默认把最多 3 篇 PDF-available primary recommendations 自动准备到 source-staging。主推荐清单使用 `primary_recommendations`，默认最多 10 篇，只包含非 `review-candidate` 的 Tier A/B 或 `advance-candidate` 论文，并按阅读优先级排序；Tier C 和 `review-candidate` 论文只能进入 `review_appendix`，不得混入主推荐。若还有更多主推荐候选，报告 `overflow.hidden_count` 并指向 artifact，禁止返回未排序的标题清单。每篇用编号标题、venue/year、DOI（缺失或未核实时按合同写 `缺失` / `未核实`）、引用数、影响因子/分区或 `未核实`、CiteScore 或 `未核实`、PDF/manual-download 状态、auto-staging 状态和 2-3 句中文简短摘要，说明方法主线、控制任务、证据强度、优先级和 caveat。`discover-papers` 对 review/survey/meta-analysis 默认保留，只有明确 non-review intent 才排除；`paper-source-auto-staging-plan-v1` 只会从主推荐中默认选择最多 3 篇 PDF-available 论文进入 fast source-staging，review/survey/meta-analysis 默认最多 1 个 slot，`needs_pdf` 论文保留 manual-download links 但不 staging；该路径不创建 human approval、wiki trigger、Paper Wiki 正式页或 ingest record。Paper Source 脚本只提供 original abstract/evidence 字段，不内置 LLM 或翻译；中文摘要由调用 agent 在会话层生成。影响因子、JCR 分区、CiteScore 等质量指标必须实时核实或来自可信元数据；不能核实时明确写 `影响因子/分区：未核实`，不得凭印象补数字。随后再给“Paper Source 实测证据”，包含 `discover-papers` run 路径、linked discovery / auto-staging run ids、`source_mode`、accepted/rejected 数量、`session_recommendations.rejected_summary`、`auto_staging_plan` 摘要，以及 setup 检查时的 `MINERU_TOKEN set/missing` 状态。不得输出 raw JSON、长摘要或任何 secret。

高质量论文检索不能把 `paper_search_mcp` 返回结果本身当成质量定义。`paper-discovery` 采用类似 `nature-academic-search` 的 bundle 结构：`SKILL.md` 只保留入口和边界，具体 mode routing、检索协议、query planner、论文类型 taxonomy、ranking rubric、领域词表、source tier、去重、venue prior、two-stage retrieval、citation graph、评测集、质量门控、多源 workflow、anti-patterns 和输出格式分别放在 `scripts/query-planner.py`、`references/mode-routing.md`、`references/query-planner.md`、`references/paper-type-taxonomy.md`、`references/ranking-rubric.md`、`references/domain-ontology.md`、`references/search-protocol.md`、`references/source-tiers.md`、`references/dedup-engine.md`、`references/venue-prior.md`、`references/two-stage-retrieval.md`、`references/citation-graph.md`、`references/evaluation-set.md`、`workflows/multi-source-discovery.md`、`references/quality-gate.md`、`references/anti-patterns.md`、`references/output-format.md`。后续优化 query planning、source routing、分类、质量筛选、去重或输出格式时只改对应分层文件，不把所有规则塞回一个大 skill。`query_plan` 里的硬过滤信号是 `hard_domain_anchors`：只允许来自用户显式输入、config 中与本轮请求匹配的域词、Research Brief `domain_scope` 或 agent plan 的 `hard_constraints` / `hard_domain_anchors`。从自然语言 topic 切出的 n-gram 只能进入 `soft_recall_terms` 和 `term_provenance`，用于召回、解释和 gap check，不得升级成 hard filter。

期刊/会议分层可用于提高高质量论文筛选能力，但只能作为 `venue_prior`。Paper Source 是通用插件，不能把机器人、AUV、AI、医学或任何单一学科写成全局默认；venue prior 必须来自用户画像/config、当前请求或本轮明确验证的领域资料。专业学会列表、领域数据库、出版社专题页、curated community lists 等只能作为对应领域的 prior 或 recall gap 检查来源；论坛或博客排名只能作为弱召回线索和社区主观背景，不能直接当作影响因子、JCR 分区、引用数、录用率或最终质量标签。推荐结果必须把 `venue_prior` 和 `verified_metrics` 分开展示；若影响因子、分区、CiteScore、引用数没有在本轮核实，就写 `未核实`。

自然语言主题，尤其是中英混合、包含“尽可能有公开代码”“近 5 年”“现代控制或 RL”等约束的请求，不应直接作为 MCP 主检索式。agent 必须先实时分析用户表述，把对象/任务/方法/约束/质量信号形成透明 query plan，再通过 repeated `--query-variant` 或 `--agent-query-plan-json` 传给 `dry-run`，必要时用 repeated `--domain-focus-term` 或 agent plan 的 `hard_domain_anchors` / `hard_constraints` 传硬过滤锚点。`--year-min` 表示明确近期窗口；`--code-policy prefer` 表示代码优先但不硬丢无代码论文，`--code-policy require` 表示必须有 `code_url` / repository identity。`--selection-policy` 控制推荐到推进的阈值。`--query` 保留原始用户意图用于报告、resume signature 和审计；`query-plan.json` 会记录 `query_variants_source=agent_supplied`、`agent_supplied.query_variants`、`hard_constraints`、`soft_recall_terms`、`term_provenance` 和 `request_constraints`。脚本允许硬编码 artifact schema、source routing、安全 gate、去重和通用过滤修复，但不应硬编码每个学科的自然语言语义映射，也不应新增 `request_compiler.py` 或 `compile-query-plan` 这类固定语义编译入口。

当用户给出紧凑主题或要求“最新/高质量/非综述”时，`paper-discovery` 应先形成 `query_plan`：从 `_paper_source/meta/paper-source-config.yaml` 的 profile、domains、positive_keywords、negative_keywords、venue_prior 和当前请求衍生 `research_mode`、概念块、`hard_domain_anchors`、`soft_recall_terms`、5-8 条 query variants、source route、recall gap checks、quality signals、selection policy 和 request constraints。`scripts/query-planner.py` 是离线辅助工具，只生成计划不访问网络；自然语言默认入口 `discover-papers` 会先调用底层 `dry-run` evidence 路径，写 `_paper_source/runs/<discovery-run-id>/query-plan.json`，并把 `source_routing` 写入 `query-plan.json` 和 `search-record.json`。`dry-run` 还会写 `discovery-diagnostics.json`，记录硬/软词 provenance、candidate pool、recommendable/staging_ready/needs_pdf/rejected 分流、wiki `_meta/reference-index.json` / raw fallback 去重状态、rejection reason counts 和 source coverage。缺 PDF 且有稳定 DOI/arXiv/publisher identity 的候选可以继续作为 recommendable，但进入 `needs_pdf`，不应被当作质量拒绝；无稳定身份且缺 PDF 才可硬拒绝。Google Scholar、BASE、SSRN 这类 `unstable` source 默认 demote，除非用户明确要求或召回缺口需要补跑；Unpaywall 缺 email 要写成 `provider_gaps` / `unpaywall_email_missing`，不能把 OA fallback 失败解释成论文不可得。可选 Grok targeted 模式会先等待 paper-search 经过 normalize/filter/rank 评估；如果 paper-search 至少已有 3 个 Tier A/B 或 advance-candidate、至少 2 个 staging-ready 或稳定身份、且没有 required/recommended provider gap，就跳过 Grok。Grok parallel 模式在 paper-search 完整生命周期旁边启动静态补短板 query set，优先覆盖 paper-search query variants，再补 IEEE/ACM/ScienceDirect/Springer/JSTOR/Web of Science/Scopus/ResearchGate 等 gap domains；Grok 早完成不改变 paper-search，Grok 慢则按 fan-in grace 记录 timeout。Provider artifact 先分开写 `paper-search-record.json`、`grok-search-record.json`、`grok-search-raw.json`、`grok-search-evidence.json`，再合并为下游 `search-record.json`。Grok-only salvage 没有 paper-search usable candidate 时只能进 evidence/diagnostics；最终推荐至少要包含一个 usable paper-search candidate。`dry-run` 按 query variants 多次调用上游 MCP/CLI 搜索，并在 `search-record.json.query_records` 留下每条 query 的证据；`request_constraints` 会进入 `query-plan.json`、`filter-report.json`、`report.json.discovery_context.request_constraints` 和 `run-state.json`，其中 `year_min` 在 filter 阶段拒绝旧论文/缺年份候选，`code_policy=require` 拒绝缺代码元数据候选，`code_policy=prefer` 只影响排序和解释。`discover-papers` 默认保留 review/survey/meta-analysis 候选并分类排序；只有明确 non-review intent 时，query variants 才应带 `-review -survey`，filter 阶段才把 review/survey/meta-analysis 作为 hard exclusion。`report.json.discovery_context.source_coverage` 和 `report.md` 的 `Source Coverage` / `Source Routing` / `Grok Supplemental Search` 会汇总 `sources_used`、`source_results`、`errors`、`raw_total`、`deduped_total`、`query_count`、`capabilities`、`provider_readiness`、`source_routing`、`provider_gaps`、Grok mode/status/reason/counts 和 evidence paths，用于判断 paper-search MCP 是否真的完成多源召回、哪些 source 为空或失败、source 是否支持 download/read、哪些 provider env 缺口会影响 OA fallback，以及后续是否需要补跑 source route。`doctor --json` 的 `paper_search_provider_readiness` 和 `grok_search_mcp` 是同一风险层的安装期视图。`discover-papers --json` 可打印高层 run id、linked discovery / auto-staging run ids、`session_recommendations`、`auto_staging_plan` 和 artifact paths；`dry-run --json` 仍可打印底层 evidence run id 和 `query-plan.json`、`search-record.json`、`filter-report.json`、`discovery-diagnostics.json`、`rank.json`、`report.md`、`report.json`、`run-state.json` 路径，便于 agent 串联后续命令。工作流图中的 Report step 对应公开 CLI `report --run-id <run-id> [--json]`：它只读取已有 `_paper_source/runs/<run-id>/report.md`、`report.json` 和 `run-state.json` 并展示，JSON 输出包含 `report`、`run_state`、`markdown` 和 artifact paths，不重新执行 discovery、ingest、MinerU、staging、Zotero 或 wiki 写入；`report_run.py` 是生成和读取这些 run report artifact 的内部模块，不是单独的 `run-report` CLI。`--no-query-plan` 可用于单条原始检索调试，也可用于 profile-derived 计划偏离当前请求时的精确短语重跑；如果 planned query 把主题泛化成用户画像之外的宽泛方向，不要停在泛化结果上。检索应采用 two-stage retrieval：第一阶段扩大 raw candidate pool，第二阶段按 DOI/arXiv base id/source_id/title 去重，先查 wiki `_meta/reference-index.json`，再查 `_paper_source/raw/*/metadata.json` fallback，按显式请求过滤综述/非综述、分类 paper type、核验 DOI/venue/year/PDF/citation/metric，再排序输出。`rank.json` 必须把 `quality_gate` 和 `quality_tier` 作为独立证据层暴露：Tier A 需要 stable identity、PDF、topic fit 和验证信号，venue prior 不能单独放行。query plan 扩展词只用于召回和 venue/source gap 检查；ranking 的正向画像匹配词应来自用户 config 和当前请求核心词，避免把 `world model`、`foundation model`、`reinforcement learning` 这类宽召回词当成窄主题必须命中项而压低优质候选。对强 seed paper，允许用 citation graph 查 journal version、recent cited-by、references 和 related papers，并在 `Paper Source 实测证据` 记录扩展证据。

`topic-tracking` skill 负责把 wiki `_meta/reference-index.json`、多次 dry-run 和库内去重串成纵向账本：它比较 deposited reference index、prior runs、raw metadata、`already_in_wiki` / `already_in_library` 结果、coverage gap 和 backlog priority，而不是把单轮 top-N 当成最终主题答案。`paper-discovery` 仍然是检索、query plan、source routing 和 ranking 的底层能力。

自然语言 `discover-papers` 不默认排除 review/survey/meta-analysis。它会保留这些候选进入分类、排序和推荐附录，并由 auto-staging policy 对进入 source-staging 的 review/survey/meta-analysis 默认最多占 1 个 slot。只有用户明确要求“非综述”“不要 survey”“original research only”等 non-review intent 时，查询才应带上 `-review -survey`，并且 filter 阶段把 review、survey、systematic review、literature review、meta-analysis 等文档类型作为 hard exclusion 写入 `filter_reasons`，例如 `excluded_terms:review,survey`。若用户明确找综述或 survey，则继续保留并单独标注这些 paper type。

### 3. 采集、解析与 raw 留痕

入口：`prepare-ranked` 用于搜索后采集 + MinerU 解析 + source-staging 报告，并停在用户批准和最终 wiki 写入之前；`advance-ranked`、`advance-paper`、`advance-batch`、`ingest-one`、`parse-paper` 用于继续完整 ingest 或单步修复。默认 `workflow_mode=fast-ingest`，只保存源论文材料、写中文审批报告和 `wiki-ingest-brief.json`，不跑 reader/critic；`--mode reviewed-ingest` 才加 reader；`--mode audited-ingest` 才加 reader+critic。实测批量命令应使用 `prepare-ranked --max-papers 10 --skip-existing`，使已完成 source-staging 的论文不占补跑预算；`--max-papers 1` 仅用于 smoke test。`--skip-existing` 要求 `paper.pdf`、MinerU Markdown/images/manifest、`parse-record.json status=success` 以及同模式 `promotion-plan.json` 同时成立；若存在非空原生 `mineru/paper.tex`，它也作为可选公式源参与后续复核，但 Markdown-only 成功解析不能因缺少 TeX 被判为未完成。采集阶段先用 DOI/title/source identity 调用 paper-search MCP `download_with_fallback`，默认开放访问链为 source-native、OpenAIRE、CORE、Europe PMC、PMC、Unpaywall；Sci-Hub 默认关闭，只有显式 opt-in 才加入 fallback chain。若候选没有 direct PDF URL 且 OA fallback 无 PDF，立即写 `failure_class=manual-download-required` 和 `manual_download.candidate_manual_urls`，由 agent 把 DOI/出版商链接给用户，通过 organization/institution 手动下载或提供本地 PDF；不要继续弱 fallback 循环。`prepare-ranked` report 和 `runs-query --json` 必须暴露 `manual_downloads`，让对话层能直接给用户 DOI/publisher 跳转链接。若候选有 direct PDF URL，fallback tool 不可用或没有产出 PDF 时再回退 source-native MCP `download_<source>`、CLI 或 direct URL。成功 `acquire-record.json` 记录 `doi`、`title`、`use_scihub`、`fallback_chain`、`mcp_server_probe` 和 `upstream.tool`；采集成功后必须先做轻量 PDF 身份核验，写 `identity_check`，只有 DOI/title 通过或无法提取时才允许进入 MinerU；若提取出的 DOI/title 明确不匹配，写 `identity-check.json`、`failure_class=identity-mismatch`，把 PDF 移入 `_paper_source/quarantine/papers/<slug>/paper.pdf`，并阻止 MinerU。采集成功后可调用 MCP `read_<source>_paper` 或 CLI read 写 `_paper_source/raw/<slug>/paper-search-read-preview.txt`，并在 `retrieval_preview` 记录 status、tool、char_count 和上游 probe。这个 sidecar 是 non-authoritative retrieval preview，用来判断上游 retrieval/extraction 是否可读，not replacing MinerU；final wiki ingest must use MinerU Markdown as the primary formula, notation, method-context, and prose source, and fall back to `paper.pdf`, figure/formula indexes, or image evidence only when Markdown is missing, wrong, ambiguous, or insufficient; non-empty native `mineru/paper.tex` is only an optional cross-check. 失败记录仍保留 direct URL 的 `candidate_pdf_urls`、`acquire_attempts`、`failure_class`、`retryable`、`recovery_hint`，以及需要人工补 PDF 时的 `manual_download`。自动化串联时使用 `prepare-ranked --json`，输出 prepared run id、source run id、processed/skipped counts、`stops_after=source-staging` 和 report artifact 路径。MinerU 子进程默认超时 7200 秒，可用 `--mineru-timeout <seconds>` 或 `PAPER_SOURCE_MINERU_TIMEOUT` 覆盖；若 MinerU 已 `done` 但 `full_zip_url` 因 Clash/mihomo fake-IP、TLS EOF 或 CDN DNS 问题下载失败，可在 MinerU env file 中设置 `PAPER_SOURCE_MINERU_CDN_RESOLVE=cdn-mineru.openxlab.org.cn=<ip>`，下载器会在普通重试失败后对匹配 host 临时使用该 IP，同时保留原 HTTPS hostname/SNI，并在成功时把 `download_recovery` 写入 `mineru-manifest.json`。

关键产物：

- `_paper_source/raw/<slug>/paper.pdf`
- `_paper_source/raw/<slug>/metadata.json`
- `_paper_source/raw/<slug>/acquire-record.json`
- `_paper_source/raw/<slug>/paper-search-read-preview.txt`（可选 non-authoritative retrieval preview）
- `_paper_source/raw/<slug>/mineru/<slug>.md`
- `_paper_source/raw/<slug>/mineru/paper.tex`（可选，只有 MinerU 返回非空原生 TeX 时保留）
- `_paper_source/raw/<slug>/mineru/images/...`
- `_paper_source/raw/<slug>/mineru/mineru-manifest.json`
- `_paper_source/raw/<slug>/figure-index.json`
- `_paper_source/raw/<slug>/formula-index.json`
- `_paper_source/raw/<slug>/asset-normalization-record.json`
- `_paper_source/raw/<slug>/evidence-index.json`
- `_paper_source/meta/evidence-index.json`
- `_paper_source/raw/<slug>/run-state.json`

采集失败时，`acquire-record.json` 必须包含 `failure_class`、`retryable` 和 `recovery_hint`，用于区分 `manual-download-required`、`no-url`、`already-exists`、`empty-pdf`、`access-denied`、`not-found`、`rate-limited`、`server-error`、`http-error`、`network` 和 `unknown`，让 agent 决定重试、换源、手动补 PDF 或跳过。`manual-download-required` 必须附带 `manual_download`，包含 `doi_url`、`candidate_manual_urls`、`preferred_next_step` 和 `_paper_source/tmp-manual-pdfs` 入口。

成功解析时只保留最终 `mineru/` 产物和 `mineru-command/stdout.txt`、`mineru-command/stderr.txt` 日志，不保留重复的 `mineru-command/paper` 或 `mineru-command/parsed` 大型工作副本。若 MinerU 返回非空原生 `.tex`，Paper Source 保留为 `mineru/paper.tex` 并记录 `tex_source=mineru-native`；若 MinerU 只返回 Markdown，Paper Source 记录 `tex_source=paused-no-native-tex`，不再从 Markdown 合成整篇 LaTeX fallback，Markdown 中的公式必须保持完整。解析成功后默认运行 raw asset normalization：hash-like 图片按附近 `Fig.` / `Figure` / `图` 标签重命名为稳定 `fig-###-*` 文件，无法映射的图片保留为 `unmapped-*` 并进入 review；有 Markdown/TeX LaTeX 证据的公式截图不作为 evidence figure 保存，原图片删除，Markdown 图片引用删除，公式记录进入 `formula-index.json`。解析失败时保留错误和 run-state，不进入 staging 或 compiled wiki；若 stdout 显示 batch done 但缺少 Markdown，记录 `MinerU reported done but produced no Markdown output` 以便区分 upstream 完成但本地无可用 Markdown 的情况。

历史 raw bundle 或 historical `_epi/raw/<slug>` 可用 `normalize-mineru-assets --slug <slug> --vault <vault> [--execute] [--json]` 修复。默认不带 `--execute` 是 dry-run，只输出 rename/drop/review 计划；执行模式才重命名 raw 图片、改写 MinerU Markdown、同步 sibling Markdown（如历史 `paper.md`）、写入 `figure-index.json`、`formula-index.json` 和 `asset-normalization-record.json`。该命令只修复 raw bundle，不修改正式 wiki 页面。

### MinerU Figure And Formula Indexes

After MinerU parse success or explicit `normalize-mineru-assets --execute`, Paper Source writes three raw-bundle sidecars:

- `figure-index.json`: one record per preserved figure/image, including `figure_id`, original `Fig.` / `图` label, normalized path, old hash path, caption text, Markdown locator, image hash, mapping status, and warnings.
- `formula-index.json`: formula screenshot cleanup records, including equation label when detected, recovered Markdown/TeX LaTeX when available, Markdown/TeX locators, dropped image refs, confidence, and warnings.
- `asset-normalization-record.json`: run record with `mode`, input hashes, rename plan, dropped formula images, rewritten files, review queue, warnings, embedded figure/formula index payloads, and output hashes.

这些 sidecar 是 Paper Wiki 修复正式页证据图和公式引用的输入。Paper Source 负责 raw 命名和公式截图过滤；Paper Wiki 只消费索引并维护正式页，不在 wiki 维护流程中重命名 raw assets。

### Full-Text Evidence Index

After MinerU parse success, Paper Source writes `_paper_source/raw/<slug>/evidence-index.json` and updates `_paper_source/meta/evidence-index.json`. The per-paper index stores page/section/chunk locators, chunk hashes, source artifact hashes, and warnings. It is a locator aid for claim support and wiki provenance; it does not replace `paper.pdf`, MinerU Markdown/images/manifest, optional non-empty native TeX, or final source review.

### 4. Reader 生成

reader 的目标是降低阅读负担，并在 reviewed/audited 模式下给 critic 或最终 wiki agent 提供证据索引；它不替用户生成无限扩展的研究议程，也不是默认 fast-ingest 的必经步骤。

三角色分工：

- `nature-sci-editor`：中心主张、重要性、叙事克制、scope 是否过度。
- `peer-reviewer`：方法、baseline、metric、dataset/task、实验设置、证据链。
- `senior-domain-researcher`：理论启发、实验思路、领域迁移价值、应进入 wiki 的知识点。

关键产物：`reader/reader.md`、`reader/editorial-summary.md`、`reader/technical-reading.md`、`reader/research-notes.md`、`reader/figures.md`、`reader/reproducibility.md`、`reader/implementation-ideas.md`、`reader/evidence-map.json`、`reader/claim-support.json`。任何核心贡献、性能提升、SOTA、泛化能力和实验结论都应能追溯到 Evidence；`claim-support.json` 用于区分 source-grounded、metadata-only、inferred 和 unsupported claim。

### 5. Critic 质量门

audited-ingest 硬规则：critic report 一旦存在，必须 pass 才允许进入 source-staging 和后续 wiki handoff；默认 fast-ingest 不要求 critic。

critic 包含：`paper-quality-critic`、`parse-quality-critic`、`reader-quality-critic`、`editorial-significance-critic`、`peer-review-methods-critic`、`domain-fit-critic`。`parse-quality-critic` 不只是确认 `mineru/<slug>.md` 存在，还会把 `mineru/images/*`、`mineru/mineru-manifest.json`、`parse-record.json`、figure/formula indexes，以及非空原生 `mineru/paper.tex`（若存在）一起当成解析物化证据面板；Markdown-only 成功解析应从 MinerU Markdown/PDF 复核公式，不能因为没有 TeX fallback 被误判为失败。

paper-quality 重点检查学术论文可靠性：

- `paper_identity`：title、来源 URL、DOI、arXiv ID、venue 至少有稳定身份信息。
- `claim_support`：核心贡献、性能提升、SOTA、泛化声明必须有 Evidence。
- `benchmark_integrity`：reader artifact 自己写出的 better/outperform/SOTA 断言需要 baseline、metric、dataset/task 或实验设置；源论文全文中的综述性 improvement/better 词汇不能单独把 reader 打回。
- `engineering_reproducibility`：code/data/model/config/simulator/hardware 缺失只 warning。
- `scope_overclaim`：防止 simulation/demo/small-scale 被写成真实部署或通用结论。
- `parse_vs_paper_failure`：防止 MinerU 缺图/公式导致误判论文没有相关内容。

关键产物：`critic/critic-report.json`、`critic/critic-quorum.json`、`critic/research-decision.json`、`critic/reader-revision-plan.json`、`critic/reproduction-plan.json`。`reproduction-plan.json` 只作为 reproducibility caveat，不是主阅读报告，也不默认写 compiled wiki。

### 6. Paper Gate

入口：`paper-gate --slug <slug> [--json]`。它是 GitHub checks 风格的只读状态面板，只读 `_paper_source/raw` 和 `_paper_source/staging` 证据，不写 `_paper_source/runs`、raw、staging 或 compiled wiki。

检查项：`critic-report`、`critic-outcome`、`hard-rule`、`critic-quorum`、`promotion-plan`、`staged-drafts`、`wiki-ingest-brief`、`final-wiki-authority`、`human-approval`；新 agent-mediated 计划不把 retired task file 当成 ready，也不检查 compiled targets。gate `failure` 时不得进入最终 wiki 写入。当前 agent-mediated 计划只有在 `next_action=run-wiki-ingest-agent`、`failure_checks=[]` 且 `action_required_checks == ["human-approval"]` 时，才允许记录前置批准：`record-human-approval --scope run-wiki-ingest-agent` 会写 `_paper_source/staging/papers/<slug>/human-approval.json`。批准记录有效后，gate 进入 `status=ready_for_wiki_ingest_agent`、`check_suite.conclusion=success`，`wiki-ingest-handoff` 才显示 `ready_for_agent=true`；此时 `wiki-ingest-trigger` 可写 `_paper_source/staging/papers/<slug>/wiki-agent-trigger.json`，把当前 Claude、Codex 或其他 wiki-capable agent 需要执行的 source-first wiki 写入指令变成机器可读 resume artifact。agent 完成最终页后，`record-wiki-ingest` 会验证这个前置批准 artifact 和相同 `approved-by`，再写入 `wiki-ingest-record.json`；此后 gate 进入 `status=wiki_ingest_recorded`、`next_action=review-recorded-wiki-pages`。

`wiki-ingest-brief.json` 是 canonical Paper Source-to-Paper Wiki handoff；`wiki_deposition_task.json` 是历史清理对象，task-only handoff 不能被 gate 当成 ready。brief 检查必须验证 `wiki_rule_source_model`、formal page families、required Paper Source/Paper Wiki skills 和 frontmatter schema，确保 handoff 明确 target vault contract 和 Paper Wiki canonical 写入层 `paper-research-wiki` / `$paper-research-wiki`。`llm-wiki`、`wiki-ingest`、`wiki-context-pack`、`wiki-lint`、`wiki-stage-commit`、`wiki-status`、`wiki-query`、`wiki-provenance` 和 `tag-taxonomy` 等 external wiki skills are optional helpers / policy references；个性化 wiki-skills、Ar9av/obsidian-wiki、kepano/obsidian-skills 和本机 helper skills 只作为规则来源优先级，不是 Paper Source runtime required stack。

### 7. Source Staging 与轻阅读报告

默认 fast-ingest 在源材料完整后即可写 source-staging 报告；reviewed-ingest 需要 reader 完整；audited-ingest 需要 critic pass。若任何模式下已经存在 critic report 且 outcome 非 pass，Paper Source 不会绕过该失败继续 staging。

staging 生成证据包和非权威 handoff，不生成 per-paper 正式路由草稿：

- `_paper_source/staging/papers/<slug>/evidence/source-reader.md`
- `_paper_source/staging/papers/<slug>/briefs/reading-report.md`
- `_paper_source/staging/papers/<slug>/wiki-ingest-brief.json`
- `_paper_source/staging/papers/<slug>/promotion-plan.json`
- `_paper_source/staging/wiki-batches/pending/wiki-batch-ingest-brief.json`

轻阅读报告是默认入口，也是人工确认报告（approval report）的默认来源。结构侧重：`快速判断`、`论文身份`、`术语中英对照`、`理论与方法`、`实验/验证方式`、`证据强度与可信状态`、`主要 Caveat`、`Wiki 沉淀价值`、`质量门禁`、`沉淀建议`、`复现 Caveat`。`证据强度与可信状态` 把 critic panel 的 blocking/warning 与复核 caveat 翻译成 `accepted`、`accepted-with-caveats` 或 `blocked-by-critic`，帮助用户先判断阅读信任边界。

人工确认报告（approval report）是 `record-human-approval` 前给用户看的唯一阅读入口，优先复用完整的 `_paper_source/staging/papers/<slug>/briefs/reading-report.md`，批处理时可汇总成一份 report 并给每篇论文一张短卡片。它必须中文优先、可快速扫读、信息密度足够，禁止要求用户从 raw JSON、gate 输出、critic sidecar 或路径清单里做批准判断。每篇卡片应包含论文身份信息、理论方法思路、实验/验证方式、证据强度、主要 caveat、建议进入的 wiki 路由和中英对照术语；每篇结尾必须给出 `建议沉淀`、`谨慎沉淀` 或 `暂不沉淀` 三档沉淀建议。

`wiki-ingest-brief.json` 是给 wiki-ingest agent 的机器可读证据 handoff，记录 trust status、source bundle、suggested routes、三角色阅读 lens、证据计数、推荐阅读路径和 `final_source_review_contract`；它不决定最终 wiki 页面，也不进入 compiled targets。`source bundle` 必须先读 `paper.pdf`、`metadata.json`、`mineru/<slug>.md`、`mineru/images/*`、`mineru/mineru-manifest.json`、`figure-index.json`、`formula-index.json` 和 `asset-normalization-record.json`；若存在非空原生 `mineru/paper.tex`，再作为可选公式/符号源补充复核。reader/critic 只是降低阅读负担的导航层，不是源论文本身。最终 Obsidian/LLM Wiki 沉淀必须由 agent 读取目标 vault contract 后执行：优先 `AGENTS.md`、`_meta/agent-operating-contract.md`、`_meta/schema.md`、`_meta/taxonomy.md`、`_meta/directory-structure.md`，再结合 Ar9av/obsidian-wiki 的 agent-mediated wiki 框架、kepano/obsidian-skills 的 Obsidian 语法约定、initiatione/obsidian-wiki-dev `liuchf/wiki-skills` 的个性化 vault-contract 规则，搜索已有页面后再蒸馏、合并、写入或 staged writes。QMD 只能作为检索辅助：`paper-research-wiki` qmd collection 可索引七类正式页 `references/`、`concepts/`、`derivations/`、`experiments/`、`synthesis/`、`reports/`、`opportunities/`，以及 `AGENTS.md`、`index.md`、`hot.md`、`log.md`、`_meta/` 合约页；必须 ignore `_paper_source/**`、`.obsidian/**`、`.claude/**`，因此 `_paper_source/meta/formal-page-snapshots/`、`_paper_source/raw/<slug>/mineru/<slug>.md`、`_paper_source/raw/<slug>/mineru/paper.md`、`_paper_source/raw/<slug>/mineru/paper.tex` 和其他 MinerU source Markdown 不进入 QMD。用 `qmd collection show paper-research-wiki`、`qmd ls paper-research-wiki/_paper_source`、`qmd ls paper-research-wiki/_paper_source/meta/formal-page-snapshots` 验证边界后再信任 QMD 查询。最终页面必须重读原文、公式、图片和表格，不可只靠 reader summary 落页；写完最终页后还要生成 `final-source-review.json`，记录源工件 hash、公式复核、图表/图片复核、PDF fallback 决策和最终页 provenance。`wiki-provenance` skill 负责把 source-grounded、metadata-only、inferred 和 unsupported claim 继续保持到最终页，让 provenance 和 evidence address 进入可查询页面，而不是只留在 Paper Source sidecar JSON。复现相关内容只放在 caveats 中，不挤占理论和实验思路篇幅。

`wiki-ingest-brief.json` 还会暴露 `evidence-index.json`、`figure-index.json`、`formula-index.json`、chunk count、input hashes、warnings 和 `_paper_source/meta/evidence-index.json`，供 wiki agent 按 page/section/chunk、figure label 和 formula locator 快速定位候选证据。这些 index 只能作为 locator aid；最终页上任何关键 claim 仍必须回查 MinerU Markdown、images、manifest、非空原生 TeX（若存在）和必要时的 `paper.pdf`，并在 `final-source-review.json` 中记录 source-first 复核。

### 8. Wiki Ingest Handoff、Legacy Promotion、Rollback、Redo

当前默认路径是 Paper Wiki brief-first handoff：`promotion-plan.json` 记录 `handoff_type=agent-mediated-wiki-ingest`、`wiki_write_model=wiki-skill-batch-distillation`、`final_page_authority=wiki-skill-batch-distillation`、`wiki_ingest_brief_path`、`wiki_batch_ingest_brief_path`、`agent_handoff_paths`、`final_source_review_contract` 和 `suggested_final_source_review_path`。Paper Source 不用固定脚本决定最终 Obsidian Wiki 页面路径；`references/`、`concepts/`、`derivations/`、`experiments/`、`synthesis/`、`reports/`、`opportunities/` 是 Paper Wiki `$paper-research-wiki` 和 obsidian-wiki skill layer 的正式写入区。`paper-source-paper-deposition` 只用于历史 handoff 清理，不再由 Paper Source staging 生成 per-paper pseudo routes。

注：`wiki-ingest-brief.json` 是 canonical handoff；`wiki_deposition_task.json` is deprecated（只作为历史 cleanup / migration artifact），新链路不应再依赖它作为必需 artifact。

入口：`wiki-ingest-handoff --slug <slug> [--json]`。它是只读 handoff 渲染器，不写 `_paper_source/runs`、raw、staging 或 compiled wiki。输出内容包括：当前 `paper-gate` 摘要、`promotion-plan.json` / `wiki-ingest-brief.json` / `human-approval.json` 路径、目标 vault contract 文件是否存在、`wiki_rule_source_model` 的优先级、framework references、suggested routes、trust status、final-source-review 合同、执行器中立策略和 agent checklist。`research-queue --bucket ready_to_promote --actions` 对 agent-mediated plan 必须给出该命令，用户或 agent 先阅读 handoff，再记录前置 human approval，之后才按目标 vault contract 执行最终 wiki ingest。

入口：`record-human-approval --slug <slug> --approved-by <name> --scope run-wiki-ingest-agent [--json]`。它是 agent-mediated wiki ingest 的前置人类批准记录器，只在当前 `paper-gate` 无 failure checks、唯一 action-required 为 `human-approval`，并且用户已经读过单一人工确认报告（approval report）后，才写 `_paper_source/staging/papers/<slug>/human-approval.json`，schema 为 `paper-source-human-approval-v1`。Codex automation 只能显式 opt-in：`--approved-by codex-automation:<task-id> --automation-mode codex-task --automation-task-id <task-id> --automation-task-source <task-path-or-session> --automation-authorization "<explicit user authorization>"` 必须同时出现并匹配；普通 `discover-papers`、auto-staging 或“找论文”请求不得推断 automation。automation approval 仍使用同一个 approval artifact，只增加 `approval_actor_type=codex-automation` 和 `automation` 审计对象。它不得写最终 wiki 页面，也不得替代 final wiki agent。

入口：`wiki-ingest-trigger --slug <slug> [--json]`。它是 agent-mediated wiki ingest 的继续/触发入口，只在 `wiki-ingest-handoff.ready_for_agent=true` 时写 `_paper_source/staging/papers/<slug>/wiki-agent-trigger.json`，schema 为 `paper-source-wiki-agent-trigger-v1`。未批准时返回 `status=action_required`、`next_action=record-human-approval`，不写 trigger artifact；已完成记录时返回 `next_action=review-recorded-wiki-pages`。批准记录包含 automation metadata 时，trigger 透传 `approved_by`、`approval_actor_type`、`automation_mode` 和 `automation_handoff`，让正在运行的 Codex 任务可审计继续依据；普通 human approval trigger 不包含 `automation_handoff`。该命令不在后台自动启动 Claude/Codex 进程，也不写最终 wiki 页；它把“当前 agent 可以开始按目标 vault contract、wiki-provenance 和 source-first closure 写 wiki”变成下一次 `@Paper Source` 或当前会话可消费的机器可读指令。

入口：`record-wiki-ingest --slug <slug> --page <final-page.md> [--page ...] --approved-by <name> --source-review <final-source-review.json> [--json]`，或 ask-mode 自动化入口 `record-wiki-ingest --from-paper-wiki-request _paper_source/staging/papers/<slug>/paper-wiki-record-request.json [--json]`。

Paper Wiki writes the request artifact; Paper Source consumes it：`paper-wiki-record-request.json` 使用 `paper-wiki-record-request-v1` 和 `automation_mode=ask`，携带最终页路径/hash、`final-source-review.json` 路径/hash 与 human approval identity。它是 agent-mediated 完成态记录器，不替 final wiki agent 写页面。

它重新检查 `paper-gate`，只允许无 failure checks 且当前为 agent-mediated wiki ingest 状态；要求已存在前置 `human-approval.json`，且 `--approved-by` 或 request 内的 `approved_by` 必须和批准 artifact 的 `approved_by` 完全一致。Paper Source validates live page hashes、校验每个最终页是 vault 内 Markdown 文件，且不在 `_paper_source`、旧 `_raw`、旧 `_staging`、旧 `_runs`、旧 `_quarantine`、`.obsidian` 等内部目录。

`record-wiki-ingest` 验证 `final-source-review.json` 中的 `paper.pdf`、`metadata.json`、MinerU Markdown、images、manifest、figure/formula indexes hash；若存在非空原生 `mineru/paper.tex`，只作为 optional cross-check 复核记录。它要求公式复核以 MinerU Markdown 为主，只有 Markdown 缺失、错误、歧义或不足时才回退 PDF、`formula-index.json`、`figure-index.json` 或图片证据；还要求图表/图片复核、PDF fallback 决策和每个最终页 `source_grounded=true` provenance。

它还要验证 formal frontmatter 必填字段 `title/category/page_family/tags/aliases/sources/summary/provenance/base_confidence/lifecycle/lifecycle_changed/tier/created/updated`、`category/page_family` 与七类目录一致、initial lifecycle 只能是 `draft`、frontmatter `sources` 必须是标题显示的 canonical `_paper_source/raw/<slug>/paper.pdf` Markdown PDF 链接、正文 `## 原文与证据入口` 必须包含同样以论文标题显示的 clickable PDF URI、Obsidian wikilinks 只指向正式页面家族、provenance.extracted/inferred/ambiguous、禁止 `_paper_source/` 进入正式图谱、禁止 forbidden formula blocks，以及 `derivations/` 变量定义/推导链、`references/` 模型/公式/实验/限制、`synthesis/` cross-paper comparison matrix 等 family-specific gate。旧 `lifecycle: review-needed` 只能作为迁移/修复对象，不能作为记录后的 steady state。

记录器读取并记录页面 sha256、大小、相对路径、`promotion-plan.json`、`wiki-ingest-brief.json`、`human-approval.json`、`source_bundle`、`wiki_rule_source_model`、`final_source_review`、Paper Wiki request metadata 和 approval 元数据；历史 cleanup 才可引用 `wiki_deposition_task.json` 作为迁移线索。它只写 `_paper_source/raw/<slug>/wiki-ingest-record.json`、`_paper_source/staging/papers/<slug>/wiki-ingest-record.json`、一次 `_paper_source/runs/record-wiki-ingest-*` 报告和该论文 raw `run-state.json`，不得修改最终 wiki 页面、manifest/index/log/hot。记录后 `paper-gate` 应显示 `wiki_ingest_recorded`，后续 Zotero/report/人工复核可以读取真实 final page paths、hashes 和 source-first closure。

入口：`wiki-ask --question "<research question>" --vault <vault> [--json]`。这是 read-only formal graph query，不是 record-request ask-mode automation。只读问答的对话主入口是 Paper Wiki `$paper-research-wiki` 的 `ask_wiki`；Paper Source `wiki-ask` CLI 是同源能力的 fallback / 程序化 `--json` 入口。对话场景优先 Paper Wiki。它从正式页根 `references/`、`concepts/`、`derivations/`、`experiments/`、`synthesis/`、`reports/`、`opportunities/` 检索，利用 backlinks、outlinks、reciprocal links、aliases、tags 和 co-links 扩展上下文，并只读解析 frontmatter `sources` 及正文 `## 原文与证据入口` 中的 canonical `_paper_source/raw/<slug>/paper.pdf` Markdown PDF URI 来确认源 PDF/MinerU artifact 可用性；historical `_epi`、内部 wikilink PDF、短标签或 plain path 仅作为修复候选，不作为正常 evidence fallback，`_paper_source/raw` 不进入 formal graph。QMD 仅作为 optional accelerator；不可写 `log.md`、正式页、QMD、`paper-wiki-record-request.json` 或任何 Paper Source artifacts。输出必须区分具体的 `【Wiki 证据】`、`【综合判断】`、`【推断】`、`【边界/不确定】` answer sections，并把 broken wikilinks、duplicate aliases、source/frontmatter mismatch、stale tracking links 和 forbidden `_paper_source/**` formal graph links 作为 correction candidates，ask before repair。

若已有记录被修正为 `premature-wiki-ingest-record`，修正记录写在 `_paper_source/meta/record-corrections/`。当 `status_after_correction.wiki_quality_status=pending-paper-wiki-review` 时，`paper-gate` 显示 `wiki_ingest_record_corrected`，不能把旧 `wiki-ingest-record.json` 当作已完成；下一步是让 Paper Wiki 检查或修复正式页和 `final-source-review.json`。Paper Wiki repairs pages and `final-source-review.json`; Paper Source writes or replaces `wiki-ingest-record.json`: 当状态变成 `paper-wiki-reviewed-ready-for-paper-source-record` 后，`paper-gate` 回到 `ready_for_wiki_ingest_agent`，此时应 rerun `record-wiki-ingest` to replace the premature record。Paper Wiki 只能报告 readiness，不能直接替 Paper Source 写 replacement record。

Zotero 是可选 side tool，不是论文/wikibase 质量门。`record-wiki-ingest` 会根据 `<vault>/_paper_source/meta/paper-source-config.yaml` 的 `zotero.enabled` / `zotero.collection` 写本地 `_paper_source/raw/<slug>/zotero-record.json`：禁用或未配置时记录 `status=skipped` 和 reason；启用时记录 `status=recorded`、collection、metadata snapshot、`wiki-ingest-record.json` 摘要和 final wiki page hashes。它不调用外部 Zotero API、不删除已有 Zotero 数据；`report.md` / `report.json` 会显示 `zotero_results`，让 Step 12 -> Step 14 在运行证据里闭合。

`redo-acquire`、`redo-parse`、`redo-read`、`redo-read --from-revision-plan --recritic`、`recritic` 用于修复阶段问题；audited-ingest 的 reader 修复后必须重新 critic。

### 9. Run Index 与 Research Queue

run index 是状态面板，不是 research agenda。Paper Source 不暴露 `research-agenda`，也不生成 `_paper_source/runs/research-agenda.json` 或 `_paper_source/runs/research-agenda.md`。

队列 bucket：

- `ready_to_promote`：critic/staging 看起来可推进；当前默认含义是 ready for wiki-ingest handoff，仍需当前 paper-gate 和人类批准。
- `needs_reader_repair`：reader 或 critic 有阻塞问题，需要 redo-read/recritic。
- `warning_only`：无阻塞但有 warning，需要用户理解风险。
- `reproducibility_caveats`：工程可复核性信息不完整，只作为短复核提醒。

`waiting_for_human_gate` 是非失败状态，应进入 human gate pending 和 `ready_to_promote`，不计入 failed runs。`ready_to_promote` item 可附带紧凑 `paper_gate` 摘要：`status`、`conclusion`、`next_action`、`action_required_checks`、`failure_checks`。

`research-queue --bucket ready_to_promote --actions` 必须以当前 `paper-gate` 为准，而不是旧 run report 或 `_paper_source/runs/index.json` 缓存。生成 actions 时要现场重算 `paper_gate` 和 reason。若当前 gate failure、unknown、构建失败，或待办不是精确 `human-approval`，只能建议 `inspect-paper-gate`；agent-mediated plan 应先建议 `wiki-ingest-handoff` 和 `record-human-approval`，批准后建议 `wiki-ingest-handoff` 和 `wiki-ingest-trigger`。

`_paper_source/runs` 和 `_paper_source/meta/*` 维护记录都是过渡态证据区，需要生命周期管理。Paper Source run 结束后会自动检查 `_paper_source/runs` 下单次 run 目录数量；超过 15 个时自动应用 lifecycle cleanup，保留最新 15 个 terminal run，并按 workflow 至少保留 2 个。`paper-source-repository-cleanup` 的默认总量预算是 3000 files / 1 GiB；它不再只在总文件数/体积超阈值时才清理，还会按 `_paper_source/policies/retention.json` 的 lifecycle 上限持续约束可再生产物：terminal run dirs、run-lifecycle manifests、raw-cleanup manifests、repository-maintenance manifests、migration/reset manifests、formal-page snapshots 和临时 manual PDFs。手动入口：`run-lifecycle --keep-latest 15 --keep-per-workflow 2 [--max-age-days N] [--apply] [--json]` 和 `paper-source-repository-cleanup --preview --json` / `paper-source-repository-cleanup --json`。`paper-source-repository-cleanup --preview --json` 必须是 no-write inspection，不刷新 `_paper_source/manifest.json`，不创建缺失目录，不 seed policy；非 preview 才可删除 lifecycle-bounded maintenance artifacts。它不得删除 `_paper_source/raw` 原始论文、最终 wiki、Zotero 记录、配置文件或配置历史；清理 manifest 写入 `_paper_source/meta/repository-maintenance/`，且该目录自身也受 retention 上限约束。

论文发现必须和 wiki backlog / 已下载库去重。`dry-run` 在 filter 阶段先读取 `_meta/reference-index.json`，按 DOI、arXiv base id、source_id、normalized title 匹配已沉淀论文；命中时写入 `filter_reasons: already_in_wiki:<page>`。随后扫描 `_paper_source/raw/*/metadata.json` 作为 fallback；命中 source bundle 时写入 `filter_reasons: already_in_library:<slug>`。两者都不得再次进入 `rank.json` 推荐，除非用户明确要求更新、修复或重读该论文。

## Skill-Aware Evolve

Paper Source 自进化是 proposal-based，不直接修改插件代码、用户配置或 compiled wiki。设计借鉴 SkillOpt（有边界的目标资产优化、rejected edit buffer、非退化验证）和 EmbodiSkill（先区分技能缺陷与执行偏差）。

输入：run evidence、human feedback、Plugin Eval、`paper-source-quality-gates` metric pack、benchmark report、critic warning/failure pattern。输出：reflection type、evidence type、classification、target asset、rationale、proposed change、evidence、before metrics、acceptance gates、bounded change、risk level、approval requirement。

插件开发质量环必须闭合为：Plugin Eval -> `paper-source-quality-gates` -> benchmark -> compare before/after -> `evaluation-brief` improvement brief -> `propose-evolution`。`evaluation-brief` 是本环的机器可读桥接命令：它把 Plugin Eval、metric pack、benchmark 和 before/after metrics 合并成 `paper-source-improvement-brief-v1`，并生成 `proposed_evolution` payload。完整 dev-loop brief 必须有 Plugin Eval JSON、`paper-source-quality-gates` JSON 和 benchmark/comparison JSON；缺任一证据源时，brief 必须写出 `source_completeness.complete=false`、`missing_sources` 和 `quality_loop_sources_complete` acceptance gate，`next_action` 应为 `collect-missing-quality-evidence`，不能伪装成可直接 `propose-evolution` 的完整证据包。`activate-evolution` 会在执行点重新检查 `quality_loop_sources_complete`：只要 `missing_sources` 或 `invalid_sources` 非空，即使 `validation_result.passed=true` 也必须拒绝激活。brief 默认写入 `.plugin-eval/improvement-briefs/`，属于本地开发产物，不随插件发布；真正改变 skill/template 仍必须走 `propose-evolution`、human approval 和 validation gates。

classification：

- `skill_change`：技能/模板确实需要变更。白名单模板如 `templates/ranking.example.yaml`、`templates/critic-checklist.example.yaml` 可在 human approval + validation pass 后应用。
- `execution_lapse`：已有指导正确但执行没遵守，必须 record-only，不改技能或模板。
- `configuration_change`：配置层问题，走配置 proposal，不由 evolution 直接改用户配置。

`configuration_change 必须 record-only`，即使目标是白名单模板也不得应用模板修改；`evolution-query` 的下一步应指向 `propose-config-update`。`skill-aware-evolve` 技能入口也必须保留这条边界提示。

激活规则：没有 human approval 不应用；没有 validation result 时进入 `_paper_source/evolution/pending/<proposal-id>.json`，`check_suite.conclusion=action_required`；验证失败进入 `_paper_source/evolution/rejected/<proposal-id>.json`，`check_suite.conclusion=failure`；通过后才进入 active。即使自定义 acceptance gates 只写 `human_approval`，系统也必须补 validation check run。带 `metric`、`operator`、`value` 的 acceptance gate 必须真实读取 validation result 并比较，例如 `plugin_eval_score >= 91`；外层 `passed=true` 不能绕过分数退化、缺失或无法比较的指标，也不能绕过 `quality_loop_sources_complete` 的缺失/无效证据源。

入口：`propose-evolution`、`activate-evolution`、`evolution-query`。推荐顺序是先 propose，再 query 看 check suite 和 next action，最后在验证可用时 activate。

## 发布质量信号

发布前至少运行：

```powershell
python -m pytest tests\paper_source -q
python -m pytest plugins\paper-source -q
python -m coverage run -m pytest tests\paper_source
python -m coverage xml -o plugins\paper-source\coverage\coverage.xml
node <plugin-eval.js> analyze <plugin-root> --format markdown
```

`tests\paper_source` 是源码仓库主测试集；`tests\paper_source\test_wrapper_entrypoints.py` 覆盖 marketplace 可见 wrapper：`scripts\orchestrator.py`、`scripts\init_paper_wiki.py` 和 MinerU skill wrapper。当前 Windows 版 Plugin Eval 用反斜杠绝对路径传给 Python 测试识别正则，而该正则只匹配 `/tests/` 或 `/test_*.py`，所以源码测试通过时仍可能出现 `py-tests-missing`。coverage XML 放在 `plugins\paper-source\coverage\coverage.xml`，默认被 `coverage/` ignore；只有发布时明确刷新才需要 `git add -f`。

Plugin Eval 是发布门槛之一：目标是 `0 fail`、coverage artifact 存在、分数不低于 `70/100`。若出现 token budget warning，优先删重复/生成文件和重复话术；不要为了静态分数把本文档移出 `plugins\paper-source\docs`，因为它是用户要求的中文链路维护契约。若出现 missing tests warning，先核对 `tests\paper_source`、coverage 和评估器路径识别；当前 Windows 反斜杠路径会导致误报，则以 pytest 与 coverage 为测试信号，并在评估记录中保留该限制。

为降低 deferred token，`docs/workflow.md`、`docs/evaluation.md` 和 `docs/config.md` 保持入口索引/最小话术；完整链路事实以本文档为准。

## 安全边界

- discover-papers 写高层 run，链接 discovery run 和 optional auto-staging run；默认可写 source-staging，但不写 approval、wiki trigger、wiki-ingest record 或 Paper Wiki 正式页。
- dry-run 写 `_paper_source/runs` 和 resumable `_paper_source/reviews`，不写 raw/staging/compiled wiki。
- raw/staging 可以写本地 artifact，但不写 compiled wiki。
- 默认 fast-ingest 不要求 critic；audited-ingest 和已有 critic report 的论文必须 critic pass。
- agent-mediated wiki ingest 和 deprecated promotion 都必须有人类 approval。
- 当前默认 plan 不产生 compiled targets；deprecated compiled targets 必须限制在允许 wiki 根目录。
- rollback 只处理 deprecated promotion record 中记录的目标。
- token、API key、MinerU token 不写入报告、不打印。
- runtime.json 不保存 token 明文；`MINERU_TOKEN` 只能来自进程环境或 `mineru.env`，报告只显示 set/missing。
- 外部工具缺失不阻止离线结构诊断。

## 用户体验目标

用户给出方向后，Paper Source 找候选论文并排序；用户或批处理推进少量高价值论文；Paper Source 保存原始证据并生成多角色 reader；critic 检查身份、证据、benchmark、scope 和解析质量；通过后生成 evidence staging、canonical `wiki-ingest-brief.json` 和轻阅读报告；用户批准后由 agent 通过 Paper Wiki `$paper-research-wiki` 按目标 vault contract 写入 Obsidian/LLM Wiki staging/formal pages；历史 handoff 残留需要清理时才经过 `paper-source-paper-deposition`；写入完成后用 `record-wiki-ingest` 回填最终页路径、hash 和 approval 完成态；用户从阅读报告开始低负担吸收知识。
