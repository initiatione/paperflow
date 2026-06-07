# EPI Routed Run Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add unified run-level `report.md` / `report.json` for `advance-batch` and `advance-ranked` so routed workflow runs are readable and machine-consumable like dry-run runs.

**Architecture:** Reuse the existing `report_run.py` instead of creating a second reporting system. Extend it with routed-run friendly fields, then have `advance_paper_batch()` and `advance_paper_batch_from_run()` write `_runs/<run-id>/report.md` and `report.json` from the batch result payload without changing no-compiled-write or human-gate semantics.

**Tech Stack:** Python 3.13 standard library, existing EPI orchestrator/report modules, pytest.

---

## Scope

Included:

- Run-level routed report generation for `advance-batch`.
- Run-level routed report generation for `advance-ranked`.
- Human-readable and machine-readable summaries of per-paper states and next actions.
- Tests covering routed report content and continuity with existing batch records.

Excluded:

- `advance-paper` single-paper `_runs` reports.
- Promotion / rollback / redo / recritic routed reports.
- Cross-run aggregation.

## Report Contract

For this batch, routed reports must include at least:

- `workflow_type`
- `run_id`
- `accepted`
- `rejected`
- `quarantined`
- `critic_failures`
- `paper_states`
- `failed_papers`
- `budget_usage`
- `wiki_pages_written`
- `zotero_results`
- `next_actions`

Policy for this batch:

- `accepted` is the list of processed papers whose `state` does not end with `_failed`.
- `failed_papers` is the subset whose `state` ends with `_failed`.
- `critic_failures` is the subset whose final state is `critic_failed`.
- `wiki_pages_written` remains empty for these routed report types because promotion is still manual and separate.
- `next_actions` must reflect whether the batch is waiting on parse/read/critic/staging work or on the promotion human gate.

## Files

- Modify `D:\paper-search\plugins\epi\scripts\epi\report_run.py`
- Modify `D:\paper-search\plugins\epi\scripts\epi\orchestrator.py`
- Modify `D:\paper-search\tests\epi\test_batch_advance_router.py`
- Create `D:\paper-search\tests\epi\test_routed_run_report.py`

## Tasks

### Task 1: Report Builder Red Tests

- [ ] Create `tests\epi\test_routed_run_report.py`.
- [ ] Write a failing test for a routed batch report payload that asserts `report.json` includes `workflow_type`, `paper_states`, `failed_papers`, `budget_usage`, `wiki_pages_written`, and `next_actions`.
- [ ] Assert `report.md` renders a routed-run title/summary instead of the dry-run-only shape.
- [ ] Run `python -m pytest tests\epi\test_routed_run_report.py -v`.
- [ ] Expected red failure: `write_report()` lacks routed-run support.

### Task 2: Report Builder Implementation

- [ ] Extend `report_run.py` so it can render both dry-run and routed-run reports without breaking current dry-run tests.
- [ ] Keep the existing dry-run default behavior when routed-only fields are absent.
- [ ] Add a `workflow_type` discriminator in `report.json`.
- [ ] Re-run `tests\epi\test_routed_run_report.py -v` to green.

### Task 3: Orchestrator Red Tests

- [ ] Extend `tests\epi\test_batch_advance_router.py`.
- [ ] Add assertions that `advance_paper_batch()` writes `_runs/<run-id>/report.md` and `report.json`.
- [ ] Add assertions that `advance_paper_batch_from_run()` writes routed-run reports and preserves `source_run_id`.
- [ ] Add assertions that `report.json` reflects `processed_count`, `skipped_count`, `paper_states`, and correct `next_actions`.
- [ ] Run `python -m pytest tests\epi\test_batch_advance_router.py -v`.
- [ ] Expected red failure: missing routed report artifacts or missing fields.

### Task 4: Orchestrator Implementation

- [ ] Update `advance_paper_batch()` to call the extended `write_report()` after writing batch records.
- [ ] Route `advance-ranked` through the same report path.
- [ ] Ensure report content stays consistent with existing batch record state and no-compiled-write behavior.
- [ ] Re-run `tests\epi\test_batch_advance_router.py -v` to green.

### Task 5: Verification

- [ ] Run `python -m pytest tests\epi\test_routed_run_report.py tests\epi\test_batch_advance_router.py -v`.
- [ ] Run `python -m pytest tests\epi -q --basetemp .pytest_tmp_routed_report`.
