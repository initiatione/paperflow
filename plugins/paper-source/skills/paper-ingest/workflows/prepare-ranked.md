# Prepare Ranked

Use after `paper-discovery` produced a ranked dry-run and the user wants source artifacts or a source-first handoff.

## Commands

```powershell
python scripts\orchestrator.py prepare-ranked --run-id <dry-run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <dry-run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault> --json
python scripts\orchestrator.py discover-to-handoff --query "<topic>" --max-results 20 --max-papers 10 --selection-policy balanced_high_quality --skip-existing --vault <vault> --json
python scripts\orchestrator.py prepare-ranked --run-id <dry-run-id> --max-papers 1 --vault <vault>
python scripts\orchestrator.py advance-ranked --run-id <dry-run-id> --max-papers 3 --mode reviewed-ingest --vault <vault>
python scripts\orchestrator.py advance-ranked --run-id <dry-run-id> --max-papers 3 --mode audited-ingest --vault <vault>
python scripts\orchestrator.py advance-batch --candidates <candidate-json> --max-papers 3 --mode audited-ingest --vault <vault>
```

Use `--max-papers 10 --skip-existing` for real testing; `--max-papers 1` is a smoke test. Use `--json` to capture prepared/source run ids, processed/skipped counts, `stops_after=source-staging`, selection policy, and artifact paths. `--skip-existing` skips only papers with complete source artifacts plus matching source-staging `promotion-plan.json`; parsed-only papers still need staging and a report. Use `--selection-policy strict_advance` to keep old advance-only behavior, `balanced_high_quality` for the default high-quality review-candidate path, and `code_required` only when the user made code a hard requirement. Use `reviewed-ingest` when reader navigation is needed; use `audited-ingest` for key, reproducibility, contradiction, explicit-review, or project-decision papers. `discover-to-handoff` wraps dry-run plus prepare-ranked and writes a summary run, but it does not record approval, invoke Paper Wiki, or write final wiki pages.

## Acquisition Policy

OA-first order: paper-search MCP `download_with_fallback` with source id/DOI/title; Sci-Hub disabled unless `PAPER_SOURCE_PAPER_SEARCH_MCP_USE_SCIHUB=1`; if no direct candidate PDF URL and OA fallback yields no PDF, stop with `failure_class=manual-download-required`, write `manual_download`, and avoid weak fallbacks; if direct PDF URLs exist and fallback fails, try source-native MCP `download_<source>`, then CLI/direct URL behavior with the same failure recording; after any PDF download, run DOI/title identity check and on `failure_class=identity-mismatch` keep `identity-check.json`, quarantine `_paper_source/quarantine/papers/<slug>/paper.pdf`, and do not run MinerU.

Successful MCP acquisition records `fallback_chain`, `use_scihub=false`, DOI/title, `mcp_server_probe`, `upstream.tool`, and `identity_check` in `acquire-record.json`. Optional `read_<source>_paper`/CLI read writes `paper-search-read-preview.txt` and `acquire-record.json.retrieval_preview`; this is non-authoritative and does not replace `paper.pdf` plus MinerU Markdown/images/manifest and optional non-empty native TeX.

## Failures And Parse

Inspect `acquire_failed`, `parse_failed`, and `prepare_failed`. Failed `acquire-record.json` includes `candidate_pdf_urls`, `acquire_attempts`, `failure_class`, `retryable`, and `recovery_hint`.

- `manual-download-required`: use `manual_download.doi_url`, `manual_download.candidate_manual_urls`, report-level `manual_downloads`, or `runs-query --json`; ask the user for an institutional/local PDF under `_paper_source/tmp-manual-pdfs` or direct OA PDF URL, and do not suggest Sci-Hub unless explicitly opted in.
- `identity-mismatch`: real PDF but wrong DOI/title; do not parse. Use `identity-check.json` and quarantine PDF for debugging, then reacquire from corrected DOI/publisher/OA link.
- `not-pdf`: URL returned landing page/HTML/non-PDF; try landing-page recovery from `citation_pdf_url` or obvious publisher PDF links once, then switch to direct PDF, arXiv, Unpaywall, or OA source.

Failed acquire attempts without `paper.pdf` are not library entries; `prepare-ranked` cleans raw folders only when there is no source PDF, staging plan, wiki-ingest record, or Zotero record, and writes cleanup manifest under `_paper_source/meta/raw-cleanup/`.

For slow MinerU jobs, pass `--mineru-timeout <seconds>` or set `PAPER_SOURCE_MINERU_TIMEOUT`. Complete parse reuse requires `parse-record.json status=success`, not just a Markdown file.

After MinerU parse success, Paper Source writes `_paper_source/raw/<slug>/evidence-index.json` and refreshes `_paper_source/meta/evidence-index.json`; this supports claim provenance but does not replace `paper.pdf`, `mineru/<slug>.md`, `mineru/images/*`, `mineru/mineru-manifest.json`, figure/formula indexes, or optional non-empty native `mineru/paper.tex`.

## Source-First Handoff Check

```powershell
python scripts\orchestrator.py paper-gate --slug <slug> --vault <vault>
python scripts\orchestrator.py wiki-ingest-handoff --slug <slug> --vault <vault>
```

The handoff must include `paper.pdf`, `metadata.json`, `mineru/<slug>.md`, non-empty `mineru/paper.tex` when present, `mineru/images/*`, and `mineru/mineru-manifest.json`. Optional aids: `evidence-index.json`, `_paper_source/meta/evidence-index.json`, `paper-search-read-preview.txt`, `reader/evidence-map.json`, `reader/claim-support.json`, `reader/figures.md`, and `critic/*.json`.

If source artifacts, formula/figure review cues, parse uncertainty, source provenance, or `final-source-review.json` requirements are missing, repair staging or rerun the relevant Paper Source step before final wiki writing.
