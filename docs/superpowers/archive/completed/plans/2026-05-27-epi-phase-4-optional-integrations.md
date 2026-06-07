# EPI Phase 4 Optional Integrations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe optional-integration scaffolding for Zotero, feedback capture, and skill-aware evolution without requiring external services or self-modifying plugin code.

**Architecture:** Keep optional integrations as explicit, auditable local records. Zotero writes are skipped unless enabled and still represented by `zotero-record.json`; feedback writes append-only JSONL records; evolution proposes controlled asset changes and requires a human-approved activation command.

**Tech Stack:** Python 3.13 standard library, existing EPI vault layout, pytest.

---

## Scope

Included:

- Explicit Zotero disabled/enabled record behavior.
- Feedback JSONL capture for recommendations, paper decisions, reader corrections, wiki corrections, and Plugin Eval findings.
- Skill-aware evolution proposal files under `_evolution/proposals`.
- Activation records under `_evolution/active` only when the caller passes approval.

Excluded:

- Real Zotero Desktop API writes.
- Automatic code edits.
- Automatic activation without human approval.
- Multi-agent critics.

## Files

- Create `plugins/epi/scripts/epi/zotero_sync.py`
- Create `plugins/epi/scripts/epi/feedback.py`
- Create `plugins/epi/scripts/epi/skill_aware_evolve.py`
- Modify `plugins/epi/scripts/epi/orchestrator.py`
- Create `plugins/epi/skills/zotero-sync/SKILL.md`
- Create `plugins/epi/skills/skill-aware-evolve/SKILL.md`
- Modify `plugins/epi/docs/workflow.md`
- Test `tests/epi/test_optional_integrations.py`

## Tasks

### Task 1: Red Tests

- [ ] Add tests for Zotero disabled records, feedback append, evolution proposal, activation approval gate.
- [ ] Run `python -m pytest tests\epi\test_optional_integrations.py -v`.
- [ ] Expected red failure: missing optional integration modules.

### Task 2: Implement Local Records

- [ ] Implement `sync_zotero_record()` with disabled/fixture-enabled modes.
- [ ] Implement `record_feedback()`.
- [ ] Implement `propose_evolution()` and `activate_evolution()`.

### Task 3: CLI And Skills

- [ ] Add `zotero-sync`, `record-feedback`, `propose-evolution`, and `activate-evolution` commands.
- [ ] Add skill docs and workflow docs.

### Task 4: Verification

- [ ] Run `python -m pytest tests\epi -v`.
- [ ] Run plugin validation and EPI metric pack.
- [ ] Confirm no code files are modified by evolution activation.
