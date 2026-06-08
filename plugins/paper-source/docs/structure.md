# Paper Source / EPI 插件结构说明

本文档描述当前 Paper Source/EPI 插件的源代码结构、运行边界和主要产物位置。Paper Source 是用户可见名，当前 machine-facing name 是 `paper-source`；EPI / `epi` 是 pre-Stage-2 legacy alias 和内部 artifact/skill 历史词。它回答“文件在哪里、谁负责什么、哪些目录不能被当成最终知识库写入入口”。文档权威分工（doc map）见 `docs/epi-linkage.md` 顶部；本文档只承担结构说明。若需要一份中文导航，先读 `docs/overview.zh.md`。

## 总体边界

Paper Source/EPI 是 Codex 插件源码包，位于 `<plugin-root>`。插件的目标链路是：按用户画像/config 衍生高质量论文发现和排序 -> raw artifact 留痕 -> Reader/Critic 证据审查 -> staging evidence package -> `wiki-ingest-brief.json` canonical EPI-to-PRW handoff -> Paper Wiki/PRW `$paper-research-wiki` -> lint/review -> EPI record。`wiki_deposition_task.json is legacy` compatibility only, routed through `epi-paper-deposition` when needed。它是通用学术论文插件，不把任何单一学科写成默认方向。

Paper Source/EPI 自身不应该把最终 Obsidian 页面路径、标签、合并策略或 staged writes 固定死。最终写入规则来自目标 vault 的 `AGENTS.md` 和根 `_meta/*` contract 文件，并参考个性化 `obsidian-wiki-dev`、`Ar9av/obsidian-wiki`、`kepano/obsidian-skills`。本插件只准备 `_epi/` 内部仓库中的证据、报告、审计记录、brief-first handoff 和 legacy compatibility metadata。

Sibling 插件包 Paper Wiki/PRW（目录 `plugins/paper-wiki`，machine-facing name `paper-wiki`；`prw` 是 pre-Stage-2 legacy alias）是面向用户的一体化论文 wiki 助手，并提供公共 skill `$paper-research-wiki`：用户只需要请求 `提取` Paper Source/EPI 论文、`根据 wiki 提问`、`检测` wiki 库、`更新` wiki 库或 `重link` 论文知识。它内部消费 Paper Source/EPI 产出的 `wiki-ingest-brief.json`、source bundle 和 final-source-review contract；`wiki_deposition_task.json is legacy` compatibility only。Paper Source/EPI 保留发现、采集、MinerU、paper-gate、人类批准记录和 `record-wiki-ingest`。

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
- `docs/`：用户可读说明。`overview.zh.md` 是中文总览入口；`epi-linkage.md` 是主链路维护契约；`structure.md` 是本文件；`progress.md` 是开发进度说明；`config.md` 是首次配置和修改配置的话术来源。
- `scripts/`：Codex 插件内的可执行 wrapper。用户和技能通常调用 `python scripts\orchestrator.py ...`。
- `scripts/build/epi/`：实际 Python 实现模块。wrapper 会把这里作为包代码运行。
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
- Wiki 库初始化/重置：`wiki-setup` skill 负责初始化和重置流程；初始化只补缺失结构，并在 `<vault>\.git` 缺失时自动 `git init`，但不自动创建首个 commit。初始化后的 EPI 内部产物只在 `_epi/` 下展开，根 `_meta/` 只保留 wiki contract 文件。重置必须先盘点、备份计划并要求用户二次确认 `确认重置 EPI wiki`。`wiki-reset --preview` 先列出会备份、删除、保留的路径；`wiki-reset` 是执行器，默认备份内容并保留 `_epi\meta\epi-config.yaml`、`_epi\meta\epi-config-state.json`、config history 目录，且不得触碰用户级 `%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json`。如需同时重置配置，必须另行确认 `确认同时重置 EPI config` 并显式传入 `--reset-config-confirmed-by`。若出现误删或误操作，先停止后续论文流程，用 `wiki-repair` 单入口检查恢复状态，或用 `config-recover` 查找候选配置，再用 `config-restore` 在确认后恢复。
- 发现与推进：`dry-run`、`advance-ranked`、`advance-paper`、`advance-batch`、`ingest-one`、`acquire-paper`。
- 解析与修复：`parse-paper`、`redo-acquire`、`redo-parse`、`redo-read`、`recritic`。
- Reader/Critic/Gate：推进命令内部生成 reader 和 critic；只读检查用 `paper-gate`。
- Report：`report` 是公开读取入口；`report --run-id <run-id> [--json]` 读取已有 run report artifact；内部生成模块是 `report_run.py`，不是额外的 `run-report` CLI。
- Staging 与 Wiki handoff：`stage_wiki.py` 生成 `wiki-ingest-brief.json` canonical EPI-to-PRW handoff 和 `promotion-plan.json`，只在显式 legacy compatibility 下生成 `wiki_deposition_task.json`；`wiki-ingest-handoff` 渲染 agent-mediated handoff；`record-human-approval` 记录外部 agent 写入前的人类批准；`wiki-ingest-trigger` 写继续任务；PRW `$paper-research-wiki` 是用户级正式论文 wiki 写入和维护入口；`epi-paper-deposition` 仅保留旧 handoff / record provenance 的 compatibility adapter；`record-wiki-ingest` 记录外部 agent 已完成的最终页路径、hash 和 formal page gate；`promote-to-wiki` 仅保留 legacy compiled-draft 兼容。
- 索引与查询：`runs-query`、`research-queue`、`wiki-query`、`wiki-ask`。
- 反馈、评估与进化：`record-feedback`、`evaluation-brief`、`propose-evolution`、`activate-evolution`、`evolution-query`。`evaluation-brief` 把 Plugin Eval、`epi-quality-gates`、benchmark 和 before/after metrics 合并成本地 improvement brief，再交给 `propose-evolution`。
- 外部集成：`zotero-sync`，以及 MinerU 解析相关命令。

