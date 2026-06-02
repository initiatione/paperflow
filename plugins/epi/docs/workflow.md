# EPI Workflow

Use `doctor --json` when install, dependency, or vault state is unclear.

中文总览入口见 `docs\overview.zh.md`；中文主链路和维护契约见 `docs\epi-linkage.md`。每次修改或优化 EPI 插件，都必须检查并同步更新这些文档。

本机依赖由 `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json` 自动加载：优先 paper-search MCP server，CLI 作为 fallback，MinerU token 从环境或 `mineru.env` 读取。MinerU 子进程默认超时 7200 秒，可用 `--mineru-timeout <seconds>` 或 `EPI_MINERU_TIMEOUT` 覆盖。不要把 token 写入 runtime.json，也不要在报告里打印 token 值。

EPI 是通用论文插件，不默认任何学科方向。`dry-run` 会从 `<vault>\_epi\meta\epi-config.yaml` 的 profile、domains、positive/negative keywords、venue prior 和当前请求生成 `query-plan.json`，记录 `research_mode`，再按 query variants 调用 MCP/CLI 搜索、去重、过滤、分类和排序。Query plan 的扩展词用于扩大召回；ranking 的画像匹配词只来自用户 config 和当前请求核心词，避免宽召回词稀释窄主题相关性。`rank.json` 会暴露 `paper_type`、`paper_classification`、`quality_gate`、`quality_tier`、`ranking_rubric` 和 `ranking_confidence`，用于解释阅读优先级，不替代源论文阅读。AUV、机器人、医学等只能来自用户配置、当前请求或显式领域 hint。

持续方向跟踪使用 `topic-tracking` skill 作为外层：先比较 prior runs、`_epi/raw/papers` 和 `already_in_library` 去重信号，再报告 net-new、backlog、coverage gap、parse fidelity 和 acquisition fallback。`paper-discovery` 仍是单轮检索/排序层。

```powershell
python scripts\orchestrator.py dry-run --query "<your topic>" --max-results 20 --vault <vault>
python scripts\orchestrator.py dry-run --query "<your topic>" --max-results 20 --vault <vault> --json
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
python scripts\orchestrator.py zotero-sync --paper-root <vault>\_epi\raw\papers\<paper-slug> --collection EPI --enabled
```

Dry-run writes only `_epi/runs`; `--json` prints the run id and key artifact paths for agent/tool chaining. The workflow image's Report step maps to `report --run-id <run-id>`: it reads existing `_epi/runs/<run-id>/report.md`, `report.json`, and `run-state.json`, then prints Markdown or a JSON envelope containing `report`, `run_state`, `markdown`, and artifact paths without rerunning discovery, ingest, MinerU, staging, Zotero, or wiki writes. The implementation module is `report_run.py`, but the public CLI surface is `report`; do not document a separate `run-report` command unless the CLI adds one. `prepare-ranked` is the precise search -> acquire -> MinerU raw-parse path and stops before reader/critic/staging; use `--max-papers 10 --skip-existing` for real batches and `--max-papers 1` only for smoke tests. `prepare-ranked --json` prints the prepared run id, source run id, processed/skipped counts, stop point, and key report paths for automation. Failed `acquire-record.json` includes `failure_class`, `retryable`, and `recovery_hint`; use those fields to decide retry, source switch, or skip. Full ingest writes raw artifacts, then staging writes `_epi/staging` only after critic pass. EPI prepares evidence drafts, a lightweight report, and `wiki-ingest-brief.json`; final Obsidian/LLM Wiki pages are written by the wiki ingest agent according to the target vault contract.

Reader v2 creates role notes plus `reader/evidence-map.json` and `reader/claim-support.json`:

- `nature-sci-editor`: novelty, audience, caveat.
- `peer-reviewer`: method, benchmark, reproducibility.
- `senior-domain-researcher`: theory insight, experiment ideas, domain fit.

Critic quorum combines paper, parse, reader, editorial, peer-review, and domain-fit gates. The parse critic checks source-first companions (`mineru/<slug>.md`, `mineru/paper.tex`, `mineru/images/*`, `mineru/mineru-manifest.json`, and `parse-record.json`) instead of treating Markdown alone as enough for a source-grounded paper read. Hard failures set `outcome=revise-reader`; warnings become caveats. Staging prepares evidence drafts plus `_epi/staging/papers/<slug>/briefs/reading-report.md` as the Chinese-first human approval report and low-burden entrypoint.

```powershell
python scripts\orchestrator.py research-queue --bucket needs_reader_repair --vault <vault>
python scripts\orchestrator.py research-queue --bucket reproducibility_caveats --actions --json --vault <vault>
```

