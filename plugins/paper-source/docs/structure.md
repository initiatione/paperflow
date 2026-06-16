# Paper Source 插件结构说明

本文档描述当前 Paper Source 插件的源代码结构、运行边界和主要产物位置。Paper Source 是用户可见名，machine-facing name 是 `paper-source`。旧别名不再作为用户入口、路由触发条件或新 artifact 合同。它回答“文件在哪里、谁负责什么、哪些目录不能被当成最终知识库写入入口”。文档权威分工（doc map）见 `docs/paper-source-linkage.md` 顶部；本文档只承担结构说明。若需要一份中文导航，先读 `docs/overview.zh.md`。

## 总体边界

Paper Source 是 Codex 插件源码包，位于 `<plugin-root>`。插件的默认链路是：按用户画像/config 衍生高质量论文发现和排序 -> 先用 wiki `_meta/reference-index.json` 去重 -> 输出候选给用户/Paper Wiki。raw artifact、Reader/Critic、staging evidence package 和 `wiki-ingest-brief.json` 是显式 source-staging 深入路径，不是每次发现的默认负担。`wiki_deposition_task.json` 只作为历史 handoff 清理对象，不是新链路入口。它是通用学术论文插件，不把任何单一学科写成默认方向。

Paper Source 自身不应该把最终 Obsidian 页面路径、标签、合并策略或 staged writes 固定死。最终写入规则来自目标 vault 的 `AGENTS.md` 和根 `_meta/*` contract 文件，并参考个性化 `obsidian-wiki-dev`、`Ar9av/obsidian-wiki`、`kepano/obsidian-skills`。本插件只准备 `_paper_source/` 内部仓库中的证据、报告、审计记录、brief-first handoff 和 record metadata。

Sibling 插件包 Paper Wiki（目录 `plugins/paper-wiki`，machine-facing name `paper-wiki`）是面向用户的一体化论文 wiki 助手，并提供公共 skill `$paper-research-wiki`：用户只需要请求 `提取` Paper Source 论文、`根据 wiki 提问`、`检测` wiki 库、`更新` wiki 库或 `重link` 论文知识。它内部消费 Paper Source 产出的 `wiki-ingest-brief.json`、source bundle 和 final-source-review contract。Paper Source 保留发现、采集、MinerU、paper-gate、人类批准记录和 `record-wiki-ingest`。

## 插件包目录

```text
plugins/paper-source/
  .codex-plugin/plugin.json
  docs/
  scripts/
  skills/
  templates/
  coverage/
```

- `.codex-plugin/plugin.json`：Codex marketplace 识别入口，包含插件名称、版本、展示文案、技能目录和 marketplace 链接。安装刷新通常需要更新版本 cachebuster。
- `docs/`：用户可读说明。`overview.zh.md` 是中文总览入口；`paper-source-linkage.md` 是主链路维护契约；`structure.md` 是本文件；`progress.md` 是开发进度说明；`config.md` 是首次配置和修改配置的话术来源。
- `scripts/`：Codex 插件内的可执行 wrapper。用户和技能通常调用 `python scripts\orchestrator.py ...`。
- `scripts/build/paper_source/`：实际 Python 实现模块。旧导入 shim 不作为用户入口。
- `skills/`：Codex skills。每个 skill 的 `SKILL.md` 只保留触发条件、安全边界和核心命令，详细链路放在 docs。
- `templates/`：ranking、filter、interest、routing、critic checklist 示例。skill-aware evolution 只能在白名单和验证通过后提出或应用有限变更。
- `coverage/`：本地 coverage artifact 位置。`coverage.xml` 通常被 git ignore，只在发布评估需要时刷新或强制加入。

## CLI 入口

主入口是：

```powershell
python scripts\orchestrator.py <command>
```

当前命令分组：

