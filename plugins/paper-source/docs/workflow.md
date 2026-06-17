# Paper Source Workflow

Use `doctor --json` when install, dependency, or vault state is unclear.

命名说明：Paper Source 是本插件的用户可见名，machine-facing name 是 `paper-source`。Paper Wiki 是 sibling wiki 插件的用户可见名，machine-facing name 是 `paper-wiki`。PS/PW 只是自然语言短称，不新增 dollar-prefixed plugin or skill entrypoint；旧别名不再作为用户入口或路由触发条件。

中文总览入口见 `docs/overview.zh.md`；主链路和维护契约见 `docs/paper-source-linkage.md`。本文档是安装后短入口，不复制完整 runbook。

## User Golden Path

日常使用优先走这条主线：

1. `doctor --json` 检查安装、依赖和 vault 状态；配置缺失时先完成 `config-setup`。
2. 方向模糊时先生成 Research Brief；方向明确时运行 `discover-papers --query "<your topic>" --max-results 20 --vault <vault> --json`。`discover-papers` 先跑 discovery evidence，再按 primary recommendations 自动准备最多 3 篇 PDF-available 论文到 source-staging；review/survey/meta-analysis 默认保留，只有明确 non-review intent 才排除。
3. 用 `report --run-id <discovery-run-id> --vault <vault>` 查看底层 discovery report，或直接读取 `discover-papers` JSON 输出里的 `session_recommendations` / `auto_staging_plan`；持续追踪、net-new、coverage 和 backlog 以 wiki `_meta/reference-index.json` 为准，`topic-tracking` 只做增量视图。
4. 选中的论文如果已经有足够 source evidence，交给 Paper Wiki `$paper-research-wiki` 做沉淀或更新。
5. 只有需要覆盖默认 auto-staging 选择、补 PDF、MinerU、source-staging、approval report 或 `wiki-ingest-brief.json` 时，才显式运行 `prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault> --json`；`dry-run` 是 evidence/debug 底层命令，`discover-to-handoff` 是显式重流程捷径，仍停在 source-staging。
6. 如果走 source-staging，先读中文 approval report；同意后运行 `record-human-approval`，再用 `wiki-ingest-trigger` 生成 wiki agent resume package。Codex automation 只能在用户明确授权当前 Trellis/Codex 任务继续沉淀时显式启用，不能从普通 `discover-papers`、auto-staging 或“找论文”请求推断。
7. 由 Paper Wiki `$paper-research-wiki` 或当前 wiki-capable agent 消费 `wiki-ingest-brief.json`，写正式页面和 `final-source-review.json`。
8. 最后运行 `record-wiki-ingest`，让 Paper Source 记录最终页路径、hash、source review 和可选 Zotero sidecar。

新任务只使用 `wiki-ingest-brief.json` 作为 handoff。`wiki_deposition_task.json` 只属于历史残留清理，不是黄金路径的一步。

## Skill-Based Routing And Task Closure

Paper Source 依照 `skill-based-architecture` 维护轻量多 skill 插件：`plugins/paper-source/AGENTS.md` 只指向 `skills/routing.yaml`；`skills/routing.yaml` 是 Always Read、route rematch、task_closure、Codex sub-agent permission 和 skill route 分类来源。

每个 skill 必须提供 `agents/openai.yaml`，且 `interface.default_prompt` 必须包含对应 `$skill-name`。步骤性流程放在各自 `workflows/*.md`，并必须从 `skills/routing.yaml` 的 `workflows` 字段可达。

安装缓存验证必须跑 `doctor --json` 并检查 `skill_bundle_contract`：`status=ok`，`agent_metadata_count` 等于 `skill_count`，`workflow_count` 覆盖 routing 中声明的 workflow，且 missing/empty/orphan workflow 列表为空。还要检查 `mcp_outer_launcher` 与 `codex_mcp_registration`：前者确认插件 `.mcp.json` 外层 bootstrap command、`cwd: "."` 和 `cmd /c .\scripts\paper_search_mcp_launcher.cmd` 相对 launcher script 可被 Codex 解析，且没有残留 `${CLAUDE_PLUGIN_ROOT}` / `${PLUGIN_ROOT}`；后者确认用户级 `config.toml` 没有残留会遮蔽插件自注册的 `[mcp_servers.paper-search-mcp]`。

