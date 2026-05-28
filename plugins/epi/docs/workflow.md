# EPI Workflow

Use `python scripts\orchestrator.py doctor` before a run when installation or dependency state is unclear.

Primary commands:

```powershell
python scripts\orchestrator.py dry-run --query "robotics embodied intelligence control" --max-results 20 --vault D:\paper-research-wiki
python scripts\orchestrator.py advance-ranked --run-id <run-id> --max-papers 3 --vault D:\paper-research-wiki
python scripts\orchestrator.py promote-to-wiki --slug <paper-slug> --approved-by <name> --vault D:\paper-research-wiki
```

Safety boundary: dry-run writes only `_runs`; ingest and staging do not write compiled wiki pages; promotion requires a critic pass and explicit human approval.
