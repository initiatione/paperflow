# Maintain Figure And Formula Evidence

Use when formal wiki pages still point at MinerU hash image names, when evidence figure cards need normalized paths, or when formula screenshots should become Markdown/Obsidian math grounded in MinerU Markdown. Optional non-empty native `paper.tex` is cross-check only.

## Boundary

Paper Wiki maintains formal pages only. Do not rename files under `_paper_source/raw/**` or legacy `_epi/raw/**`. If `figure-index.json`, `formula-index.json`, or `asset-normalization-record.json` is missing, report that Paper Source raw bundle normalization must run first.

Paper Source owns MinerU parsing, raw image renaming, formula screenshot filtering, `figure-index.json`, `formula-index.json`, and `asset-normalization-record.json`. Paper Wiki owns formal page image path repair, Evidence figure card repair, formula/figure provenance wording, formal page snapshots before material repairs, and post-repair graph, manifest, hash, and QMD checks.

## Audit

1. Read the routing manifest and required Paper Wiki references from `SKILL.md`.
2. Scan only formal roots: `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.
3. Find raw MinerU image paths (`../_paper_source/raw/.../mineru/images/<hash>...`, legacy `../_epi/raw/...`), Markdown embeds into raw image directories, `image images/<hash>` source lines, and evidence lines mentioning `Fig.`, `Figure`, `图`, `Table`, `Eq.`, or formula image evidence.
4. For each slug, read `figure-index.json`, `formula-index.json`, optional `table-index.json`, and `asset-normalization-record.json`.
5. Report groups: `auto_repairable`, `needs_review`, `missing_source_index`, and `broken_path`.

Do not write formal pages during audit.

## Repair

Repair only after user approval or reviewed patch set.

1. Create a pre-repair snapshot under `_paper_source/meta/formal-page-snapshots/<timestamp>-pre-figure-repair/` with a hash manifest for every changed formal page; legacy `_epi/meta/formal-page-snapshots/` is audit/rollback only.
2. Patch only evidence lines: image `src` paths, Evidence figure card source lines, original labels, Chinese captions when locator changed, and provenance entries citing figure/formula evidence.
3. Do not rewrite unrelated paragraphs, frontmatter, tags, aliases, or page routing.
4. Preserve Obsidian math delimiters; do not introduce fenced `math`, `tex`, or `latex` code blocks.
5. Replace a formula screenshot only when MinerU Markdown or `formula-index.json` contains complete LaTeX; cite the Markdown locator and index entry. If incomplete, keep `needs_formula_review`.
6. Refresh sidecars only when reviewed artifact hashes changed: `final-source-review.json`, `paper-wiki-record-request.json`, legacy `prw-record-request.json` only for old staging bundles, and related Paper Source record request artifacts. Include `schema_version: paper-wiki-record-request-v1`, `automation_mode: ask`, and `record-wiki-ingest --from-paper-wiki-request ...`; Paper Wiki writes the request artifact; Paper Source consumes it.

## Verification

After repair, verify patched image paths exist, no new Markdown image embeds point to hash-like MinerU image names unless the index marks them `unmapped`, no fenced math blocks were introduced, and the Paper Wiki post-task check through `check-wiki.md` passes. Run QMD update/embed when configured or state why skipped, then report the exact remaining Paper Source action if `record-wiki-ingest` is not ready.
