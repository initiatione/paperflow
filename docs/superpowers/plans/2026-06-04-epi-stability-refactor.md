# EPI Stability Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split EPI stability gates and oversized workflow scripts into focused modules, then make real-vault wiki deposition safer.

**Architecture:** Add focused modules for source bundle audit, formal-page language policy, graph visibility, wiki handoff contracts, CLI routes, and wiki record workflows. Keep `cli.py`, `stage_wiki.py`, and `orchestrator.py` as routers or compatibility facades where possible, then update docs/skills/version after tests pass.

**Tech Stack:** Python stdlib, pytest, Codex plugin manifest JSON, EPI Markdown skills/docs.

---

### Task 1: Source Bundle Audit

**Files:**
- Create: `plugins/paper-source/scripts/build/epi/source_bundle_audit.py`
- Modify: `plugins/paper-source/scripts/build/epi/paper_gate.py`
- Test: `tests/epi/test_source_bundle_audit.py`
- Test: `tests/epi/test_paper_gate.py`

- [ ] Add failing tests for complete and incomplete raw source bundles.
- [ ] Add failing paper-gate test that disk-missing source artifacts block agent handoff.
- [ ] Implement `audit_source_bundle(paper_root)` returning status, missing artifacts, and per-artifact records.
- [ ] Wire source bundle audit into `paper_gate.py`.
- [ ] Run focused tests for source bundle and paper gate.

### Task 2: Formal Wiki Language Gate

**Files:**
- Create: `plugins/paper-source/scripts/build/epi/wiki_language.py`
- Create: `plugins/paper-source/scripts/build/epi/wiki_handoff_contracts.py`
- Modify: `plugins/paper-source/scripts/build/epi/wiki_contracts.py`
- Modify: `plugins/paper-source/scripts/build/epi/wiki_ingest_record.py`
- Modify: `plugins/paper-source/scripts/build/epi/stage_wiki.py`
- Test: `tests/epi/test_wiki_ingest_record.py`
- Test: `tests/epi/test_wiki_deposition_task.py`

- [ ] Add failing test that English-only formal page body is rejected.
- [ ] Add failing test that `final-source-review.json` must record Chinese-default language review.
- [ ] Implement page-body language validation with CJK signal after stripping frontmatter and code fences.
- [ ] Add language-policy contract fields to final-source-review guidance.
- [ ] Move wiki rule source model, final-source-review contract, deposition paths, deposition task, and wiki-ingest brief builders out of `stage_wiki.py` into `wiki_handoff_contracts.py`.
- [ ] Add `agent_context_policy` / `worker_delegation_policy` to wiki handoff artifacts so independent subtasks use fresh-context workers and return only final artifacts.
- [ ] Leave `stage_wiki.py` as the stage coordinator that imports the builder functions.
- [ ] Update test fixtures to use Chinese-default formal page prose.
- [ ] Run focused wiki ingest record tests.

### Task 3: CLI Routing Split

**Files:**
- Create: `plugins/paper-source/scripts/build/epi/cli_routes.py`
- Modify: `plugins/paper-source/scripts/build/epi/cli.py`
- Test: `tests/epi/test_cli_parser.py`

- [ ] Move argparse subcommand registration helpers into `cli_routes.py`.
- [ ] Move handler map construction into a named router function.
- [ ] Keep `cli.py` public `build_parser()`, `main()`, and handler compatibility intact.
- [ ] Run CLI parser tests.

### Task 4: Orchestrator Workflow Split

**Files:**
- Create: `plugins/paper-source/scripts/build/epi/wiki_record_workflows.py`
- Modify: `plugins/paper-source/scripts/build/epi/orchestrator.py`
- Test: `tests/epi/test_wiki_ingest_record.py`
- Test: `tests/epi/test_paper_gate.py`

- [ ] Move human approval and wiki-ingest record orchestration helpers out of `orchestrator.py`.
- [ ] Keep existing `record_human_approval()` and `record_wiki_ingest()` imports callable from `epi.orchestrator`.
- [ ] Ensure run-state/report/zotero output remains byte-shape compatible for tests.
- [ ] Run focused wiki ingest record tests.

### Task 5: Graph Visibility Split

**Files:**
- Create: `plugins/paper-source/scripts/build/epi/graph_visibility.py`
- Modify: `plugins/paper-source/scripts/build/epi/wiki_init.py`
- Test: `tests/epi/test_wiki_init.py`

- [ ] Add failing test for graph filter helper and over-escaped filter repair.
- [ ] Move graph search construction and sync logic into `graph_visibility.py`.
- [ ] Wire `wiki_init.py` to the new module.
- [ ] Run focused wiki init tests.

### Task 6: Run Index Atomic Writes

**Files:**
- Modify: `plugins/paper-source/scripts/build/epi/run_index.py`
- Test: `tests/epi/test_run_index_dashboard.py`

- [ ] Add failing test proving machine JSON writes use `write_json_atomic`.
- [ ] Replace direct JSON writes in `run_index.py` with the shared atomic writer.
- [ ] Run focused run index tests.

### Task 7: Docs, Skills, Version, And Verification

**Files:**
- Modify: `plugins/paper-source/skills/epi-paper-deposition/SKILL.md`
- Modify: `plugins/paper-source/skills/wiki-provenance/SKILL.md`
- Modify: `plugins/paper-source/skills/run-lifecycle/SKILL.md`
- Modify: `plugins/paper-source/docs/workflow.md`
- Modify: `plugins/paper-source/docs/recovery.md`
- Modify: `plugins/paper-source/docs/progress.md`
- Modify: `plugins/paper-source/docs/structure.md`
- Modify: `plugins/paper-source/.codex-plugin/plugin.json`
- Test: `tests/epi/test_current_docs.py`

- [ ] Document raw bundle completeness, Chinese-default formal prose, hash-bound final-source-review refresh, graph repair, run index audit, clean-worker delegation, and router/workflow module boundaries.
- [ ] Add skill rules that future EPI changes should create focused modules instead of growing `cli.py`, `stage_wiki.py`, or `orchestrator.py`.
- [ ] Bump plugin version and short description together.
- [ ] Run focused docs tests.
- [ ] Run broader EPI pytest with repo-local `--basetemp`.
- [ ] Validate plugin manifest.
- [ ] With approval, run a real `D:\paper-research-wiki` EPI full-chain test and iterate on any failures.
