# Prepare Ranked

Use this workflow after `paper-discovery` has produced a ranked dry-run and the user wants source artifacts or a source-first handoff.

## Default Fast Path

```powershell
python scripts\orchestrator.py prepare-ranked --run-id <dry-run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <dry-run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault> --json
python scripts\orchestrator.py prepare-ranked --run-id <dry-run-id> --max-papers 1 --vault <vault>
```

Use `--max-papers 10 --skip-existing` for real testing. Use `--max-papers 1` only as a smoke test. Use `--json` for the prepared run id, source run id, processed/skipped counts, `stops_after=source-staging`, and report artifact paths.

`--skip-existing` skips only papers that already have complete source artifacts and a matching source-staging `promotion-plan.json`; parsed-only papers still need staging and a report.

## Reviewed Or Audited Mode

```powershell
python scripts\orchestrator.py advance-ranked --run-id <dry-run-id> --max-papers 3 --mode reviewed-ingest --vault <vault>
python scripts\orchestrator.py advance-ranked --run-id <dry-run-id> --max-papers 3 --mode audited-ingest --vault <vault>
python scripts\orchestrator.py advance-batch --candidates <candidate-json> --max-papers 3 --mode audited-ingest --vault <vault>
```

Use `reviewed-ingest` when reader navigation is needed. Use `audited-ingest` for key, reproducibility, contradiction, explicit-review, or project-decision papers.

## Failure Handling

Inspect per-paper failures:

- `acquire_failed`
- `parse_failed`
- `prepare_failed`

Failed `acquire-record.json` includes `failure_class`, `retryable`, and `recovery_hint`; use those fields to decide retry, source switch, or skip.

For slow MinerU jobs, pass `--mineru-timeout <seconds>` or set `EPI_MINERU_TIMEOUT`. Complete parse reuse requires `parse-record.json status=success`, not just a Markdown file.

## Source-First Handoff Check

Before final wiki ingest, run:

```powershell
python scripts\orchestrator.py paper-gate --slug <slug> --vault <vault>
python scripts\orchestrator.py wiki-ingest-handoff --slug <slug> --vault <vault>
```

The handoff must require source artifacts:

- `paper.pdf`
- `metadata.json`
- `mineru/<slug>.md`
- `mineru/paper.tex`
- `mineru/images/*`
- `mineru/mineru-manifest.json`

Optional evidence aids when generated:

- `reader/evidence-map.json`
- `reader/claim-support.json`
- `reader/figures.md`
- `critic/*.json`

If the handoff lacks source artifacts, formula/figure review cues, parse uncertainty, source provenance, or `final-source-review.json` requirements, repair staging or rerun the relevant EPI step before final wiki writing.
