---
name: run-lifecycle
description: >
  Use when cleaning Paper Source runs: "清理 runs", _paper_source/runs, queues, indexes, logs.
---

# Paper Source Run Lifecycle

Manage transient Paper Source workflow artifacts without touching downloaded papers, staging papers, final wiki content, Zotero records, or configuration history.

## Default To Dry Run

Lifecycle cleanup is destructive, so manual cleanup starts with a dry run and adds `--apply` only after explicit approval:

```powershell
python scripts\orchestrator.py run-lifecycle --vault <vault> --keep-latest 15 --keep-per-workflow 2 --json
python scripts\orchestrator.py run-lifecycle --vault <vault> --keep-latest 15 --keep-per-workflow 2 --apply --json
```

The workflow may auto-apply lifecycle cleanup after `_paper_source/runs` exceeds 15 single-run directories. Manual operation remains approval-first.

## Cleanup Boundary

Clean only terminal single-run directories under `_paper_source/runs`. Never delete `_paper_source/runs/index.json`, dashboards, research queue, feedback logs, `_paper_source/raw`, `_paper_source/staging`, final wiki pages, Zotero records, config history, active runs, human-gate-pending runs, or protected non-terminal failures.

The command writes a manifest under `_paper_source\meta\run-lifecycle\`.

## Optional Delegation

Codex may use subagents only when the user explicitly authorizes delegation or parallel agent work. If authorized, delegate lifecycle inventory only: run dry-run first, report candidate paths and manifest path, and wait for explicit approval before `--apply`.

## Discovery Coordination

Discovery must deduplicate against wiki `_meta/reference-index.json` as the canonical backlog (`already_in_wiki:<page>` for deposited entries) and use `_paper_source\\raw` only as a missing-index fallback (`already_in_library:<slug>`). This keeps lifecycle cleanup separate from library identity.
