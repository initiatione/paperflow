---
name: epi-paper-deposition
description: >
  Use when an EPI wiki_deposition_task.json or legacy epi-wiki-deposition artifact
  must be bridged to the paper wiki layer, especially "兼容旧沉淀任务",
  EPI handoff adapter, PRW unavailable, or historical EPI deposition records.
---

# EPI Paper Deposition

Use this skill only as the legacy compatibility adapter at the EPI-to-PRW boundary.

Canonical path: formal paper wiki work goes through PRW `$paper-research-wiki` using `_epi/staging/papers/<slug>/wiki-ingest-brief.json` as the handoff.

Legacy compatibility: older artifacts may say legacy `wiki_deposition_task.json` or `epi-wiki-deposition`. Treat those as legacy names and route the user to PRW after confirming that `wiki-ingest-brief.json` exists. If only the legacy task exists, ask EPI to regenerate or repair the brief before formal writes.

## Workflow Routing

| Intent | Load |
| --- | --- |
| User-facing formal paper wiki writing, extraction, checks, updates, relinking, or graph-aware rewrite | `$paper-research-wiki` from PRW |
| Legacy handoff mentions `wiki_deposition_task.json` or `epi-wiki-deposition` | `workflows/formal-wiki-write.md` |

## Boundaries

- EPI source bundles and `_epi/` artifacts are evidence inputs, not formal wiki pages.
- EPI owns `paper-gate`, human approval records, and `record-wiki-ingest`.
- PRW owns formal page writing, graph-aware rewrite, provenance sidecars, language gate, link repair, and post-task checks.
- Internal `_epi/` pages must not enter the formal graph.
