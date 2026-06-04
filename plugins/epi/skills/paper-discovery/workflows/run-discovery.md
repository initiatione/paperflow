# Run Discovery

Use this workflow for one-off EPI paper search, ranking, and read-priority reporting.

## Preflight

Run a dependency and vault check when install state, config, MCP, or MinerU availability is unclear:

```powershell
python scripts\orchestrator.py doctor --plugin-root <plugin-root> --vault <vault> --json
```

If config is missing, stop and use `config-setup` before searching.

## Query Planning

For offline query planning or to inspect the profile-derived query variants:

```powershell
python skills\paper-discovery\scripts\query-planner.py --topic "<topic>" --domain auto --max-queries 8
python skills\paper-discovery\scripts\query-planner.py --topic "<review topic>" --domain auto --include-reviews --max-queries 8
```

Default `dry-run` writes `_epi/runs/<run-id>/query-plan.json`, records `research_mode`, runs query variants, and excludes review/survey/meta candidates unless reviews are explicitly requested.

## Dry Run

```powershell
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex,crossref --plugin-root <plugin-root> --vault <vault>
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex,crossref --plugin-root <plugin-root> --vault <vault> --json
```

Use `--json` when another agent or script needs the run id and artifact paths.

Use `--no-query-plan` only when debugging or when the profile-derived plan drifts from the narrow topic:

```powershell
python scripts\orchestrator.py dry-run --query "<exact narrow topic>" --no-query-plan --max-results 10 --sources arxiv,semantic,openalex,crossref --plugin-root <plugin-root> --vault <vault>
```

## Report Existing Run

The public CLI command is `report`; `report_run.py` is an implementation module.

```powershell
python scripts\orchestrator.py report --run-id <run-id> --vault <vault>
python scripts\orchestrator.py report --run-id <run-id> --vault <vault> --json
```

Do not document or invent a separate `run-report` command unless the CLI adds one.

## Evidence Check

Before reporting success, inspect the relevant artifacts:

- `search-record.json`
- `rank.json`
- `_epi/runs/<run-id>/report.md`
- `_epi/runs/<run-id>/report.json`
- `_epi/runs/<run-id>/run-state.json`

Track `paper_type`, `classification_confidence`, `ranking_confidence`, and per-paper `acquire_failed`, `parse_failed`, or `prepare_failed` when a later source-staging step ran.

## Safety Boundary

`dry-run` writes only `_epi/runs/<run-id>/`. It does not acquire PDFs, run MinerU, create source-staging handoffs, run reader/critic, or write final wiki pages.
