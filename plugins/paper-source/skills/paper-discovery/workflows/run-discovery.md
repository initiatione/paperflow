# Run Discovery

Use for one-off Paper Source paper search, ranking, and read-priority reporting.

## Preflight

When install state, config, MCP, or MinerU availability is unclear, run:

```powershell
python scripts\orchestrator.py doctor --plugin-root <plugin-root> --vault <vault> --json
```

If config is missing, stop and use `config-setup` before searching.

## Query Planning

For offline query planning and profile-derived variants:

```powershell
python skills\paper-discovery\scripts\query-planner.py --topic "<topic>" --domain auto --max-queries 8
python skills\paper-discovery\scripts\query-planner.py --topic "<review topic>" --domain auto --include-reviews --max-queries 8
```

Default `dry-run` writes `_paper_source/runs/<run-id>/query-plan.json`, records `research_mode`, runs query variants, excludes review/survey/meta candidates unless reviews are requested, and writes/resumes `_paper_source/reviews/<review-id>/`. A repeated matching dry-run resumes by default and skips provider calls; use `--refresh` for a new provider search, `--no-resume` only for debugging.

Do not start with Firecrawl, generic web search, publisher search, or GitHub search for recommendations. Use them only after `dry-run`, resumed review, or user-provided DOI/arXiv/title gives a candidate identity needing targeted verification.

## Dry Run And Report

```powershell
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex,crossref,unpaywall --plugin-root <plugin-root> --vault <vault>
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex,crossref,unpaywall --plugin-root <plugin-root> --vault <vault> --json
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex,crossref,unpaywall --plugin-root <plugin-root> --vault <vault> --refresh
python scripts\orchestrator.py dry-run --query "<exact narrow topic>" --no-query-plan --max-results 10 --sources arxiv,semantic,openalex,crossref,unpaywall --plugin-root <plugin-root> --vault <vault>
python scripts\orchestrator.py report --run-id <run-id> --vault <vault>
python scripts\orchestrator.py report --run-id <run-id> --vault <vault> --json
```

Use `--json` when another agent/script needs the run id and artifact paths. The default source list includes `unpaywall`; if `PAPER_SEARCH_MCP_UNPAYWALL_EMAIL` / `UNPAYWALL_EMAIL` is missing, configure the provider env file before judging PDF recall. Use `--no-query-plan` only for debugging or exact narrow topics.

The public CLI command is `report`; `report_run.py` is an implementation module. Do not document or invent a separate `run-report` command unless the CLI adds one.

## Evidence Check

Before reporting success, inspect `search-record.json`, `rank.json`, `_paper_source/runs/<run-id>/report.md`, `report.json`, `run-state.json`, review `state.json`, `candidates.json`, `shortlist.json`, `fetch_plan.json`, and `coverage.json`. Track `paper_type`, `classification_confidence`, `ranking_confidence`, plus per-paper `acquire_failed`, `parse_failed`, or `prepare_failed` if source-staging later ran.

`dry-run` writes `_paper_source/runs/<run-id>/` and resumable `_paper_source/reviews/<review-id>/`. It does not acquire PDFs, run MinerU, create source-staging handoffs, run reader/critic, or write final wiki pages.
