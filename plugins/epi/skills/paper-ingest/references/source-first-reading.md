# Source-First Reading Protocol

Use this file when moving from raw parsed paper artifacts into reader, critic, staging, or final wiki ingest.

## Source Order

Read or inspect source artifacts in this order:

1. `metadata.json` for identity, venue, year, DOI/arXiv, PDF/code/source hints.
2. `mineru/paper.md` for section-level content and local evidence anchors.
3. `mineru/paper.tex` for formulas, notation, and equation cues that Markdown may flatten.
4. `mineru/images/*` plus `reader/figures.md` for figure/table/image interpretation.
5. `mineru/mineru-manifest.json` for parse completeness and uncertainty.
6. `paper.pdf` when Markdown/TeX/images conflict or important content is missing.

Reader and critic outputs are navigation aids; they never replace the source paper.

## Claim Cards

For each important paper, preserve compact claim/evidence cards:

- central contribution
- method mechanism
- core formula or notation
- experiment/task/benchmark claim
- dataset/hardware/source artifact claim
- limitation or caveat
- wiki-deposition candidate concept

Each card needs a source pointer: metadata field, MinerU heading, equation/TeX cue, image filename, or explicit inference basis.

## Formula And Figure Rules

1. Preserve formulas that define the method, objective, constraint, update rule, proof step, or evaluation metric.
2. Explain notation only when the source provides enough context.
3. For figures/tables/images, state what they show, why they matter, and any parse uncertainty.
4. If an image is present but cannot be interpreted confidently, record the filename and uncertainty instead of omitting it.
5. If MinerU misses a formula or figure, mark the parse limitation and inspect the PDF if available.

## Wiki Handoff Rules

Final wiki ingest must read the source bundle again:

- `paper.pdf`
- `metadata.json`
- `mineru/paper.md`
- `mineru/paper.tex`
- `mineru/images/*`
- `mineru/mineru-manifest.json`

Use `reader/evidence-map.json`, `reader/figures.md`, and `critic/*.json` as supporting evidence only. The final wiki pages must not lose the original paper's formulas, figures, tables, source caveats, or negative findings.
