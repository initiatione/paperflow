---
name: zotero-sync
description: "Use when recording or running optional EPI Zotero sync; default is local record only."
---

# Zotero Sync

Zotero sync is optional and explicit. Check config first:

```powershell
python scripts\orchestrator.py config-status --vault D:\paper-research-wiki --json
```

If config is missing, stop before Zotero sync and follow `docs\config.md` 的 `## 聊天式初始化脚本`. 不要自由发挥成技术字段问卷. The user must confirm the plain-language summary before any config write or Zotero action.

```powershell
python scripts\orchestrator.py zotero-sync --paper-root D:\paper-research-wiki\_raw\papers\<paper-slug> --collection EPI
python scripts\orchestrator.py zotero-sync --paper-root D:\paper-research-wiki\_raw\papers\<paper-slug> --collection EPI --enabled --item-key <zotero-item-key>
```

Never delete existing Zotero records during config reset/update.
