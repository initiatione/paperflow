# Recovery

Phase 1 dry-run is idempotent at the run directory level. Each run writes a new `_runs/<run-id>/` folder.

To inspect a run:

```powershell
Get-Content D:\paper-research-wiki\_runs\<run-id>\run-state.json
Get-Content D:\paper-research-wiki\_runs\<run-id>\report.md
```

If `paper-search-mcp` is unavailable, the run fails closed by writing an error to `search-record.json` and `report.md`. It must not fabricate search results.

Dry-run artifacts may be removed when the user explicitly wants to discard a run. Raw papers and compiled wiki pages are not created by Phase 1.

For raw paper recovery after one-paper ingest:

```powershell
python scripts\orchestrator.py redo-acquire --slug <paper-slug> --pdf D:\codex-tmp\replacement.pdf --reason "better source" --vault D:\paper-research-wiki
python scripts\orchestrator.py redo-parse --slug <paper-slug> --mineru-md D:\codex-tmp\paper.md --mineru-tex D:\codex-tmp\paper.tex --reason "parse critic requested redo" --vault D:\paper-research-wiki
python scripts\orchestrator.py redo-read --slug <paper-slug> --reason "reader stale after parse redo" --vault D:\paper-research-wiki
python scripts\orchestrator.py recritic --slug <paper-slug> --reason "reader revised" --vault D:\paper-research-wiki
```

Redo commands append audit events to `_raw\papers\<paper-slug>\redo-records.jsonl`. They do not write compiled pages under `references`, `concepts`, or `synthesis`.

For compiled wiki promotion recovery, promotion requires explicit approval:

```powershell
python scripts\orchestrator.py promote-to-wiki --slug <paper-slug> --approved-by <name> --vault D:\paper-research-wiki
python scripts\orchestrator.py rollback-promotion --slug <paper-slug> --vault D:\paper-research-wiki
```

If approval is missing, EPI refuses promotion before writing `references\<paper-slug>.md`.

Promotion stores rollback evidence under `_raw\papers\<paper-slug>\promotion-backups\`, including compiled page snapshots plus state snapshots for `.manifest.json`, `index.md`, `hot.md`, and `log.md`. Rollback restores those snapshots and appends a rollback entry to the restored `log.md`.