## Python 模块职责

```text
scripts/build/epi/
  cli.py
  cli_parser.py
  cli_routes.py
  orchestrator.py
  artifacts.py
  config.py
  doctor.py
  runtime_config.py
  paper_search_adapter.py
  normalize_candidates.py
  filter_candidates.py
  rank_papers.py
  review_sessions.py
  fetch_plan.py
  acquire_papers.py
  run_mineru_parse.py
  evidence_index.py
  generate_reader.py
  reader_*.py
  run_critic.py
  report_run.py
  wiki_contracts.py
  paper_quality.py
  role_critics.py
  research_decision.py
  reproduction_plan.py
  reader_revision_*.py
  stage_wiki.py
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
  promote_to_wiki.py
  raw_cleanup.py
  run_index.py
  wiki_query.py
  skill_aware_evolve.py
  evaluation_loop.py
```

- `cli.py` 保留公开 CLI 入口；`cli_parser.py` 和 `cli_routes.py` 拆出参数定义、JSON/Markdown 输出和命令分发，避免入口继续膨胀。
- `orchestrator.py` 是兼容入口和流程编排层，负责 dry-run、one-paper ingest、batch advance、redo/recritic 等阶段串联；record/promote 相关 helper 已拆到 `wiki_record_workflows.py`。
- `artifacts.py` 负责 EPI 路径约定、sha256、时间戳和原子写入；`write_json_atomic` / `write_text_atomic` 用临时文件加 `os.replace` 写 JSON/Markdown，避免 `_epi/runs/index.json`、record 和 report 在异常中写坏。
- `config.py` 负责 `_epi/meta/epi-config.yaml` 的读取、初始化、提案和更新历史；配置缺失时必须走聊天式 `config-setup`。旧 `_meta/epi-config.yaml` 只作为迁移/兼容读取来源。
- `config_protection.py` 负责共享确认口令和 config 保护白名单，供 reset、repair、restore 复用。
- `wiki_reset.py` 负责 wiki reset 执行器：preview、确认口令、备份/删除、config 默认保护、初始化和 reset manifest。
- `doctor.py` 负责只读健康检查；外部依赖缺失是 warning，插件结构缺失才 error。它还报告 `mcp_outer_launcher` 和 `codex_mcp_registration`，用于区分插件 `.mcp.json` 外层 bootstrap 不可启动、用户级 `config.toml` 静态 MCP 覆盖、runtime.json 内层解释器失效这几层问题。
- `runtime_config.py` 负责从 `%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json` 加载本机依赖配置，只补缺失的进程环境变量，不覆盖显式 env，不保存 token 明文；paper-search provider key/email 只能通过 `paper_search_mcp.env_file` 或显式进程环境进入。
- `paper_search_adapter.py` 优先调用外部 `paper-search-mcp` stdio server，并在失败、超时或空结果时回退到 `paper-search` CLI，把上游输出标准化为 EPI 候选记录；`plan_source_routing` 会把 Google Scholar 等 `unstable` source 默认降级，并把 Unpaywall email 缺失写成 `source_routing.provider_gaps` / `unpaywall_email_missing`；dry-run report 会保留 `source_coverage`，包含 `sources_used`、`source_results`、`errors`、`raw_total`、`deduped_total`、`query_count`、source capability matrix、provider readiness、source routing 和 provider gaps；`doctor --json` 也会输出 `paper_search_provider_readiness`，暴露 Unpaywall/CORE/Semantic Scholar/Google Scholar/DOAJ/Zenodo provider env 缺口；acquire 后可调用 MCP `read_<source>_paper` 或 CLI read 写 non-authoritative retrieval preview。
- `review_sessions.py` 负责 `_epi/reviews/<review-id>/` 的 default resume 状态：signature、`state.json`、`candidates.json`、`shortlist.json`、`fetch_plan.json`、`coverage.json`、`provider-cache/query-*.json`、resume 计数和 provider-call skip 记录。
- `fetch_plan.py` 从 ranked candidates 生成 `fetch_plan.json`，保留候选 PDF URL、source identities、manual download URL 和推荐采集顺序，避免 resume 后重复推导下载计划。
- `acquire_papers.py` 负责下载或复制 PDF，优先用 MCP `download_with_fallback` 做开放访问 fallback chain；若候选没有 direct PDF URL 且 OA fallback 无 PDF，会快速返回 `failure_class=manual-download-required` 和 `manual_download.candidate_manual_urls`，让 agent 直接给用户 DOI/出版商链接并要求通过 organization/institution 手动下载；有 direct PDF URL 时才继续回退 source-native MCP、CLI 和 direct URL。下载到 PDF 后会做轻量 DOI/title identity check：通过或无法提取时记录 `identity_check` 并继续；明确不匹配时写 `identity-check.json`、`failure_class=identity-mismatch`，把 PDF 隔离到 `_epi/quarantine/papers/<slug>/paper.pdf`，不进入 MinerU。成功 `acquire-record.json` 记录 `doi`、`title`、`use_scihub`、`fallback_chain`、`mcp_server_probe`、`upstream.tool` 和可选 `retrieval_preview`，并把 `paper-search-read-preview.txt` 写作 `_epi/raw/<slug>/` 下的 sidecar。该 sidecar 不是 source bundle 的权威解析，MinerU remains canonical parse，最终 wiki 仍必须重读 `paper.pdf`、MinerU Markdown/TeX/images/manifest；失败记录保留合并候选的 `candidate_pdf_urls`、`acquire_attempts`、`failure_class`、`retryable`、`recovery_hint` 和可选 `manual_download`，让后续 agent 区分重试、换源、手动补 PDF、identity mismatch quarantine 和跳过。
- `raw_cleanup.py` 负责清理失败的 `_epi/raw/<slug>` 目录；只有在没有下载到 `paper.pdf`、没有 staging、没有 wiki-ingest/zotero 下游记录且路径仍直属 raw root 时才删除，并把 manifest 写到 `_epi/meta/raw-cleanup/`。
- `rank_papers.py` 负责 paper type classification、ranking signals、ranking rubric、ranking protocol 和三角色排序解释。
- `run_mineru_parse.py` 负责 MinerU 命令调用、失败记录和 fixture materialization；默认 7200 秒超时，可由 `--mineru-timeout` 或 `EPI_MINERU_TIMEOUT` 覆盖。成功 parse 会调用 `evidence_index.py` 写 `_epi/raw/<slug>/evidence-index.json` 并刷新 `_epi/meta/evidence-index.json`。
- `evidence_index.py` 负责从 MinerU Markdown 建立 full-text locator index：按 heading/page marker/chunk 记录 page、section_path、source_locator、chunk hash、input hashes 和 warnings；它是 wiki provenance 的检索辅助，不替代 source-first reread。
- `generate_reader.py`、`reader_outputs.py`、`reader_evidence.py`、`reader_protocol.py` 负责多角色 reader、evidence map 和证据地址校验；reader 会把 TeX、MinerU manifest 和 PDF fallback 作为 source-first 证据写入 evidence/claim-support，而不是只输出摘要。
- `run_critic.py`、`paper_quality.py`、`role_critics.py` 负责 critic quorum、学术论文可靠性检查和三角色质量门；其中 `parse-quality-critic` 会检查 MinerU Markdown、TeX、images、manifest 和 `parse-record.json`，避免原文公式/图像证据在进入 reader/wiki 前被静默抹掉。
- `report_run.py` 负责生成 `_epi/runs/<run-id>/report.md` 和 `report.json`，并提供 `report --run-id` 的只读 loader；该 CLI 会展示 run report artifact 和 `run-state.json` payload，但不刷新 index、queue、raw、staging、Zotero 或 wiki。
- `research_decision.py`、`reader_revision_plan.py`、`reader_revision_guidance.py`、`reproduction_plan.py` 把 critic 结果翻译成决策、修复建议和紧凑复现 caveat。
- `wiki_contracts.py` 固定七类正式页面、brief-first required EPI/PRW skills、frontmatter schema、quality gates、legacy alias 和 QMD collection boundary 等跨模块常量；`paper-research-wiki` qmd collection 允许正式页目录加 `AGENTS.md`、`index.md`、`hot.md`、`log.md`、`_meta/`，必须 ignore `_epi/**`、`.obsidian/**`、`.claude/**`，让 `_epi/meta/formal-page-snapshots/`、raw MinerU source Markdown 和 staging handoff 不进入 QMD。external wiki skills are optional helpers / policy references。
- `stage_wiki.py` 负责 `_epi/staging` 内部证据包、轻阅读报告、`wiki-ingest-brief.json` canonical EPI-to-PRW handoff、`final_source_review_contract` 和 `promotion-plan.json`；默认新 staging 不需要 `wiki_deposition_task.json`，只在显式 legacy compatibility 下生成。它会把 `evidence-index.json`、chunk count、input hashes、warnings 和 `_epi/meta/evidence-index.json` 作为 locator aid 暴露给 handoff，但不得把审计页当成正式 wiki 页写到根目录。
- `paper_gate.py` 是只读质量门面板，决定当前 slug 是 failure、waiting for human gate，还是允许进入下一动作；它调用 `source_bundle_audit.py` 检查 `paper.pdf`、`metadata.json`、MinerU Markdown、`mineru/paper.tex`、`mineru/images/*` 和 `mineru/mineru-manifest.json`，当 source bundle is incomplete 时阻止 final handoff。
- `source_bundle_audit.py` 负责 raw source bundle 的磁盘完整性审计和 image hash 明细，供 `paper_gate.py` 与 record provenance 复用。
- `graph_visibility.py` 负责 Obsidian `.obsidian/graph.json` 的正式目录 filter 和 `collapse-filter` 修复，避免过度转义导致图谱只剩 index。
- `wiki_language.py` 负责 formal page language gate：formal wiki page body prose defaults to Chinese；英文只保留论文题名、术语、缩写、证据字段和路径。
- `wiki_handoff_contracts.py` 保存 agent context policy：独立 wiki deposition 子任务可交给 fresh-context worker，主 agent 只读最终产物、changed file list 和 verification result；Codex 仍必须先有用户显式授权才可用 subagents。
- `wiki_ingest_handoff.py` 是只读 handoff 渲染器，给最终 wiki ingest agent 提供路径、规则优先级、final-source-review 合同、QMD 边界、agent context policy 和 checklist；它应显示 `qmd collection show paper-research-wiki`、`qmd ls paper-research-wiki/_epi`、`qmd ls paper-research-wiki/_epi/meta/formal-page-snapshots` 这类验证命令。
- `wiki_ingest_approval.py` 是 agent-mediated 前置人类批准 helper：写入并校验 `_epi/staging/papers/<slug>/human-approval.json`，要求当前 gate 只有 `human-approval` 待办。
- `wiki_ingest_trigger.py` 是批准后的继续/触发 helper：写入 `_epi/staging/papers/<slug>/wiki-agent-trigger.json`，让 PRW `$paper-research-wiki` 或当前 Claude、Codex 等 wiki-capable agent 按同一 target vault contract 继续最终页写入；它不写最终 wiki 页面。
- `wiki_ingest_record.py` 是 agent-mediated 完成态记录器：只读取最终 Markdown 页面、前置 `human-approval.json`、canonical `wiki-ingest-brief.json` 和 `final-source-review.json`，校验路径在 vault 内且不在 EPI 内部目录，验证源工件 hash、公式/图片/PDF 复核和 final page provenance，检查 formal frontmatter、`category/page_family`、provenance、wikilinks、Chinese-default 正文、forbidden formula blocks 和 family-specific quality gates，记录 hash 和 human approval，不写最终页面。legacy `wiki_deposition_task.json` 只作为兼容 sidecar 记录。
- `wiki_record_workflows.py` 承接 `record-human-approval`、`record-wiki-ingest`、legacy promote/rollback run-state/report 写入，先完成 record 校验再创建 `_epi/runs/record-wiki-ingest-*`，避免失败校验留下空 run 目录。
- `promote_to_wiki.py` 只保留 legacy compiled-draft promotion 和 rollback，不能替代 agent-mediated wiki ingest。
- `zotero_sync.py` 负责本地 record-only Zotero sidecar：读取论文 metadata 和 wiki ingest record，写 `zotero-record.json`，不调用外部 Zotero API。
- `run_index.py` 负责 `_epi/runs/index.json`、dashboard 和 `research-queue.json`，并在 ready queue 里嵌入当前 paper-gate 摘要；record/promote routed runs 会把 `zotero_results` 带入 index 和 dashboard。
- `wiki_query.py` 同时保留 legacy manifest/index 视角的 `wiki-query`，并提供 read-only `wiki-ask` formal graph retrieval：读取正式页根目录，扩展 backlinks/outlinks/aliases/tags/co-links，输出具体的证据/综合/推断/不确定 answer sections 和 correction candidates；它可只读解析正式页 `sources` 或正文中的 `_epi/raw/<slug>/paper.pdf` source evidence 来确认源工件可用性，但 `_epi/raw` 不作为 formal graph node；它不写 `log.md`、正式页、QMD、`prw-record-request.json` 或 EPI artifacts。
- `skill_aware_evolve.py` 负责 proposal-based 自进化，默认不直接修改插件代码、用户配置或 compiled wiki。
- `evaluation_loop.py` 负责插件开发质量环：合并 Plugin Eval、`epi-quality-gates`、benchmark、before/after metrics，写出 `epi-improvement-brief-v1` JSON/Markdown 和 `proposed_evolution` payload。默认输出目录是 `.plugin-eval/improvement-briefs/`，属于本地开发产物。
- `epi_repository.py` 负责 `_epi` 初始化、manifest、legacy migration 和 repository cleanup。`epi-repository-cleanup --preview --json` 是 no-write inspection；非 preview cleanup 即使未超总文件/体积阈值，也会按 retention lifecycle 上限清理 terminal run dirs、维护 manifest、formal-page snapshots 和临时 manual PDFs，但不得删除 `_epi/raw`、`_epi/reviews`、配置历史、Zotero record 或最终 wiki 页。

