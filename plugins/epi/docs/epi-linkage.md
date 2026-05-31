# EPI 插件链路说明

本文档是 EPI 插件的主链路说明和维护契约。EPI 的核心目标是：按用户画像/config 衍生高质量论文收集 -> Obsidian/LLM Wiki 知识沉淀 -> 轻阅读负担的阅读报告。它是通用学术论文插件，不默认任何学科方向；AUV、机器人、AI、医学等词只能来自用户配置、当前请求或显式领域 hint。它不是从 0 到完成投稿的自动科研工作台，也不默认生成大型复现实验 agenda；复现只作为短小的验证线索。

## 维护契约

每次修改或优化 EPI 插件，都必须同步更新本文档。需要更新的变化包括：CLI 命令、dry-run/ingest/critic/staging/promotion/rollback/redo/wiki-query/evolution 链路、生成物路径、JSON 字段、Markdown 报告结构、Wiki 页面类型、安全边界、人类确认门、配置流程、技能说明、模板、ranking/critic 规则和阅读报告侧重点。若一次改动确实不影响链路，提交说明应写明无需更新本文档的原因。

配套文档：

- `docs/structure.md`：当前插件目录、CLI 模块、技能、模板、vault artifact 和测试边界。
- `docs/progress.md`：当前开发进度、已验证信号、未完成工作和下一步发布前检查。
- `docs/config.md`：首次使用和修改配置时的聊天式引导话术，是 `config-setup` skill 的话术来源。
- `docs/workflow.md`：给用户和安装副本看的短流程入口，避免把完整链路文档塞进日常提示。

## 目标边界

EPI 服务论文知识摄取，而不是替用户完成完整科研闭环。

- 发现：按用户研究画像、关键词、venue prior、来源和 ranking 规则找到值得读的论文。
- 留痕：保存 PDF、元数据、解析文本、reader、critic、staging draft 和 run-state。
- 审查：critic 是论文/知识库质量门。无 critic pass，不写入 compiled wiki。
- 沉淀：critic pass 后生成 wiki-ingest handoff；最终 Obsidian/LLM Wiki 页面由 agent 按 vault contract 蒸馏、合并和写入。
- 轻读：用户默认从 `reports/<slug>-reading-report.md` 开始，必要时再看 reader、evidence map 或原文。

## Obsidian Wiki 规则来源模型

EPI 不能把 Obsidian Wiki 写入规则简化成“调用本机 `llm-wiki` / `wiki-ingest` 两个 skill”。这两个 skill 只是本机执行适配器；真正的构建和写入规则必须按优先级解析：

1. 当前用户指令：本次任务目标、语言、写入边界和安全要求。
2. 目标 vault `AGENTS.md`：用户个性化约定、领域词汇、写作风格和安全边界。
3. 目标 vault `_meta/agent-operating-contract.md`。
4. 目标 vault `_meta/schema.md`、`_meta/taxonomy.md`、`_meta/directory-structure.md`：最终路由、页面类型、标签、链接、staged writes、合并/拆分策略。
5. `initiatione/obsidian-wiki-dev` 的 `liuchf/wiki-skills` 分支：个性化 multi-vault contract、QMD 只是检索辅助、Markdown vault 是 source of truth。
6. `Ar9av/obsidian-wiki`：agent-mediated LLM Wiki 架构、manifest/index/log/hot、provenance、先搜索/合并再创建页面。
7. `kepano/obsidian-skills`：Obsidian 语法、properties/frontmatter、wikilinks、embeds、callouts、bases/canvas 等格式约定。
8. 本机 `llm-wiki` / `wiki-ingest` / `obsidian-markdown`：按上述规则执行的本地 helper/adapters，不覆盖目标 vault contract。

因此 `wiki-ingest-brief.json` 必须包含 `wiki_rule_source_model`，记录 `resolution_order`、`must_read_before_final_write` 和 `write_contract_requirements`。`paper-gate` 要把这个字段纳入 `wiki-ingest-brief` 检查，避免 EPI 退化成固定脚本或单一 skill 默认规则。

