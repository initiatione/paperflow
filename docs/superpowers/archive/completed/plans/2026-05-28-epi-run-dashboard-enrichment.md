# EPI Run Dashboard Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich EPI's file-based run dashboard so `_runs/dashboard.md` and `_runs/index.json` provide a more useful operational overview without introducing a UI layer.

**Architecture:** Build on the existing `run_index.py` rather than introducing a new subsystem. Keep `runs` as the source list, then add a top-level summary block to `index.json` plus richer `dashboard.md` sections for run counts, items needing attention, and recent workflow distribution. Existing commands should continue to refresh the dashboard through the already-wired `refresh_run_index(vault_path)` calls.

**Tech Stack:** Python 3.13 standard library, existing EPI run artifacts, pytest.

---

## Scope

Included:

- Top-level `summary` in `_runs/index.json`.
- Richer `_runs/dashboard.md` sections:
  - Summary
  - Needs Attention
  - Runs By Workflow
  - Recent Runs
- Tests for summary counts, attention selection, and dashboard rendering.

Excluded:

- Interactive dashboard UI.
- New CLI commands.
- Historical trend graphs.
- Pagination or filtering controls.

## Summary Contract

`_runs/index.json` gains a top-level `summary` object with at least:

- `total_runs`
- `workflow_counts`
- `status_counts`
- `human_gate_pending_count`
- `failed_run_count`

Dashboard rules:

- `Needs Attention` should list runs that either:
  - have `status != "succeeded"`/`"success"`, or
  - carry a `human_gate.status` of `required` or `pending`, or
  - include a non-empty `next_actions`.
- `Runs By Workflow` should render simple counts by workflow type.
- `Recent Runs` should keep the current newest-first run list.

## Files

- Modify `D:\paper-search\plugins\epi\scripts\epi\run_index.py`
- Modify `D:\paper-search\tests\epi\test_run_index_dashboard.py`

## Tasks

### Task 1: Red Tests

- [ ] Extend `tests\epi\test_run_index_dashboard.py`.
- [ ] Add assertions that `index.json` includes `summary.total_runs`, `summary.workflow_counts`, `summary.status_counts`, `summary.human_gate_pending_count`, and `summary.failed_run_count`.
- [ ] Add assertions that `dashboard.md` contains `## Summary`, `## Needs Attention`, and `## Runs By Workflow`.
- [ ] Add assertions that pending-human-gate and failed runs appear in `Needs Attention`.
- [ ] Run `python -m pytest tests\epi\test_run_index_dashboard.py -v`.
- [ ] Expected red failure: missing summary fields or missing dashboard sections.

### Task 2: Implementation

- [ ] Update `run_index.py` to compute top-level summary statistics from normalized entries.
- [ ] Enrich dashboard markdown with the new sections while preserving newest-first recent run ordering.
- [ ] Keep broken/incomplete run directories safely ignored.
- [ ] Re-run `tests\epi\test_run_index_dashboard.py -v` to green.

### Task 3: Verification

- [ ] Run `python -m pytest tests\epi\test_run_index_dashboard.py -v`.
- [ ] Run `python -m pytest tests\epi -q --basetemp .pytest_tmp_run_dashboard_enrichment`.