- 安装与配置：`doctor`、`config-status`、`init-config`、`propose-config-update`、`apply-config-update`。
- Wiki 库初始化/重置：`wiki-setup` skill 负责初始化和重置流程；初始化只补缺失结构，并在 `<vault>\.git` 缺失时自动 `git init`，但不自动创建首个 commit。初始化后的 Paper Source 内部产物只在 `_paper_source/` 下展开，根 `_meta/` 只保留 wiki contract 文件。重置必须先盘点、备份计划并要求用户二次确认 `确认重置 Paper Source wiki`。`wiki-reset --preview` 先列出会备份、删除、保留的路径；`wiki-reset` 是执行器，默认备份内容并保留 `_paper_source\meta\paper-source-config.yaml`、`_paper_source\meta\paper-source-config-state.json`、config history 目录，且不得触碰用户级 `%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json`。如需同时重置配置，必须另行确认 `确认同时重置 Paper Source config` 并显式传入 `--reset-config-confirmed-by`。若出现误删或误操作，先停止后续论文流程，用 `wiki-repair` 单入口检查恢复状态，或用 `config-recover` 查找候选配置，再用 `config-restore` 在确认后恢复。
- 发现与推进：`discover-papers`、`dry-run`、`discover-to-handoff`、`prepare-ranked`、`advance-ranked`、`advance-paper`、`advance-batch`、`ingest-one`、`acquire-paper`。
- 解析与修复：`parse-paper`、`normalize-mineru-assets`、`redo-acquire`、`redo-parse`、`redo-read`、`recritic`。
- Reader/Critic/Gate：推进命令内部生成 reader 和 critic；只读检查用 `paper-gate`。
- Report：`report` 是公开读取入口；`report --run-id <run-id> [--json]` 读取已有 run report artifact；内部生成模块是 `report_run.py`，不是额外的 `run-report` CLI。
- Staging 与 Wiki handoff：`stage_wiki.py` 生成 `wiki-ingest-brief.json` canonical Paper Source-to-Paper Wiki handoff 和 `promotion-plan.json`，新链路不生成 `wiki_deposition_task.json`；`wiki-ingest-handoff` 渲染 agent-mediated handoff；`record-human-approval` 记录外部 agent 写入前的人类批准；`wiki-ingest-trigger` 写继续任务；Paper Wiki `$paper-research-wiki` 是用户级正式论文 wiki 写入和维护入口；`paper-source-paper-deposition` 仅用于历史 handoff 清理；`record-wiki-ingest` 记录外部 agent 已完成的最终页路径、hash 和 formal page gate。
- 索引与查询：`runs-query`、`research-queue`、`wiki-query`、`wiki-ask`。
- 反馈、评估与进化：`record-feedback`、`evaluation-brief`、`propose-evolution`、`activate-evolution`、`evolution-query`。`evaluation-brief` 把 Plugin Eval、`paper-source-quality-gates`、benchmark 和 before/after metrics 合并成本地 improvement brief，再交给 `propose-evolution`。
- 外部集成：`zotero-sync`，以及 MinerU 解析相关命令。

## Python 模块职责

```text
scripts/build/paper_source/
  cli.py
  cli_parser.py
  cli_routes.py
  orchestrator.py
  discover_papers.py
  artifacts.py
  config.py
  doctor.py
  runtime_config.py
  paper_search_adapter.py
  paper_library.py
  normalize_candidates.py
  filter_candidates.py
  rank_papers.py
  review_sessions.py
  fetch_plan.py
  frontmatter.py
  acquire_papers.py
  run_mineru_parse.py
  asset_normalization.py
  evidence_index.py
  review/
    generate_reader.py
    reader_*.py
    run_critic.py
    role_critics.py
    critic_contracts.py
  recommendation_output.py
  auto_staging.py
  report_run.py
  wiki_contracts.py
  paper_quality.py
  research_decision.py
  reproduction_plan.py
  query_plan_build.py
  orchestrator_discovery.py
  orchestrator_repair.py
  stage_wiki.py
  stage_wiki_brief.py
  paper_gate.py
  source_bundle_audit.py
  graph_visibility.py
  wiki_language.py
  wiki_handoff_contracts.py
  wiki_ingest_handoff.py
  wiki_ingest_approval.py
  wiki_ingest_trigger.py
  wiki_ingest_record.py
  wiki_record_workflows.py
  raw_cleanup.py
  run_index.py
  wiki_query.py
  skill_aware_evolve.py
  evaluation_loop.py
```

