# Paper Source/Paper Wiki Changelog

## Unreleased

- Paper Source 2.1.1: add `auto_staging.py` and `paper-source-auto-staging-plan-v1` for automatic staging policy over `report.json.session_recommendations`. The policy selects at most 3 PDF-available primary recommendations, caps review/survey/meta-analysis papers to 1 default slot unless explicitly requested, skips `needs_pdf` papers while preserving manual-download links, and records `auto_staging_plan` plus refreshed `auto_staging_status` without creating approval, Paper Wiki trigger, final page, or record artifacts. Source-checkout change only; marketplace refresh / reinstall / installed-cache verification remain to be run separately.
- Paper Source 2.1.0: add `report.json.session_recommendations` / `paper-source-session-recommendations-v1` as the chat-facing recommendation contract. Primary recommendations are capped, exclude `review-candidate` papers, preserve Tier C/review items in a compact appendix, summarize rejected reasons, and leave semantic Chinese summaries to the calling agent from original abstract evidence. Source-checkout change only; marketplace refresh / reinstall / installed-cache verification remain to be run separately.
- Paper Source 2.0.0 (slim-down, breaking): remove dead/deprecated code. Delete the standalone `migrate_active_internal_artifacts.py` migration script, the deprecated `promote_to_wiki.py` compiled-draft path, and the legacy `epi_repository.py` import shim, together with the user-visible `promote-to-wiki` and `rollback-promotion` CLI commands. The agent-mediated `wiki-ingest-handoff` + `record-human-approval` + `wiki-ingest-trigger` + `record-wiki-ingest` flow remains the only golden path. `paper-source-repository-migrate` / `paper-source-repository-cleanup` are unaffected. Source-checkout change only; marketplace refresh / reinstall / installed-cache verification remain to be run separately.
- Paper Source 1.1.0: add transparent hard/soft query-plan provenance, `discovery-diagnostics.json`, configurable `--selection-policy`, missing-PDF readiness separation, wiki `_meta/reference-index.json` first dedupe with `already_in_wiki:<page>`, and `discover-to-handoff` as an explicit discovery -> source-staging wrapper that does not approve papers or write final wiki pages.
- Paper Source 1.0.6: switch the `paper-search-mcp` outer MCP registration to `cmd /c .\scripts\paper_search_mcp_launcher.cmd` with plugin-root `cwd: "."`, so Codex Desktop does not depend on its own `python` PATH before the launcher can load runtime.json and select the configured Python interpreter.
- Paper Source 1.0.5: fix Codex MCP self-registration for `paper-search-mcp` by using plugin-root `cwd: "."` plus `./scripts/paper_search_mcp_launcher.py` instead of an unresolved `${CLAUDE_PLUGIN_ROOT}` path, and teach `doctor --json` to flag unresolved plugin-root placeholders before they become opaque handshake failures.
- Paper Source 1.0.4: harden MinerU output ZIP retrieval. MinerU batch downloads now retry transient CDN/network failures, write `download_failed` manifest entries, and surface concrete output-download errors in `parse-record.json` instead of only reporting missing Markdown.
- Paper Source 1.0.3: add structured agent query plans and request constraints for discovery. `dry-run` accepts `--agent-query-plan-json`, `--year-min`, and `--code-policy ignore|prefer|require`; run artifacts record `request_constraints`, filter enforces recency/code requirements, and ranking/report output surfaces code and constraint evidence.
- Paper Source 1.0.2: remove built-in discipline query packs from paper discovery. The query planner and `dry-run --query-plan-domain` now accept only `auto` / `profile`; field vocabulary must come from config, Research Briefs, current user requests, or explicit agent-supplied query variants/domain focus terms.
- Paper Source 1.0.1: add agent-supplied discovery inputs. `dry-run` accepts repeated `--query-variant` and `--domain-focus-term`, records them in `query-plan.json`, and executes compiled academic queries instead of using raw natural-language topics as MCP search strings. Also tightens excluded-term matching so `surveying` is not rejected as `survey`.
- Paper Source 1.0.0 / Paper Wiki 1.0.0: current-only handoff and naming cleanup. `wiki-ingest-brief.json` is the only new Paper Source-to-Paper Wiki handoff; old aliases are not user entrypoints, route triggers, env fallbacks, or new artifact contracts.
- Paper Source 0.2.6: historical installed-cache/source-line marker retained for upgrade audits; current runtime claims must still be checked against the installed plugin cache.
- Paper Source 0.2.5 / Paper Wiki 0.2.4: enforce title-display canonical PDF Markdown links in formal-page `sources` and body source PDF entries, reject `原论文 PDF` as clickable link text, refresh active `_paper_source` sidecars, and document the installed-cache refresh boundary.
- S3b brief-first machine-contract 收敛用户黄金路径：`wiki-ingest-brief.json` 作为新链路 canonical handoff，`wiki_deposition_task.json` 只作为历史 handoff 清理对象，旧别名不再作为用户入口或路由触发条件。

