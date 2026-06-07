# EPI Phase 3 Redo And Recritic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit redo and recritic commands for local paper artifacts so EPI can safely recover from bad acquire, parse, reader, or critic outputs.

**Architecture:** Add a focused `redo.py` module that reuses existing acquire, MinerU fixture materialization, reader generation, and critic functions. Each redo writes an append-only `redo-records.jsonl` event under the raw paper root and never promotes compiled wiki pages. CLI commands stay in `orchestrator.py`.

**Tech Stack:** Python 3.13 standard library, existing EPI artifact helpers, pytest.

---

## Files

- Create `D:\paper-search\plugins\epi\scripts\epi\redo.py`
- Modify `D:\paper-search\plugins\epi\scripts\epi\orchestrator.py`
- Modify `D:\paper-search\plugins\epi\docs\workflow.md`
- Modify `D:\paper-search\plugins\epi\docs\recovery.md`
- Test `D:\paper-search\tests\epi\test_redo_recritic.py`

## Tasks

### Task 1: Red Tests

- [x] Add tests for `redo_acquire`, `redo_parse`, `redo_read`, and `recritic`.
- [x] Verify each redo writes `redo-records.jsonl` with `stage`, `status`, `reason`, and output paths.
- [x] Verify redo/recritic do not write compiled `references/<slug>.md`.
- [x] Run `python -m pytest tests\epi\test_redo_recritic.py -v`.
- [x] Expected red failure: missing `epi.redo`.

### Task 2: Implement Redo Module

- [x] Implement `redo_acquire(vault_path, slug, pdf_path, reason)`.
- [x] Implement `redo_parse(vault_path, slug, markdown_path, tex_path=None, images_dir=None, reason=None)`.
- [x] Implement `redo_read(vault_path, slug, reason)`.
- [x] Implement `recritic(vault_path, slug, reason)`.
- [x] Keep all writes under `_raw/papers/<slug>/`.

### Task 3: CLI And Docs

- [x] Add `redo-acquire`, `redo-parse`, `redo-read`, and `recritic` commands to `orchestrator.py`.
- [x] Update workflow and recovery docs with example commands.

### Task 4: Verification

- [ ] Run `python -m pytest tests\epi -v`.
- [ ] Run plugin manifest validation.
- [ ] Run EPI custom metric pack.
- [ ] Run Plugin Eval and record warnings.
