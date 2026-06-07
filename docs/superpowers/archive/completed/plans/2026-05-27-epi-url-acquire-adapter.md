# EPI URL Acquire Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let EPI acquire a selected paper from `pdf_url` into `_raw/papers/<slug>/paper.pdf` with auditable success and failure records.

**Architecture:** Keep existing local-file acquisition for fixture ingest and redo. Add `acquire_paper_from_url()` as an additive path that streams HTTP(S) PDF bytes to a temporary file, validates non-empty output, writes metadata, and writes `acquire-record.json` for both success and failure.

**Tech Stack:** Python 3.13 standard library (`urllib.request`, local pytest HTTP server), existing EPI artifact helpers.

---

## Scope

Included:

- URL acquisition from candidate `pdf_url`.
- Failure record for missing URL, HTTP errors, unavailable network, empty response, and overwrite protection.
- `acquire-paper --candidate <json> --vault <vault>` CLI.
- Offline tests using a local HTTP server.

Excluded:

- Authenticated PDF providers.
- Browser/session-based PDF download.
- Retrying or mirror selection.
- Parsing, reader generation, or promotion.

## Files

- Modify `plugins/epi/scripts/epi/acquire_papers.py`
- Modify `plugins/epi/scripts/epi/orchestrator.py`
- Modify `plugins/epi/docs/workflow.md`
- Modify `docs/superpowers/specs/2026-05-27-epi-plugin-design.md`
- Test `tests/epi/test_acquire_url.py`

## Tasks

### Task 1: Red Tests

- [x] Add local HTTP success test for `acquire_paper_from_url()`.
- [x] Add local HTTP 404 failure test that writes failed `acquire-record.json` and does not create `paper.pdf`.
- [x] Add orchestrator boundary test for `acquire_paper_from_candidate(vault, candidate)`.
- [x] Run `python -m pytest tests\epi\test_acquire_url.py -v`.
- [x] Expected red failure: missing `acquire_paper_from_url`.

### Task 2: Adapter

- [x] Implement metadata extraction helper shared by local and URL acquisition.
- [x] Implement success path with temp download and non-empty validation.
- [x] Implement failure path that records `status: failed`, `pdf_url`, and `error`.
- [x] Preserve existing `acquire_paper(candidate, pdf_path, paper_root)` behavior.

### Task 3: CLI And Docs

- [x] Add `acquire-paper --candidate <json> --vault <vault>`.
- [x] Document URL acquisition and failure behavior.

### Task 4: Verification

- [x] Run `acquire-paper` CLI smoke with a local HTTP PDF.
- [ ] Run `python -m pytest tests\epi -v`.
- [ ] Run plugin validation and EPI quality gates.