- `cli.py` 保留公开 CLI 入口；`cli_parser.py` 和 `cli_routes.py` 拆出参数定义、JSON/Markdown 输出和命令分发，避免入口继续膨胀。`dry-run` 支持 repeated `--query-variant`、`--domain-focus-term`、`--agent-query-plan-json`、`--year-min`、`--code-policy` 和 `--selection-policy`，用于记录 agent 计划后的检索式、显式硬过滤锚点和请求级约束。
- `orchestrator.py` 是低层流程编排层，负责 dry-run、discover-to-handoff、one-paper ingest、batch advance、redo/recritic 等阶段串联；repair、query-plan assembly 和 discovery/source coverage 已分别拆到 `orchestrator_repair.py`、`query_plan_build.py`、`orchestrator_discovery.py`，record/promote 相关 helper 已拆到 `wiki_record_workflows.py`。dry-run 把原始自然语言 `--query` 当作意图标签，把 agent-supplied query variants 当作实际 MCP 搜索输入，并在 `query-plan.json` 中审计来源、`hard_domain_anchors`、`soft_recall_terms`、`term_provenance`、`year_min`、`code_policy` 和 `selection_policy`；`discover-to-handoff` 只串联 dry-run 与 prepare-ranked，停在 source-staging。
- `discover_papers.py` 是自然语言发现的高层编排模块：调用 `run_dry_run(...)` 生成 evidence/report，再调用 `auto_stage_recommendations_from_run(...)` 按 `session_recommendations.primary_recommendations` 自动准备 source-staging，写 `discover-papers-record.json`、`report.json` 和 `run-state.json`。它默认保留 review/survey/meta-analysis 候选，除非用户显式要求 non-review；它不写 approval、wiki-ingest trigger/record 或 Paper Wiki 正式页。
- `artifacts.py` 负责 Paper Source 路径约定、sha256、时间戳和原子写入；`write_json_atomic` / `write_text_atomic` 用临时文件加 `os.replace` 写 JSON/Markdown，避免 `_paper_source/runs/index.json`、record 和 report 在异常中写坏；`read_json` / `read_json_dict` 是 JSON artifact 读取入口。
- `frontmatter.py` 是宽松 YAML/frontmatter 解析、strip 和 scalar/list 处理 helper，供 record、query、language gate 和 Stage Wiki brief 复用。
- `config.py` 负责 `_paper_source/meta/paper-source-config.yaml` 的读取、初始化、提案和更新历史；配置缺失时必须走聊天式 `config-setup`。旧配置文件只作为迁移读取来源，不作为新配置入口。
- `config_protection.py` 负责共享确认口令和 config 保护白名单，供 reset、repair、restore 复用。
- `wiki_reset.py` 负责 wiki reset 执行器：preview、确认口令、备份/删除、config 默认保护、初始化和 reset manifest。
- `doctor.py` 负责只读健康检查；外部依赖缺失是 warning，插件结构缺失才 error。它还报告 `mcp_outer_launcher` 和 `codex_mcp_registration`，用于区分插件 `.mcp.json` 外层 bootstrap 不可启动、`cwd` / 相对 launcher 配置错误、未展开的 `${CLAUDE_PLUGIN_ROOT}` / `${PLUGIN_ROOT}` 占位符、用户级 `config.toml` 静态 MCP 覆盖、runtime.json 内层解释器失效这几层问题。
- `runtime_config.py` 负责从 `%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json` 加载本机依赖配置，只补缺失的进程环境变量，不覆盖显式 env，不保存 token 明文；paper-search provider key/email 只能通过 `paper_search_mcp.env_file` 或显式进程环境进入。
- `paper_search_adapter.py` 优先调用外部 `paper-search-mcp` stdio server，并在失败、超时或空结果时回退到 `paper-search` CLI，把上游输出标准化为 Paper Source 候选记录；`plan_source_routing` 会把 Google Scholar 等 `unstable` source 默认降级，并把 Unpaywall email 缺失写成 `source_routing.provider_gaps` / `unpaywall_email_missing`；dry-run report 会保留 `source_coverage`，包含 `sources_used`、`source_results`、`errors`、`raw_total`、`deduped_total`、`query_count`、source capability matrix、provider readiness、source routing 和 provider gaps；`doctor --json` 也会输出 `paper_search_provider_readiness`，暴露 Unpaywall/CORE/Semantic Scholar/Google Scholar/DOAJ/Zenodo provider env 缺口；acquire 后可调用 MCP `read_<source>_paper` 或 CLI read 写 non-authoritative retrieval preview。
- `paper_library.py` 负责轻量文献去重索引：先读取 wiki `_meta/reference-index.json`，按 DOI、arXiv base id、source_id、normalized title 建键；再补 `_paper_source/raw/*/metadata.json` 作为 fallback。命中正式 wiki 页时 filter reason 是 `already_in_wiki:<page>`，命中 raw source bundle 时是 `already_in_library:<slug>`。
- `review_sessions.py` 负责 `_paper_source/reviews/<review-id>/` 的 default resume 状态：signature、`state.json`、`candidates.json`、`shortlist.json`、`fetch_plan.json`、`coverage.json`、`provider-cache/query-*.json`、resume 计数和 provider-call skip 记录。
- `fetch_plan.py` 从 ranked candidates 生成 `fetch_plan.json`，保留候选 PDF URL、source identities、manual download URL 和推荐采集顺序，避免 resume 后重复推导下载计划。
- `acquire_papers.py` 负责下载或复制 PDF，优先用 MCP `download_with_fallback` 做开放访问 fallback chain；若候选没有 direct PDF URL 且 OA fallback 无 PDF，会快速返回 `failure_class=manual-download-required` 和 `manual_download.candidate_manual_urls`，让 agent 直接给用户 DOI/出版商链接并要求通过 organization/institution 手动下载；有 direct PDF URL 时才继续回退 source-native MCP、CLI 和 direct URL。下载到 PDF 后会做轻量 DOI/title identity check：通过或无法提取时记录 `identity_check` 并继续；明确不匹配时写 `identity-check.json`、`failure_class=identity-mismatch`，把 PDF 隔离到 `_paper_source/quarantine/papers/<slug>/paper.pdf`，不进入 MinerU。成功 `acquire-record.json` 记录 `doi`、`title`、`use_scihub`、`fallback_chain`、`mcp_server_probe`、`upstream.tool` 和可选 `retrieval_preview`，并把 `paper-search-read-preview.txt` 写作 `_paper_source/raw/<slug>/` 下的 sidecar。该 sidecar 不是 source bundle 的权威解析，MinerU remains canonical parse；最终 wiki 对公式、符号、方法上下文和正文以 MinerU Markdown 为主源，只有 Markdown 缺失、错误、歧义或不足时才回退 `paper.pdf`、figure/formula indexes 和图片证据，非空原生 TeX（若存在）只作可选交叉复核；失败记录保留合并候选的 `candidate_pdf_urls`、`acquire_attempts`、`failure_class`、`retryable`、`recovery_hint` 和可选 `manual_download`，让后续 agent 区分重试、换源、手动补 PDF、identity mismatch quarantine 和跳过。
- `raw_cleanup.py` 负责清理失败的 `_paper_source/raw/<slug>` 目录；只有在没有下载到 `paper.pdf`、没有 staging、没有 wiki-ingest/zotero 下游记录且路径仍直属 raw root 时才删除，并把 manifest 写到 `_paper_source/meta/raw-cleanup/`。
- `filter_candidates.py` 将 recommendation eligibility 与 staging readiness 分开：稳定 DOI/arXiv/publisher identity 的缺 PDF 论文进入 `needs_pdf`，无稳定身份且缺 PDF 才硬拒绝。
- `rank_papers.py` 负责 paper type classification、ranking signals、ranking rubric、ranking protocol、selection policies 和三角色排序解释。
- `run_mineru_parse.py` 负责 MinerU 命令调用、失败记录和 fixture materialization；默认 7200 秒超时，可由 `--mineru-timeout` 或 `PAPER_SOURCE_MINERU_TIMEOUT` 覆盖。成功 parse 会调用 `asset_normalization.py` 规范化 MinerU raw 图片/公式截图，再调用 `evidence_index.py` 写 `_paper_source/raw/<slug>/evidence-index.json` 并刷新 `_paper_source/meta/evidence-index.json`。
- `asset_normalization.py` 负责 raw MinerU asset normalization：按 `Fig.` / `Figure` / `图` 标签把 hash-like 图片重命名为 `fig-###-*`，把无法映射的图片标记为 `unmapped-*`，把有 Markdown/TeX LaTeX 证据的公式截图从 raw 图片中删除并从 Markdown 图片引用中移除，同时写 `figure-index.json`、`formula-index.json` 和 `asset-normalization-record.json`。公开 CLI `normalize-mineru-assets --slug <slug> [--execute] [--json]` 可对 `_paper_source/raw` 或 legacy `_epi/raw` 历史 bundle 做 dry-run-first 修复；它不修改正式 wiki 页面。
- `evidence_index.py` 负责从 MinerU Markdown 建立 full-text locator index：按 heading/page marker/chunk 记录 page、section_path、source_locator、chunk hash、input hashes 和 warnings；它是 wiki provenance 的检索辅助，不替代 source-first reread。
- `review/generate_reader.py`、`review/reader_outputs.py`、`review/reader_evidence.py`、`review/reader_protocol.py` 负责可选 reviewed/audited ingest 的多角色 reader、evidence map 和证据地址校验；reader 以 MinerU Markdown 为主记录文本/公式/记号证据，并把 MinerU manifest、PDF fallback、figure/formula indexes、图片证据和可选非空原生 TeX（若存在）作为复核线索写入 evidence/claim-support，而不是只输出摘要。
- `review/run_critic.py`、`paper_quality.py`、`review/role_critics.py` 负责可选 audited ingest 的 critic quorum、学术论文可靠性检查和三角色质量门；其中 `parse-quality-critic` 会检查 MinerU Markdown、images、manifest、figure/formula indexes、`parse-record.json`，以及可选非空原生 TeX（若存在），避免原文公式/图像证据在进入 reader/wiki 前被静默抹掉。
- `recommendation_output.py` 负责 `report.json.session_recommendations` / `paper-source-session-recommendations-v1` 的 chat-facing 推荐投影；`auto_staging.py` 负责 `paper-source-auto-staging-plan-v1`，从 primary recommendations 中选择最多 3 篇 PDF-available 论文进入 fast source-staging，并把 `needs_pdf` / review-sideline / execution state 写回 `auto_staging_status`；`report_run.py` 负责生成 `_paper_source/runs/<run-id>/report.md` 和 `report.json`，并提供 `report --run-id` 的只读 loader；该 CLI 会展示 run report artifact 和 `run-state.json` payload，但不刷新 index、queue、raw、staging、Zotero 或 wiki。
- `research_decision.py`、`reader_revision_plan.py`、`reader_revision_guidance.py`、`reproduction_plan.py` 把 critic 结果翻译成决策、修复建议和紧凑复现 caveat。
- `wiki_contracts.py` 固定七类正式页面、brief-first required Paper Source/Paper Wiki skills、frontmatter schema、quality gates、retired handoff cleanup 和 QMD collection boundary 等跨模块常量；`paper-research-wiki` qmd collection 允许正式页目录加 `AGENTS.md`、`index.md`、`hot.md`、`log.md`、`_meta/`，必须 ignore `_paper_source/**`、`.obsidian/**`、`.claude/**`，让 `_paper_source/meta/formal-page-snapshots/`、raw MinerU source Markdown 和 staging handoff 不进入 QMD。external wiki skills are optional helpers / policy references。
- `stage_wiki.py` 负责 `_paper_source/staging` 内部证据包和 staging 写入编排；`stage_wiki_brief.py` 负责轻阅读报告、`wiki-ingest-brief.json` canonical Paper Source-to-Paper Wiki handoff、rule-source model、`final_source_review_contract` 和 reading-report Markdown 生成。默认新 staging 不需要也不生成 `wiki_deposition_task.json`。它会把 `evidence-index.json`、chunk count、input hashes、warnings 和 `_paper_source/meta/evidence-index.json` 作为 locator aid 暴露给 handoff，但不得把审计页当成正式 wiki 页写到根目录。
- `paper_gate.py` 是只读质量门面板，决定当前 slug 是 failure、waiting for human gate，还是允许进入下一动作；它调用 `source_bundle_audit.py` 检查 `paper.pdf`、`metadata.json`、MinerU Markdown、`mineru/images/*` 和 `mineru/mineru-manifest.json`，当 source bundle is incomplete 时阻止 final handoff；`mineru/paper.tex` 只在非空原生 TeX 存在时作为可选公式源进入审阅。
- `source_bundle_audit.py` 负责 raw source bundle 的磁盘完整性审计和 image hash 明细，供 `paper_gate.py` 与 record provenance 复用。
- `graph_visibility.py` 负责 Obsidian `.obsidian/graph.json` 的正式目录 filter 和 `collapse-filter` 修复，避免过度转义导致图谱只剩 index。
- `wiki_language.py` 负责 formal page language gate：formal wiki page body prose defaults to Chinese；英文只保留论文题名、术语、缩写、证据字段和路径。
- `wiki_handoff_contracts.py` 保存 agent context policy：独立 wiki deposition 子任务可交给 fresh-context worker，主 agent 只读最终产物、changed file list 和 verification result；Codex 仍必须先有用户显式授权才可用 subagents。
- `wiki_ingest_handoff.py` 是只读 handoff 渲染器，给最终 wiki ingest agent 提供路径、规则优先级、final-source-review 合同、QMD 边界、agent context policy 和 checklist；它应显示 `qmd collection show paper-research-wiki`、`qmd ls paper-research-wiki/_paper_source`、`qmd ls paper-research-wiki/_paper_source/meta/formal-page-snapshots` 这类验证命令。
- `wiki_ingest_approval.py` 是 agent-mediated 前置人类批准 helper：写入并校验 `_paper_source/staging/papers/<slug>/human-approval.json`，要求当前 gate 只有 `human-approval` 待办；显式 Codex automation approval 仍使用 `paper-source-human-approval-v1`，但要求 `approved_by=codex-automation:<task-id>` 并记录 task/source/original authorization 审计字段。
- `wiki_ingest_trigger.py` 是批准后的继续/触发 helper：写入 `_paper_source/staging/papers/<slug>/wiki-agent-trigger.json`，让 Paper Wiki `$paper-research-wiki` 或当前 Claude、Codex 等 wiki-capable agent 按同一 target vault contract 继续最终页写入；若 approval 含 automation metadata，则透传 `automation_handoff`，否则普通 human approval trigger 不含 automation 字段；它不写最终 wiki 页面。
- `wiki_ingest_record.py` 是 agent-mediated 完成态记录器：只读取最终 Markdown 页面、前置 `human-approval.json`、canonical `wiki-ingest-brief.json` 和 `final-source-review.json`，校验路径在 vault 内且不在 Paper Source 内部目录，验证源工件 hash、公式/图片/PDF 复核和 final page provenance，检查 formal frontmatter、`category/page_family`、provenance、wikilinks、Chinese-default 正文、forbidden formula blocks 和 family-specific quality gates，记录 hash 和 human approval，不写最终页面。legacy `wiki_deposition_task.json` 只作为兼容 sidecar 记录。
- `wiki_record_workflows.py` 承接 `record-human-approval`、`record-wiki-ingest` 的 run-state/report 写入，先完成 record 校验再创建 `_paper_source/runs/record-wiki-ingest-*`，避免失败校验留下空 run 目录。
- `zotero_sync.py` 负责本地 record-only Zotero sidecar：读取论文 metadata 和 wiki ingest record，写 `zotero-record.json`，不调用外部 Zotero API。
- `run_index.py` 负责 `_paper_source/runs/index.json`、dashboard 和 `research-queue.json`，并在 ready queue 里嵌入当前 paper-gate 摘要；record routed runs 会把 `zotero_results` 带入 index 和 dashboard。
- `wiki_query.py` 同时保留 manifest/index 视角的 `wiki-query`，并提供 read-only `wiki-ask` formal graph retrieval：读取正式页根目录，扩展 backlinks/outlinks/aliases/tags/co-links，输出具体的证据/综合/推断/不确定 answer sections 和 correction candidates；它只读解析 frontmatter `sources` 和正文 `## 原文与证据入口` 中标题显示的 canonical `_paper_source/raw/<slug>/paper.pdf` Markdown PDF URI 来确认源工件可用性，短标签、plain path、retired `_epi` 或内部 wikilink PDF 只作为修复候选，不作为正常 evidence fallback；`_paper_source/raw` 不作为 formal graph node；它不写 `log.md`、正式页、QMD、`paper-wiki-record-request.json` 或 Paper Source artifacts。
- `skill_aware_evolve.py` 负责 proposal-based 自进化，默认不直接修改插件代码、用户配置或 compiled wiki。
- `evaluation_loop.py` 负责插件开发质量环：合并 Plugin Eval、`paper-source-quality-gates`、benchmark、before/after metrics，写出 `paper-source-improvement-brief-v1` JSON/Markdown 和 `proposed_evolution` payload。默认输出目录是 `.plugin-eval/improvement-briefs/`，属于本地开发产物。
- `paper_source_repository.py` 负责 `_paper_source` 初始化、manifest、migration 和 repository cleanup；旧 `epi_repository.py` shim 已在 Paper Source 2.0.0 删除，不再作为代码入口或用户入口。`paper-source-repository-cleanup --preview --json` 是 no-write inspection；非 preview cleanup 即使未超总文件/体积阈值，也会按 retention lifecycle 上限清理 terminal run dirs、维护 manifest、formal-page snapshots 和临时 manual PDFs，但不得删除 `_paper_source/raw`、`_paper_source/reviews`、配置历史、Zotero record 或最终 wiki 页。

