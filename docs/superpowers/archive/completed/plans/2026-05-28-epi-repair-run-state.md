# EPI Repair Run State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend EPI so `redo-acquire`, `redo-parse`, `redo-read`, and `recritic` write `_runs/<run-id>/run-state.json` using the same routed-run contract already used by batch and promotion/rollback flows.

**Architecture:** Keep the change narrowly scoped to repair-path CLI flows. Reuse the existing repair routed-report helper in `orchestrator.py`, and add a companion helper that writes run-state records with consistent metadata, hashes, and workflow identifiers. Do not change `redo.py` business behavior or `redo-records.jsonl` semantics.

**Tech Stack:** Python 3.13 standard library, existing EPI orchestrator/redo modules, pytest.

---

## Scope

Included:

- `_runs/<run-id>/run-state.json` for `redo-acquire`
- `_runs/<run-id>/run-state.json` for `redo-parse`
- `_runs/<run-id>/run-state.json` for `redo-read`
- `_runs/<run-id>/run-state.json` for `recritic`
- Tests covering run-state creation and key fields

Excluded:

- New redo business logic
- Cross-run run-state aggregation
- New repair outcome states beyond current routed report semantics

## Contract

For this batch, repair-path run-state must include at least:

- `stage`
- `run_id`
- `workflow_type`
- `state`
- `status`
- `paper_slug`
- `vault_path`
- `compiled_wiki_write`
- `started_at`
- `finished_at`
- `exit_status`
- `tool_versions`
- `input_artifact_hashes`
- `output_artifact_hashes`

Policy:

- `compiled_wiki_write` stays `false`.
- `status` stays `success` for current successful repair CLI tests.
- `state` should reflect the routed report paper state:
  - `reacquired`
  - `reparsed`
  - `reader_regenerated`
  - `critic_passed` or `critic_failed`

## Files

- Modify `D:\paper-search\plugins\epi\scripts\epi\orchestrator.py`
- Modify `D:\paper-search\tests\epi\test_redo_recritic.py`

## Tasks

### Task 1: Red Tests

- [ ] Extend `tests\epi\test_redo_recritic.py`.
- [ ] Add assertions that each repair-path CLI writes `_runs/<run-id>/run-state.json`.
- [ ] Assert `run-state.json` contains the correct `workflow_type`, `paper_slug`, `state`, `compiled_wiki_write`, and report hash outputs.
- [ ] Run `python -m pytest tests\epi\test_redo_recritic.py -v`.
- [ ] Expected red failure: missing `run-state.json` for repair-path CLI runs.

### Task 2: Implementation

- [ ] Add a repair-path run-state helper in `orchestrator.py`.
- [ ] Reuse the existing repair report contract so `state` stays aligned with routed reports.
- [ ] Write input hashes from the relevant repair event source and output hashes for `report.md`, `report.json`, and the repair event source where appropriate.
- [ ] Re-run `tests\epi\test_redo_recritic.py -v` to green.

### Task 3: Verification

- [ ] Run `python -m pytest tests\epi\test_redo_recritic.py -v`.
- [ ] Run `python -m pytest tests\epi -q --basetemp .pytest_tmp_repair_run_state`.