Task closure 只适用于代码、文档或 skill 行为变更。非平凡变更结束前要 restate original constraints、记录 verification commands and outcomes，并做 30-second AAR。Codex may use subagents only when the user explicitly authorizes delegation or parallel agent work.

## Daily Commands

```powershell
python scripts\orchestrator.py dry-run --query "<your topic>" --max-results 20 --vault <vault>
python scripts\orchestrator.py dry-run --query "<your topic>" --max-results 20 --vault <vault> --json
python scripts\orchestrator.py discover-papers --query "<your topic>" --max-results 20 --vault <vault> --json
python scripts\orchestrator.py discover-papers --query "<your topic>" --grok-mode parallel --max-results 20 --vault <vault> --json
python scripts\orchestrator.py discover-papers --query "<your topic>" --no-grok-search --max-results 20 --vault <vault> --json
python scripts\orchestrator.py discover-papers --query "<natural language topic>" --agent-query-plan-json <agent-query-plan.json> --max-results 20 --vault <vault> --json
python scripts\orchestrator.py discover-papers --query "<your topic>" --max-results 20 --vault <vault> --no-auto-stage --json
python scripts\orchestrator.py dry-run --query "<natural language topic>" --query-variant "\"<domain object>\" \"<task>\" \"<method>\" -review -survey" --query-variant "\"<domain object>\" \"<task>\" code -review -survey" --domain-focus-term "<domain object>" --year-min 2021 --code-policy prefer --max-results 20 --vault <vault> --json
python scripts\orchestrator.py dry-run --query "<natural language topic>" --agent-query-plan-json <agent-query-plan.json> --max-results 20 --vault <vault> --json
python scripts\orchestrator.py dry-run --query "<natural language topic>" --agent-query-plan-json <agent-query-plan.json> --selection-policy balanced_high_quality --max-results 20 --vault <vault> --json
python scripts\orchestrator.py dry-run --query "<your topic>" --max-results 20 --vault <vault> --refresh
python scripts\orchestrator.py report --run-id <run-id> --vault <vault>
python scripts\orchestrator.py report --run-id <run-id> --vault <vault> --json
python scripts\orchestrator.py discover-to-handoff --query "<your topic>" --max-results 20 --max-papers 10 --skip-existing --vault <vault> --json
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault> --json
python scripts\orchestrator.py advance-ranked --run-id <run-id> --max-papers 3 --vault <vault>
python scripts\orchestrator.py research-queue --vault <vault>
python scripts\orchestrator.py normalize-mineru-assets --slug <paper-slug> --vault <vault>
python scripts\orchestrator.py normalize-mineru-assets --slug <paper-slug> --vault <vault> --execute --json
python scripts\orchestrator.py paper-gate --slug <paper-slug> --vault <vault>
python scripts\orchestrator.py wiki-ingest-handoff --slug <paper-slug> --vault <vault>
python scripts\orchestrator.py record-human-approval --slug <paper-slug> --approved-by <name> --scope run-wiki-ingest-agent --vault <vault>
python scripts\orchestrator.py record-human-approval --slug <paper-slug> --approved-by codex-automation:<task-id> --scope run-wiki-ingest-agent --automation-mode codex-task --automation-task-id <task-id> --automation-task-source <task-path-or-session> --automation-authorization "<explicit user authorization>" --vault <vault> --json
python scripts\orchestrator.py wiki-ingest-trigger --slug <paper-slug> --vault <vault>
python scripts\orchestrator.py record-wiki-ingest --slug <paper-slug> --page <final-page.md> --approved-by <name> --source-review <final-source-review.json> --vault <vault>
python scripts\orchestrator.py wiki-ask --question "<research question>" --vault <vault>
python scripts\orchestrator.py wiki-ask --question "<research question>" --vault <vault> --json
python scripts\orchestrator.py zotero-sync --paper-root <vault>\_paper_source\\raw\\<paper-slug> --collection Paper Source --enabled
```

Full command semantics, artifact paths, and safety gates live in `docs/paper-source-linkage.md`.

## Discovery And Source Intake