## 主链路

### 1. 初始诊断与配置

入口：`doctor`、`config-status`、`config-setup` skill、`init-config`、`propose-config-update`、`apply-config-update`。

职责：检查插件结构、模板、技能目录、默认 vault、`paper-search` CLI、MinerU 命令、`MINERU_TOKEN` 和 EPI vault 配置。外部依赖缺失只提示 warning，插件结构缺失才 error。用户初次使用或修改配置时必须走 `config-setup` skill：一次只问一个问题，每步说明影响、推荐值和参考方向，不把字段名直接丢给用户，不一次性输出完整默认配置；最终确认前不得运行 `init-config` 或 `apply-config-update`。skill-aware evolution 不直接改用户配置。

配置分两层：研究画像、关键词、预算、Zotero 和人工确认门属于目标 vault 的 `_meta/epi-config.yaml`；本机 runtime 依赖属于 `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json`。runtime.json 只记录 `paper-search` MCP command/args、CLI fallback、MinerU 命令和 `mineru.env` 路径，不保存 token 明文。`runtime_config.py` 在 doctor、paper-search discovery/download 和 MinerU parse 前自动加载它，并且只补缺失的环境变量；显式进程 env 永远优先。

### 2. 论文发现与排序

入口：`dry-run`。输出只写 `_runs/<run-id>/`，不下载 PDF，不调用 MinerU，不写 raw/staging/compiled wiki。

关键产物：

- `_runs/<run-id>/normalized.json`
- `_runs/<run-id>/rank.json`
- `_runs/<run-id>/report.md`
- `_runs/index.json`
- `_runs/research-queue.json`

ranking 必须同时给机器信号和低阅读负担解释：

- `ranking_signals`：topic、venue、citation、freshness、PDF/code、benchmark、reproducibility、negative keyword penalty。
- `ranking_protocol`：advance/review 决策、正负关键词、reasons/cautions、editorial/peer-review/domain/reproducibility lens。
- `ranking_rationale`：一句话推荐、用户兴趣匹配、Nature/Sci editor、peer reviewer、senior domain researcher 三角色短评，以及建议进入 wiki 的页面类型。

当用户是在对话中要求“找最新/高质量论文”时，`paper-discovery` skill 不应只转述 `report.md` 或 `rank.json`。它需要先运行并留存 EPI dry-run 证据，再在对话框中给出人工可扫读的“推荐优先看”清单。该清单必须包含本轮找到且保留下来的全部候选论文，按阅读优先级排序，而不是只列 top 几篇；低优先级项可以缩短说明但不能直接省略。每篇用编号标题、venue/year、DOI、引用数、影响因子/分区或 `未核实`、PDF/代码可用性和 2-3 句中文说明，说明方法主线、控制任务、证据强度、优先级和 caveat。影响因子、JCR 分区、CiteScore 等质量指标必须实时核实或来自可信元数据；不能核实时明确写 `影响因子/分区：未核实`，不得凭印象补数字。随后再给“EPI 实测证据”，包含 run 路径、`source_mode`、accepted/rejected 数量，以及 setup 检查时的 `MINERU_TOKEN set/missing` 状态。不得输出 raw JSON、长摘要或任何 secret。

高质量论文检索不能把 `paper_search_mcp` 返回结果本身当成质量定义。`paper-discovery` 采用类似 `nature-academic-search` 的 bundle 结构：`SKILL.md` 只保留入口和边界，具体检索协议、query planner、领域词表、source tier、去重、venue prior、two-stage retrieval、citation graph、评测集、质量门控、多源 workflow 和输出格式分别放在 `README.md`、`scripts/query-planner.py`、`references/query-planner.md`、`references/domain-ontology.md`、`references/search-protocol.md`、`references/source-tiers.md`、`references/dedup-engine.md`、`references/venue-prior.md`、`references/two-stage-retrieval.md`、`references/citation-graph.md`、`references/evaluation-set.md`、`references/workflows/multi-source-discovery.md`、`references/quality-gate.md`、`references/output-format.md`。后续优化 query planning、source routing、质量筛选、去重或输出格式时只改对应分层文件，不把所有规则塞回一个大 skill。`query_plan` 里新增的 `domain_focus_terms` 就是这套 bundle 的“硬锚点”信号：它优先从用户画像/当前请求提取对象与任务域，和 `domain_terms` 一起把 method-only 候选挡在外面。

