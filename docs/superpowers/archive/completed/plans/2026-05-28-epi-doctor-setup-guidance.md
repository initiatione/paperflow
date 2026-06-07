# EPI Doctor Setup Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-use setup guidance to EPI doctor without changing the plugin's safe offline behavior.

**Architecture:** Keep `doctor` as the single diagnostic entrypoint. Extend its report model with optional setup metadata, and let the CLI open setup pages only behind an explicit `--open-setup` flag.

**Tech Stack:** Python standard library, argparse, pytest, Codex plugin runtime files.

---

### Task 1: Doctor Setup Metadata

**Files:**
- Modify: `D:\paper-search\plugins\epi\scripts\build\epi\doctor.py`
- Test: `D:\paper-search\tests\epi\test_doctor_cli.py`

- [x] Add failing tests for text setup guidance and JSON setup metadata.
- [x] Add setup guide constants for `paper_search_cli` and `mineru_token`.
- [x] Attach `setup` only to warning checks that need user action.
- [x] Add top-level `setup_required` and `setup_links`.
- [x] Verify with `python -m pytest tests\epi\test_doctor_cli.py -q --basetemp .pytest_tmp_doctor_setup_green`.

### Task 2: Explicit Browser Opening

**Files:**
- Modify: `D:\paper-search\plugins\epi\scripts\build\epi\doctor.py`
- Modify: `D:\paper-search\plugins\epi\scripts\build\epi\cli.py`
- Test: `D:\paper-search\tests\epi\test_doctor_cli.py`

- [x] Add failing test for `doctor --open-setup --json`.
- [x] Add `open_setup_links(report)` using `webbrowser.open`.
- [x] Add `--open-setup` CLI flag.
- [x] Add `opened_setup_urls` to the JSON report only when the flag is used.
- [x] Keep default `doctor` side-effect free.

### Task 3: Documentation And Verification

**Files:**
- Modify: `D:\paper-search\README.md`
- Modify: `D:\paper-search\plugins\epi\docs\config.md`
- Modify: `D:\paper-search\plugins\epi\docs\workflow.md`
- Modify: `D:\paper-search\plugins\epi\build\docs\config.md`
- Modify: `D:\paper-search\plugins\epi\build\docs\workflow.md`

- [x] Document default setup guidance and explicit browser opening.
- [x] Run source plugin validation.
- [x] Run installed-source unit tests.
- [x] Run Plugin Eval after implementation.