## Skills 结构

```text
skills/
  config-setup/
  paper-source-paper-deposition/
  paper-discovery/
  paper-ingest/
  mineru-paper-parser/
  topic-tracking/
  run-lifecycle/
  wiki-provenance/
  wiki-setup/
  skill-aware-evolve/
  zotero-sync/
```

- `config-setup`：首次使用或修改配置时的唯一交互入口。入口保持短句和边界，完整聊天式引导与更新流见 `docs/config.md`；最终确认前不运行 `init-config` 或 `apply-config-update`。
- `paper-discovery`：自然语言 `discover-papers`、低层 dry-run、搜索、排序和推荐输出；默认 `discover-papers` 会先保留轻量候选排序和 wiki reference-index 去重，再按 auto-staging policy 选择最多 3 篇 PDF-available primary recommendations 写入 source-staging，不写 approval/final wiki。`dry-run` 是 evidence/debug 底层命令。`prepare-ranked` 是显式深入入口，写 raw 源材料、MinerU 解析产物和 source-staging 审批报告，不写最终 wiki。
  - `paper-discovery/scripts/query-planner.py` 与 `paper-discovery/references/` 保存可维护检索策略：mode routing、query planner、paper type taxonomy、ranking rubric、domain ontology、source tiers、dedup engine、venue prior、two-stage retrieval、citation graph、evaluation set、multi-source workflow、quality gate、anti-patterns 和对话输出格式。自然语言主题由 agent 实时拆解为 `--query-variant`，脚本不硬编码每个学科的语义词典；venue prior 从用户画像/config 衍生，社区榜单只进入对应领域的弱 prior，真实指标仍需单独核验。
