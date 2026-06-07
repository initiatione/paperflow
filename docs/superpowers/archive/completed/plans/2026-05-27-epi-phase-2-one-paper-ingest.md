# EPI Phase 2 One-Paper Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe one-paper ingest path that preserves raw artifacts, creates source-grounded reader drafts, runs a deterministic critic gate, and writes staging drafts only after critic pass.

**Architecture:** Extend the existing `epi` Python package with focused modules for acquisition, reader generation, critic, staging, and a Phase 2 orchestrator command. Phase 2 accepts fixture/local inputs and never writes compiled wiki pages; Phase 3 will own transactional promotion.

**Tech Stack:** Python 3.13 standard library, Codex plugin skills/docs, pytest, existing EPI paper wiki layout.

---

## Scope

Included:

- One selected normalized/ranked paper candidate.
- Local/fixture PDF acquisition by copy, with `paper.pdf`, `metadata.json`, and `acquire-record.json`.
- Fixture MinerU Markdown/LaTeX/image layout materialized under `_raw/papers/<slug>/mineru/`.
- Reader files under `reader/` with explicit evidence markers.
- Critic files under `critic/` with a hard `pass` or `revise-reader` gate.
- Staging reference draft and `promotion-plan.json` only after critic pass.
- Orchestrator command `ingest-one` for local smoke tests.

Excluded:

- Live PDF downloading from arbitrary URLs.
- Live MinerU API execution.
- LLM-generated reading.
- Compiled wiki promotion.
- Zotero writes.

## File Structure

- Create `plugins/epi/scripts/epi/artifacts.py`
  - Shared path helpers and atomic JSON/text writes.
- Create `plugins/epi/scripts/epi/acquire_papers.py`
  - Copy local/fixture PDFs and write metadata/acquire records.
- Create `plugins/epi/scripts/epi/run_mineru_parse.py`
  - Materialize fixture parse outputs into the required `mineru/` layout.
- Create `plugins/epi/scripts/epi/generate_reader.py`
  - Generate deterministic source-grounded reader outputs from metadata and MinerU Markdown.
- Create `plugins/epi/scripts/epi/run_critic.py`
  - Check raw/parse/reader artifacts and emit three critic reports plus `critic-report.json`.
- Create `plugins/epi/scripts/epi/stage_wiki.py`
  - Write staging drafts only when `critic-report.json` outcome is `pass`.
- Modify `plugins/epi/scripts/epi/orchestrator.py`
  - Add `run_one_paper_ingest()` and CLI subcommand `ingest-one`.
- Create `plugins/epi/skills/paper-ingest/SKILL.md`
  - User-facing Phase 2 skill.
- Modify `plugins/epi/docs/workflow.md`
  - Document Phase 2 and the no compiled write boundary.
- Test `tests/epi/test_one_paper_ingest.py`
  - Verify artifact layout, critic gate, staging, and no compiled wiki writes.

## Tasks

### Task 1: Red Test

- [ ] Add `tests/epi/test_one_paper_ingest.py` with one passing-path test and one critic-failure gate test.
- [ ] Run `python -m pytest tests\epi\test_one_paper_ingest.py -v`.
- [ ] Expected red failure: `ModuleNotFoundError` or missing `run_one_paper_ingest`.

### Task 2: Acquire And Parse Fixtures

- [ ] Implement `artifacts.py`, `acquire_papers.py`, and `run_mineru_parse.py`.
- [ ] Run the Phase 2 test and keep failures focused on reader/critic/staging.

### Task 3: Reader, Critic, Staging

- [ ] Implement `generate_reader.py`, `run_critic.py`, and `stage_wiki.py`.
- [ ] Ensure `stage_wiki()` raises when critic outcome is not `pass`.
- [ ] Run `python -m pytest tests\epi\test_one_paper_ingest.py -v`.

### Task 4: Orchestrator And Skill

- [ ] Add `run_one_paper_ingest()` and `ingest-one` CLI.
- [ ] Add `paper-ingest` skill and workflow docs.
- [ ] Run `python -m pytest tests\epi -v`.

### Task 5: Validation

- [ ] Run plugin manifest validation.
- [ ] Run Plugin Eval with the EPI metric pack.
- [ ] Run fixture `ingest-one` smoke under `D:\codex-tmp`.
- [ ] Confirm no files are written under `references`, `concepts`, or `synthesis`.

## Self-Review

- Phase 2 requirements map to concrete modules and tests.
- Promotion is explicitly excluded and remains Phase 3.
- Tests prove the critic gate blocks staging and that successful staging stays under `_staging`.
