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

Acquisition order is OA-first:

1. Try paper-search MCP `download_with_fallback` using source id, DOI, and title.
2. Keep Sci-Hub disabled by default. Only include it when the user explicitly sets `EPI_PAPER_SEARCH_MCP_USE_SCIHUB=1`; `EPI_PAPER_SEARCH_MCP_SCIHUB_BASE_URL` only changes the configured base URL.
3. If there is no direct candidate PDF URL and OA fallback produces no PDF, stop with `failure_class=manual-download-required` and write `manual_download` instead of trying weak source-native/CLI/direct fallbacks.
4. If the candidate has direct PDF URLs, and the fallback tool fails or produces no PDF, try source-native MCP `download_<source>`.
5. If MCP cannot produce a usable PDF, fall back to CLI/direct URL behavior and keep the same failure recording rules.
6. After any PDF download, require the lightweight DOI/title identity check. If it writes `failure_class=identity-mismatch`, keep `identity-check.json`, use `_epi/quarantine/papers/<slug>/paper.pdf` for inspection, and do not run MinerU.

Successful MCP fallback acquisition writes `fallback_chain`, `use_scihub=false` by default, `doi`, `title`, `mcp_server_probe`, `upstream.tool`, and `identity_check` into `acquire-record.json`. Treat those fields as acquisition provenance, not as proof that the paper itself was read.

After acquire success, EPI may call MCP `read_<source>_paper` or CLI read and write `paper-search-read-preview.txt`. The matching `acquire-record.json.retrieval_preview` is a non-authoritative retrieval preview sidecar for checking upstream text extraction depth; it is not replacing MinerU, and final wiki ingest must still use `paper.pdf` plus MinerU Markdown/TeX/images/manifest.

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

Failed `acquire-record.json` includes `candidate_pdf_urls`, `acquire_attempts`, `failure_class`, `retryable`, and `recovery_hint`; use those fields to decide retry, source switch, or skip. If `failure_class=manual-download-required`, also use `manual_download.doi_url`, `manual_download.candidate_manual_urls`, report-level `manual_downloads`, or `runs-query --json` to tell the user the DOI/publisher links immediately, ask them to download through their organization/institution, and avoid exhaustive fallback attempts.

`manual_download` includes `preferred_next_step`, `tmp_manual_pdf_dir`, and `candidate_manual_urls`. The preferred recovery is a user-supplied local PDF under `_epi/tmp-manual-pdfs` or a direct open-access PDF URL; do not suggest Sci-Hub unless the user has explicitly opted in.

`failure_class=identity-mismatch` means the downloaded PDF was a real PDF but did not match the candidate DOI/title. Do not parse it. Use `identity-check.json` and `_epi/quarantine/papers/<slug>/paper.pdf` for debugging, then reacquire from a corrected DOI/publisher/OA PDF link.

`failure_class=not-pdf` means the candidate URL returned a DOI/publisher landing page, HTML, or another non-PDF payload. EPI will try landing page recovery by reading `citation_pdf_url` or an obvious publisher PDF link, and merged candidates can provide multiple `candidate_pdf_urls` fallback attempts; if those still fail, switch to a direct PDF, arXiv, Unpaywall, or open-access source before rerunning acquisition.

Failed acquire attempts that never downloaded `paper.pdf` are not library entries. `prepare-ranked` cleans those `_epi/raw/<slug>` folders only when there is no source PDF, staging plan, wiki-ingest record, or Zotero record, and records the cleanup manifest under `_epi/meta/raw-cleanup/`. Parse failures with `paper.pdf` present stay in raw for retry or manual repair.

For slow MinerU jobs, pass `--mineru-timeout <seconds>` or set `EPI_MINERU_TIMEOUT`. Complete parse reuse requires `parse-record.json status=success`, not just a Markdown file.

After MinerU parse success, EPI writes `_epi/raw/<slug>/evidence-index.json` and refreshes `_epi/meta/evidence-index.json`. Treat `evidence-index.json` as a full-text page/section/chunk locator for later claim support and wiki provenance; it is generated from MinerU Markdown and does not replace `paper.pdf`, `mineru/<slug>.md`, `mineru/paper.tex`, `mineru/images/*`, or `mineru/mineru-manifest.json`.

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

- `evidence-index.json`
- `_epi/meta/evidence-index.json`
- `paper-search-read-preview.txt`
- `reader/evidence-map.json`
- `reader/claim-support.json`
- `reader/figures.md`
- `critic/*.json`

If the handoff lacks source artifacts, formula/figure review cues, parse uncertainty, source provenance, or `final-source-review.json` requirements, repair staging or rerun the relevant EPI step before final wiki writing.