期刊/会议分层可用于提高高质量论文筛选能力，但只能作为 `venue_prior`。EPI 是通用插件，不能把机器人、AUV、AI、医学或任何单一学科写成全局默认；venue prior 必须来自用户画像/config、当前请求或本轮明确验证的领域资料。专业学会列表、领域数据库、出版社专题页、curated community lists 等只能作为对应领域的 prior 或 recall gap 检查来源；论坛或博客排名只能作为弱召回线索和社区主观背景，不能直接当作影响因子、JCR 分区、引用数、录用率或最终质量标签。推荐结果必须把 `venue_prior` 和 `verified_metrics` 分开展示；若影响因子、分区、CiteScore、引用数没有在本轮核实，就写 `未核实`。

当用户给出紧凑主题或要求“最新/高质量/非综述”时，`paper-discovery` 应先形成 `query_plan`：从 `_meta\epi-config.yaml` 的 profile、domains、positive_keywords、negative_keywords、venue_prior 和当前请求衍生概念块、`domain_focus_terms`、5-8 条 query variants、source route、recall gap checks 和 quality signals。`scripts/query-planner.py` 是离线辅助工具，只生成计划不访问网络；默认 `dry-run` 会写 `_runs/<run-id>/query-plan.json`，按 query variants 多次调用上游 MCP/CLI 搜索，并在 `search-record.json.query_records` 留下每条 query 的证据。`dry-run --json` 可打印 run id 和 `query-plan.json`、`search-record.json`、`rank.json`、`report.md`、`report.json`、`run-state.json` 路径，便于 agent 串联后续命令。`--no-query-plan` 可用于单条原始检索调试，也可用于 profile-derived 计划偏离当前请求时的精确短语重跑；如果 planned query 把主题泛化成用户画像之外的宽泛方向，不要停在泛化结果上。检索应采用 two-stage retrieval：第一阶段扩大 raw candidate pool，第二阶段按 DOI/arXiv/title/library 去重、过滤综述、核验 DOI/venue/year/PDF/citation/metric，再排序输出。query plan 扩展词只用于召回和 venue/source gap 检查；`domain_focus_terms` 和当前请求核心词一起构成硬域锚点，ranking 的正向画像匹配词应来自用户 config 和当前请求核心词，避免把 `world model`、`foundation model`、`reinforcement learning` 这类宽召回词当成窄主题必须命中项而压低优质候选。对强 seed paper，允许用 citation graph 查 journal version、recent cited-by、references 和 related papers，并在 `EPI 实测证据` 记录扩展证据。

默认论文发现面向方法/系统/实验论文，不默认找综述。除非用户明确要求 review/survey/综述类论文，查询应带上 `-review -survey`，并且 filter 阶段把 review、survey、systematic review、literature review、meta-analysis 等文档类型作为 hard exclusion 写入 `filter_reasons`，例如 `excluded_terms:review,survey`。若用户明确找综述或 survey，才放开该 hard exclusion。

### 3. 采集、解析与 raw 留痕

入口：`prepare-ranked` 用于只走搜索后采集 + MinerU 解析并停止；`advance-ranked`、`advance-paper`、`advance-batch`、`ingest-one`、`parse-paper` 用于继续完整 ingest 或单步修复。实测批量命令应使用 `prepare-ranked --max-papers 10 --skip-existing`，使已解析论文不占补跑预算；`--max-papers 1` 仅用于 smoke test。

关键产物：

- `_raw/papers/<slug>/paper.pdf`
- `_raw/papers/<slug>/metadata.json`
- `_raw/papers/<slug>/acquire-record.json`
- `_raw/papers/<slug>/mineru/paper.md`
- `_raw/papers/<slug>/mineru/paper.tex`
- `_raw/papers/<slug>/mineru/images/...`
- `_raw/papers/<slug>/mineru/mineru-manifest.json`
- `_raw/papers/<slug>/run-state.json`

