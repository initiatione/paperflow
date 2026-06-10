# Source-First Reading Protocol

Use this file when moving from raw parsed paper artifacts into reader, critic, staging, or final wiki ingest.

## Source Order

Read or inspect source artifacts in this order:

1. `metadata.json` for identity, venue, year, DOI/arXiv, PDF/code/source hints.
2. `mineru/<slug>.md` for section-level content and local evidence anchors.
3. `mineru/paper.tex` only when non-empty native TeX exists; otherwise review formulas directly from MinerU Markdown and use PDF fallback when needed.
4. `mineru/images/*` plus `reader/figures.md` for figure/table/image interpretation.
5. `mineru/mineru-manifest.json` for parse completeness and uncertainty.
6. `paper.pdf` when Markdown/TeX/images conflict or important content is missing.

Reader and critic outputs are navigation aids; they never replace the source paper.

Parse-quality review should treat `mineru/<slug>.md`, `images/*`, `mineru-manifest.json`, `parse-record.json`, figure/formula indexes, and optional non-empty native `paper.tex` as one evidence bundle when parse succeeded.

## Approval Report Rules

Before human approval for wiki ingest, expose a single approval report, not raw JSON. The report should be Chinese-first and short enough to read quickly while preserving enough paper information for a real decision: title, authors/year/venue/DOI or arXiv, PDF and metric status, theory/method idea, experiment or validation setup, evidence strength, caveats, and wiki deposition value. Use Chinese-English terms on first mention and one final recommendation per paper: `建议沉淀`, `谨慎沉淀`, or `暂不沉淀`.

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
- `mineru/<slug>.md`
- `mineru/paper.tex` when non-empty native TeX exists
- `mineru/images/*`
- `mineru/mineru-manifest.json`

Use `reader/evidence-map.json`, `reader/claim-support.json`, `reader/figures.md`, and `critic/*.json` as supporting evidence only. Treat `source-grounded`, `metadata-only`, and `inferred` claims differently during final wiki writing. The final wiki pages must not lose the original paper's formulas, figures, tables, source caveats, or negative findings.

Before `record-wiki-ingest`, write `final-source-review.json` near the staging handoff. Use schema `paper-source-final-source-review-v1` and include:

- `reviewed_artifacts[]`: `paper.pdf`, `metadata.json`, `mineru/<slug>.md`, `mineru/images/*`, `mineru/mineru-manifest.json`, figure/formula indexes, and optional `mineru/paper.tex`; file artifacts need `status=reviewed` and `sha256`.
- `mineru/images/*`: `status=reviewed`, `file_count`, and per-image `relative_path` plus `sha256` when images exist.
- `formula_review`: `status=reviewed` and a short summary of formulas, notation, assumptions, derivations, or parse gaps.
- `figure_table_image_review`: `status=reviewed` and a short summary of visual evidence and uncertainty.
- `pdf_fallback_review`: `status=reviewed` or `not-needed` with the PDF fallback decision.
- `final_page_provenance[]`: every final wiki page `relative_path`, optional page `sha256`, and `source_grounded=true`.

Then run `record-wiki-ingest --source-review <final-source-review.json>` so Paper Source records a machine-verifiable source-first closure instead of relying on the reader summary or brief text alone.
