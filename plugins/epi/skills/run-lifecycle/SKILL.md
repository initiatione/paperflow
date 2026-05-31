---
name: run-lifecycle
description: "Use when EPI _runs, dashboards, research-queue, run logs, or transition-state artifacts accumulate too much, or when the user asks to clean, prune, archive, deduplicate, or lifecycle-manage EPI workflow artifacts."
---

# EPI Run Lifecycle

Use this skill to manage transient EPI workflow artifacts without touching downloaded papers or final wiki content.

When subagents are available, delegate lifecycle maintenance to a small/cost-efficient worker so the main agent can continue the user-facing workflow. The worker should run dry-run first, report candidates and manifest path, and wait for explicit approval before using `--apply`.

The workflow auto-applies lifecycle cleanup after EPI runs when `_runs` has more than 15 single-run directories. Manual cleanup still defaults to dry-run first:

```powershell
python scripts\orchestrator.py run-lifecycle --vault <vault> --keep-latest 15 --keep-per-workflow 2 --json
```

Apply only after the user agrees:

```powershell
python scripts\orchestrator.py run-lifecycle --vault <vault> --keep-latest 15 --keep-per-workflow 2 --apply --json
```

Rules:

- Clean only single-run directories under `_runs`; keep `_runs/index.json`, dashboards, research queue, and feedback logs.
- Never delete `_raw`, `_staging`, final wiki pages, Zotero records, or config history.
- The command writes a lifecycle manifest under `_meta\run-lifecycle\`.
- Active runs, human-gate-pending runs, and non-terminal failures are protected by default.
- Discovery must also deduplicate against `_raw\papers`: already downloaded papers should be rejected with `already_in_library:<slug>` rather than recommended again.