成功解析时只保留最终 `mineru/` 产物和 `mineru-command/stdout.txt`、`mineru-command/stderr.txt` 日志，不保留重复的 `mineru-command/paper` 或 `mineru-command/parsed` 大型工作副本。若 MinerU 没有返回原生 `.tex`，EPI 从 `paper.md` 生成非空 LaTeX fallback，并在 `parse-record.json` 记录 `tex_source=markdown-fallback`；原生 TeX 记录 `tex_source=mineru-native`。解析失败时保留错误和 run-state，不进入 staging 或 compiled wiki；若 stdout 显示 batch done 但缺少 Markdown，记录 `MinerU reported done but produced no Markdown output` 以便区分 upstream 完成但本地无可用 `paper.md` 的情况。

### 4. Reader 生成

reader 的目标是降低阅读负担，并给 critic 提供证据索引，不替用户生成无限扩展的研究议程。

三角色分工：

- `nature-sci-editor`：中心主张、重要性、叙事克制、scope 是否过度。
- `peer-reviewer`：方法、baseline、metric、dataset/task、实验设置、证据链。
- `senior-domain-researcher`：理论启发、实验思路、领域迁移价值、应进入 wiki 的知识点。

关键产物：`reader/reader.md`、`reader/editorial-summary.md`、`reader/technical-reading.md`、`reader/research-notes.md`、`reader/figures.md`、`reader/reproducibility.md`、`reader/implementation-ideas.md`、`reader/evidence-map.json`。任何核心贡献、性能提升、SOTA、泛化能力和实验结论都应能追溯到 Evidence。

### 5. Critic 质量门

硬规则：无 critic pass，不写入 compiled wiki。

critic 包含：`paper-quality-critic`、`parse-quality-critic`、`reader-quality-critic`、`editorial-significance-critic`、`peer-review-methods-critic`、`domain-fit-critic`。

paper-quality 重点检查学术论文可靠性：

- `paper_identity`：title、来源 URL、DOI、arXiv ID、venue 至少有稳定身份信息。
- `claim_support`：核心贡献、性能提升、SOTA、泛化声明必须有 Evidence。
- `benchmark_integrity`：reader artifact 自己写出的 better/outperform/SOTA 断言需要 baseline、metric、dataset/task 或实验设置；源论文全文中的综述性 improvement/better 词汇不能单独把 reader 打回。
- `engineering_reproducibility`：code/data/model/config/simulator/hardware 缺失只 warning。
- `scope_overclaim`：防止 simulation/demo/small-scale 被写成真实部署或通用结论。
- `parse_vs_paper_failure`：防止 MinerU 缺图/公式导致误判论文没有相关内容。

关键产物：`critic/critic-report.json`、`critic/critic-quorum.json`、`critic/research-decision.json`、`critic/reader-revision-plan.json`、`critic/reproduction-plan.json`。`reproduction-plan.json` 只作为 reproducibility caveat，不是主阅读报告，也不默认写 compiled wiki。

### 6. Paper Gate

入口：`paper-gate --slug <slug> [--json]`。它是 GitHub checks 风格的只读状态面板，只读 raw/staging 证据，不写 `_runs`、raw、staging 或 compiled wiki。

检查项：`critic-report`、`critic-outcome`、`hard-rule`、`critic-quorum`、`promotion-plan`、`staged-drafts`、`wiki-ingest-brief`、`final-wiki-authority`、`human-approval`；只有 legacy compiled-draft plan 才检查 `compiled-targets`。gate `failure` 时不得进入最终 wiki 写入。当前 agent-mediated 计划只有在 `next_action=run-wiki-ingest-agent`、`failure_checks=[]` 且 `action_required_checks == ["human-approval"]` 时，才允许建议由 agent 执行 wiki ingest；legacy 计划才可能建议 `promote-to-wiki`。`wiki-ingest-brief` 检查必须验证 `wiki_rule_source_model`，确保 handoff 不是单纯列出三个仓库名，而是明确 target vault contract、个性化 wiki-skills、Ar9av/obsidian-wiki、kepano/obsidian-skills、本机 helper skills 的优先级。

