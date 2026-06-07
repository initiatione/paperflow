# EPI Advance Paper Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a resumable single-paper router that advances one selected paper by exactly one safe stage based on artifact presence.

**Architecture:** Add `advance_paper_once()` as an orchestration layer over existing stage functions. It inspects `_raw` and `_staging` artifacts, chooses one next stage, writes a paper-local `run-state.json`, and stops before compiled wiki promotion so the human gate remains explicit.

**Tech Stack:** Python 3.13 standard library, existing EPI stage modules, pytest.

---

## Scope

Included:

- Artifact-based routing for acquire, parse, read, critic, staging, and awaiting promotion.
- `advance-paper --candidate <json> --vault <vault> [--mineru-command <command>]` CLI.
- `run-state.json` under `_raw/papers/<slug>/` for the latest single-paper route decision.
- No compiled wiki writes from `advance-paper`.
- Tests with local HTTP PDF and fake MinerU command.

Excluded:

- Automatic `promote-to-wiki`.
- Multi-paper batch routing.
- Zotero, feedback, and evolution activation.
- Retrying failed stages automatically.

## Files

- Modify `plugins/epi/scripts/epi/orchestrator.py`
- Modify `plugins/epi/docs/workflow.md`
- Modify `docs/superpowers/specs/2026-05-27-epi-plugin-design.md`
- Test `tests/epi/test_advance_paper_router.py`

## Tasks

### Task 1: Red Tests

- [ ] Add a test showing repeated `advance_paper_once()` calls route through `acquire`, `parse`, `read`, `critic`, `staging`, then `awaiting-promotion`.
- [ ] Assert compiled `references/<slug>.md` is never written by the router.
- [ ] Assert `_raw/papers/<slug>/run-state.json` records last state and next action.
- [ ] Run `python -m pytest tests\epi\test_advance_paper_router.py -v`.
- [ ] Expected red failure: missing `advance_paper_once`.

### Task 2: Router

- [ ] Implement artifact inspection in `advance_paper_once()`.
- [ ] Call exactly one stage per invocation.
- [ ] Stop if acquire, parse, or critic fails.
- [ ] Write paper-local `run-state.json` after every invocation.

### Task 3: CLI And Docs

- [ ] Add `advance-paper --candidate <json> --vault <vault> --mineru-command <command>`.
- [ ] Document that the router stops before promotion and requires `promote-to-wiki --approved-by`.

### Task 4: Verification

- [ ] Run `python -m pytest tests\epi -v`.
- [ ] Run plugin validation and EPI quality gates.