## Skills 结构

```text
skills/
  config-setup/
  epi-paper-deposition/
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
- `paper-discovery`：搜索、排序和 dry-run；默认指向 `prepare-ranked` 快路，写 raw 源材料、MinerU 解析产物和 source-staging 审批报告，不写最终 wiki。
  - `paper-discovery/scripts/query-planner.py` 与 `paper-discovery/references/` 保存可维护检索策略：mode routing、query planner、paper type taxonomy、ranking rubric、domain ontology、source tiers、dedup engine、venue prior、two-stage retrieval、citation graph、evaluation set、multi-source workflow、quality gate、anti-patterns 和对话输出格式。venue prior 从用户画像/config 衍生，社区榜单只进入对应领域的弱 prior，真实指标仍需单独核验。
- `topic-tracking`：主题中心、纵向增量、backlog、coverage 和 broad-to-deep 阅读视图；它承接“这次之后有什么新东西”“我有没有漏掉关键分支”这类问题，`paper-discovery` 只保留检索/排序底层。
- `paper-ingest`：推进已选论文进入 raw、source-staging 和 handoff；默认 `fast-ingest` 不跑 reader/critic，`reviewed-ingest` / `audited-ingest` 才按需加入。
  - `paper-ingest/references/source-first-reading.md` 是 source-staging/wiki handoff 的 source-first 阅读协议，要求最终沉淀前重读 MinerU Markdown、TeX、images、manifest 和必要时的 PDF，最终记录 `final-source-review.json`；`reader/claim-support.json` 只有在 reviewed/audited ingest 生成时才作为辅助区分源文摘取、metadata-only 与 inference。
- `epi-paper-deposition`：legacy compatibility adapter；当旧 artifact 提到 `wiki_deposition_task.json` 或 `epi-wiki-deposition` 时，确认 `wiki-ingest-brief.json` exists 后转给 sibling 插件包 `paper-wiki` / `plugins/paper-wiki` 提供的 `$paper-research-wiki`。`llm-wiki`、`wiki-ingest`、`wiki-context-pack`、`wiki-lint`、`wiki-stage-commit`、`wiki-status`、`wiki-query`、`wiki-provenance` 和 `tag-taxonomy` 等 external wiki skills are optional helpers / policy references。
- `mineru-paper-parser`：低层 PDF -> Markdown/TeX/images/manifest 解析能力；成功后最终产物只放在 `mineru/`，`paper.tex` 必须非空，必要时使用 Markdown fallback。
- `wiki-provenance`：final wiki 页 provenance、claim support status、evidence address 和 round-trip retrieval hook；它承接“最终页上的这句话到底来自哪里”这类问题，`paper-ingest` 只保留 source-first handoff。
- `skill-aware-evolve`：根据 evidence 和验证结果提出受控变更；配置问题必须走配置 proposal。
- `wiki-setup`：初始化、检查、修复和重置 paper wiki vault。入口只保留边界和命令，详细恢复与误删清单见 `skills/wiki-setup/references/reset-recovery.md`。初始化会创建或保留 vault-local git repository，写入 `AGENTS.md` 和 `_meta/agent-operating-contract.md`、`_meta/schema.md`、`_meta/taxonomy.md`、`_meta/directory-structure.md`，默认要求 source-first paper ingest：最终 wiki 写入先读 `mineru/<slug>.md`、`mineru/paper.tex`、`mineru/images/*` 和 manifest。
- `zotero-sync`：Zotero 记录和可选同步，默认安全边界是本地记录优先；`record-wiki-ingest` 和 legacy `promote-to-wiki` 会自动写 record-only sidecar 并把结果带入 report。

## Vault Artifact 结构

EPI 默认 vault 形态。除根 `_meta/` wiki contract 文件外，EPI 的运行、审计、raw、staging、evolution、cleanup 产物都收拢在单一 `_epi/` 内部仓库中：

```text
<vault>/
  _epi/
    README.md
    manifest.json
    policies/
      retention.json
    meta/
      epi-config.yaml
      epi-config-state.json
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
        normalized.json
        rank.json
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

- `dry-run` 写 `_epi/runs` 和 resumable `_epi/reviews`；默认自动 resume，`--refresh` 强制 provider 重搜。
- raw 阶段写 `_epi/raw/<slug>`，不写最终 wiki。
- 默认 fast-ingest 在源材料完整后可写 `_epi/staging/papers/<slug>` 的轻量 handoff 和 `wiki-ingest-brief.json`；new staging does not require `wiki_deposition_task.json`，该文件仅为 legacy compatibility。audited-ingest 和已有 critic report 的论文必须 critic pass。
- `wiki-ingest-handoff` 和 `paper-gate` 都是只读。
- 当前默认 agent-mediated plan 不写 compiled wiki。
- agent-mediated wiki ingest 前，必须先用 `record-human-approval --scope run-wiki-ingest-agent` 写 `_epi/staging/papers/<slug>/human-approval.json`；`wiki-ingest-handoff` 只有在该 artifact 有效时才显示 `ready_for_agent=true`。
- 批准后可用 `wiki-ingest-trigger --slug <slug>` 写 `_epi/staging/papers/<slug>/wiki-agent-trigger.json`，作为当前 agent 或下一次 `@EPI` 的继续写入指令；该触发包不等于最终 wiki 写入。
- agent-mediated wiki ingest 完成后，先由 wiki agent 写 `final-source-review.json`，再用 `record-wiki-ingest --source-review ...` 只写 `_epi/raw/<slug>/wiki-ingest-record.json` 和 `_epi/staging/papers/<slug>/wiki-ingest-record.json`，记录目标 vault agent 已写出的最终 Markdown 页、source review、pre-write approval 及其 sha256；它不得修改最终页、manifest、index、log 或 hot。
- Zotero 集成只写 `_epi/raw/<slug>/zotero-record.json` 和 run report 中的 `zotero_results`；它不得调用外部 API、改 final wiki 页或删除 Zotero 数据。
- legacy `promote-to-wiki` 只处理显式 compiled targets，并要求 `approved-by`。
- 旧顶层 `_raw`、`_staging`、`_runs`、`_quarantine`、`_evolution` 只作为 legacy migration 输入存在；新初始化不得创建这些顶层目录。
- `_epi/policies/retention.json` 同时定义总量阈值和 lifecycle 上限。默认总量预算是 3000 files / 1 GiB，用来尽早暴露内部仓库体量压力；`_epi/meta/run-lifecycle`、`_epi/meta/raw-cleanup`、`_epi/meta/repository-maintenance`、`_epi/meta/migrations`、`_epi/meta/wiki-reset`、`_epi/meta/formal-page-snapshots` 和 `_epi/tmp-manual-pdfs` 都是有上限的维护/临时区，不应无限累计。

## 测试与发布结构

源码测试主要在宿主仓库的 `tests\epi`。插件内 wrapper smoke 由源码测试覆盖，避免在插件包内放重复测试文件增加 token budget。

常用检查：

```powershell
python -m pytest tests\epi -q
python -m pytest tests\epi tests\epi\test_wrapper_entrypoints.py -q
python <plugin-creator-validate-script> <plugin-root>
node <plugin-eval.js> analyze <plugin-root> --format markdown
python scripts\orchestrator.py evaluation-brief --target-asset <asset> --rationale "<text>" --proposed-change-json "<json>" --before-metrics-json "<json>" --after-metrics-json "<json>"
```

安装副本在 `%USERPROFILE%\.codex\plugins\cache\paperflow\paper-source\<version>`。旧缓存可能仍存在 `%USERPROFILE%\.codex\plugins\cache\paper-search\epi\<version>`；那只是 pre-Stage-2 installed cache 线索，不是当前源码入口。源码改动必须先提交并通过 GitHub/marketplace 升级流程进入安装副本；不要把安装 cache 当成开发源。

用户级 runtime 配置不放在安装 cache 版本目录，而放在 `%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json`，用于保存 MCP/CLI/MinerU 命令路径、`mineru.env` 路径，以及 `paper_search_mcp.env_file` / `easyscholar.env_file` 这类 secret env file 路径；插件升级 cache 不应覆盖它。

## Literature Wiki Contract

正式论文沉淀页面家族是 `references/`、`concepts/`、`derivations/`、`experiments/`、`synthesis/`、`reports/`、`opportunities/`。EPI 只在 `_epi/` 中生成 evidence bundle、approval、trigger、record 和 `wiki-ingest-brief.json` canonical EPI-to-PRW handoff；最终页面由 PRW `$paper-research-wiki` 作为 canonical 写入和维护入口。`wiki_deposition_task.json is legacy` compatibility only，`epi-paper-deposition` 只作为旧 artifact 或 record provenance 的 compatibility adapter，旧 `epi-wiki-deposition` 只作为兼容 alias。

完整 page-family/frontmatter 契约见 PRW `plugins/paper-wiki/rules/wiki-writing-standard.md`（canonical）。

正式写入所需 EPI/PRW skill 边界是 `paper-wiki` 插件包提供的 `$paper-research-wiki` 和 EPI `epi-paper-deposition` compatibility adapter；external wiki skills are optional helpers / policy references, including `llm-wiki`、`wiki-ingest`、`wiki-context-pack`、`wiki-lint`、`wiki-stage-commit`、`wiki-status`、`wiki-query`、`wiki-provenance`、`tag-taxonomy`。正式页 frontmatter 至少包含 `title`、`category`、`page_family`、`tags`、`aliases`、`sources`、`summary`、`provenance`、`base_confidence`、`lifecycle`、`lifecycle_changed`、`tier`、`created`、`updated`。`category` 和 `page_family` 要匹配目录；初始状态只能是 `draft` 或 `review-needed`，不能默认宣称 `source-reviewed` 或 `verified`。

科研审阅字段固定为 `theory_reconstruction`、`formula_derivation`、`figure_table_evidence`、`novelty_type`、`implementability`、`reproducibility_risk`、`research_gap`、`cost_level`。record/lint gate 还要检查 source reread、formula/figure review、Obsidian wikilinks、provenance.extracted/inferred/ambiguous、禁止 `_epi/` 进入正式图谱、禁止 forbidden formula blocks、`derivations/` 的变量定义和推导链、`references/` 的模型/公式/实验/限制，以及 `synthesis/` 的 cross-paper comparison matrix。
