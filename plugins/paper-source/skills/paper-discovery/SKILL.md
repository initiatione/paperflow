---
name: paper-discovery
description: >
  Use when Paper Source / PS should discover papers: "找最新论文", "找高质量论文", discover-papers, dry-run, rank.
---

# Academic Paper Discovery

Use for Paper Source / PS discovery and reading-priority ranking: natural-language `discover-papers`, lower-level dry-run evidence, normalize/filter/classify/rank, recommendation output, and default safe auto-staging. Parse repair, reader/critic, topic monitoring, and final wiki work route elsewhere. If config is missing, stop and use `config-setup`; see `docs\config.md`. The full Paper Source chain stays documented in `docs\paper-source-linkage.md`.

## Rules

- Discovery is profile-driven; do not treat `paper_search_mcp` result order as quality.
- Paper Source is field-agnostic. Do not hardcode robotics, AUV, AI, medicine, or any discipline unless present in config/request.
- For natural-language or multilingual topics, analyze the request first, form a transparent query plan, then pass explicit query variants. Do not send the raw user phrasing to MCP as the primary search.
- Derive query plan, `hard_domain_anchors`, `soft_recall_terms`, exclusions, `venue_prior`, request constraints, selection policy, and recommendations from `_paper_source\meta\paper-source-config.yaml` plus the current request; agent-supplied variants, hard anchors, `year_min`, and `code_policy` must be recorded in `query-plan.json`.
- For complex requests, prefer `--agent-query-plan-json` or repeated `--query-variant` / `--domain-focus-term`; use `--year-min` for explicit recency windows, `--code-policy prefer|require` for public-code requests, and `--selection-policy` for ranking-to-staging behavior. Agent-plan `domain_focus_terms` are legacy soft recall unless supplied as `hard_domain_anchors` / `hard_constraints`.
- Use `research_mode`, `paper_classification`, `ranking_rubric`, and EasyScholar `未核实` states as explanation contracts.
- Before ranking or recommending, let `discover-papers` / `dry-run` deduplicate against the target vault's `_meta/reference-index.json` first, then `_paper_source\raw\*\metadata.json` as fallback. Treat wiki reference pages as the lightweight backlog.
- For ordinary natural-language discovery, prefer `discover-papers`. Use `dry-run` when the user explicitly asks for evidence/debug mode or when you need search/rank artifacts without automatic source-staging.
- Optional Grok supplemental discovery is part of the Paper Source workflow only when configured. Default to targeted mode, let Paper Source skip it when paper-search is already good enough, use `--grok-mode parallel` only for aggressive shortfall recall, and use `--no-grok-search` / `--grok-mode off` when the user wants the trusted paper-search path only.
- Do not present Grok-only results as final recommendations unless the same final recommendation set includes at least one usable paper-search candidate. Treat Grok salvage without paper-search usable candidates as evidence/diagnostics.
- For chat results, load `references/output-format.md` and report reading-priority order with short Chinese abstract, citation count, impact factor/quartile, CiteScore, or `未核实` metrics.

## Workflow Routing

- Natural-language `discover-papers`, dry-run, query planning, report existing run, or evidence check: `workflows/run-discovery.md`.
- High-quality/latest/non-review discovery with high recall before precision filtering: `workflows/multi-source-discovery.md`.
- Prepare PDFs, MinerU artifacts, and source-staging handoff from a ranked run only when the user explicitly wants source bundles or Paper Wiki needs missing source artifacts: `paper-ingest/workflows/prepare-ranked.md`. Use `discover-to-handoff` when one command should run discovery plus safe source-staging without approval or final wiki writes.
- Ongoing monitoring, deltas, backlog, or coverage: `topic-tracking/SKILL.md`.
- Formal wiki deposition after source-staging and approval: Paper Wiki `$paper-research-wiki`. Use `paper-source-paper-deposition/SKILL.md` only for retired `wiki_deposition_task.json` cleanup.

Reference map: `references/query-planner.md`, `references/mode-routing.md`, `references/paper-type-taxonomy.md`, `references/search-protocol.md`, `references/source-tiers.md`, `references/dedup-engine.md`, `references/venue-prior.md`, `references/two-stage-retrieval.md`, `references/ranking-rubric.md`, `references/quality-gate.md`, `references/output-format.md`, `references/citation-graph.md`, `references/domain-ontology.md`, `references/anti-patterns.md`, `references/evaluation-set.md`.

## Source Boundary

`discover-papers` writes a high-level run plus underlying discovery and optional auto-staging runs. It uses `dry-run` evidence internally, then selects only primary recommendations for safe source-staging by default. `dry-run` writes `_paper_source/runs/<run-id>/` plus resumable `_paper_source/reviews/<review-id>/` cache and `discovery-diagnostics.json`, but the long-lived paper backlog is the wiki `_meta/reference-index.json`. `prepare-ranked` belongs to `paper-ingest`; `discover-to-handoff` only wraps dry-run plus prepare-ranked. All discovery/staging defaults stop before approval and Paper Wiki formal pages. Final pages are written by Paper Wiki `$paper-research-wiki`; discovery never writes them.
