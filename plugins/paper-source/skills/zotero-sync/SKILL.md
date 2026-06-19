---
name: zotero-sync
description: >
  Use when recording optional local Zotero sidecar data: "记录 Zotero 文献", zotero-sync sidecars.
---

# Zotero Record Sidecar

This Paper Source route is record-only compatibility for `_paper_source\raw\<paper-slug>\zotero-record.json`.
It does not call external Zotero APIs, import Zotero items, or synchronize formal Paper Wiki pages.

Discovery-time Zotero dedupe runs through `paper-discovery` / `dry-run` and writes `zotero-dedupe-record.json`.
Formal Zotero sync/status/apply writes belong to Paper Wiki `$paper-research-wiki`.

If config is missing, stop and use `config-setup`. See `docs\config.md`.

```powershell
python scripts\orchestrator.py zotero-sync --paper-root <vault>\_paper_source\\raw\\<paper-slug> --collection Paper Source --enabled --item-key <zotero-item-key>
```

Runtime note: after `record-wiki-ingest`, Paper Source writes `_paper_source\\raw\\<paper-slug>\zotero-record.json` as a record-only sidecar using vault config. The record may include metadata, `wiki-ingest-record.json`, and final wiki page hashes. It does not call external Zotero APIs.

Never delete existing Zotero records during config reset or update.