- `topic-tracking`：主题中心、纵向增量、backlog、coverage 和 broad-to-deep 阅读视图；它承接“这次之后有什么新东西”“我有没有漏掉关键分支”这类问题，`paper-discovery` 只保留检索/排序底层。
- `paper-ingest`：推进已选论文进入 raw、source-staging 和 handoff；默认 `fast-ingest` 不跑 reader/critic，`reviewed-ingest` / `audited-ingest` 才按需加入。
  - `paper-ingest/references/source-first-reading.md` 是 source-staging/wiki handoff 的 source-first 阅读协议，要求最终沉淀前重读 MinerU Markdown、images、manifest、非空原生 TeX（若存在）和必要时的 PDF，最终记录 `final-source-review.json`；`reader/claim-support.json` 只有在 reviewed/audited ingest 生成时才作为辅助区分源文摘取、metadata-only 与 inference。
- `paper-source-paper-deposition`：历史 handoff 清理入口；当旧 artifact 只剩 `wiki_deposition_task.json` 时，先修复或重建 `wiki-ingest-brief.json`，再转给 sibling 插件包 `paper-wiki` / `plugins/paper-wiki` 提供的 `$paper-research-wiki`。`llm-wiki`、`wiki-ingest`、`wiki-context-pack`、`wiki-lint`、`wiki-stage-commit`、`wiki-status`、`wiki-query`、`wiki-provenance` 和 `tag-taxonomy` 等 external wiki skills are optional helpers / policy references。
- `mineru-paper-parser`：低层 PDF -> Markdown/images/manifest 解析能力；若 MinerU 返回非空原生 TeX，则保留 `paper.tex`，否则不再从 Markdown 生成 LaTeX fallback，公式以 Markdown 和可选 TeX 复核。
- `wiki-provenance`：final wiki 页 provenance、claim support status、evidence address 和 round-trip retrieval hook；它承接“最终页上的这句话到底来自哪里”这类问题，`paper-ingest` 只保留 source-first handoff。
- `skill-aware-evolve`：根据 evidence 和验证结果提出受控变更；配置问题必须走配置 proposal。
- `wiki-setup`：初始化、检查、修复和重置 paper wiki vault。入口只保留边界和命令，详细恢复与误删清单见 `skills/wiki-setup/references/reset-recovery.md`。初始化会创建或保留 vault-local git repository，写入 `AGENTS.md` 和 `_meta/agent-operating-contract.md`、`_meta/schema.md`、`_meta/taxonomy.md`、`_meta/directory-structure.md`，默认要求 source-first paper ingest：最终 wiki 写入先读 `mineru/<slug>.md`、`mineru/images/*`、manifest，以及非空原生 `mineru/paper.tex`（若存在）。
- `zotero-sync`：Zotero 记录和可选同步，默认安全边界是本地记录优先；`record-wiki-ingest` 会自动写 record-only sidecar 并把结果带入 report。

