---
name: wiki-setup
description: "Use when the user wants to initialize, create, inspect, repair, or reset the EPI paper research wiki vault structure. Reset is destructive and must require a second explicit confirmation before any deletion or move."
---

# EPI Wiki Setup

Use this skill only for the target paper research wiki vault structure, not for paper search, paper ingest, MinerU, Zotero, or final wiki writing.

## Initialize

Initialization is idempotent. It creates missing directories and seed files without deleting existing content:

```powershell
python scripts\init_paper_wiki.py --vault D:\paper-research-wiki
```

Expected structure includes `_raw\papers`, `_staging\papers`, `_quarantine\papers`, `_runs`, `_evolution`, `_meta`, `references`, `concepts`, `synthesis`, `entities`, `skills`, `projects`, `journal`, `.obsidian`, `index.md`, `log.md`, `hot.md`, and `.manifest.json`.

After initialization, summarize the created paths and tell the user that existing files were preserved.

## Reset

Reset is destructive. Do not reset immediately from a single user sentence.

Before reset:

1. Run a read-only inventory of the vault root and important EPI directories.
2. Explain exactly what will be moved or removed.
3. Create or propose a backup outside the active vault, such as `D:\paper-research-wiki-reset-backups\<timestamp>`.
4. Ask for a second explicit confirmation using the exact phrase: `确认重置 EPI wiki`.
5. Only after that confirmation, move existing vault contents to the backup location, then run initialization.

Never reset or delete:

- without the exact second confirmation
- if the resolved target path is not the intended vault
- by touching unrelated repositories or parent directories
- while paper ingest, MinerU parse, promotion, or wiki ingest is running

When unsure, stop after inventory and backup proposal.
