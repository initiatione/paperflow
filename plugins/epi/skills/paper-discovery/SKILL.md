---
name: paper-discovery
description: "Use when running EPI paper search/ranking dry-runs without acquisition, parsing, promotion, or Zotero."
---

# Engineering Paper Discovery

Use this for search, normalize, filter, and rank dry-runs. Check config first:

```powershell
python scripts\orchestrator.py config-status --vault D:\paper-research-wiki --json
```

If config is missing, stop before discovery and follow `docs\config.md` 的 `## 聊天式初始化脚本`. 不要自由发挥成技术字段问卷, and do not run search, dry-run, ingest, MinerU, or Zotero before the user confirms the summary. After confirmation, write answers JSON and run:

```powershell
python scripts\orchestrator.py init-config --vault D:\paper-research-wiki --answers-json <answers.json>
```

Run discovery:

```powershell
python scripts\orchestrator.py dry-run --query "robotics embodied intelligence control" --max-results 20 --vault D:\paper-research-wiki
```

Dry-run writes only `_runs/<run-id>/`. Use `doctor` first when installation or dependency state is unclear.
