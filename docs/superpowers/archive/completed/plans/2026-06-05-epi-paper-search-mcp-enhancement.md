# EPI Paper Search MCP Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make EPI use `openags/paper-search-mcp` as a real multi-source retrieval layer instead of a shallow search/download wrapper.

**Architecture:** EPI keeps ownership of query planning, filtering, ranking, paper gates, source bundles, and PRW handoff. The `paper-search-mcp` adapter becomes the search/acquisition capability boundary: `search_papers` telemetry is preserved in run reports, MCP `download_with_fallback` is tried before source-native or direct URL acquisition, and successful acquisition can produce a non-authoritative `read_<source>_paper` retrieval preview sidecar. Sci-Hub remains disabled by default unless explicitly enabled through environment/config.

**Tech Stack:** Python standard library, existing EPI adapter/orchestrator/report modules, Codex plugin manifest, pytest, plugin-creator validator.

---

### Task 1: Adapter Fallback Download

**Files:**
- Modify: `plugins/epi/scripts/build/epi/paper_search_adapter.py`
- Test: `tests/epi/test_paper_search_adapter.py`

- [x] Add failing tests for MCP `download_with_fallback` success, fallback failure to source-native `download_<source>`, and default `use_scihub=False`.
- [x] Extend `download_paper_pdf()` to accept `doi`, `title`, `use_scihub`, and `scihub_base_url`.
- [x] Try MCP `download_with_fallback` first and record `mode=paper_search_mcp_fallback_download`.
- [x] Preserve the old source-native MCP and CLI download paths as compatibility fallback.

### Task 2: Acquisition Uses DOI/Title Fallback

**Files:**
- Modify: `plugins/epi/scripts/build/epi/acquire_papers.py`
- Test: `tests/epi/test_acquire_url.py`

- [x] Add a test proving acquisition passes candidate DOI/title into `download_paper_pdf()`.
- [x] Record `fallback_chain`, `doi`, `title`, `use_scihub`, and upstream mode in `acquire-record.json`.
- [x] Keep URL fallback behavior unchanged when MCP/CLI acquisition fails.

### Task 3: Source Telemetry In Reports

**Files:**
- Modify: `plugins/epi/scripts/build/epi/report_run.py`
- Modify: `plugins/epi/scripts/build/epi/orchestrator.py`
- Test: `tests/epi/test_report_run.py`
- Test: `tests/epi/test_orchestrator_dry_run.py`

- [x] Add report tests for source coverage summary.
- [x] Preserve and render per-source `source_results`, `errors`, `sources_used`, `raw_total`, and dedupe totals.
- [x] Include the summary in `report.json.discovery_context` and `report.md`.

### Task 4: Version And Docs Sync

**Files:**
- Modify: `plugins/epi/.codex-plugin/plugin.json`
- Modify: `plugins/epi/docs/config.md`
- Modify: `plugins/epi/docs/epi-linkage.md`
- Modify: `plugins/epi/docs/workflow.md`
- Modify: `plugins/epi/docs/progress.md`
- Modify: `plugins/epi/skills/paper-discovery/references/search-protocol.md`
- Modify: `plugins/epi/skills/paper-ingest/workflows/prepare-ranked.md`

- [x] Bump EPI from `0.1.4` to `0.1.5`.
- [x] Update short description and docs to state that EPI now uses MCP `download_with_fallback` with Sci-Hub disabled by default.
- [x] Keep PRW docs untouched unless EPI/PRW boundaries change.

### Task 5: Verification

**Commands:**
- `python -m pytest tests\epi\test_paper_search_adapter.py tests\epi\test_acquire_url.py tests\epi\test_report_run.py tests\epi\test_orchestrator_dry_run.py -q`
- `python -m pytest tests\epi\test_current_docs.py plugins\epi\tests\test_skill_bundle_contract.py -q`
- `python C:\Users\liuchf\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py D:\paper-search\plugins\epi`
- `git diff --check`

- [x] Run focused tests.
- [x] Run plugin validator.
- [x] Report whether installed cache refresh is still needed.

### Task 6: Retrieval Preview From MCP Read Tools

**Files:**
- Modify: `plugins/epi/scripts/build/epi/paper_search_adapter.py`
- Modify: `plugins/epi/scripts/build/epi/acquire_papers.py`
- Test: `tests/epi/test_paper_search_adapter.py`
- Test: `tests/epi/test_acquire_url.py`

- [x] Add `read_paper_preview()` with MCP `read_<source>_paper` first and CLI read fallback.
- [x] Write `paper-search-read-preview.txt` only when upstream returns meaningful text.
- [x] Record `retrieval_preview` in `acquire-record.json` as non-authoritative and `replaces_mineru=false`.
- [x] Keep preview failures soft so acquisition, MinerU parse, and source-staging can continue.

### Task 7: Version 0.1.6 Docs And Verification

**Files:**
- Modify: `plugins/epi/.codex-plugin/plugin.json`
- Modify: `plugins/epi/.mcp.json`
- Modify: `plugins/epi/docs/*.md`
- Modify: `plugins/epi/skills/paper-ingest/workflows/prepare-ranked.md`
- Modify: `plugins/epi/vendor-notices/paper-search-mcp.md`
- Test: `tests/epi/test_current_docs.py`

- [x] Bump EPI from `0.1.5` to `0.1.6`.
- [x] Document `retrieval_preview`, `paper-search-read-preview.txt`, `read_<source>_paper`, CLI read, and the non-authoritative / not replacing MinerU boundary.
- [x] Keep PRW docs untouched because the EPI/PRW responsibility boundary did not change.

### Task 8: Provider Readiness And Source Capabilities

**Files:**
- Modify: `plugins/epi/scripts/build/epi/paper_search_adapter.py`
- Modify: `plugins/epi/scripts/build/epi/doctor.py`
- Modify: `plugins/epi/scripts/build/epi/orchestrator.py`
- Modify: `plugins/epi/scripts/build/epi/report_run.py`
- Modify: `plugins/epi/.codex-plugin/plugin.json`
- Modify: `plugins/epi/.mcp.json`
- Modify: `plugins/epi/docs/*.md`
- Modify: `plugins/epi/skills/paper-discovery/references/search-protocol.md`
- Test: `tests/epi/test_doctor_cli.py`
- Test: `tests/epi/test_report_run.py`
- Test: `tests/epi/test_current_docs.py`

- [x] Add `SOURCE_CAPABILITIES` so reports can distinguish search, download, and read boundaries per source.
- [x] Add `paper_search_provider_readiness()` for Unpaywall, CORE, Semantic Scholar, Google Scholar proxy, DOAJ, and Zenodo provider env gaps.
- [x] Surface provider readiness in `doctor --json` as `paper_search_provider_readiness`.
- [x] Surface capabilities and provider readiness in `report.json.discovery_context.source_coverage` and `report.md` Source Coverage.
- [x] Bump EPI from `0.1.6` to `0.1.7` and update docs/tests so provider gaps are visible workflow contract, not hidden setup trivia.
