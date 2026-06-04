---
name: paper-discovery
description: "Use when discovering high-quality EPI papers via one-off search/rank dry-runs, review exclusion, acquisition, MinerU parsing, or default fast source-staging preparation."
---

# Academic Paper Discovery

Use for EPI discovery and the default fast path: route the research mode, search, normalize/filter/classify/rank, acquire, MinerU parse, then prepare a source-first candidate report and wiki-ingest handoff. Do not run reader or critic unless the user asks for reviewed/audited ingest or the source bundle has quality problems.

The full EPI chain stays documented in `docs\epi-linkage.md`. Detailed discovery policy lives in `references/`.

For ongoing topic monitoring, "what is new since last run/date", backlog priority, breadth coverage, or systematic-review coverage, use `topic-tracking` as the outer workflow and this skill only as the retrieval/ranking layer.

## Rules

- Discovery is profile-driven. Do not treat `paper_search_mcp` result order as quality.
- EPI is field-agnostic. Do not hardcode robotics, AUV, AI, medicine, or any other discipline unless present in config/request.
- Derive query plan, `domain_focus_terms`, exclusions, `venue_prior`, and recommendations from `_epi\meta\epi-config.yaml` plus the current request.
- Use `research_mode`, `paper_classification`, and `ranking_rubric` as routing/explanation contracts, not as final scholarly truth.
- For chat-window results, load `references/output-format.md` and return papers in reading-priority order with title, short Chinese abstract, and quality metrics such as citations, impact factor/quartile, CiteScore, or `未核实`.
- If config is missing, stop and use `config-setup`. See `docs\config.md`.
- EasyScholar enrichment is default-on in `dry-run`; inspect `easyscholar-record.json`, candidate `verified_metrics.easyscholar`, and `easyscholar_score` when explaining venue quality. Missing `EASYSCHOLAR_SECRET_KEY`, no match, timeout, or API error is a soft failure and must be reported as `未核实`, not guessed. Use `--no-easyscholar` only for a run that must avoid the external check.

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

`prepare-ranked` writes source artifacts plus source-staging handoff and stops before final wiki writing. Default mode is `fast-ingest`; use `--mode reviewed-ingest` only when reader navigation is needed, and `--mode audited-ingest` only for key/reproducibility/contradiction/review cases.

```powershell
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault> --json
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 1 --vault <vault>
```

Use `--max-papers 10 --skip-existing` for real runs; `--max-papers 1` is a smoke test. Use `--json` for automation and expect `stops_after=source-staging`. `review-candidate` means lower ranking confidence, not necessarily review/survey.

## Evidence Check

Before reporting success, inspect `search-record.json`, `rank.json`, `_epi\runs\<run-id>\report.md`, `_epi\runs\<run-id>\report.json`, `acquire-record.json`, `parse-record.json`, `paper.pdf`, `mineru\<slug>.md`, `mineru\paper.tex`, `mineru\images`, `mineru\mineru-manifest.json`, `_epi\staging\papers\<slug>\wiki-ingest-brief.json`, and `_epi\staging\papers\<slug>\briefs\reading-report.md`. Track `paper_type`, `classification_confidence`, `ranking_confidence`, and per-paper `acquire_failed`, `parse_failed`, or `prepare_failed`.

Safety: `dry-run` writes only `_epi/runs/<run-id>/`; default `prepare-ranked` writes `_epi\raw\papers\<slug>\...` plus lightweight `_epi\staging\papers\<slug>\...` source-staging handoff files. It does not run reader, critic, or final wiki writing in `fast-ingest`.