### 7. Staging 与轻阅读报告

只有 critic pass 后才允许 staging。

staging 生成证据包和非权威草稿：

- `_staging/papers/<slug>/references/<slug>.md`
- `_staging/papers/<slug>/concepts/<slug>-concept.md`
- `_staging/papers/<slug>/synthesis/<slug>-synthesis.md`
- `_staging/papers/<slug>/reports/<slug>-reading-report.md`
- `_staging/papers/<slug>/wiki-ingest-brief.json`
- `_staging/papers/<slug>/promotion-plan.json`

轻阅读报告是默认入口，结构侧重：`Quick Take`、`What To Read If You Only Have 5 Minutes`、`Reading Trust Status`、`Wiki Ingest Brief`、`Role-Specific Notes`、`Theory And Experiment Ideas`、`Evidence Map`、`Suggested Wiki Routes`、`Quality Gates`、`Figure / Table Skim`、`Reproducibility Caveats`。`Reading Trust Status` 把 critic panel 的 blocking/warning 与复核 caveat 翻译成 `accepted`、`accepted-with-caveats` 或 `blocked-by-critic`，帮助用户先判断阅读信任边界。`wiki-ingest-brief.json` 是给 wiki-ingest agent 的机器可读证据 handoff，记录 trust status、source bundle、suggested routes、三角色阅读 lens、证据计数和推荐阅读路径；它不决定最终 wiki 页面，也不进入 compiled targets。最终 Obsidian/LLM Wiki 沉淀必须由 agent 读取目标 vault contract 后执行：优先 `AGENTS.md`、`_meta/agent-operating-contract.md`、`_meta/schema.md`、`_meta/taxonomy.md`、`_meta/directory-structure.md`，再结合 Ar9av/obsidian-wiki 的 agent-mediated wiki 框架、kepano/obsidian-skills 的 Obsidian 语法约定、initiatione/obsidian-wiki-dev `liuchf/wiki-skills` 的个性化 vault-contract 规则，搜索已有页面后再蒸馏、合并、写入或 staged writes。复现相关内容只放在 caveats 中，不挤占理论和实验思路篇幅。

### 8. Wiki Ingest Handoff、Legacy Promotion、Rollback、Redo

当前默认路径是 agent-mediated wiki ingest handoff：`promotion-plan.json` 记录 `handoff_type=agent-mediated-wiki-ingest`、`wiki_write_model=agent-mediated-vault-contract`、`final_page_authority=target-vault-contract-and-wiki-ingest-agent`、`wiki_ingest_brief_path` 和 `agent_handoff_paths`。EPI 不用固定脚本决定最终 Obsidian Wiki 页面路径；`references/`、`concepts/`、`synthesis/`、`reports/` 只是不具约束力的 suggested draft routes。

入口：`wiki-ingest-handoff --slug <slug> [--json]`。它是只读 handoff 渲染器，不写 `_runs`、raw、staging 或 compiled wiki。输出内容包括：当前 `paper-gate` 摘要、`promotion-plan.json` / `wiki-ingest-brief.json` 路径、目标 vault contract 文件是否存在、`wiki_rule_source_model` 的优先级、framework references、suggested routes、trust status 和 agent checklist。`research-queue --bucket ready_to_promote --actions` 对 agent-mediated plan 必须给出该命令，用户或 agent 先阅读 handoff，再按目标 vault contract 执行最终 wiki ingest。

`promote-to-wiki` 保留为 legacy compiled-draft 兼容入口，只能处理显式提供非空 `compiled_targets` 的旧 plan。该 legacy 路径写 compiled wiki 前必须满足：critic outcome pass、promotion plan 存在、用户提供 `approved-by`、compiled targets 只来自 staging plan、且只能写入 vault 内相对路径 `references/`、`concepts/`、`synthesis/`、`reports/`。禁止 `..`、绝对路径和任意目录写入；promotion 不默认写 `reproduction/` 页面。新 agent-mediated plan 不提供 `compiled_targets`，因此不会被该固定脚本直接写入最终 wiki。

