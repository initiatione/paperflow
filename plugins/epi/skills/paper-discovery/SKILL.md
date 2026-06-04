---
name: paper-discovery
description: >
  Use when the user asks to find academic papers with EPI, including "找最新论文",
  "找高质量论文", "推荐优先阅读论文", one-off search/rank dry-runs, review
  exclusion, acquisition, MinerU parsing, or default fast source-staging preparation.
---

# Academic Paper Discovery

Use for EPI discovery and reading-priority ranking. This skill routes the research mode, search, normalize/filter/classify/rank, and report steps. It may hand off to source preparation, but it must not run reader, critic, or final wiki writing unless another routed skill explicitly takes over.

For ongoing topic monitoring, "what is new since last run/date", backlog priority, breadth coverage, or systematic-review coverage, use `topic-tracking` as the outer workflow and keep this skill as the retrieval/ranking layer.

If config is missing, stop and use `config-setup`. See `docs\config.md`.

The full EPI chain stays documented in `docs\epi-linkage.md`; this skill only owns discovery and ranking.

## Rules

- Discovery is profile-driven. Do not treat `paper_search_mcp` result order as quality.
- EPI is field-agnostic. Do not hardcode robotics, AUV, AI, medicine, or any other discipline unless present in config/request.
- Derive query plan, `domain_focus_terms`, exclusions, `venue_prior`, and recommendations from `_epi\meta\epi-config.yaml` plus the current request.
- Use `research_mode`, `paper_classification`, and `ranking_rubric` as routing/explanation contracts, not as final scholarly truth.
- For chat-window results, load `references/output-format.md` and return papers in reading-priority order with title, short Chinese abstract, and quality metrics such as citations, impact factor/quartile, CiteScore, or `未核实`.
- EasyScholar enrichment is default-on in `dry-run`; inspect `easyscholar-record.json`, candidate `verified_metrics.easyscholar`, and `easyscholar_score` when explaining venue quality. Missing `EASYSCHOLAR_SECRET_KEY`, no match, timeout, or API error is a soft failure and must be reported as `未核实`, not guessed. Use `--no-easyscholar` only for a run that must avoid the external check.

## Workflow Routing

| Intent | Load |
| --- | --- |
| One-off dry-run, query planning, report existing run, or evidence check | `workflows/run-discovery.md` |
| High-quality/latest/non-review discovery that needs high recall before precision filtering | `workflows/multi-source-discovery.md` |
| Prepare PDFs, MinerU artifacts, and source-staging handoff from a ranked run | `paper-ingest/workflows/prepare-ranked.md` |
| Track deltas across prior runs, backlog, coverage gap, or library duplicates | `topic-tracking/SKILL.md` |
| Formal wiki deposition after source-staging and approval | PRW `$paper-research-wiki`; compatibility fallback `epi-paper-deposition/SKILL.md` |

## Reference Routing

Load only what is needed:

- Planning: `references/query-planner.md`
- Mode routing: `references/mode-routing.md`
- Search/rerun protocol: `references/search-protocol.md`
- Paper type taxonomy: `references/paper-type-taxonomy.md`
- Ranking rubric: `references/ranking-rubric.md`
- Source roles: `references/source-tiers.md`
- Dedup: `references/dedup-engine.md`
- Venue prior: `references/venue-prior.md`
- High-recall to precision flow: `references/two-stage-retrieval.md`
- Seed expansion: `references/citation-graph.md`
- Domain examples, not defaults: `references/domain-ontology.md`
- Quality gates: `references/quality-gate.md`
- Chat output: `references/output-format.md`
- Anti-patterns: `references/anti-patterns.md`
- Regression checks: `references/evaluation-set.md`

## Source Boundary

`dry-run` writes only `_epi/runs/<run-id>/`. `prepare-ranked` belongs to `paper-ingest` and stops at source-staging. Final Obsidian/LLM Wiki pages are written by PRW `$paper-research-wiki` or, for compatibility, through `epi-paper-deposition`; discovery never writes them.
