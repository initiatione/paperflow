# EPI Run Index Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local run index for EPI that aggregates existing `_runs/<run-id>/run-state.json` and `report.json` into `_runs/index.json` and `_runs/dashboard.md`.

**Architecture:** Keep the dashboard file-based and local-first. Add a small aggregator module that scans the `_runs` directory, normalizes run metadata, sorts runs by recency, and writes one machine-readable index plus one human-readable dashboard. Existing commands that already create `_runs/<run-id>/` outputs will call the aggregator at the end of successful execution so the dashboard stays fresh without introducing a new service or CLI dependency.

**Tech Stack:** Python 3.13 standard library, existing EPI run artifacts, pytest.

---

## Scope

Included:

- `_runs/index.json` machine-readable aggregate of run metadata.
- `_runs/dashboard.md` human-readable summary ordered by newest run first.
- Refresh hooks from existing run-producing orchestrator commands.
- Tests for aggregation, sorting, and refresh after command execution.

Excluded:

- Interactive dashboard UI.
- New CLI query commands.
- Cross-vault aggregation.
- Historical backfill beyond scanning current `_runs/*`.

## Dashboard Contract

Each index entry must include at least:

- `run_id`
- `workflow_type`
- `state`
- `status`
- `paper_slug` when applicable
- `started_at`
- `finished_at`
- `next_actions`
- `human_gate`

Dashboard rendering requirements:

- Newest runs first by `finished_at`, then `started_at`, then `run_id`.
- Show workflow type, status/state, and the key paper slug or query context.
- Show one-line next action summary when present.
- Render empty-state text when no runs exist.

## Files

- Create `D:\paper-search\plugins\epi\scripts\epi\run_index.py`
- Modify `D:\paper-search\plugins\epi\scripts\epi\orchestrator.py`
- Create `D:\paper-search\tests\epi\test_run_index_dashboard.py`
- Modify `D:\paper-search\tests\epi\test_orchestrator_dry_run.py`
- Modify `D:\paper-search\tests\epi\test_batch_advance_router.py`
- Modify `D:\paper-search\tests\epi\test_promote_to_wiki.py`
- Modify `D:\paper-search\tests\epi\test_redo_recritic.py`

## Tasks

### Task 1: Aggregator Red Tests

- [ ] Create `tests\epi\test_run_index_dashboard.py`.
- [ ] Write a failing test that seeds multiple `_runs/<run-id>/run-state.json` + `report.json` pairs and asserts `_runs/index.json` contains normalized entries sorted by recency.
- [ ] Write a failing test that asserts `_runs/dashboard.md` renders a compact summary with workflow type, state/status, paper slug/query, and next actions.
- [ ] Run `python -m pytest tests\epi\test_run_index_dashboard.py -v`.
- [ ] Expected red failure: missing `run_index.py` or missing aggregate outputs.

### Task 2: Aggregator Implementation

- [ ] Add `run_index.py` with scan, normalize, sort, and write helpers.
- [ ] Ignore non-run directories and incomplete runs gracefully.
- [ ] Re-run `tests\epi\test_run_index_dashboard.py -v` to green.

### Task 3: Command Refresh Red Tests

- [ ] Extend existing command-level tests so successful run-producing commands assert `_runs/index.json` and `_runs/dashboard.md` refresh after execution.
- [ ] Cover at least one example from each family:
  - `dry-run`
  - `advance-batch` or `advance-ranked`
  - `promote-to-wiki` or `rollback-promotion`
  - `redo-*` or `recritic`
- [ ] Run the targeted tests and confirm the expected red failures.

### Task 4: Command Refresh Implementation

- [ ] Update `orchestrator.py` so each command that creates `_runs/<run-id>/run-state.json` and report files refreshes the run index after writing its own outputs.
- [ ] Keep existing command payloads and return codes stable.
- [ ] Re-run the command-level tests to green.

### Task 5: Verification

- [ ] Run `python -m pytest tests\epi\test_run_index_dashboard.py tests\epi\test_orchestrator_dry_run.py tests\epi\test_batch_advance_router.py tests\epi\test_promote_to_wiki.py tests\epi\test_redo_recritic.py -v`.
- [ ] Run `python -m pytest tests\epi -q --basetemp .pytest_tmp_run_index`.
