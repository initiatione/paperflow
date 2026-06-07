# EPI Run Dashboard Filter Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend EPI's file-based run dashboard with a few lightweight, pre-filtered markdown views that make common operational questions faster to answer.

**Architecture:** Keep this batch entirely inside `run_index.py` and the existing dashboard tests. Reuse the normalized run entries already produced during `refresh_run_index(vault_path)`, then render three extra markdown outputs under `_runs/` without changing the primary `index.json` contract or adding CLI/UI features.

**Tech Stack:** Python 3.13 standard library, existing EPI run index module, pytest.

---

## Scope

Included:

- `_runs/dashboard-failures.md`
- `_runs/dashboard-human-gate.md`
- `_runs/dashboard-recent-success.md`
- Tests for content, ordering, and empty-state behavior

Excluded:

- Any orchestrator changes
- Interactive UI or CLI filters
- New JSON schemas beyond the existing `index.json`
- Cross-vault aggregation

## View Contracts

- `dashboard-failures.md`: all failed runs, newest first
- `dashboard-human-gate.md`: all runs with `human_gate.status` in `required` or `pending`, newest first
- `dashboard-recent-success.md`: all successful runs, newest first

Each view should:

- start with a short H1 title
- show empty-state text if there are no matching runs
- use the same compact run-line format as the main dashboard
- include one-line next action text when available

## Files

- Modify `D:\paper-search\plugins\epi\scripts\epi\run_index.py`
- Modify `D:\paper-search\tests\epi\test_run_index_dashboard.py`

## Tasks

### Task 1: Red Tests

- [ ] Extend `tests\epi\test_run_index_dashboard.py`.
- [ ] Add assertions that `refresh_run_index()` writes the three new markdown files.
- [ ] Add assertions that failures view contains only failed runs.
- [ ] Add assertions that human-gate view contains only `required`/`pending` runs.
- [ ] Add assertions that recent-success view contains only successful runs in newest-first order.
- [ ] Add empty-state assertions for at least one filtered view.
- [ ] Run `python -m pytest tests\epi\test_run_index_dashboard.py -v`.
- [ ] Expected red failure: missing filtered view outputs or incorrect content.

### Task 2: Implementation

- [ ] Add helper filtering/rendering functions in `run_index.py`.
- [ ] Reuse the existing compact run-line and next-action rendering style.
- [ ] Write the three new view files from `refresh_run_index()`.
- [ ] Keep `index.json` and `dashboard.md` behavior stable.
- [ ] Re-run `tests\epi\test_run_index_dashboard.py -v` to green.

### Task 3: Verification

- [ ] Run `python -m pytest tests\epi\test_run_index_dashboard.py -v`.
- [ ] Run `python -m pytest tests\epi -q --basetemp .pytest_tmp_run_dashboard_views`.