Paper Source 是通用论文插件，不默认任何学科方向。`dry-run` derives `query-plan.json` from profile, domains, positive/negative keywords, venue prior, and the current request; AUV、机器人、医学等只能来自用户配置、当前请求、Research Brief 或 agent 显式传入的 query variants / hard domain anchors。

自然语言主题不能直接当作 MCP 主检索式。Agent 应先把用户意图形成透明 query plan，生成 5-8 条短学术 query variants，再用 `--query-variant` 或 `--agent-query-plan-json` 传给 `dry-run`；需要硬过滤时用 `--domain-focus-term`、`hard_domain_anchors` 或 `hard_constraints` 传对象/领域锚点。topic 推断词只能进入 `soft_recall_terms`，不得自动升级成 hard filter。`--year-min` 表达明确的近期窗口，`--code-policy prefer` 表达“尽可能有公开代码”，`--code-policy require` 表达硬性代码要求，`--selection-policy` 控制推荐到推进的阈值。脚本负责验证、记录和执行这些显式输入，而不是在 Python 里写死每个学科的语义词典。

`discover-papers` is the natural-language default. It writes a high-level `discover-papers` run that links the underlying discovery run and optional auto-staging run, surfaces `session_recommendations`, `auto_staging_plan`, `manual_downloads`, `discover-papers-record.json`, `report.json`, and `run-state.json`, and stops before approval/Paper Wiki. `dry-run` remains the lower-level evidence/debug command: it writes `_paper_source/runs` and resumable `_paper_source/reviews`; default resume skips provider calls for the same signature. Use `--refresh` to force provider search. Long-term library/backlog state lives in wiki `_meta/reference-index.json`, not in review sessions. It writes source coverage into `report.json.discovery_context.source_coverage`, request constraints into `report.json.discovery_context.request_constraints` / `query-plan.json`, chat-facing reading decisions into `report.json.session_recommendations`, and filtering/readiness diagnostics into `discovery-diagnostics.json`, with `sources_used`, `source_results`, `errors`, `raw_total`, `deduped_total`, `query_count`, `capabilities`, `provider_readiness`, `source_routing`, `provider_gaps`, `recommendable`, `staging_ready`, `needs_pdf`, `rejected`, `already_in_wiki`, and `already_in_library`.

`paper-search-mcp` is the broad retrieval and metadata provider behind the default source route, not the final judge of paper quality. Paper Source treats upstream source counts, errors, rate limits, unsupported download/read capabilities, and DOI-only sources as source-coverage evidence. Paper Source owns the cross-discipline quality gate: strict `priority_keywords` drive relevance when hard anchors exist; otherwise saturated positive keyword matches can pass topic fit while `keyword_coverage_score` remains diagnostic. `quality_gate.dimensions` explains identity, relevance, inspectability, validation, source confidence, reproducibility, and request risk for each ranked candidate.

Optional `grok-search-rs MCP` is a supplemental discovery path inside this same workflow. It is configured locally through runtime.json and controlled by vault `grok_search` plus `--grok-mode targeted|parallel|off` / `--no-grok-search`. Default targeted mode runs paper-search first and may skip Grok when paper-search is good enough. Parallel mode is aggressive shortfall recall that starts a static Grok query set beside the full paper-search lifecycle; it does not stop or shorten paper-search. The adapter calls MCP `web_search` with `response_format=detailed`, keeps `OPENAI_COMPATIBLE_MODEL` as the primary model, retries configured/default model fallbacks only for provider fallback or `source_fallback` responses, and records non-secret `model_attempts` in `grok-search-raw.json`. Provider artifacts stay separate as `paper-search-record.json`, `grok-search-record.json`, `grok-search-raw.json`, and `grok-search-evidence.json` before merged `search-record.json`. Final recommendations still require at least one usable paper-search candidate; Grok-only salvage is evidence/diagnostics only.