## Vault Artifact 结构

Paper Source 默认 vault 形态。除根 `_meta/` wiki contract 文件外，Paper Source 的运行、审计、raw、staging、evolution、cleanup 产物都收拢在单一 `_paper_source/` 内部仓库中：

```text
<vault>/
  _paper_source/
    README.md
    manifest.json
    policies/
      retention.json
    meta/
      paper-source-config.yaml
      paper-source-config-state.json
      config-history/
      run-lifecycle/
      raw-cleanup/
      repository-maintenance/
      migrations/
      wiki-reset/
      formal-page-snapshots/
    tmp-manual-pdfs/
    runs/
      <run-id>/
        query-plan.json
        search-record.json
        normalized.json
        filter-report.json
        discovery-diagnostics.json
        rank.json
        report.md
        report.json
        run-state.json
      discover-papers-<id>/
        discover-papers-record.json
        report.md
        report.json
        run-state.json
      discover-to-handoff-<id>/
        discover-to-handoff-record.json
        report.md
        report.json
        run-state.json
      index.json
      research-queue.json
    reviews/
      <review-id>/
        state.json
        query-plan.json
        candidates.json
        shortlist.json
        fetch_plan.json
        coverage.json
        provider-cache/
          query-01.json
    raw/
      <slug>/
        paper.pdf
        metadata.json
        acquire-record.json
        paper-search-read-preview.txt  # optional non-authoritative retrieval preview
        figure-index.json
        formula-index.json
        asset-normalization-record.json
        evidence-index.json
        zotero-record.json
        mineru/
        reader/
        critic/
        run-state.json
    meta/
      evidence-index.json
    staging/
      papers/<slug>/
        evidence/
        briefs/
        wiki-ingest-brief.json
        wiki_deposition_task.json  # legacy optional
        human-approval.json
        wiki-agent-trigger.json
        final-source-review.json
        promotion-plan.json
      wiki-batches/
        pending/
          wiki-batch-ingest-brief.json
    quarantine/
      papers/
    evolution/
      proposals/
      pending/
      active/
      archive/
      rejected/
  _meta/
    agent-operating-contract.md
    schema.md
    taxonomy.md
    directory-structure.md
    reference-index.json
  AGENTS.md
  references/
  concepts/
  derivations/
  experiments/
  synthesis/
  reports/
  opportunities/
```

