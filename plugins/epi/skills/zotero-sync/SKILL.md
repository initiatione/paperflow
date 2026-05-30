---
name: zotero-sync
description: "Use when recording or running optional EPI Zotero sync; default is local record only."
---

# Zotero Sync

Zotero sync is optional and explicit. If config is missing, stop sync and use `config-setup`; config onboarding lives in `docs\config.md` 的 `## 聊天式初始化脚本`，不要自由发挥成技术字段问卷，不要一次性输出完整默认配置.

```powershell
python scripts\orchestrator.py zotero-sync --paper-root <vault>\_raw\papers\<paper-slug> --collection EPI --enabled --item-key <zotero-item-key>
```

Never delete existing Zotero records during config reset/update.
