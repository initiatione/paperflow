# EPI Artifact Contract

Canonical handoff = `wiki-ingest-brief.json`; `wiki_deposition_task.json` is a deprecated compatibility artifact. PRW still reads it for legacy handoffs, but new dependencies should point to the brief.

Required inputs:

- `wiki-ingest-brief.json`
- `wiki_deposition_task.json` (deprecated compatibility)
- `briefs/reading-report.md`
- `metadata.json`
- `paper.pdf`
- MinerU Markdown, TeX, images, and manifest

Optional aids are reader evidence maps, claim support JSON, critic reports, and `wiki-agent-trigger.json`.

EPI owns `paper-gate`, human approval records, and `record-wiki-ingest`.
