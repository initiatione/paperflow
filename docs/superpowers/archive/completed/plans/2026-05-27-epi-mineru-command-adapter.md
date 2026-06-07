# EPI MinerU Command Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real MinerU command boundary that can parse an acquired paper PDF while preserving EPI's raw artifact contract and offline testability.

**Architecture:** Keep fixture parsing for deterministic tests and add a separate `run_mineru_command()` path. EPI prepares a one-paper MinerU work directory, invokes a configured command, imports the produced Markdown/images/manifest into `_raw/papers/<slug>/mineru/`, and records success or failure in `parse-record.json`.

**Tech Stack:** Python 3.13 standard library, existing bundled `skills/mineru-paper-parser/scripts/mineru_batch_to_md.py`, pytest.

---

## Scope

Included:

- `run_mineru_command(paper_root, command=...)` for acquired papers with `paper.pdf`.
- `EPI_MINERU_COMMAND` environment override and `--mineru-command` CLI flag.
- `parse-paper` CLI command for `_raw/papers/<slug>/paper.pdf`.
- Success record with command, exit code, batch id, stdout/stderr logs, Markdown path, TeX path, and image count.
- Failure record when the command is missing, exits nonzero, or produces no Markdown.
- Offline tests using fake local commands.

Excluded:

- Replacing the bundled MinerU precise batch script.
- Live MinerU network smoke as a required test.
- Removing fixture parse mode from `ingest-one` or `redo-parse`.

## Files

- Modify `plugins/epi/scripts/epi/run_mineru_parse.py`
- Modify `plugins/epi/scripts/epi/orchestrator.py`
- Modify `plugins/epi/docs/workflow.md`
- Modify `plugins/epi/docs/config.md`
- Modify `.env_example`
- Test `tests/epi/test_mineru_parse_adapter.py`

## Tasks

### Task 1: Red Tests

- [x] Add `test_mineru_command_imports_markdown_images_manifest_and_records_job`.
- [x] Add `test_mineru_command_failure_records_error_without_fake_markdown`.
- [x] Add `test_parse_paper_with_mineru_uses_vault_slug_boundary`.
- [x] Run `python -m pytest tests\epi\test_mineru_parse_adapter.py -v`.
- [x] Expected red failure: `ImportError` or missing `run_mineru_command`.

### Task 2: Adapter

- [x] Implement command resolution from explicit command, `EPI_MINERU_COMMAND`, or bundled script.
- [x] Copy `paper.pdf` to a per-run MinerU input folder.
- [x] Run the command with `--project-root`, `--input-dir`, `--output-dir`, and `--layout document-dir`.
- [x] Store stdout/stderr logs under `_raw/papers/<slug>/mineru-command/`.
- [x] Import the first produced Markdown into `mineru/paper.md`, optional TeX into `mineru/paper.tex`, images into `mineru/images/`, and manifest into `mineru/mineru-manifest.json`.
- [x] Write `parse-record.json` for both success and failure.

### Task 3: CLI And Docs

- [x] Add `parse-paper --slug <slug> --vault <vault> --mineru-command <command>`.
- [x] Document `EPI_MINERU_COMMAND` and the bundled precise batch script.
- [x] Keep `ingest-one` fixture behavior unchanged.

### Task 4: Verification

- [x] Run `python -m pytest tests\epi -v`.
- [x] Run plugin validation.
- [x] Run EPI quality gates.
- [x] Run `parse-paper` CLI smoke with a fake MinerU command.
