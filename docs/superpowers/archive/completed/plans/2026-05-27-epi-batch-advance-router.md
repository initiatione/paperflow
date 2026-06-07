# EPI Batch Advance Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a batch router that advances selected paper candidates by one safe stage per invocation while preserving the promotion human gate.

**Architecture:** Reuse `advance_paper_once()` for each candidate and add a thin run-level coordinator that reads candidate JSON, records a batch `run-state.json`, and stops on explicit per-paper failures without fabricating later-stage artifacts. The coordinator is intentionally sequential and idempotent so the MVP remains single-agent and crash-recoverable.

**Tech Stack:** Python 3.13 standard library, existing EPI orchestrator stage modules, pytest.

---

## Scope

Included:

- Advance up to `max_papers` candidates by one stage each.
- Skip already staged candidates at the promotion gate without writing compiled wiki pages.
- Write a run-level `_runs/<run-id>/run-state.json` and `batch-advance-record.json`.
- Provide `advance-batch --candidates <json> --vault <vault> [--max-papers N] [--mineru-command <command>]`.
- Test batch state, per-paper states, and the no compiled wiki write invariant.

Excluded:

- Automatic `promote-to-wiki`.
- Parallel execution and locking.
- Budget accounting beyond `max_papers`.
- Zotero, feedback, and evolution activation.

## Files

- Modify `D:\paper-search\plugins\epi\scripts\epi\orchestrator.py`
- Modify `D:\paper-search\plugins\epi\docs\workflow.md`
- Test `D:\paper-search\tests\epi\test_batch_advance_router.py`

## Tasks

### Task 1: Red Test

- [ ] Create `tests\epi\test_batch_advance_router.py`.
- [ ] Write `test_advance_batch_routes_candidates_once_and_records_run_state`.
- [ ] Arrange two local HTTP PDF candidates and a fake MinerU command.
- [ ] Call `advance_paper_batch(vault, candidates, mineru_command=mineru_command, max_papers=2)`.
- [ ] Assert both results have `last_action == "acquire"` and `next_action == "parse"`.
- [ ] Assert `_runs/<run-id>/run-state.json` and `batch-advance-record.json` exist.
- [ ] Assert no `references/<slug>.md` compiled page exists.
- [ ] Run `python -m pytest tests\epi\test_batch_advance_router.py -v`.
- [ ] Expected red failure: `ImportError` for missing `advance_paper_batch`.

### Task 2: Batch Coordinator

- [ ] Add `_new_run_dir(vault_path, prefix)` helper in `orchestrator.py`.
- [ ] Add `advance_paper_batch(vault_path, candidates, mineru_command=None, max_papers=None)`.
- [ ] Initialize the vault.
- [ ] Advance candidates sequentially using `advance_paper_once`.
- [ ] Stop after `max_papers` processed candidates when provided.
- [ ] Write `batch-advance-record.json` with `stage`, `status`, `processed_count`, `results`, `compiled_wiki_write: false`, and `human_gate_required` when any paper awaits promotion.
- [ ] Write run-level `run-state.json` with matching summary and `state` equal to `batch_failed`, `awaiting_promotion`, or `batch_advanced`.

### Task 3: CLI And Docs

- [ ] Add `advance-batch` CLI with `--candidates`, `--vault`, `--max-papers`, and `--mineru-command`.
- [ ] Print `run_dir`, `batch_state`, and `processed_count`.
- [ ] Return nonzero only for `batch_failed`.
- [ ] Document that `advance-batch` is one-stage-per-paper and never promotes compiled pages.

### Task 4: Verification

- [ ] Run `python -m pytest tests\epi\test_batch_advance_router.py -v`.
- [ ] Run `python -m pytest tests\epi\test_advance_paper_router.py tests\epi\test_batch_advance_router.py -v`.
- [ ] Run `python -m pytest tests\epi -v`.

### Task 5: Dry-Run Handoff

- [ ] Add `advance_paper_batch_from_run(vault_path, run_id, mineru_command=None, max_papers=None)` to load `_runs/<run-id>/rank.json`.
- [ ] Use the same `advance_paper_batch` coordinator so per-paper and run-level state contracts stay identical.
- [ ] Add `advance-ranked --run-id <run-id> --vault <vault> [--max-papers N] [--mineru-command <command>]`.
- [ ] Test that a ranked dry-run artifact can directly drive acquisition without manually copying a candidates JSON file.
- [ ] Test that missing `rank.json` fails closed with `FileNotFoundError`.
