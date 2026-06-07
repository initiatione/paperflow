# EPI Promotion Rollback Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend EPI's unified run reporting so `promote-to-wiki` and `rollback-promotion` produce `_runs/<run-id>/report.md` and `report.json` with routed-run summaries.

**Architecture:** Reuse the existing `report_run.py` routed-run contract instead of creating a second reporting path. Keep `promote_to_wiki.py` and `rollback_promotion()` as the source of truth for promotion/rollback facts, then have the orchestrator write a run-level routed report after each command completes. The report should summarize page-set writes, state transitions, human gate decisions, and next actions without changing the existing promotion/rollback record files.

**Tech Stack:** Python 3.13 standard library, existing EPI orchestrator/report/promotion modules, pytest.

---

## Scope

Included:

- Run-level routed report generation for `promote-to-wiki`.
- Run-level routed report generation for `rollback-promotion`.
- Human-readable and machine-readable summaries of page writes/restores/removals and next actions.
- Tests covering routed report content and continuity with existing promotion records.

Excluded:

- `redo-*` and `recritic` run-level reports.
- Cross-run aggregation dashboards.
- New promotion business rules or rollback semantics.

## Report Contract

For this batch, promotion/rollback routed reports must include at least:

- `workflow_type`
- `run_id`
- `paper_states`
- `failed_papers`
- `budget_usage`
- `wiki_pages_written`
- `next_actions`
- `human_gate`

Policy for this batch:

- `paper_states` should be a one-item list keyed to the affected paper slug.
- `wiki_pages_written` for promotion must include all promoted page paths.
- `wiki_pages_written` for rollback must be empty; use `restored_paths` / `removed_paths` inside routed-only fields instead.
- `failed_papers` remains empty for successful promote/rollback runs.
- `human_gate` for promotion should reflect the approval decision already stored in `promotion-record.json`.

## Files

- Modify `D:\paper-search\plugins\epi\scripts\epi\report_run.py`
- Modify `D:\paper-search\plugins\epi\scripts\epi\orchestrator.py`
- Modify `D:\paper-search\tests\epi\test_promote_to_wiki.py`
- Create `D:\paper-search\tests\epi\test_promotion_run_report.py`

## Tasks

### Task 1: Report Builder Red Tests

- [ ] Create `tests\epi\test_promotion_run_report.py`.
- [ ] Write a failing test for a promotion routed report payload that asserts `report.json` includes `workflow_type`, `paper_states`, `wiki_pages_written`, `human_gate`, and `next_actions`.
- [ ] Write a failing test for a rollback routed report payload that asserts `report.json` includes `restored_paths`, `removed_paths`, and `next_actions`.
- [ ] Run `python -m pytest tests\epi\test_promotion_run_report.py -v`.
- [ ] Expected red failure: `write_report()` lacks promotion/rollback routed-run fields or markdown rendering.

### Task 2: Report Builder Implementation

- [ ] Extend `report_run.py` so routed-run reports can optionally render `human_gate`, `restored_paths`, and `removed_paths`.
- [ ] Keep existing dry-run and batch/ranked routed-run behavior stable.
- [ ] Re-run `tests\epi\test_promotion_run_report.py -v` to green.

### Task 3: Orchestrator Red Tests

- [ ] Extend `tests\epi\test_promote_to_wiki.py`.
- [ ] Add assertions that orchestrator-driven `promote-to-wiki` writes `_runs/<run-id>/report.md` and `report.json`.
- [ ] Add assertions that orchestrator-driven `rollback-promotion` writes `_runs/<run-id>/report.md` and `report.json`.
- [ ] Add assertions that promotion routed reports include all promoted page paths and human-gate details.
- [ ] Add assertions that rollback routed reports include restored/removed paths and no `wiki_pages_written`.
- [ ] Run `python -m pytest tests\epi\test_promote_to_wiki.py -v`.
- [ ] Expected red failure: missing routed report artifacts or missing fields.

### Task 4: Orchestrator Implementation

- [ ] Update the `promote-to-wiki` CLI path in `orchestrator.py` to allocate a routed run dir, write `run-state.json`, and emit a routed report from the promotion record.
- [ ] Update the `rollback-promotion` CLI path in `orchestrator.py` to do the same for rollback records.
- [ ] Keep existing `promotion-record.json` / `rollback-record.json` contents and command return codes stable.
- [ ] Re-run `tests\epi\test_promote_to_wiki.py -v` to green.

### Task 5: Verification

- [ ] Run `python -m pytest tests\epi\test_promotion_run_report.py tests\epi\test_promote_to_wiki.py -v`.
- [ ] Run `python -m pytest tests\epi -q --basetemp .pytest_tmp_promotion_report`.