`rollback-promotion` 只处理 promotion record 中记录的目标，但仍要重新校验记录路径：compiled path 必须位于 vault 的允许 wiki 根目录下，snapshot path 必须位于该论文的 `promotion-backups/` 下。`redo-acquire`、`redo-parse`、`redo-read`、`redo-read --from-revision-plan --recritic`、`recritic` 用于修复阶段问题，但不绕过 critic gate；reader 修复后必须重新 critic。

### 9. Run Index 与 Research Queue

run index 是状态面板，不是 research agenda。EPI 不暴露 `research-agenda`，也不生成 `_runs/research-agenda.json` 或 `_runs/research-agenda.md`。

队列 bucket：

- `ready_to_promote`：critic/staging 看起来可推进；当前默认含义是 ready for wiki-ingest handoff，仍需当前 paper-gate 和人类批准。
- `needs_reader_repair`：reader 或 critic 有阻塞问题，需要 redo-read/recritic。
- `warning_only`：无阻塞但有 warning，需要用户理解风险。
- `reproducibility_caveats`：工程可复核性信息不完整，只作为短复核提醒。

`waiting_for_human_gate` 是非失败状态，应进入 human gate pending 和 `ready_to_promote`，不计入 failed runs。`ready_to_promote` item 可附带紧凑 `paper_gate` 摘要：`status`、`conclusion`、`next_action`、`action_required_checks`、`failure_checks`。

`research-queue --bucket ready_to_promote --actions` 必须以当前 `paper-gate` 为准，而不是旧 run report 或 `_runs/index.json` 缓存。生成 actions 时要现场重算 `paper_gate` 和 reason。若当前 gate failure、unknown、构建失败，或待办不是精确 `human-approval`，只能建议 `inspect-paper-gate`；agent-mediated plan 应建议 `run-wiki-ingest-agent`，legacy compiled-draft plan 才能建议 `promote-to-wiki`。

`_runs` 是过渡态证据区，需要生命周期管理。EPI run 结束后会自动检查 `_runs` 下单次 run 目录数量；超过 15 个时自动应用 lifecycle cleanup，保留最新 15 个 terminal run，并按 workflow 至少保留 2 个。手动入口：`run-lifecycle --keep-latest 15 --keep-per-workflow 2 [--max-age-days N] [--apply] [--json]`。手动模式默认 dry-run，只列候选；`--apply` 才删除单次 run 目录并刷新 index/dashboard/research-queue。它不得删除 `_runs/index.json`、dashboard、research queue、feedback log、`_raw`、`_staging`、最终 wiki、Zotero 或配置历史；清理 manifest 写入 `_meta/run-lifecycle/`。

论文发现必须和已下载库去重。`dry-run` 在 filter 阶段扫描 `_raw/papers/*/metadata.json`，按 DOI、arXiv ID、normalized title 匹配已入库论文；命中时写入 `filter_reasons: already_in_library:<slug>`，不得再次进入 `rank.json` 推荐。

## Skill-Aware Evolve

EPI 自进化是 proposal-based，不直接修改插件代码、用户配置或 compiled wiki。设计借鉴 SkillOpt（有边界的目标资产优化、rejected edit buffer、非退化验证）和 EmbodiSkill（先区分技能缺陷与执行偏差）。

输入：run evidence、human feedback、Plugin Eval、benchmark report、critic warning/failure pattern。输出：reflection type、evidence type、classification、target asset、rationale、proposed change、evidence、before metrics、acceptance gates、bounded change、risk level、approval requirement。

classification：

- `skill_change`：技能/模板确实需要变更。白名单模板如 `templates/ranking.example.yaml`、`templates/critic-checklist.example.yaml` 可在 human approval + validation pass 后应用。
- `execution_lapse`：已有指导正确但执行没遵守，必须 record-only，不改技能或模板。
- `configuration_change`：配置层问题，走配置 proposal，不由 evolution 直接改用户配置。