## Paper Source 0.2.4 / Paper Wiki 0.2.3 (2026-06-11)

- Paper Source/Paper Wiki 合同统一为新正式页 `lifecycle: draft`，不再新增 `review_status`；旧 `lifecycle: review-needed` 只作为 legacy repair input。
- Frontmatter `sources` use title-display canonical `_paper_source/raw/<slug>/paper.pdf` Markdown PDF links; body `## 原文与证据入口` uses the same PDF URI with the paper title as clickable text. Formal wikilinks still must not point to `_paper_source/` or legacy `_epi/`.
- 公式和符号证据顺序改为 MinerU Markdown 主源；只有 Markdown 缺失、错误、歧义或不足时回退 PDF、figure/formula indexes 和图片证据，非空原生 `mineru/paper.tex` 仅作可选交叉复核。
- Paper Wiki 合同扩展为 formal page、正式内容关系、stale claim、split/merge、图谱/索引/追踪/provenance/readiness 维护层。

## 0.2.3 (2026-06-10)

- Paper Source skill trigger descriptions 再精炼：保留中文任务触发词、Paper Source/Paper Wiki 边界和 research-grill-me deep-research prompt 契约，降低默认触发上下文成本。

## 0.2.2 (2026-06-10)

- Paper Source / Paper Wiki skill 入口压缩：保留路由、来源边界、handoff gate 和 post-task check，减少默认加载成本。
- Paper Source / Paper Wiki manifest 和默认 prompt 精简为短入口，版本同步到 `0.2.2`。
- Paper Wiki 继续保持一个用户级 `$paper-research-wiki` 助手，`paper-wiki-language` 作为正式页语言 gate。

## 0.2.1 (2026-06-07)

- S3a 文档/契约 canonical 化：A1 overview 导航化。
- A2 workflow 巨段拆成短入口。
- A3 doc map 收敛到 `docs/paper-source-linkage.md`。
- A4 progress 快照化，历史迁入本文件。
- A5 page-family/frontmatter 人读 canonical 指向 Paper Wiki `rules/wiki-writing-standard.md`。
- C3 只读问答归属：Paper Wiki `ask_wiki` 是对话主入口，Paper Source `wiki-ask` 是同源 fallback / 程序化入口。
- C4 `wiki-ingest-brief.json` 是 canonical handoff；`wiki_deposition_task.json` 是 deprecated 兼容 artifact。
- D3 删除 `_write_json` 私有别名，直接调用 `write_json_atomic`。
- E1 Paper Source plugin description 改为 discovery -> MinerU -> critic -> wiki handoff 全链路定位。

## 0.2.0 (2026-06-07)

- 增加 read-only formal graph `wiki-ask`。
- Paper Wiki ask-mode record automation 写 `paper-wiki-record-request.json`。
- Paper Source `record-wiki-ingest --from-paper-wiki-request` 消费 Paper Wiki request artifact；旧 record request artifact 只属于历史迁移语境，当前用户入口不再使用旧别名。
- Source manifest 同步到 Paper Source `0.2.0` / Paper Wiki `0.2.0`。

## 0.1.14 / 0.1.7

- Paper Wiki -> Paper Source ask-mode record automation。
- `automation_mode=ask` 与 live page hash 验证。
- `final-source-review.json` 与 human approval identity 一起进入 record gate。

## 0.1.13 / 0.1.6

- Workflow boundary source version sync。
- 明确 Paper Wiki `$paper-research-wiki` 与 Paper Source `paper-source-paper-deposition` 历史 handoff 清理边界。
- 更新 formal page gate 与 record provenance 说明。

## Earlier 0.1.x Notes

- Runtime 配置进入用户级 `runtime.json`。
- `paper-search` MCP/CLI fallback、provider readiness 和 MinerU env file 分层。
- `prepare-ranked --skip-existing` 防止补跑时已解析论文占用预算。
- `paper-quality-critic`、`parse-quality-critic` 和 role critic quorum 进入 audited ingest。
- `run-lifecycle` 与 bounded lifecycle cleanup 加入默认维护边界。
- Plugin Eval 历史信号包含 pass rate `1` 和 `82/100`；这些是历史快照，发布前必须重跑。
