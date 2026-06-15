# Run Discovery

Use for one-off Paper Source paper search, ranking, and read-priority reporting.

## Preflight

When install state, config, MCP, or MinerU availability is unclear, run:

```powershell
python scripts\orchestrator.py doctor --plugin-root <plugin-root> --vault <vault> --json
```

If config is missing, stop and use `config-setup` before searching.

## Query Planning

Do not pass a user's raw natural-language topic directly to `paper_search_mcp` as the main discovery query. First form a transparent query plan with 5-8 short academic query variants, task terms, method families, quality signals, exclusions, and clearly separated hard/soft terms. Use the original `--query` as the human intent label and pass planned terms with repeated `--query-variant` or `--agent-query-plan-json`; use repeated `--domain-focus-term`, `hard_domain_anchors`, or `hard_constraints` only when the user/config/Research Brief has confirmed hard anchors. Topic-derived expansion terms stay in `soft_recall_terms`. Use `--year-min`, `--code-policy prefer|require`, and `--selection-policy` when the user explicitly asks for recency, public code, or a stricter/broader selection behavior.

For offline query planning and profile-derived variants:

```powershell
python skills\paper-discovery\scripts\query-planner.py --topic "<topic>" --domain auto --max-queries 8
python skills\paper-discovery\scripts\query-planner.py --topic "<review topic>" --domain auto --include-reviews --max-queries 8
```

Default `dry-run` writes `_paper_source/runs/<run-id>/query-plan.json`, records `research_mode`, runs query variants, excludes review/survey/meta candidates unless reviews are requested, applies request constraints such as `year_min` and `code_policy`, deduplicates against `_meta/reference-index.json` first, and writes/resumes `_paper_source/reviews/<review-id>/` as a provider cache. A repeated matching dry-run resumes by default and skips provider calls; use `--refresh` for a new provider search, `--no-resume` only for debugging.

Do not start with Firecrawl, generic web search, publisher search, or GitHub search for recommendations. Use them only after `dry-run`, resumed review, or user-provided DOI/arXiv/title gives a candidate identity needing targeted verification.

## Dry Run And Report

```powershell
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex,crossref,unpaywall --plugin-root <plugin-root> --vault <vault>
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex,crossref,unpaywall --plugin-root <plugin-root> --vault <vault> --json
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex,crossref,unpaywall --plugin-root <plugin-root> --vault <vault> --refresh
python scripts\orchestrator.py dry-run --query "<natural language topic>" --query-variant "\"<domain object>\" \"<task>\" \"<method>\" -review -survey" --query-variant "\"<domain object>\" \"<task>\" code -review -survey" --domain-focus-term "<domain object>" --year-min 2021 --code-policy prefer --max-results 10 --sources arxiv,semantic,openalex,crossref,unpaywall --plugin-root <plugin-root> --vault <vault> --json
python scripts\orchestrator.py dry-run --query "<natural language topic>" --agent-query-plan-json <agent-query-plan.json> --max-results 10 --sources arxiv,semantic,openalex,crossref,unpaywall --plugin-root <plugin-root> --vault <vault> --json
python scripts\orchestrator.py discover-to-handoff --query "<natural language topic>" --agent-query-plan-json <agent-query-plan.json> --max-results 20 --max-papers 10 --selection-policy balanced_high_quality --skip-existing --plugin-root <plugin-root> --vault <vault> --json
python scripts\orchestrator.py dry-run --query "<exact narrow topic>" --no-query-plan --max-results 10 --sources arxiv,semantic,openalex,crossref,unpaywall --plugin-root <plugin-root> --vault <vault>
python scripts\orchestrator.py report --run-id <run-id> --vault <vault>
python scripts\orchestrator.py report --run-id <run-id> --vault <vault> --json
```

Use `--json` when another agent/script needs the run id and artifact paths. The default source list includes `unpaywall`; if `PAPER_SEARCH_MCP_UNPAYWALL_EMAIL` / `UNPAYWALL_EMAIL` is missing, configure the provider env file before judging PDF recall. Use `--no-query-plan` only for debugging or exact narrow topics.

When `--query-variant` or `--agent-query-plan-json` is present, the script records `query_variants_source=agent_supplied` and executes those variants instead of the raw `--query` text. `--year-min` and `--code-policy` are recorded under `request_constraints`; `prefer` affects ranking while `require` rejects missing code metadata. `--selection-policy` is recorded in rank/report artifacts. Agent-plan `domain_focus_terms` are treated as soft recall for compatibility; use `hard_domain_anchors` or `hard_constraints` for hard filtering. This is the preferred path for complex Chinese/English mixed requests, code-preferred searches, and topics where domain vocabulary quality determines recall.

The public CLI command is `report`; `report_run.py` is an implementation module. Do not document or invent a separate `run-report` command unless the CLI adds one.

## Evidence Check

Before reporting success, inspect `query-plan.json`, `search-record.json`, `filter-report.json`, `discovery-diagnostics.json`, `rank.json`, `_paper_source/runs/<run-id>/report.md`, `report.json`, `run-state.json`, review `state.json`, `candidates.json`, `shortlist.json`, `fetch_plan.json`, and `coverage.json`. Track `paper_type`, `classification_confidence`, `ranking_confidence`, hard/soft query provenance, `needs_pdf`, plus per-paper `acquire_failed`, `parse_failed`, or `prepare_failed` if source-staging later ran.

`dry-run` writes `_paper_source/runs/<run-id>/` and resumable `_paper_source/reviews/<review-id>/`. It does not acquire PDFs, run MinerU, create source-staging handoffs, run reader/critic, or write final wiki pages. For long-term dedupe/backlog, inspect or refresh the wiki `_meta/reference-index.json`; do not treat review-session cache as the user's library.
