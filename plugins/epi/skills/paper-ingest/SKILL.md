---
name: paper-ingest
description: "Use when ingesting selected papers into EPI raw artifacts, readers, critics, and staging drafts."
---

# Paper Ingest

Before ingest, check config:

```powershell
python scripts\orchestrator.py config-status --vault D:\paper-research-wiki --json
```

If config is missing, stop before ingest and follow `docs\config.md` 的 `## 聊天式初始化脚本`. 不要自由发挥成技术字段问卷, and do not acquire, parse, stage, promote, or sync anything before the user confirms the summary.

Core commands:

```powershell
python scripts\orchestrator.py ingest-one --candidate D:\codex-tmp\candidate.json --pdf D:\codex-tmp\paper.pdf --mineru-md D:\codex-tmp\paper.md --mineru-tex D:\codex-tmp\paper.tex --vault D:\paper-research-wiki
python scripts\orchestrator.py advance-paper --candidate D:\codex-tmp\candidate.json --vault D:\paper-research-wiki
python scripts\orchestrator.py advance-batch --candidates D:\codex-tmp\ranked-candidates.json --max-papers 3 --vault D:\paper-research-wiki
python scripts\orchestrator.py advance-ranked --run-id <dry-run-id> --max-papers 3 --vault D:\paper-research-wiki
```

Safety: raw/staging writes are allowed; compiled wiki writes are not. No critic pass, no promotion.
