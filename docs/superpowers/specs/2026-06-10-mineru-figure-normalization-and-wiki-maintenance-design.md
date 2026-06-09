# MinerU Figure Normalization And Wiki Maintenance Design

Date: 2026-06-10
Status: approved design
Scope: Paper Source raw source bundles and a separate Paper Wiki maintenance skill

## Context

MinerU parse outputs currently preserve image files with hash-like names under `mineru/images/`. The current Paper Source source-bundle contract preserves MinerU Markdown, `paper.tex`, `mineru/images/*`, and `mineru-manifest.json`, but it does not map image assets back to the original paper labels such as `Fig. 1`, `Figure 2`, or `图 3`.

The live vault `D:\paper-research-wiki` also has historical legacy source bundles under `_epi/raw`. A read-only scan during design found 23 raw paper bundles, 208 raw Markdown files, 23 TeX files, and 1563 hash-like image names. Formal wiki pages already embed some of these images with HTML paths such as `../_epi/raw/.../mineru/images/<hash>.jpg`.

The confirmed boundary is:

- Paper Source owns raw source-bundle normalization and repair.
- Paper Wiki owns formal wiki page maintenance.
- MinerU parser skills must not rewrite formal wiki pages.
- Formal wiki maintenance must not rename raw images or alter MinerU parse semantics.

## Goals

1. Make new MinerU parses produce stable, source-grounded image names by default.
2. Preserve Markdown and TeX formula content completely while avoiding long-term storage of redundant formula screenshots.
3. Provide a dry-run-first raw bundle repair path for legacy `_epi/raw` and current `_paper_source/raw` bundles.
4. Add a separate Paper Wiki maintenance skill for formal page repair, provenance refresh, and graph validation.
5. Keep every figure/formula/table repair traceable through structured indexes and repair records.

## Non-Goals

- Do not make one end-to-end command that edits raw bundles and formal pages in a single hidden pass.
- Do not infer a figure label when the Markdown/caption context is ambiguous.
- Do not delete suspected formula images unless Markdown or TeX already preserves the formula.
- Do not rewrite formal page prose style as part of image-path maintenance.
- Do not move legacy `_epi/raw` into `_paper_source/raw` as part of this feature.

## Architecture

The design has two layers.

### Layer 1: Paper Source Raw Bundle Normalization

Paper Source handles files under `_paper_source/raw/<slug>` and legacy `_epi/raw/<slug>` only.

The existing MinerU command flow gains an asset-normalization step after Markdown, TeX, images, and manifest are materialized. The same normalization engine is also exposed to a dry-run-first repair command for historical bundles.

Responsibilities:

- Parse MinerU Markdown image references and nearby caption/prose context.
- Detect original labels such as `Fig. 1`, `Figure 2`, `Fig. 6a-d`, and `图 3`.
- Rename preserved images to stable names, for example `fig-004-algorithmic-structure.jpg`.
- Rewrite MinerU Markdown image paths to the normalized image names.
- Preserve or regenerate `paper.tex` according to the existing native/fallback TeX contract.
- Detect redundant formula screenshots and drop them only when Markdown or TeX has the corresponding LaTeX.
- Write structured indexes and repair records.

Images that cannot be mapped with confidence are kept as `unmapped-001-<short-hash>.jpg` and recorded with warnings.

### Layer 2: Paper Wiki Formal Page Maintenance

Paper Wiki gets a separate maintenance skill for formal wiki page repairs. This skill consumes raw bundle indexes; it does not run MinerU, rename raw assets, or modify raw parse outputs.

Responsibilities:

- Audit formal pages in `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.
- Compare embedded image paths, source labels, evidence figure cards, and provenance entries against raw bundle indexes.
- Produce a read-only maintenance audit before any writes.
- Repair formal pages only after explicit approval or a clean audit gate.
- Snapshot formal pages before material repairs.
- Refresh page-support sidecars and validation records required by the Paper Wiki/Paper Source handoff.

Formal page repair must preserve the existing Chinese academic page style and page-family structure. It should repair only image/formula/table evidence, source paths, evidence cards, and provenance records unless the user explicitly approves broader rewriting.

## Data Contracts

### `figure-index.json`

One record per preserved figure-like image:

- `figure_id`: stable local id such as `fig-004`
- `original_label`: original label such as `Fig. 4`
- `normalized_path`: path under `mineru/images/`
- `old_path`: previous hash path when applicable
- `caption_text`: extracted caption text
- `caption_locator`: Markdown section or line locator
- `markdown_image_locator`: Markdown image reference locator
- `sha256`: image hash after normalization
- `status`: `mapped`, `unmapped`, `needs_review`, or `dropped`
- `warnings`: ambiguity or parse-quality warnings

### `formula-index.json`

One record per central formula or dropped formula screenshot:

- `equation_label`: label such as `Eq. (4)` when available
- `latex`: normalized LaTeX if available
- `source`: `mineru-markdown`, `mineru-tex`, or `manual-review-needed`
- `markdown_locator`: Markdown locator
- `tex_locator`: TeX locator when available
- `dropped_image_refs`: formula screenshot paths not preserved as evidence figures
- `confidence`: `high`, `medium`, or `low`
- `warnings`: parse or OCR uncertainty

### `asset-normalization-record.json`

One record per normalization run:

- `schema_version`
- `paper_slug`
- `mode`: `dry-run` or `execute`
- `started_at` and `finished_at`
- `input_hashes`
- `rename_plan`
- `rewritten_files`
- `dropped_formula_images`
- `needs_review`
- `warnings`
- `output_hashes`

## Raw Bundle Workflow

### New Parse

1. Run the existing MinerU command flow.
2. Materialize canonical Markdown, `paper.tex`, `mineru/images/*`, and `mineru-manifest.json`.
3. Normalize assets.
4. Rewrite Markdown image links.
5. Write `figure-index.json`, `formula-index.json`, and `asset-normalization-record.json`.
6. Refresh parse record and evidence index output hashes.

### Legacy Repair

1. Scan `_epi/raw/<slug>` or `_paper_source/raw/<slug>`.
2. Build a mapping plan from existing Markdown, TeX, image files, and manifest.
3. Default to dry-run and report safe mappings, ambiguous mappings, and formula-image decisions.
4. On execute, rename files, rewrite Markdown, refresh indexes, and write a repair record.
5. Do not touch formal wiki pages.

## Wiki Maintenance Workflow

### Audit

1. Scan formal page roots only.
2. Extract embedded hash image paths, figure labels, source captions, and provenance entries.
3. Resolve each formal-page reference against `figure-index.json` and `formula-index.json`.
4. Emit a Markdown/JSON audit with `auto_repairable`, `needs_review`, `missing_source_index`, and `broken_path` buckets.

### Repair

1. Require an audit and explicit approval unless the repair is a narrow, already-clean patch.
2. Snapshot current formal pages to `_epi/meta/formal-page-snapshots/<timestamp>-pre-figure-repair/` with a hash manifest.
3. Patch only source paths, figure cards, image embeds, formula evidence references, and provenance records.
4. Refresh `final-source-review.json`, `prw-record-request.json`, or related sidecars only when their hashes or reviewed artifacts changed.
5. Run vault validation and QMD refresh when available.

## Error Handling

- Ambiguous figure label: keep the image, mark `unmapped`, and require review.
- Duplicate original figure label: use subfigure or part suffixes; never overwrite files.
- Formula image with complete LaTeX: drop or omit from preserved evidence images and record in `formula-index.json`.
- Formula image with incomplete LaTeX: keep for review and mark `needs_formula_review`.
- Missing image referenced by formal page: report a broken path; do not invent a replacement.
- Dirty vault: default to audit-only and require a snapshot before repair.
- Missing index files: ask the user to run raw bundle normalization first or include the bundle in the raw repair queue.

## Testing Strategy

Paper Source tests:

- Figure label and caption extraction from Markdown.
- Stable image naming and Markdown path rewriting.
- Formula screenshot classification with complete and incomplete LaTeX.
- `figure-index.json`, `formula-index.json`, and `asset-normalization-record.json` schemas.
- Legacy `paper.md` and canonical `<slug>.md` compatibility.

Paper Wiki tests:

- Formal page audit finds hash image embeds and resolves them through `figure-index.json`.
- Repair updates image paths and Source descriptions without rewriting unrelated prose.
- Formula screenshots are not promoted to evidence figure cards when LaTeX exists.
- Snapshot and hash-manifest behavior is enforced before material formal page repair.

Integration checks:

- Dry-run against `D:\paper-research-wiki\_epi\raw`.
- Formal-page read-only audit against `D:\paper-research-wiki`.
- Focused pytest for Paper Source and Paper Wiki contracts.
- `git diff --check`.
- Vault manifest/hash validation and QMD update/embed when configured.

## Implementation Sequence

1. Implement raw bundle normalization in Paper Source with fixture tests.
2. Add a dry-run legacy raw repair command.
3. Run read-only audit against the historical vault and inspect impact.
4. Add the separate Paper Wiki maintenance skill and audit workflow.
5. Add formal page repair after snapshot enforcement.
6. Repair raw bundles in batches.
7. Repair formal pages in batches.
8. Refresh sidecars, manifest hashes, and QMD indexes after each batch.

## Approval State

The user approved the two-layer approach:

- Raw bundle repair belongs to Paper Source.
- Formal wiki maintenance belongs to a separate Paper Wiki skill.
- The recommended implementation path is incremental and dry-run-first.
