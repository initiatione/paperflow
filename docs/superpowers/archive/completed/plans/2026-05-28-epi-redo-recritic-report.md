# EPI Redo Recritic Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend EPI's unified run reporting so `redo-acquire`, `redo-parse`, `redo-read`, and `recritic` produce `_runs/<run-id>/report.md` and `report.json` with routed-run summaries.

**Architecture:** Reuse the current `report_run.py` routed-run contract instead of creating a separate repair-report path. Keep `redo.py` as the source of truth for repair event payloads, and have the orchestrator allocate a routed run dir and emit a report after each repair-path command completes. The report should summarize the affected paper, the repair stage, key changed artifacts, critic outcomes when relevant, and suggested next actions without changing `redo-records.jsonl` semantics.

**Tech Stack:** Python 3.13 standard library, existing EPI orchestrator/report/redo modules, pytest.

---

## Scope

Included:

- Run-level routed report generation for `redo-acquire`.
- Run-level routed report generation for `redo-parse`.
- Run-level routed report generation for `redo-read`.
- Run-level routed report generation for `recritic`.
- Human-readable and machine-readable summaries of changed artifacts and next actions.

Excluded:

- New redo business logic.
- Multi-paper repair aggregation.
- Cross-run repair dashboards.
- Promotion or rollback report changes.

## Report Contract

For this batch, repair-path routed reports must include at least:

- `workflow_type`
- `run_id`
- `paper_states`
- `failed_papers`
- `budget_usage`
- `wiki_pages_written`
- `next_actions`
- `changed_artifacts`

Policy for this batch:

- `paper_states` is a one-item list for the affected paper.
- `wiki_pages_written` remains empty because repair-path commands do not write compiled wiki pages directly.
- `failed_papers` remains empty for successful redo/recritic runs.
- `changed_artifacts` is a routed-only list derived from the command record, for example:
  - `redo-acquire` -> `paper.pdf`
  - `redo-parse` -> `mineru/paper.md`, `mineru/paper.tex`
  - `redo-read` -> `reader/reader.md`, `reader/figures.md`, `reader/reproducibility.md`, `reader/implementation-ideas.md`
  - `recritic` -> `critic/critic-report.json`

## Files

- Modify `D:\paper-search\plugins\epi\scripts\epi\report_run.py`
- Modify `D:\paper-search\plugins\epi\scripts\epi\orchestrator.py`
- Modify `D:\paper-search\tests\epi\test_redo_recritic.py`
- Create `D:\paper-search\tests\epi\test_repair_run_report.py`

## Tasks

### Task 1: Report Builder Red Tests

- [ ] Create `tests\epi\test_repair_run_report.py`.
- [ ] Write failing tests for routed repair reports that assert `report.json` includes `workflow_type`, `paper_states`, `changed_artifacts`, `wiki_pages_written`, and `next_actions`.
- [ ] Cover at least one redo path and one `recritic` path in builder-level tests.
- [ ] Run `python -m pytest tests\epi\test_repair_run_report.py -v`.
- [ ] Expected red failure: `write_report()` lacks repair-path routed-only fields.

### Task 2: Report Builder Implementation

- [ ] Extend `report_run.py` so routed-run reports can optionally render and persist `changed_artifacts`.
- [ ] Keep dry-run, batch/ranked, and promotion/rollback routed reports stable.
- [ ] Re-run `tests\epi\test_repair_run_report.py -v` to green.

### Task 3: Orchestrator Red Tests

- [ ] Extend `tests\epi\test_redo_recritic.py`.
- [ ] Add CLI-level assertions that `redo-acquire`, `redo-parse`, `redo-read`, and `recritic` each create `_runs/<run-id>/report.md` and `report.json`.
- [ ] Add assertions that repair reports reflect the affected paper state, changed artifacts, and correct next actions.
- [ ] Run `python -m pytest tests\epi\test_redo_recritic.py -v`.
- [ ] Expected red failure: missing routed report artifacts or missing fields.

### Task 4: Orchestrator Implementation

- [ ] Update the CLI paths for `redo-acquire`, `redo-parse`, `redo-read`, and `recritic` in `orchestrator.py` to allocate a run dir and emit a routed report from the returned repair event.
- [ ] Keep existing `redo-records.jsonl` writes and command return codes stable.
- [ ] Re-run `tests\epi\test_redo_recritic.py -v` to green.

### Task 5: Verification

- [ ] Run `python -m pytest tests\epi\test_repair_run_report.py tests\epi\test_redo_recritic.py -v`.
- [ ] Run `python -m pytest tests\epi -q --basetemp .pytest_tmp_redo_report`.
