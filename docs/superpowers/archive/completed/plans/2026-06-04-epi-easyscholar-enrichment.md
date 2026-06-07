# EPI EasyScholar Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port EasyScholar quality metrics into EPI discovery as a default-on, soft-failing enrichment layer.

**Architecture:** Add a native Python EasyScholar client/enricher that runs between filtering and ranking in `dry-run`. Enriched candidates carry verified metrics and bounded quality signals; `rank_papers.py` consumes those signals without letting venue prestige override topic fit or evidence gates.

**Tech Stack:** Python standard library, EPI orchestrator modules under `plugins/epi/scripts/build/epi`, pytest tests under `tests/epi`, existing EPI runtime config and report artifacts.

---

### Task 1: EasyScholar Core Module

**Files:**
- Create: `plugins/epi/scripts/build/epi/easyscholar.py`
- Test: `tests/epi/test_easyscholar.py`

- [ ] **Step 1: Write failing parser, scorer, cache, and soft-failure tests**

Add tests for parsing `officialRank.all/select`, scoring JCR/CAS/CCF/ABDC/AJG/IF evidence, normalizing cache keys, missing-key enrichment, API error enrichment, cache hit behavior, and secret redaction.

- [ ] **Step 2: Run focused tests and verify they fail**

Run: `python -m pytest tests/epi/test_easyscholar.py -q --basetemp=.pytest_tmp_easyscholar_red`

Expected: import or assertion failures because `epi.easyscholar` does not exist yet.

- [ ] **Step 3: Implement `easyscholar.py`**

Implement:

- `EasyScholarConfig`
- `parse_easyscholar_response`
- `score_easyscholar_metrics`
- `publication_name_for_candidate`
- `normalize_publication_name`
- `cache_key_for_publication`
- `enrich_candidates_with_easyscholar`

The module must use only standard-library HTTP, timeout handling, JSON parsing, cache reads/writes, and safe records that never include `secretKey`.

- [ ] **Step 4: Run focused tests and verify they pass**

Run: `python -m pytest tests/epi/test_easyscholar.py -q --basetemp=.pytest_tmp_easyscholar_green`

Expected: all tests in `test_easyscholar.py` pass.

### Task 2: Config, Runtime, CLI, And Doctor

**Files:**
- Modify: `plugins/epi/scripts/build/epi/config.py`
- Modify: `plugins/epi/scripts/build/epi/runtime_config.py`
- Modify: `plugins/epi/scripts/build/epi/cli_parser.py`
- Modify: `plugins/epi/scripts/build/epi/cli.py`
- Modify: `plugins/epi/scripts/build/epi/doctor.py`
- Test: `tests/epi/test_cli_parser.py`
- Test: `tests/epi/test_runtime_config.py`

- [ ] **Step 1: Write failing runtime/CLI/doctor tests**

Add tests that `dry-run` parser accepts `--no-easyscholar`, runtime env files can load `EASYSCHOLAR_SECRET_KEY` without leaking it, `config-status --include-runtime` reports `set/missing`, and `doctor --json` includes an EasyScholar check without the secret.

- [ ] **Step 2: Run focused tests and verify they fail**

Run: `python -m pytest tests/epi/test_cli_parser.py tests/epi/test_runtime_config.py -q --basetemp=.pytest_tmp_easyscholar_runtime_red`

Expected: failures for missing parser/runtime/doctor support.

- [ ] **Step 3: Implement config/runtime/CLI/doctor wiring**

Add `quality_enrichment.easyscholar` defaults to config loading, allow env files to set `EASYSCHOLAR_SECRET_KEY`, add `--no-easyscholar`, pass the flag to `run_dry_run`, report EasyScholar secret state safely, and add doctor setup guidance.

- [ ] **Step 4: Run focused tests and verify they pass**

Run: `python -m pytest tests/epi/test_cli_parser.py tests/epi/test_runtime_config.py -q --basetemp=.pytest_tmp_easyscholar_runtime_green`

Expected: focused runtime/CLI tests pass.

### Task 3: Dry-Run And Ranking Integration

**Files:**
- Modify: `plugins/epi/scripts/build/epi/orchestrator.py`
- Modify: `plugins/epi/scripts/build/epi/rank_papers.py`
- Modify: `plugins/epi/scripts/build/epi/report_run.py`
- Test: `tests/epi/test_orchestrator_dry_run.py`
- Test: `tests/epi/test_normalize_filter_rank.py`
- Test: `tests/epi/test_ranking_protocol.py`

