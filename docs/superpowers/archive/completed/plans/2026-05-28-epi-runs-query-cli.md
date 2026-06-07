# EPI Runs Query CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small local `runs-query` CLI to EPI that reads `_runs/index.json` and surfaces the most useful run filters in terminal-friendly text.

**Architecture:** Reuse the existing file-based run index rather than scanning `_runs/` again in the CLI path. Add a tiny query helper in `run_index.py` plus one new `runs-query` subcommand in `orchestrator.py`. Keep the first version text-only and read-only.

**Tech Stack:** Python 3.13 standard library, existing EPI run index, pytest.

---

## Scope

Included:

- `runs-query` CLI subcommand
- File-based queries against `_runs/index.json`
- Supported filters:
  - `--failed`
  - `--human-gate`
  - `--workflow <type>`
  - `--latest-success <type>`
- Plain-text terminal output

Excluded:

- JSON output mode
- Interactive UI
- Cross-vault querying
- Mutation of any run records

## Query Contract

Behavior:

- If `_runs/index.json` is missing, refresh it from the vault first.
- With no filter flags, print recent runs newest-first.
- `--failed` prints failed runs only.
- `--human-gate` prints runs whose `human_gate.status` is `required` or `pending`.
- `--workflow <type>` filters the selected run list by workflow.
- `--latest-success <type>` prints only the newest successful run for that workflow type.
- `--limit N` caps non-`latest-success` result lists; default is 10.

## Files

- Modify `D:\paper-search\plugins\epi\scripts\epi\run_index.py`
- Modify `D:\paper-search\plugins\epi\scripts\epi\orchestrator.py`
- Create `D:\paper-search\tests\epi\test_runs_query_cli.py`

## Tasks

### Task 1: Red Tests

- [ ] Create `tests\epi\test_runs_query_cli.py`.
- [ ] Seed `_runs/*/run-state.json` + `report.json`, refresh the index, then assert `runs-query --failed` prints only failed runs.
- [ ] Assert `runs-query --human-gate` prints only pending/required human-gate runs.
- [ ] Assert `runs-query --latest-success promote-to-wiki` prints only the newest successful promotion run.
- [ ] Assert `runs-query --workflow advance-ranked` filters the recent-run listing.
- [ ] Run `python -m pytest tests\epi\test_runs_query_cli.py -v`.
- [ ] Expected red failure: missing CLI parser or missing query helper.

### Task 2: Implementation

- [ ] Add a small `load_run_index()` / `query_runs()` helper in `run_index.py`.
- [ ] Add a text renderer for query results using the same compact run-line style as the dashboard.
- [ ] Add `runs-query` to `orchestrator.py`.
- [ ] Re-run `tests\epi\test_runs_query_cli.py -v` to green.

### Task 3: Verification

- [ ] Run `python -m pytest tests\epi\test_runs_query_cli.py -v`.
- [ ] Run `python -m pytest tests\epi -q --basetemp .pytest_tmp_runs_query`.
