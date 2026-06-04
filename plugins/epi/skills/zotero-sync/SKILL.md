---
name: zotero-sync
description: >
  Use when recording or running optional EPI Zotero sync, including Zotero,
  "同步 Zotero", "记录 Zotero 文献", "同步文献库记录", zotero-sync,
  local record-only sidecars, or post-ingest bibliographic records.
---

# Zotero Sync

Zotero integration is optional. Default to local record-only behavior unless the user config enables Zotero sync or the user asks to run it.

If config is missing, stop sync and use `config-setup`. See `docs\config.md`.

```powershell
python scripts\orchestrator.py zotero-sync --paper-root <vault>\_epi\raw\papers\<paper-slug> --collection EPI --enabled --item-key <zotero-item-key>
```

Runtime note: after `record-wiki-ingest` or legacy `promote-to-wiki`, EPI writes `_epi\raw\papers\<paper-slug>\zotero-record.json` as a record-only sidecar using vault config. The record may include metadata, `wiki-ingest-record.json`, and final wiki page hashes. It does not call external Zotero APIs.

Never delete existing Zotero records during config reset or update.