写入边界：

- `discover-papers` 写高层 `_paper_source/runs/discover-papers-*` 记录，链接 discovery run 与 optional auto-staging run；默认最多自动准备 3 篇 PDF-available primary recommendations 到 source-staging，保留 `needs_pdf` manual links，并停止在 approval/Paper Wiki 之前。
- `dry-run` 写 `_paper_source/runs`、`discovery-diagnostics.json` 和 resumable `_paper_source/reviews` provider cache；默认自动 resume，`--refresh` 强制 provider 重搜。已沉淀文献 backlog / 去重 source of truth 是 `_meta/reference-index.json`。
- `discover-to-handoff` 写一个汇总 run，引用 discovery run 和 prepare-ranked run；它不写 `human-approval.json`，不调用 Paper Wiki，不写最终 wiki 页面。
- raw 阶段写 `_paper_source/raw/<slug>`，不写最终 wiki。
- 默认 fast-ingest 在源材料完整后可写 `_paper_source/staging/papers/<slug>` 的轻量 handoff 和 `wiki-ingest-brief.json`；new staging does not require or generate `wiki_deposition_task.json`。audited-ingest 和已有 critic report 的论文必须 critic pass。
- `wiki-ingest-handoff` 和 `paper-gate` 都是只读。
- 当前默认 agent-mediated plan 不写 compiled wiki。
- agent-mediated wiki ingest 前，必须先用 `record-human-approval --scope run-wiki-ingest-agent` 写 `_paper_source/staging/papers/<slug>/human-approval.json`；Codex automation 必须显式使用 `codex-automation:<task-id>` actor 和 automation flags，不能从普通发现/auto-staging 推断；`wiki-ingest-handoff` 只有在该 artifact 有效时才显示 `ready_for_agent=true`。
- 批准后可用 `wiki-ingest-trigger --slug <slug>` 写 `_paper_source/staging/papers/<slug>/wiki-agent-trigger.json`，作为当前 agent 或下一次 `@Paper Source` 的继续写入指令；该触发包不等于最终 wiki 写入。
- agent-mediated wiki ingest 完成后，先由 wiki agent 写 `final-source-review.json`，再用 `record-wiki-ingest --source-review ...` 只写 `_paper_source/raw/<slug>/wiki-ingest-record.json` 和 `_paper_source/staging/papers/<slug>/wiki-ingest-record.json`，记录目标 vault agent 已写出的最终 Markdown 页、source review、pre-write approval 及其 sha256；它不得修改最终页、manifest、index、log 或 hot。
- Zotero 集成只写 `_paper_source/raw/<slug>/zotero-record.json` 和 run report 中的 `zotero_results`；它不得调用外部 API、改 final wiki 页或删除 Zotero 数据。
- 旧顶层 `_raw`、`_staging`、`_runs`、`_quarantine`、`_evolution` 只作为 legacy migration 输入存在；新初始化不得创建这些顶层目录。
- `_paper_source/policies/retention.json` 同时定义总量阈值和 lifecycle 上限。默认总量预算是 3000 files / 1 GiB，用来尽早暴露内部仓库体量压力；`_paper_source/meta/run-lifecycle`、`_paper_source/meta/raw-cleanup`、`_paper_source/meta/repository-maintenance`、`_paper_source/meta/migrations`、`_paper_source/meta/wiki-reset`、`_paper_source/meta/formal-page-snapshots` 和 `_paper_source/tmp-manual-pdfs` 都是有上限的维护/临时区，不应无限累计。