Queue buckets: `ready_to_promote`, `needs_reader_repair`, `warning_only`, `reproducibility_caveats`. `ready_to_promote --actions` must inspect current `paper-gate`; for current agent-mediated plans it suggests `wiki-ingest-handoff` and `record-human-approval` only while the remaining action is `human-approval`. Before recording approval, show one single human-readable 人工确认报告 / approval report instead of raw JSON, gate dumps, critic sidecars, or path lists. The report should be Chinese-first, use 中英对照 for key terms, keep each paper card dense but short, and end each paper with `建议沉淀`, `谨慎沉淀`, or `暂不沉淀`. Record pre-write approval with `record-human-approval --scope run-wiki-ingest-agent`; this writes `_epi/staging/papers/<slug>/human-approval.json` and changes the handoff to `ready_for_agent=true`. After approval, `ready_to_promote --actions` suggests `wiki-ingest-trigger`: it writes `_epi/staging/papers/<slug>/wiki-agent-trigger.json`, a machine-readable resume package for the current Claude, Codex, or other wiki-capable agent. EPI does not spawn a hidden background LLM process; the trigger is the continuation contract used when the user says `@EPI` again after reading the report. After the external wiki-ingest agent writes final pages under the target vault contract, create `final-source-review.json`, then run `record-wiki-ingest --page ... --approved-by ... --source-review ...` to record final page paths, hashes, source review, and approval without rewriting final pages. `record-wiki-ingest` requires the pre-write approval artifact and the same `--approved-by` value. If the vault config enables Zotero, the same completion step also writes a local `zotero-record.json` sidecar and reports it in the routed run report. Legacy compiled-draft plans may still expose `promote-to-wiki`.

Suggested draft routes may use `references/`, `concepts/`, `synthesis/`, and `reports/`, but they are non-authoritative. The target vault `AGENTS.md` and `_meta/*` decide final page paths, frontmatter, tags, links, merge policy, and staged writes. `wiki-ingest-brief.json` includes `wiki_rule_source_model`: resolve user instruction, target vault contract, personalized `liuchf/wiki-skills`, Ar9av/obsidian-wiki, kepano/obsidian-skills, then local `llm-wiki` / `wiki-ingest` / `obsidian-markdown` helper skills. The brief also carries a source-first policy: final wiki ingest must re-read `paper.pdf`, `metadata.json`, `mineru/<slug>.md`, `mineru/paper.tex`, `mineru/images/*`, and `mineru/mineru-manifest.json`; reader and critic outputs are supporting evidence, not substitutes for the source paper. `reader/claim-support.json` helps the final wiki agent distinguish extracted source claims from metadata-only and inferred notes. Use `wiki-provenance` when writing or reviewing final pages so support status and evidence-map addresses survive into the page, not only EPI sidecars. The final wiki executor may be Claude, Codex, or any other wiki-capable agent, as long as it follows the same target vault contract and source-first closure. `wiki-ingest-handoff` is read-only: it renders the current paper gate, contract-file presence, rule source priority, pre-write approval path, final-source-review contract, suggested routes, and the agent checklist for the wiki ingest step. `wiki-ingest-trigger` is the resume/dispatch artifact for the current agent after approval; it does not write final pages. `record-human-approval` records the human gate before final/staged vault writes. `record-wiki-ingest` is record-only: it rechecks `paper-gate`, requires matching pre-write approval and `approved-by`, validates `final-source-review.json`, verifies final Markdown pages stay inside the vault and outside EPI internal folders, stores hashes in `_epi/raw/papers/<slug>/wiki-ingest-record.json` and `_epi/staging/papers/<slug>/wiki-ingest-record.json`, and marks the slug as `wiki_ingest_recorded`. When Zotero is enabled in vault config, EPI also writes a local `zotero-record.json` sidecar and surfaces it in the routed report. Reading reports stay lighter than full reader output: quick take, 5-minute path, role notes, theory/experiment ideas, evidence map, claim support, suggested wiki routes, quality gate status, and compact reproducibility caveats.

## Literature Wiki Contract

EPI formal deposition now targets seven wiki page families, chosen by the final wiki agent under the target vault contract: `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`. The required skill stack is `epi-wiki-deposition`, `wiki-ingest`, `wiki-provenance`, and `tag-taxonomy`.

`final-source-review.json` must record `theory_reconstruction`, `formula_derivation`, `figure_table_evidence`, `novelty_type`, `implementability`, `reproducibility_risk`, `research_gap`, and `cost_level`. Page lifecycle is `draft -> source-reviewed -> under-review -> verified`; `verified` requires source reread, formula/figure review, complete evidence paths, and a complete final-source-review. The novelty review must separate author-claimed novelty from EPI-confirmed novelty.
