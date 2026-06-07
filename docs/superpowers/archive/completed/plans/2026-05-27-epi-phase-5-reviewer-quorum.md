# EPI Phase 5 Reviewer Quorum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first Phase 5 multi-agent-compatible critic contract without changing the trusted paper artifact boundary.

**Architecture:** Keep `run_critics()` as the public entry point and keep existing markdown critic files plus `critic-report.json`. Add reviewer records inside `critic-report.json` and a separate `critic-quorum.json` so later local, subagent, or LLM reviewers can plug into the same consensus shape.

**Tech Stack:** Python 3.13 standard library, pytest, existing EPI raw paper layout.

---

## Scope

Included:

- Local reviewer records for paper, parse, and reader critic checks.
- `critic-quorum.json` containing reviewer names, verdicts, disagreement status, and final gate outcome.
- `critic-report.json` compatibility with current `outcome`, `checks`, `hard_rule`, and `next_action` fields.
- A failing test before implementation.

Excluded:

- Real remote agents or LLM reviewer calls.
- Changing promotion gate semantics.
- Changing reader generation.

## Files

- Modify `plugins/epi/scripts/epi/run_critic.py`
- Modify `tests/epi/test_one_paper_ingest.py`
- Modify `plugins/epi/docs/workflow.md`

## Tasks

### Task 1: Red Test

- [x] Add assertions that `run_one_paper_ingest()` writes `_raw/papers/<slug>/critic/critic-quorum.json`.
- [x] Assert quorum contains three local reviewers: `paper-quality-critic`, `parse-quality-critic`, and `reader-quality-critic`.
- [x] Assert each reviewer has `scope`, `verdict`, `evidence`, and `mode: local`.
- [x] Assert `critic-report.json` includes `reviewer_quorum_path`, `reviewer_count`, and `disagreement: false` while keeping `outcome: pass`.
- [x] Run `python -m pytest tests\epi\test_one_paper_ingest.py::test_one_paper_ingest_preserves_raw_artifacts_and_stages_after_critic_pass -v` and confirm it fails because quorum fields are missing.
- [x] Add failure-path tests for a failing reader reviewer and for missing `reader/reader.md`.

### Task 2: Implementation

- [x] Refactor `run_critics()` to build reviewer records from the existing three checks.
- [x] Write `critic-quorum.json` atomically next to `critic-report.json`.
- [x] Include quorum summary fields in `critic-report.json`.
- [x] Keep existing critic markdown filenames and hard rule text unchanged.

### Task 3: Verification

- [x] Re-run the red test and confirm it passes.
- [x] Run `python -m pytest tests\epi\test_one_paper_ingest.py -v`.
- [ ] Run `python -m pytest tests\epi -v`.
- [ ] Run plugin validation and EPI quality gates.
