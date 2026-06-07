# EPI Paper Gate Queue Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface `paper-gate` readiness inside `research-queue` so users inspect the gate before approving promotion.

**Architecture:** Keep `paper-gate` as the authoritative read-only gate builder. `run_index` will enrich ready-to-promote queue items with a compact gate summary and recommend `paper-gate` inspection before promotion. Current gate evidence wins over stale run reports: `promote-to-wiki` is recommended only when the current gate is `action_required`, `next_action=promote-to-wiki`, has no `failure_checks`, and `action_required_checks` is exactly `["human-approval"]`.

**Tech Stack:** Python stdlib, existing EPI `pytest` suite, Markdown docs.

---

### Task 1: Paper Gate Summary in Research Queue

**Files:**
- Modify: `plugins/epi/scripts/build/epi/run_index.py`
- Modify: `plugins/epi/docs/epi-linkage.md`
- Test: `tests/epi/test_run_index_dashboard.py`
- Test: `tests/epi/test_runs_query_cli.py`

- [ ] **Step 1: Write failing run-index test**

Add a test that seeds a ready-to-promote run plus matching raw/staging gate artifacts, calls `refresh_run_index`, and asserts the `ready_to_promote` queue item contains:

```python
"paper_gate": {
    "status": "waiting_for_human_gate",
    "conclusion": "action_required",
    "next_action": "promote-to-wiki",
    "action_required_checks": ["human-approval"],
    "failure_checks": [],
}
```

Run:

```powershell
python -m pytest tests\epi\test_run_index_dashboard.py::test_refresh_run_index_enriches_ready_queue_with_paper_gate -q
```

Expected: fail because `paper_gate` is not present.

- [ ] **Step 2: Write failing CLI actions test**

Add a CLI test that seeds the same gate artifacts, runs:

```powershell
python scripts\orchestrator.py research-queue --bucket ready_to_promote --actions --json --vault <vault>
```

and asserts `recommended_actions` contains `inspect-paper-gate` with a `paper-gate --slug <slug>` command before `promote-to-wiki`.

Run:

```powershell
python -m pytest tests\epi\test_runs_query_cli.py::test_research_queue_cli_actions_puts_paper_gate_before_promotion -q
```

Expected: fail because only `promote-to-wiki` is recommended.

- [ ] **Step 3: Implement minimal queue enrichment**

In `run_index.py`, import `build_paper_gate` and add a small helper that:

- Calls `build_paper_gate(vault_path, slug)` only for ready-to-promote items.
- Stores `status`, `check_suite.conclusion`, `next_action`, failed check names, and action-required check names.
- Falls back to no `paper_gate` field if the slug is missing or gate construction cannot read usable evidence.

- [ ] **Step 4: Implement recommended action ordering**

Update ready-to-promote recommended actions to return:

1. `inspect-paper-gate`
2. `promote-to-wiki`, only when the current gate is waiting for human approval and has no failed checks

Both actions must keep `human_gate_required: true`.

- [ ] **Step 5: Update linkage doc**

In `plugins/epi/docs/epi-linkage.md`, update the Run Index section to state that `ready_to_promote` items include a compact `paper_gate` summary when raw/staging evidence is present, and `--actions` should recommend checking `paper-gate` before promotion.

- [ ] **Step 6: Verify target and full EPI suite**

Run:

```powershell
python -m pytest tests\epi\test_run_index_dashboard.py::test_refresh_run_index_enriches_ready_queue_with_paper_gate tests\epi\test_runs_query_cli.py::test_research_queue_cli_actions_puts_paper_gate_before_promotion -q
python -m pytest tests\epi -q --basetemp .pytest_tmp_epi_all_gate_queue
```

Expected: all selected tests pass, then full EPI suite passes.