- [ ] **Step 1: Write failing integration and ranking tests**

Add tests that `run_dry_run` writes `easyscholar-record.json`, missing key soft-fails but still writes `rank.json`, cache/fixture enrichment changes `easyscholar_score`, `--no-easyscholar` disables enrichment, and EasyScholar evidence raises source confidence without promoting weak/off-topic papers to Tier A.

- [ ] **Step 2: Run focused tests and verify they fail**

Run: `python -m pytest tests/epi/test_orchestrator_dry_run.py tests/epi/test_normalize_filter_rank.py tests/epi/test_ranking_protocol.py -q --basetemp=.pytest_tmp_easyscholar_integration_red`

Expected: failures because dry-run/ranking/report integration is missing.

- [ ] **Step 3: Implement integration**

Call `enrich_candidates_with_easyscholar` after filtering and before ranking. Write `easyscholar-record.json`, add enrichment summary to `run-state.json`, `report.json`, `report.md`, and `discovery_context`, include the new tool version, and make ranking consume `quality_signals.easyscholar.score`.

- [ ] **Step 4: Run focused tests and verify they pass**

Run: `python -m pytest tests/epi/test_orchestrator_dry_run.py tests/epi/test_normalize_filter_rank.py tests/epi/test_ranking_protocol.py -q --basetemp=.pytest_tmp_easyscholar_integration_green`

Expected: focused dry-run/ranking tests pass.

### Task 4: Docs, Attribution, And Contract Tests

**Files:**
- Modify: `plugins/epi/docs/attribution.md`
- Modify: `plugins/epi/docs/config.md`
- Modify: `plugins/epi/docs/workflow.md`
- Modify: `plugins/epi/skills/paper-discovery/SKILL.md`
- Modify: `plugins/epi/skills/paper-discovery/references/ranking-rubric.md`
- Modify: `plugins/epi/skills/paper-discovery/references/quality-gate.md`
- Modify: `plugins/epi/skills/paper-discovery/references/output-format.md`
- Create: `plugins/epi/vendor-notices/easyscholar-mcp.md`
- Test: `tests/epi/test_current_docs.py`
- Test: `tests/epi/test_config_onboarding_docs.py`

- [ ] **Step 1: Write failing docs tests**

Assert docs mention EasyScholar, `EASYSCHOLAR_SECRET_KEY`, default-on soft failure, `--no-easyscholar`, `easyscholar-record.json`, `未核实`, and MIT attribution.

- [ ] **Step 2: Run focused docs tests and verify they fail**

Run: `python -m pytest tests/epi/test_current_docs.py tests/epi/test_config_onboarding_docs.py -q --basetemp=.pytest_tmp_easyscholar_docs_red`

Expected: docs tests fail because docs are not updated.

- [ ] **Step 3: Update docs and vendor notice**

Document the new runtime secret, default-on behavior, reports, quality gate semantics, and upstream MIT attribution.

- [ ] **Step 4: Run docs tests and verify they pass**

Run: `python -m pytest tests/epi/test_current_docs.py tests/epi/test_config_onboarding_docs.py -q --basetemp=.pytest_tmp_easyscholar_docs_green`

Expected: focused docs tests pass.

### Task 5: Verification And Goal Audit

**Files:**
- Verify: changed files only plus focused EPI suites.

- [ ] **Step 1: Run compile check**

Run: `python -m compileall plugins/epi/scripts/build/epi`

Expected: compile succeeds.

- [ ] **Step 2: Run focused EasyScholar verification**

Run: `python -m pytest tests/epi/test_easyscholar.py tests/epi/test_cli_parser.py tests/epi/test_runtime_config.py tests/epi/test_orchestrator_dry_run.py tests/epi/test_normalize_filter_rank.py tests/epi/test_ranking_protocol.py tests/epi/test_current_docs.py tests/epi/test_config_onboarding_docs.py -q --basetemp=.pytest_tmp_easyscholar_final`

Expected: focused tests pass.

- [ ] **Step 3: Inspect final diff**

Run: `git diff --stat` and `git diff --check`

Expected: no whitespace errors; diff only contains EasyScholar-related implementation, tests, docs, and the plan/spec.

- [ ] **Step 4: Audit against the design spec**

Compare implementation against `docs/superpowers/specs/2026-06-04-epi-easyscholar-enrichment-design.md` and verify every explicit requirement is implemented or clearly called out as remaining work.
