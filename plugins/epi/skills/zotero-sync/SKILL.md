---
name: zotero-sync
description: "Use when recording or running optional EPI Zotero sync."
---

# Zotero Sync

Zotero integration is optional and explicit. Default to local record-only behavior unless the user config enables Zotero sync or the user asks to run it.

If config is missing, stop sync and use `config-setup`. See `docs\config.md`.

```powershell
python scripts\orchestrator.py zotero-sync --paper-root <vault>\_raw\papers\<paper-slug> --collection EPI --enabled --item-key <zotero-item-key>
```

Never delete existing Zotero records during config reset or update.
