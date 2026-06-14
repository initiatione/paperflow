---
name: paper-discovery
description: >
  Use when Paper Source / PS should search papers: "找最新论文", "找高质量论文", dry-run, rank.
---

# Academic Paper Discovery

Use for Paper Source / PS discovery and reading-priority ranking: search, normalize/filter/classify/rank, and report. Parse, reader/critic, topic monitoring, and final wiki work route elsewhere. If config is missing, stop and use `config-setup`; see `docs\config.md`. The full Paper Source chain stays documented in `docs\paper-source-linkage.md`.

## Rules

- Discovery is profile-driven; do not treat `paper_search_mcp` result order as quality.
- Paper Source is field-agnostic. Do not hardcode robotics, AUV, AI, medicine, or any discipline unless present in config/request.
- For natural-language or multilingual topics, analyze the request first, compile short academic search queries, then pass them as explicit query variants. Do not send the raw user phrasing to MCP as the primary search.
- Derive query plan, `domain_focus_terms`, exclusions, `venue_prior`, request constraints, and recommendations from `_paper_source\meta\paper-source-config.yaml` plus the current request; agent-supplied variants, domain anchors, `year_min`, and `code_policy` must be recorded in `query-plan.json`.
- For complex requests, prefer `--agent-query-plan-json` or repeated `--query-variant` / `--domain-focus-term`; use `--year-min` for explicit recency windows and `--code-policy prefer|require` for public-code requests.
- Use `research_mode`, `paper_classification`, `ranking_rubric`, and EasyScholar `未核实` states as explanation contracts.
- For chat results, load `references/output-format.md` and report reading-priority order with short Chinese abstract, citation count, impact factor/quartile, CiteScore, or `未核实` metrics.

## Workflow Routing

- Dry-run, query planning, report existing run, or evidence check: `workflows/run-discovery.md`.
- High-quality/latest/non-review discovery with high recall before precision filtering: `workflows/multi-source-discovery.md`.
- Prepare PDFs, MinerU artifacts, and source-staging handoff from a ranked run: `paper-ingest/workflows/prepare-ranked.md`.
- Ongoing monitoring, deltas, backlog, or coverage: `topic-tracking/SKILL.md`.
- Formal wiki deposition after source-staging and approval: Paper Wiki `$paper-research-wiki`. Use `paper-source-paper-deposition/SKILL.md` only for retired `wiki_deposition_task.json` cleanup.

Reference map: `references/query-planner.md`, `references/mode-routing.md`, `references/paper-type-taxonomy.md`, `references/search-protocol.md`, `references/source-tiers.md`, `references/dedup-engine.md`, `references/venue-prior.md`, `references/two-stage-retrieval.md`, `references/ranking-rubric.md`, `references/quality-gate.md`, `references/output-format.md`, `references/citation-graph.md`, `references/domain-ontology.md`, `references/anti-patterns.md`, `references/evaluation-set.md`.

## Source Boundary

`dry-run` writes only `_paper_source/runs/<run-id>/`. `prepare-ranked` belongs to `paper-ingest` and stops at source-staging. Final pages are written by Paper Wiki `$paper-research-wiki`; discovery never writes them.
