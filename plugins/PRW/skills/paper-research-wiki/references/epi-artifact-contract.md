# EPI Artifact Contract

canonical handoff:

- `wiki-ingest-brief.json`

legacy compatibility artifact:

- `wiki_deposition_task.json` (deprecated compatibility)

Required source inputs for PRW deposition:

- `briefs/reading-report.md`
- `metadata.json`
- `paper.pdf`
- MinerU Markdown, TeX, images, and manifest

Optional aids are reader evidence maps, claim support JSON, critic reports, and `wiki-agent-trigger.json`.

PRW must not treat task-only legacy handoffs as ready. Do not treat task-only legacy handoffs as ready. If `wiki_deposition_task.json` exists without `wiki-ingest-brief.json`, report the legacy limitation and route back to EPI to regenerate or repair the brief before formal writes.

EPI owns `paper-gate`, human approval records, and `record-wiki-ingest`.
