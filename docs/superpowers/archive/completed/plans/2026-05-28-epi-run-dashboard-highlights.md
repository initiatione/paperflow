# EPI Run Dashboard Highlights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small highlights layer to EPI's file-based run dashboard so the most important recent runs are visible immediately at the top of the dashboard and in the aggregated JSON.

**Architecture:** Keep the change constrained to `run_index.py` and its tests. Build on the existing normalized entries and grouped summaries, then compute a small top-level `highlights` object in `_runs/index.json` plus a matching `## Highlights` section in `_runs/dashboard.md` for the latest failed run, latest human-gate-pending run, latest successful promotion, and latest successful repair.

**Tech Stack:** Python 3.13 standard library, existing EPI run artifacts, pytest.

---

## Scope

Included:

- Top-level `highlights` in `_runs/index.json`
- `## Highlights` section in `_runs/dashboard.md`
- Tests for highlight selection, rendering, and empty-state behavior

Excluded:

- New dashboard files
- Orchestrator changes
- Interactive dashboard UI

## Highlights Contract

`_runs/index.json` gains a top-level `highlights` object with these optional keys:

- `latest_failed_run`
- `latest_human_gate_pending_run`
- `latest_successful_promotion`
- `latest_successful_repair`

Rules:

- Each highlight is either one normalized run entry or `null`.
- `latest_successful_promotion` matches the newest successful `promote-to-wiki`.
- `latest_successful_repair` matches the newest successful `redo-*` or `recritic`.

`dashboard.md` gains:

- `## Highlights`

Rendering rules:

- Show one bullet per available highlight using the existing compact run-line format.
- If no highlights are available, render a short empty-state line.

## Files

- Modify `D:\paper-search\plugins\epi\scripts\epi\run_index.py`
- Modify `D:\paper-search\tests\epi\test_run_index_dashboard.py`

## Tasks

### Task 1: Red Tests

- [ ] Extend `tests\epi\test_run_index_dashboard.py`.
- [ ] Add assertions that `index.json` includes the four `highlights` keys.
- [ ] Add assertions that the newest failed run, newest pending human-gate run, newest successful promotion, and newest successful repair are selected correctly.
- [ ] Add assertions that `dashboard.md` includes `## Highlights`.
- [ ] Add empty-state assertions for the highlights section when no matches exist.
- [ ] Run `python -m pytest tests\epi\test_run_index_dashboard.py -v`.
- [ ] Expected red failure: missing highlights fields or missing dashboard section.

### Task 2: Implementation

- [ ] Extend `run_index.py` to compute top-level `highlights`.
- [ ] Render `## Highlights` in `dashboard.md` above the other sections.
- [ ] Keep current `summary`, grouped summaries, filtered views, and ordering stable.
- [ ] Re-run `tests\epi\test_run_index_dashboard.py -v` to green.

### Task 3: Verification

- [ ] Run `python -m pytest tests\epi\test_run_index_dashboard.py -v`.
- [ ] Run `python -m pytest tests\epi -q --basetemp .pytest_tmp_run_dashboard_highlights`.
