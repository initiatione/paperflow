---
name: zotero-sync
description: >
  Use when recording optional Zotero data: "同步 Zotero", "记录 Zotero 文献", zotero-sync sidecars.
---

# Zotero Sync

Zotero integration is optional. Default to local record-only behavior unless the user config enables Zotero sync or the user asks to run it.

If config is missing, stop sync and use `config-setup`. See `docs\config.md`.

```powershell
python scripts\orchestrator.py zotero-sync --paper-root <vault>\_paper_source\\raw\\<paper-slug> --collection Paper Source --enabled --item-key <zotero-item-key>
```

Runtime note: after `record-wiki-ingest`, Paper Source writes `_paper_source\\raw\\<paper-slug>\zotero-record.json` as a record-only sidecar using vault config. The record may include metadata, `wiki-ingest-record.json`, and final wiki page hashes. It does not call external Zotero APIs.

Never delete existing Zotero records during config reset or update.
