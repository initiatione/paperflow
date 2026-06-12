# Paper Source Artifact Contract

canonical handoff:

- `wiki-ingest-brief.json`

legacy compatibility artifact:

- `wiki_deposition_task.json` (deprecated compatibility)

Required source inputs for Paper Wiki deposition:

- `briefs/reading-report.md`
- `metadata.json`
- `paper.pdf`
- MinerU Markdown, images, manifest, `figure-index.json`, `formula-index.json`, and `asset-normalization-record.json`

MinerU Markdown is the primary source for formulas, notation, method context, and prose. Native TeX is not required for Paper Wiki deposition, and missing `mineru/paper.tex` must not block formal writing or record readiness. Use the PDF, `formula-index.json`, `figure-index.json`, and image evidence as fallback checks only when MinerU Markdown is missing, wrong, ambiguous, or insufficient. Optional aids are non-empty native `mineru/paper.tex` when present, reader evidence maps, claim support JSON, critic reports, and `wiki-agent-trigger.json`.

Paper Wiki must not treat task-only legacy handoffs as ready. Do not treat task-only legacy handoffs as ready. If `wiki_deposition_task.json` exists without `wiki-ingest-brief.json`, report the legacy limitation and route back to Paper Source to regenerate or repair the brief before formal writes.

Paper Source owns `paper-gate`, human approval records, and `record-wiki-ingest`.
