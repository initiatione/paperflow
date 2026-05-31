---
name: run-lifecycle
description: "Use when inspecting, cleaning, pruning, or archiving transient EPI _runs dashboards, queues, and logs."
---

# EPI Run Lifecycle

Manage transient EPI workflow artifacts without touching downloaded papers, staging papers, final wiki content, Zotero records, or configuration history.

## Default To Dry Run

Lifecycle cleanup is destructive, so manual cleanup starts with a dry run:

```powershell
python scripts\orchestrator.py run-lifecycle --vault <vault> --keep-latest 15 --keep-per-workflow 2 --json
```

Add `--apply` only after explicit approval:

```powershell
python scripts\orchestrator.py run-lifecycle --vault <vault> --keep-latest 15 --keep-per-workflow 2 --apply --json
```

The EPI workflow may auto-apply lifecycle cleanup after runs when `_runs` exceeds 15 single-run directories. Manual operation remains approval-first.

## Cleanup Boundary

Clean only terminal single-run directories under `_runs`.

Never delete:

- `_runs/index.json`, dashboards, research queue, feedback logs
- `_raw`, `_staging`, final wiki pages, Zotero records, config history
- active runs, human-gate-pending runs, or protected non-terminal failures

The command writes a manifest under `_meta\run-lifecycle\`.

## Optional Delegation

If subagents are available, delegate lifecycle inventory to a small worker. The worker should run dry-run first, report candidate paths and manifest path, and wait for explicit approval before `--apply`.

## Discovery Coordination

Discovery must deduplicate against `_raw\papers`: already downloaded papers should be rejected as `already_in_library:<slug>` rather than recommended again. This keeps lifecycle cleanup separate from library identity.
