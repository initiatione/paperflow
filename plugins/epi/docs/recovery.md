# EPI Recovery

Repair commands operate on raw paper artifacts and append audit records:

```powershell
python scripts\orchestrator.py redo-acquire --slug <paper-slug> --pdf D:\codex-tmp\replacement.pdf --reason "better source" --vault D:\paper-research-wiki
python scripts\orchestrator.py recritic --slug <paper-slug> --reason "review after repair" --vault D:\paper-research-wiki
```

Rollback restores promotion snapshots and records the rollback in the wiki log.
