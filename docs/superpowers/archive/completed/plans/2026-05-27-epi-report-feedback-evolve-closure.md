# EPI Report Feedback Evolve Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn EPI's post-run local loop into a usable closed chain by upgrading run reports, binding feedback to concrete run context, and allowing approved evolution proposals to apply reversible changes to whitelisted template assets.

**Architecture:** Keep this batch local-first and reversible. `report_run.py` will generate richer human and machine-readable run summaries for current dry-run and routed workflows; `feedback.py` will append feedback plus optional run linkage and maintain a per-run feedback summary; `skill_aware_evolve.py` will keep proposals staged and approval-gated, but `activate_evolution()` will now apply changes only to a small whitelist of non-code template assets with backups and rollback metadata.

**Tech Stack:** Python 3.13 standard library, existing EPI scripts, pytest.

---

## Scope

Included:

- Richer `report.md` / `report.json` structure for dry-run and later pipeline reuse.
- Feedback records linked to specific runs when provided.
- Run-level feedback summary artifact.
- White-listed evolution activation that updates selected template files.
- Reversible activation metadata and backup snapshots.

Excluded:

- Real Zotero external writes.
- Arbitrary file editing through evolution proposals.
- Plugin code rewriting via evolution activation.
- Multi-run aggregation dashboards.

## Whitelist

This batch only allows `activate_evolution()` to apply approved changes to:

- `templates/ranking.example.yaml`
- `templates/critic-checklist.example.yaml`

All other `target_asset` values remain record-only proposals and must not be applied.

## Files

- Modify `D:\paper-search\plugins\epi\scripts\epi\report_run.py`
- Modify `D:\paper-search\plugins\epi\scripts\epi\orchestrator.py`
- Modify `D:\paper-search\plugins\epi\scripts\epi\filter_candidates.py`
- Modify `D:\paper-search\plugins\epi\scripts\epi\feedback.py`
- Modify `D:\paper-search\plugins\epi\scripts\epi\skill_aware_evolve.py`
- Test `D:\paper-search\tests\epi\test_orchestrator_dry_run.py`
- Test `D:\paper-search\tests\epi\test_optional_integrations.py`
- Create `D:\paper-search\tests\epi\test_report_run.py`

## Tasks

### Task 1: Report Red Tests

- [ ] Add `tests\epi\test_report_run.py`.
- [ ] Write a failing test that asserts `report.json` contains accepted, rejected, quarantined, critic_failures, budget_usage, wiki_pages_written, zotero_results, and next_actions keys even when some are empty.
- [ ] Extend `tests\epi\test_orchestrator_dry_run.py` to assert dry-run writes richer `report.json` / `report.md` content, including budget usage and next suggested actions.
- [ ] If needed, refactor `filter_candidates.py` so dry-run can preserve rejected candidates with reasons for reporting.
- [ ] Run the targeted tests and confirm the expected red failures.

### Task 2: Report Implementation

- [ ] Update `report_run.py` to accept/report structured sections rather than only ranked papers plus errors.
- [ ] Keep current dry-run output readable while adding machine-readable keys required by the spec.
- [ ] Update `run_dry_run()` to pass budget usage, rejected candidates with reasons, and next suggested actions into the report.
- [ ] Re-run the report tests to green.

### Task 3: Feedback And Evolution Red Tests

- [ ] Extend `tests\epi\test_optional_integrations.py`.
- [ ] Write a failing test showing `record_feedback()` can bind feedback to a specific `run_id` and writes/updates a run-local feedback summary artifact.
- [ ] Write a failing test showing `activate_evolution()` applies an approved change to `templates/ranking.example.yaml`.
- [ ] Write a failing test showing `activate_evolution()` rejects or skips non-whitelisted target assets without editing files.
- [ ] Write a failing test showing activation stores backup/rollback metadata for the applied template asset.
- [ ] Run the targeted tests and confirm the expected red failures.

### Task 4: Feedback And Evolution Implementation

- [ ] Update `feedback.py` to accept optional `run_id` and maintain `_runs/<run-id>/feedback-summary.json` when present.
- [ ] Update `skill_aware_evolve.py` so approved activations can apply reversible changes to whitelisted template assets only.
- [ ] Preserve proposal-first, approval-gated semantics and keep `code_modified` false for plugin code.
- [ ] Archive the pre-activation asset snapshot and write rollback metadata into the active evolution record.
- [ ] Re-run optional integrations tests to green.

### Task 5: Verification

- [ ] Run `python -m pytest tests\epi\test_report_run.py tests\epi\test_orchestrator_dry_run.py tests\epi\test_optional_integrations.py -v`.
- [ ] Run `python -m pytest tests\epi -q --basetemp .pytest_tmp_report_feedback_evolve`.