`configuration_change 必须 record-only`，即使目标是白名单模板也不得应用模板修改；`evolution-query` 的下一步应指向 `propose-config-update`。`skill-aware-evolve` 技能入口也必须保留这条边界提示。

激活规则：没有 human approval 不应用；没有 validation result 时进入 `_evolution/pending/<proposal-id>.json`，`check_suite.conclusion=action_required`；验证失败进入 `_evolution/rejected/<proposal-id>.json`，`check_suite.conclusion=failure`；通过后才进入 active。即使自定义 acceptance gates 只写 `human_approval`，系统也必须补 validation check run。带 `metric`、`operator`、`value` 的 acceptance gate 必须真实读取 validation result 并比较，例如 `plugin_eval_score >= 91`；外层 `passed=true` 不能绕过分数退化、缺失或无法比较的指标。

入口：`propose-evolution`、`activate-evolution`、`evolution-query`。推荐顺序是先 propose，再 query 看 check suite 和 next action，最后在验证可用时 activate。

## 发布质量信号

发布前至少运行：

```powershell
python -m pytest tests\epi -q
python -m pytest plugins\epi -q
python -m coverage run -m pytest tests\epi
python -m coverage xml -o plugins\epi\coverage\coverage.xml
node <plugin-eval.js> analyze <plugin-root> --format markdown
```

`tests\epi` 是源码仓库主测试集；`tests\epi\test_wrapper_entrypoints.py` 覆盖 marketplace 可见 wrapper：`scripts\orchestrator.py`、`scripts\init_paper_wiki.py` 和 MinerU skill wrapper。当前 Windows 版 Plugin Eval 用反斜杠绝对路径传给 Python 测试识别正则，而该正则只匹配 `/tests/` 或 `/test_*.py`，所以源码测试通过时仍可能出现 `py-tests-missing`。coverage XML 放在 `plugins\epi\coverage\coverage.xml`，默认被 `coverage/` ignore；只有发布时明确刷新才需要 `git add -f`。

Plugin Eval 是发布门槛之一：目标是 `0 fail`、coverage artifact 存在、分数不低于 `70/100`。若出现 token budget warning，优先删重复/生成文件和重复话术；不要为了静态分数把本文档移出 `plugins\epi\docs`，因为它是用户要求的中文链路维护契约。若出现 missing tests warning，先核对 `tests\epi`、coverage 和评估器路径识别；当前 Windows 反斜杠路径会导致误报，则以 pytest 与 coverage 为测试信号，并在评估记录中保留该限制。

为降低 deferred token，`docs/workflow.md`、`docs/evaluation.md` 和 `docs/config.md` 保持入口索引/最小话术；完整链路事实以本文档为准。

## 安全边界

- dry-run 只写 `_runs`。
- raw/staging 可以写本地 artifact，但不写 compiled wiki。
- 无 critic pass，不写入 compiled wiki。
- agent-mediated wiki ingest 和 legacy promotion 都必须有人类 approval。
- 当前默认 plan 不产生 compiled targets；legacy compiled targets 必须限制在允许 wiki 根目录。
- rollback 只处理 legacy promotion record 中记录的目标。
- token、API key、MinerU token 不写入报告、不打印。
- runtime.json 不保存 token 明文；`MINERU_TOKEN` 只能来自进程环境或 `mineru.env`，报告只显示 set/missing。
- 外部工具缺失不阻止离线结构诊断。

## 用户体验目标

用户给出方向后，EPI 找候选论文并排序；用户或批处理推进少量高价值论文；EPI 保存原始证据并生成多角色 reader；critic 检查身份、证据、benchmark、scope 和解析质量；通过后生成 evidence staging、wiki-ingest brief 和轻阅读报告；用户批准后由 agent 按目标 vault contract 写入 Obsidian/LLM Wiki；用户从阅读报告开始低负担吸收知识。
