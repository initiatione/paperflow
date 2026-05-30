# EPI Recovery

Repair commands operate on raw paper artifacts and append audit records:

```powershell
python scripts\orchestrator.py redo-acquire --slug <paper-slug> --pdf <replacement-pdf> --reason "better source" --vault <vault>
python scripts\orchestrator.py recritic --slug <paper-slug> --reason "review after repair" --vault <vault>
```

Rollback restores promotion snapshots and records the rollback in the wiki log.
