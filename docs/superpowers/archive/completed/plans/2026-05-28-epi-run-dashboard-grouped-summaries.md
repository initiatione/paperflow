# EPI Run Dashboard Grouped Summaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich EPI's file-based run dashboard with grouped summary sections that surface the most important recent runs without introducing a UI layer.

**Architecture:** Build directly on the current `run_index.py` aggregation pipeline. Keep the existing `index.json`, `dashboard.md`, and filtered markdown views intact, then add grouped summary structures to `index.json` plus matching grouped sections in `dashboard.md` for the latest failed runs, latest pending human-gate runs, and the latest successful run for each workflow type.

**Tech Stack:** Python 3.13 standard library, existing EPI run artifacts, pytest.

---

## Scope

Included:

- Top-level grouped summary fields in `_runs/index.json`
- New grouped sections in `_runs/dashboard.md`
- Tests for grouped content, ordering, and empty-state behavior

Excluded:

- New dashboard files
- CLI commands or interactive filters
- Cross-vault aggregation

## Grouped Summary Contract

`_runs/index.json` gains:

- `latest_failures`
- `latest_human_gate_pending`
- `latest_success_by_workflow`

Rules:

- `latest_failures`: newest-first list of failed runs
- `latest_human_gate_pending`: newest-first list of runs whose `human_gate.status` is `required` or `pending`
- `latest_success_by_workflow`: mapping from workflow type to the newest successful run of that type

`dashboard.md` gains:

- `## Recent Failures`
- `## Pending Human Gate`
- `## Latest Success By Workflow`

Each grouped section must:

- use the same compact run-line format as the existing dashboard
- preserve newest-first order where applicable
- show a simple empty-state line when no runs match

## Files

- Modify `D:\paper-search\plugins\epi\scripts\epi\run_index.py`
- Modify `D:\paper-search\tests\epi\test_run_index_dashboard.py`

## Tasks

### Task 1: Red Tests

- [ ] Extend `tests\epi\test_run_index_dashboard.py`.
- [ ] Add assertions that `index.json` includes `latest_failures`, `latest_human_gate_pending`, and `latest_success_by_workflow`.
- [ ] Add assertions that `dashboard.md` includes `## Recent Failures`, `## Pending Human Gate`, and `## Latest Success By Workflow`.
- [ ] Add assertions that grouped sections preserve newest-first or per-workflow latest semantics.
- [ ] Add empty-state assertions for at least one grouped section.
- [ ] Run `python -m pytest tests\epi\test_run_index_dashboard.py -v`.
- [ ] Expected red failure: grouped summary fields or dashboard sections missing.

### Task 2: Implementation

- [ ] Extend `run_index.py` to compute grouped summary data from normalized entries.
- [ ] Render the three new grouped sections in `dashboard.md`.
- [ ] Keep existing `summary`, `Needs Attention`, `Runs By Workflow`, `Recent Runs`, and filtered view files stable.
- [ ] Re-run `tests\epi\test_run_index_dashboard.py -v` to green.

### Task 3: Verification

- [ ] Run `python -m pytest tests\epi\test_run_index_dashboard.py -v`.
- [ ] Run `python -m pytest tests\epi -q --basetemp .pytest_tmp_run_dashboard_grouped`.