## 测试与发布结构

源码测试主要在宿主仓库的 `tests\paper_source`。插件内 wrapper smoke 由源码测试覆盖，避免在插件包内放重复测试文件增加 token budget。

常用检查：

```powershell
python -m pytest tests\paper_source -q
python -m pytest tests\paper_source tests\paper_source\test_wrapper_entrypoints.py -q
python <plugin-creator-validate-script> <plugin-root>
node <plugin-eval.js> analyze <plugin-root> --format markdown
python scripts\orchestrator.py evaluation-brief --target-asset <asset> --rationale "<text>" --proposed-change-json "<json>" --before-metrics-json "<json>" --after-metrics-json "<json>"
```

当前 Codex 运行态安装副本以 `codex plugin list` 为准；在本机应显示为 `%USERPROFILE%\.codex\.tmp\marketplaces\paperflow\plugins\paper-source`。旧缓存只作为历史安装线索，不是当前源码入口。源码改动必须先提交并通过 GitHub/marketplace 升级流程进入安装副本；不要把安装 cache 当成开发源。

用户级 runtime 配置不放在安装 cache 版本目录，而放在 `%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json`，用于保存 MCP/CLI/MinerU 命令路径、`mineru.env` 路径，以及 `paper_search_mcp.env_file` / `easyscholar.env_file` 这类 secret env file 路径；插件升级 cache 不应覆盖它。

## Literature Wiki Contract

正式论文沉淀页面家族是 `references/`、`concepts/`、`derivations/`、`experiments/`、`synthesis/`、`reports/`、`opportunities/`。Paper Source 只在 `_paper_source/` 中生成 evidence bundle、approval、trigger、record 和 `wiki-ingest-brief.json` canonical Paper Source-to-Paper Wiki handoff；最终页面由 Paper Wiki `$paper-research-wiki` 作为 canonical 写入和维护入口。`wiki_deposition_task.json` 只作为历史 handoff 清理对象，`paper-source-paper-deposition` 不作为新任务入口。

完整 page-family/frontmatter 契约见 Paper Wiki `plugins/paper-wiki/rules/wiki-writing-standard.md`（canonical）。

正式写入所需 Paper Source/Paper Wiki skill 边界是 `paper-wiki` 插件包提供的 `$paper-research-wiki`；Paper Source `paper-source-paper-deposition` 只用于历史 handoff cleanup。external wiki skills are optional helpers / policy references, including `llm-wiki`、`wiki-ingest`、`wiki-context-pack`、`wiki-lint`、`wiki-stage-commit`、`wiki-status`、`wiki-query`、`wiki-provenance`、`tag-taxonomy`。正式页 frontmatter 至少包含 `title`、`category`、`page_family`、`tags`、`aliases`、`sources`、`summary`、`provenance`、`base_confidence`、`lifecycle`、`lifecycle_changed`、`tier`、`created`、`updated`。`category` 和 `page_family` 要匹配目录；初始状态只能是 `draft`，旧 `review-needed` 只作为迁移/修复对象，不能使用 `source-reviewed` 或 `verified` 作为正式页 lifecycle。

科研审阅字段固定为 `theory_reconstruction`、`formula_derivation`、`figure_table_evidence`、`novelty_type`、`implementability`、`reproducibility_risk`、`research_gap`、`cost_level`。record/lint gate 还要检查 source reread、formula/figure review、Obsidian wikilinks、provenance.extracted/inferred/ambiguous、禁止 `_paper_source/` 进入正式图谱、禁止 forbidden formula blocks、`derivations/` 的变量定义和推导链、`references/` 的模型/公式/实验/限制，以及 `synthesis/` 的 cross-paper comparison matrix。
