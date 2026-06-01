---
name: paper-discovery
description: "Use when discovering high-quality EPI papers via one-off search/rank dry-runs, review exclusion, acquisition, or MinerU steps 1-3."
---

# Academic Paper Discovery

Use for EPI discovery and the steps 1-3 path: route the research mode, search, normalize/filter/classify/rank, acquire, and MinerU parse. Stop at raw artifacts unless the user asks for reader/critic/staging/wiki handoff.

The full EPI chain stays documented in `docs\epi-linkage.md`. Detailed discovery policy lives in `references/`.

For ongoing topic monitoring, "what is new since last run/date", backlog priority, breadth coverage, or systematic-review coverage, use `topic-tracking` as the outer workflow and this skill only as the retrieval/ranking layer.

## Rules

- Discovery is profile-driven. Do not treat `paper_search_mcp` result order as quality.
- EPI is field-agnostic. Do not hardcode robotics, AUV, AI, medicine, or any other discipline unless present in config/request.
- Derive query plan, `domain_focus_terms`, exclusions, `venue_prior`, and recommendations from `_epi\meta\epi-config.yaml` plus the current request.
- Use `research_mode`, `paper_classification`, and `ranking_rubric` as routing/explanation contracts, not as final scholarly truth.
- For chat-window results, load `references/output-format.md` and return papers in reading-priority order with title, short Chinese abstract, and quality metrics such as citations, impact factor/quartile, CiteScore, or `未核实`.
- If config is missing, stop and use `config-setup`. See `docs\config.md`.

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
- Full workflow: `references/workflows/multi-source-discovery.md`
- Regression checks: `references/evaluation-set.md`

## Commands

Dependency/setup check:

```powershell
python scripts\orchestrator.py doctor --plugin-root <plugin-root> --vault <vault> --json
```

Offline query planning:

```powershell
python skills\paper-discovery\scripts\query-planner.py --topic "<topic>" --domain auto --max-queries 8
python skills\paper-discovery\scripts\query-planner.py --topic "<review topic>" --domain auto --include-reviews --max-queries 8
```

Default `dry-run` writes `_epi/runs/<run-id>/query-plan.json`, records `research_mode`, runs variants, and excludes review/survey/meta unless reviews are requested.

```powershell
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex,crossref --plugin-root <plugin-root> --vault <vault>
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex,crossref --plugin-root <plugin-root> --vault <vault> --json
```

Use the Report step to display an existing run without rerunning discovery:

```powershell
python scripts\orchestrator.py report --run-id <run-id> --vault <vault>
python scripts\orchestrator.py report --run-id <run-id> --vault <vault> --json
```

The CLI command is `report`; `report_run.py` is the internal report generator. Do not refer users to a separate `run-report` command unless the CLI adds one.

Use `--no-query-plan` only when debugging or when the profile-derived plan drifts from the narrow topic.

```powershell
python scripts\orchestrator.py dry-run --query "<exact narrow topic>" --no-query-plan --max-results 10 --sources arxiv,semantic,openalex,crossref --plugin-root <plugin-root> --vault <vault>
```

`prepare-ranked` writes raw artifacts only and stops after parse.

```powershell
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault> --json
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 1 --vault <vault>
```

Use `--max-papers 10 --skip-existing` for real runs; `--max-papers 1` is a smoke test. Use `--json` for automation. `review-candidate` means lower ranking confidence, not necessarily review/survey.

## Evidence Check

Before reporting success, inspect `search-record.json`, `rank.json`, `_epi\runs\<run-id>\report.md`, `_epi\runs\<run-id>\report.json`, `acquire-record.json`, `parse-record.json`, `paper.pdf`, `mineru\paper.md`, `mineru\paper.tex`, `mineru\images`, and `mineru\mineru-manifest.json`. Track `paper_type`, `classification_confidence`, `ranking_confidence`, and per-paper `acquire_failed`, `parse_failed`, or `prepare_failed`.

Safety: `dry-run` writes only `_epi/runs/<run-id>/`; `prepare-ranked` writes only `_epi\raw\papers\<slug>\...`; neither path enters reader, critic, staging, or wiki writing.
