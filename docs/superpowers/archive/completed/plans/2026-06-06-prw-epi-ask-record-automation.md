# PRW EPI Ask Record Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build ask-mode automation from PRW formal page completion to EPI `record-wiki-ingest` through a machine-readable PRW record request artifact.

**Architecture:** PRW documents and emits `_epi/staging/papers/<slug>/prw-record-request.json`; EPI consumes it through `record-wiki-ingest --from-prw-request`. EPI validates live hashes, approval, paper gate, final pages, and `final-source-review.json` before writing record files.

**Tech Stack:** Python EPI CLI and pytest contract tests; PRW markdown workflow contracts.

---

### Task 1: Add Failing Tests For Request Consumption

**Files:**
- Modify: `tests/epi/test_wiki_ingest_record.py`
- Modify: `tests/epi/test_cli_parser.py`

- [ ] **Step 1: Write request-consumption tests**

Add tests that build a valid `prw-record-request.json`, call `record_wiki_ingest(..., from_prw_request=...)`, and assert the normal EPI record files are written with `source_request` metadata. Add a stale page hash test that expects failure before records are written.

- [ ] **Step 2: Write parser test**

Add a parser test showing `record-wiki-ingest --from-prw-request _epi/staging/papers/fixture-paper/prw-record-request.json --json` is accepted without `--slug`, `--page`, or `--approved-by`.

- [ ] **Step 3: Verify RED**

Run:

```powershell
python -m pytest tests\epi\test_wiki_ingest_record.py::test_record_wiki_ingest_consumes_prw_record_request tests\epi\test_wiki_ingest_record.py::test_record_wiki_ingest_from_prw_request_rejects_stale_page_hash tests\epi\test_cli_parser.py::test_record_wiki_ingest_parser_accepts_prw_record_request -q --basetemp=.pytest_tmp_prw_record_request_red
```

Expected: fail because `from_prw_request` is not implemented.

### Task 2: Implement EPI Request Loader And CLI Hook

**Files:**
- Modify: `plugins/epi/scripts/build/epi/wiki_ingest_record.py`
- Modify: `plugins/epi/scripts/build/epi/wiki_record_workflows.py`
- Modify: `plugins/epi/scripts/build/epi/cli_parser.py`
- Modify: `plugins/epi/scripts/build/epi/cli.py`

- [ ] **Step 1: Add request validation helpers**

Add `PRW_RECORD_REQUEST_SCHEMA_VERSION`, request path resolution, JSON loading, hash validation, and `create_wiki_ingest_record_from_prw_request()`.

- [ ] **Step 2: Add optional source request metadata**

Extend `create_wiki_ingest_record()` with an optional `source_request` parameter and persist it into the record payload.

- [ ] **Step 3: Add workflow support**

Extend `record_wiki_ingest()` with `from_prw_request`. When present, derive slug, pages, approval, and source review from the request and then write the normal run report.

- [ ] **Step 4: Add CLI support**

Add `--from-prw-request` to `record-wiki-ingest`. Make `--slug`, `--page`, and `--approved-by` conditionally required by workflow validation rather than argparse.

- [ ] **Step 5: Verify GREEN**

Run the three tests from Task 1. Expected: pass.

### Task 3: Document PRW Ask-Mode Handoff

**Files:**
- Modify: `plugins/PRW/docs/epi-integration.md`
- Modify: `plugins/PRW/skills/paper-research-wiki/workflows/extract-papers.md`
- Modify: `plugins/PRW/skills/paper-research-wiki/workflows/update-wiki.md`
- Modify: `plugins/PRW/skills/paper-research-wiki/workflows/redo-extraction.md`
- Modify: `plugins/epi/docs/workflow.md`
- Modify: `plugins/epi/skills/paper-ingest/workflows/approval-and-trigger.md`
- Modify: `tests/paper_research_wiki/test_plugin_contract.py`
- Modify: `tests/epi/test_current_docs.py`

- [ ] **Step 1: Add failing docs-contract tests**

Assert PRW docs mention `prw-record-request.json`, `automation_mode=ask`, and `record-wiki-ingest --from-prw-request`, while still asserting PRW does not write `wiki-ingest-record.json`.

- [ ] **Step 2: Verify RED**

Run the docs-contract tests and confirm they fail on missing phrases.

- [ ] **Step 3: Update PRW and EPI docs**

Document the request artifact, ask default, and EPI-owned consumption path.

- [ ] **Step 4: Verify GREEN**

Run the docs-contract tests. Expected: pass.

### Task 4: Final Verification

**Files:**
- All modified files.

- [ ] **Step 1: Run focused suite**

```powershell
python -m pytest tests\paper_research_wiki\test_plugin_contract.py tests\epi\test_current_docs.py tests\epi\test_wiki_ingest_record.py tests\epi\test_cli_parser.py tests\epi\test_paper_gate.py -q --basetemp=.pytest_tmp_prw_epi_ask_record_final
```

- [ ] **Step 2: Run compile and manifest checks**

```powershell
python -m compileall plugins\epi\scripts\build\epi\wiki_ingest_record.py plugins\epi\scripts\build\epi\wiki_record_workflows.py plugins\epi\scripts\build\epi\cli.py plugins\epi\scripts\build\epi\cli_parser.py
python -m json.tool plugins\epi\.codex-plugin\plugin.json
python -m json.tool plugins\PRW\.codex-plugin\plugin.json
git diff --check
```

- [ ] **Step 3: Report exact status**

Summarize implemented request flow, tests run, and any remaining source/install boundary.