`report.json.session_recommendations` uses `paper-source-session-recommendations-v1`: `primary_recommendations` is the capped chat-visible priority list, `review_appendix` keeps Tier C / non-Reject `review-candidate` papers out of the primary recommendation list, `existing_library_appendix` keeps already-in-wiki/raw-library papers out of new recommendations, `doi_required_policy` requires DOI-present papers for primary/review output, `doi_recovery_summary` / `doi_resolution_summary` show targeted DOI recovery success and failure counts, `doi_filtered_summary` records any remaining `missing_required_doi` candidates, `quality_reject_debug` keeps Reject records as diagnostics, `rejected_summary` gives count/reason evidence, and `overflow.hidden_count` tells the agent when more primary candidates remain in artifacts. Paper Source does not generate semantic Chinese summaries internally; the calling agent writes them from `original_abstract` / `chinese_summary.source_text`.

Automatic staging policy uses `paper-source-auto-staging-plan-v1`: only `session_recommendations.primary_recommendations` are eligible, at most 3 PDF-available papers are selected by default, review/survey/meta-analysis papers consume at most 1 default slot unless explicitly requested, and `needs_pdf` papers keep DOI/arXiv/publisher/manual links but are skipped until the user supplies a PDF. The auto-staging run records `auto_staging_plan` and refreshed `session_recommendations.primary_recommendations[*].auto_staging_status`; it stops at source-staging and does not create human approval records, wiki-ingest triggers, Paper Wiki formal pages, or wiki-ingest records.

本机 runtime 由 `%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json` 补齐；token/secret/provider key 只来自进程环境或 approved env file。Grok/OpenAI-compatible relay 必须由每个用户自行配置 endpoint/key/model；`PAPER_SOURCE_GROK_MODEL_FALLBACKS` 和 `PAPER_SOURCE_GROK_PARALLEL_GRACE_SECONDS` 只控制非 secret 的 fallback/等待策略。浏览器 Cloudflare challenge、TUN/fake-IP 或代理 DIRECT 规则属于本机网络诊断，不写入插件默认。`doctor --json` reports `paper_search_provider_readiness`, optional `grok_search_mcp`, and provider gaps such as `PAPER_SEARCH_MCP_UNPAYWALL_EMAIL`, `PAPER_SEARCH_MCP_CORE_API_KEY`, `PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY`, `PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL`, `PAPER_SEARCH_MCP_DOAJ_API_KEY`, and `PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN`.

EasyScholar is default-on after filter and before rank. It writes `easyscholar-record.json`, `verified_metrics.easyscholar`, and `easyscholar_score`; missing key, no match, timeout, or API error soft-fails as `未核实`. Use `--no-easyscholar` for a single run.

`prepare-ranked` is the explicit search -> acquire -> MinerU -> source-staging path. Use it only after selection when source artifacts are needed; use `--max-papers 10 --skip-existing` for real batches and `--max-papers 1` only for smoke tests. It stops before human approval and final wiki writing. `discover-to-handoff` is also an explicit heavy shortcut: it runs dry-run plus prepare-ranked and writes a summary run; it does not approve papers, invoke Paper Wiki, or write final pages.

Acquisition first tries MCP `download_with_fallback`; no direct PDF plus exhausted OA fallback becomes `manual-download-required` with `manual_download.candidate_manual_urls`. Direct DOI/publisher links should be shown for organization/institution download instead of weak fallback loops. Successful source read preview writes `paper-search-read-preview.txt` only as non-authoritative retrieval preview, not replacing MinerU.

`acquire_failed` source folders with no `paper.pdf`, staging, wiki-ingest record, Zotero record, or identity-mismatch quarantine are cleaned from `_paper_source/raw/<slug>` and logged in `_paper_source/meta/raw-cleanup/` so failed attempts do not accumulate as library entries.

After MinerU parse success, Paper Source normalizes raw MinerU assets, writes `_paper_source/raw/<slug>/figure-index.json`, `_paper_source/raw/<slug>/formula-index.json`, `_paper_source/raw/<slug>/asset-normalization-record.json`, writes `_paper_source/raw/<slug>/evidence-index.json`, and refreshes `_paper_source/meta/evidence-index.json`; these locator aids do not replace source reread. Use `normalize-mineru-assets` dry-run first for historical raw bundles, then add `--execute` only after reviewing the rename/drop plan. Reader and critic details remain in `docs/paper-source-linkage.md`.

## Human Gate And Recording

Queue buckets are `ready_to_promote`, `needs_reader_repair`, `warning_only`, and `reproducibility_caveats`.

