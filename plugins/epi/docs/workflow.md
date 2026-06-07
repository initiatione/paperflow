# EPI Workflow

Use `doctor --json` when install, dependency, or vault state is unclear.

中文总览入口见 `docs/overview.zh.md`；主链路和维护契约见 `docs/epi-linkage.md`。本文档是安装后短入口，不复制完整 runbook。

## Skill-Based Routing And Task Closure

EPI 依照 `skill-based-architecture` 维护轻量多 skill 插件：`plugins/epi/AGENTS.md` 只指向 `skills/routing.yaml`；`skills/routing.yaml` 是 Always Read、route rematch、task_closure、Codex sub-agent permission 和 skill route 分类来源。

每个 skill 必须提供 `agents/openai.yaml`，且 `interface.default_prompt` 必须包含对应 `$skill-name`。步骤性流程放在各自 `workflows/*.md`，并必须从 `skills/routing.yaml` 的 `workflows` 字段可达。

安装缓存验证必须跑 `doctor --json` 并检查 `skill_bundle_contract`：`status=ok`，`agent_metadata_count` 等于 `skill_count`，`workflow_count` 覆盖 routing 中声明的 workflow，且 missing/empty/orphan workflow 列表为空。

Task closure 只适用于代码、文档或 skill 行为变更。非平凡变更结束前要 restate original constraints、记录 verification commands and outcomes，并做 30-second AAR。Codex may use subagents only when the user explicitly authorizes delegation or parallel agent work.

## Daily Commands

```powershell
python scripts\orchestrator.py dry-run --query "<your topic>" --max-results 20 --vault <vault>
python scripts\orchestrator.py dry-run --query "<your topic>" --max-results 20 --vault <vault> --json
python scripts\orchestrator.py dry-run --query "<your topic>" --max-results 20 --vault <vault> --refresh
python scripts\orchestrator.py report --run-id <run-id> --vault <vault>
python scripts\orchestrator.py report --run-id <run-id> --vault <vault> --json
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault> --json
python scripts\orchestrator.py advance-ranked --run-id <run-id> --max-papers 3 --vault <vault>
python scripts\orchestrator.py research-queue --vault <vault>
python scripts\orchestrator.py paper-gate --slug <paper-slug> --vault <vault>
python scripts\orchestrator.py wiki-ingest-handoff --slug <paper-slug> --vault <vault>
python scripts\orchestrator.py record-human-approval --slug <paper-slug> --approved-by <name> --scope run-wiki-ingest-agent --vault <vault>
python scripts\orchestrator.py wiki-ingest-trigger --slug <paper-slug> --vault <vault>
python scripts\orchestrator.py record-wiki-ingest --slug <paper-slug> --page <final-page.md> --approved-by <name> --source-review <final-source-review.json> --vault <vault>
python scripts\orchestrator.py wiki-ask --question "<research question>" --vault <vault>
python scripts\orchestrator.py wiki-ask --question "<research question>" --vault <vault> --json
python scripts\orchestrator.py zotero-sync --paper-root <vault>\_epi\\raw\\<paper-slug> --collection EPI --enabled
```

Full command semantics, artifact paths, and safety gates live in `docs/epi-linkage.md`.

## Discovery And Source Intake

EPI 是通用论文插件，不默认任何学科方向。`dry-run` derives `query-plan.json` from profile, domains, positive/negative keywords, venue prior, and the current request; AUV、机器人、医学等只能来自用户配置、当前请求或显式领域 hint。

`dry-run` writes `_epi/runs` and resumable `_epi/reviews`; default resume skips provider calls for the same signature. Use `--refresh` to force provider search. It writes source coverage into `report.json.discovery_context.source_coverage` and `report.md` with `sources_used`, `source_results`, `errors`, `raw_total`, `deduped_total`, `query_count`, `capabilities`, `provider_readiness`, `source_routing`, and `provider_gaps`.

本机 runtime 由 `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json` 补齐；token/secret/provider key 只来自进程环境或 approved env file。`doctor --json` reports `paper_search_provider_readiness` and provider gaps such as `PAPER_SEARCH_MCP_UNPAYWALL_EMAIL`, `PAPER_SEARCH_MCP_CORE_API_KEY`, `PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY`, `PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL`, `PAPER_SEARCH_MCP_DOAJ_API_KEY`, and `PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN`.

EasyScholar is default-on after filter and before rank. It writes `easyscholar-record.json`, `verified_metrics.easyscholar`, and `easyscholar_score`; missing key, no match, timeout, or API error soft-fails as `未核实`. Use `--no-easyscholar` for a single run.

