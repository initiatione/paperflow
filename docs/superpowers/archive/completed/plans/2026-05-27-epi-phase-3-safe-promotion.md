# EPI Phase 3 Safe Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote staged paper drafts into compiled wiki pages only after critic approval, with backup, provenance, manifest/log updates, promotion records, and rollback.

**Architecture:** Add a small transactional promotion module that copies staged drafts into compiled wiki locations after validating critic and staging contracts. Promotion records live with the raw paper artifacts; rollback uses those records and backups to restore or remove compiled pages.

**Tech Stack:** Python 3.13 standard library, existing EPI wiki layout, pytest.

---

## Scope

Included:

- `promote-to-wiki` for staged reference drafts.
- Hard gate validation: critic outcome must be `pass`.
- Human gate validation: promotion requires explicit `approved_by` / `--approved-by`.
- Previous compiled page snapshot before overwrite.
- Previous `.manifest.json` and `log.md` snapshots before update.
- Previous `index.md` and `hot.md` snapshots before update.
- `promotion-record.json` under the raw paper directory.
- `.manifest.json` paper entry update, `index.md`/`hot.md` refresh, and `log.md` append.
- `rollback-promotion` for a promoted paper slug.

Excluded:

- Concept/synthesis merge intelligence.
- Human approval UI.
- Zotero sync.
- Concept/synthesis index intelligence beyond the promoted-paper sections.

## Files

- Create `plugins/epi/scripts/epi/promote_to_wiki.py`
- Modify `plugins/epi/scripts/epi/orchestrator.py`
- Modify `plugins/epi/docs/workflow.md`
- Test `tests/epi/test_promote_to_wiki.py`

## Tasks

### Task 1: Red Tests

- [x] Add tests for promotion success, no-critic/no-promote gate, missing human approval gate, state snapshots, and rollback.
- [x] Run `python -m pytest tests\epi\test_promote_to_wiki.py -v`.
- [x] Expected red failure: missing `approved_by` / missing human gate enforcement.

### Task 2: Promotion Module

- [x] Implement `promote_paper()` with backup and manifest/log updates.
- [x] Implement `rollback_promotion()`.
- [x] Keep writes scoped to `references/<slug>.md`, `.manifest.json`, `log.md`, and raw promotion records/backups.
- [x] Record `human_gate_decision` in `promotion-record.json`.
- [x] Snapshot `.manifest.json` and `log.md` before promotion and restore them during rollback.

### Task 2.5: Index And Hot State

- [x] Add a failing test that promotion snapshots and refreshes `index.md` and `hot.md`.
- [x] Run `python -m pytest tests\epi\test_promote_to_wiki.py::test_promotion_refreshes_index_and_hot_and_rolls_them_back -v`.
- [x] Implement managed promoted-paper sections in `index.md` and `hot.md`.
- [x] Include `index` and `hot` in `previous_state_snapshot_paths` and rollback restoration.
- [x] Re-run `python -m pytest tests\epi\test_promote_to_wiki.py -v`.

### Task 3: CLI And Docs

- [x] Add `promote-to-wiki` and `rollback-promotion` CLI commands.
- [x] Add `--approved-by` to `promote-to-wiki`.
- [x] Update workflow docs with gate and rollback examples.

### Task 4: Verification

- [ ] Run `python -m pytest tests\epi -v`.
- [ ] Run plugin validation.
- [ ] Run Plugin Eval with EPI metric pack.
- [ ] Run an ingest + promote + rollback smoke test under `D:\codex-tmp`.