Before recording approval, show one single human-readable 人工确认报告 / approval report instead of raw JSON, gate dumps, critic sidecars, or path lists. The report should be Chinese-first, use Chinese-English / 中英对照 for key terms, keep each card dense, and end with `建议沉淀`, `谨慎沉淀`, or `暂不沉淀`.

Record pre-write approval with `record-human-approval --scope run-wiki-ingest-agent`; it writes `human-approval.json` and lets `wiki-ingest-handoff` show `ready_for_agent=true`. Explicit Codex automation uses the same `paper-source-human-approval-v1` artifact with `approved_by=codex-automation:<task-id>`, optional `automation` metadata, and `approval_actor_type=codex-automation`; all automation flags must be supplied together and match the actor. Ordinary human approval keeps `approval_actor_type=human` and has no `automation` object. `wiki-ingest-trigger` writes a resume package for the current Claude, Codex, or other wiki-capable agent and includes `automation_handoff` only when the approval record contains automation metadata; it does not write final pages.

After Paper Wiki or another wiki-capable agent writes final pages and `final-source-review.json`, run `record-wiki-ingest`. Paper Wiki writes `paper-wiki-record-request.json` in ask-mode automation; Paper Source consumes it with `record-wiki-ingest --from-paper-wiki-request`, validates live page hashes, and writes or replaces `wiki-ingest-record.json`.

If a prior completion is corrected as `premature-wiki-ingest-record`, Paper Wiki repairs pages and `final-source-review.json`; Paper Source writes or replaces `wiki-ingest-record.json` when the correction becomes `paper-wiki-reviewed-ready-for-paper-source-record`.

## Read-Only Wiki Ask

`wiki-ask --question ... --vault <vault>` is a read-only formal graph query CLI. The conversational primary entrypoint is Paper Wiki `$paper-research-wiki` route `ask_wiki`; Paper Source `wiki-ask` is the same-source fallback / 程序化 `--json` entry. 对话场景优先 Paper Wiki。

It retrieves from `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`, expands backlinks/outlinks/aliases/tags/co-links, labels `【Wiki 证据】`, `【综合判断】`, `【推断】`, and `【边界/不确定】`, and reports correction candidates. It does not write `log.md`, formal pages, QMD, `paper-wiki-record-request.json`, or Paper Source artifacts.

## Literature Wiki Contract

Paper Source formal deposition targets seven wiki page families: `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.

Page-family/frontmatter human-readable canonical source is Paper Wiki `plugins/paper-wiki/rules/wiki-writing-standard.md` (canonical). This file only keeps an entry summary; full field rules live there.

Every formal page must include frontmatter fields `title`, `category`, `page_family`, `tags`, `aliases`, `sources`, `summary`, `provenance`, `base_confidence`, `lifecycle`, `lifecycle_changed`, `tier`, `created`, and `updated`. Initial lifecycle is `draft`; old `review-needed` pages are legacy repair inputs, not accepted steady state. Do not use `source-reviewed` or `verified` as formal page lifecycle states; source reread, formula/figure review, wiki-lint, and human stage review belong in `final-source-review.json`, provenance, or target-vault maintenance records.

Quality gates require Obsidian wikilinks, source bundle paths, `provenance.extracted/inferred/ambiguous`, no `_paper_source/` pages in the formal graph, no forbidden formula blocks such as fenced `math`/`tex`/`latex`, derivation pages with variable definitions and derivation chains, reference pages with model/formula/experiment/limit content, and synthesis pages with a cross-paper comparison matrix.

`final-source-review.json` must still record `theory_reconstruction`, `formula_derivation`, `figure_table_evidence`, `novelty_type`, `implementability`, `reproducibility_risk`, `research_gap`, and `cost_level`. Novelty review separates author-claimed novelty from Paper Source-confirmed novelty.

`wiki-ingest-brief.json` is the canonical Paper Source-to-Paper Wiki handoff. New staging does not require or generate `wiki_deposition_task.json`. The next formal write step is Paper Wiki `$paper-research-wiki`, while Paper Source keeps ownership of `paper-gate`, human approval, `wiki-ingest-trigger`, and `record-wiki-ingest`. `paper-source-paper-deposition` is only for historical handoff cleanup, and external wiki skills are optional helpers / policy references.