`prepare-ranked` is the search -> acquire -> MinerU -> source-staging path. Use `--max-papers 10 --skip-existing` for real batches and `--max-papers 1` only for smoke tests. It stops before human approval and final wiki writing.

Acquisition first tries MCP `download_with_fallback`; no direct PDF plus exhausted OA fallback becomes `manual-download-required` with `manual_download.candidate_manual_urls`. Direct DOI/publisher links should be shown for organization/institution download instead of weak fallback loops. Successful source read preview writes `paper-search-read-preview.txt` only as non-authoritative retrieval preview, not replacing MinerU.

`acquire_failed` source folders with no `paper.pdf`, staging, wiki-ingest record, Zotero record, or identity-mismatch quarantine are cleaned from `_epi/raw/<slug>` and logged in `_epi/meta/raw-cleanup/` so failed attempts do not accumulate as library entries.

After MinerU parse success, EPI writes `_epi/raw/<slug>/evidence-index.json` and refreshes `_epi/meta/evidence-index.json`; this locator aid does not replace source reread. Reader and critic details remain in `docs/epi-linkage.md`.

## Human Gate And Recording

Queue buckets are `ready_to_promote`, `needs_reader_repair`, `warning_only`, and `reproducibility_caveats`.

Before recording approval, show one single human-readable 人工确认报告 / approval report instead of raw JSON, gate dumps, critic sidecars, or path lists. The report should be Chinese-first, use Chinese-English / 中英对照 for key terms, keep each card dense, and end with `建议沉淀`, `谨慎沉淀`, or `暂不沉淀`.

Record pre-write approval with `record-human-approval --scope run-wiki-ingest-agent`; it writes `human-approval.json` and lets `wiki-ingest-handoff` show `ready_for_agent=true`. `wiki-ingest-trigger` writes a resume package for the current Claude, Codex, or other wiki-capable agent; it does not write final pages.

After PRW or another wiki-capable agent writes final pages and `final-source-review.json`, run `record-wiki-ingest`. PRW writes `prw-record-request.json` in ask-mode automation; EPI consumes it with `record-wiki-ingest --from-prw-request`, validates live page hashes, and writes or replaces `wiki-ingest-record.json`.

If a prior completion is corrected as `premature-wiki-ingest-record`, PRW repairs pages and `final-source-review.json`; EPI writes or replaces `wiki-ingest-record.json` when the correction becomes `prw-reviewed-ready-for-epi-record`.

## Read-Only Wiki Ask

`wiki-ask --question ... --vault <vault>` is a read-only formal graph query CLI. The conversational primary entrypoint is PRW `$paper-research-wiki` route `ask_wiki`; EPI `wiki-ask` is the same-source fallback / 程序化 `--json` entry. 对话场景优先 PRW。

It retrieves from `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`, expands backlinks/outlinks/aliases/tags/co-links, labels `【Wiki 证据】`, `【综合判断】`, `【推断】`, and `【边界/不确定】`, and reports correction candidates. It does not write `log.md`, formal pages, QMD, `prw-record-request.json`, or EPI artifacts.

## Literature Wiki Contract

EPI formal deposition targets seven wiki page families: `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.

Page-family/frontmatter human-readable canonical source is PRW `plugins/PRW/rules/wiki-writing-standard.md` (canonical). This file only keeps an entry summary; full field rules live there.

Every formal page must include frontmatter fields `title`, `category`, `page_family`, `tags`, `aliases`, `sources`, `summary`, `provenance`, `base_confidence`, `lifecycle`, `lifecycle_changed`, `tier`, `created`, and `updated`. Initial lifecycle is `draft` or `review-needed`; do not mark pages `source-reviewed` or `verified` before source reread, formula/figure review, wiki-lint, and human stage review actually happen.

Quality gates require Obsidian wikilinks, source bundle paths, `provenance.extracted/inferred/ambiguous`, no `_epi/` pages in the formal graph, no forbidden formula blocks such as fenced `math`/`tex`/`latex`, derivation pages with variable definitions and derivation chains, reference pages with model/formula/experiment/limit content, and synthesis pages with a cross-paper comparison matrix.

`final-source-review.json` must still record `theory_reconstruction`, `formula_derivation`, `figure_table_evidence`, `novelty_type`, `implementability`, `reproducibility_risk`, `research_gap`, and `cost_level`. Novelty review separates author-claimed novelty from EPI-confirmed novelty.

`wiki-ingest-brief.json` is the canonical handoff. `wiki_deposition_task.json` is a deprecated compatibility artifact, still read for old handoffs but not the new required source of truth. `epi-wiki-deposition` is only a compatibility alias.
