# Maintain Figure And Formula Evidence

Use this workflow when the user asks to repair formal wiki pages whose evidence figures still point at MinerU hash image names, or when formula screenshots should be replaced by Markdown/Obsidian math grounded in MinerU Markdown. Optional non-empty native `paper.tex` may be used only as a cross-check when present.

## Boundary

Paper Wiki maintains formal pages only. Do not rename files under `_paper_source/raw/**` or legacy `_epi/raw/**`. If a paper lacks `figure-index.json`, `formula-index.json`, or `asset-normalization-record.json`, report that Paper Source raw bundle normalization must run first.

Paper Source owns:

- MinerU parsing.
- Raw image renaming.
- Formula screenshot filtering inside raw bundles.
- `figure-index.json`, `formula-index.json`, and `asset-normalization-record.json`.

Paper Wiki owns:

- Formal page image path repair.
- Evidence figure card repair.
- Formula and figure provenance wording.
- Formal page snapshots before material repairs.
- Post-repair graph, manifest, hash, and QMD checks.

## Audit

1. Read the routing manifest and required Paper Wiki references from `SKILL.md`.
2. Identify the vault root and formal page roots:
   - `references/`
   - `concepts/`
   - `derivations/`
   - `experiments/`
   - `synthesis/`
   - `reports/`
   - `opportunities/`
3. Scan formal Markdown for:
   - `<img src="../_epi/raw/.../mineru/images/<hash>...">`
   - `<img src="../_paper_source/raw/.../mineru/images/<hash>...">`
   - Markdown image embeds that point into raw MinerU image directories.
   - Source lines that mention `image images/<hash>`.
   - Provenance lines that mention `Fig.`, `Figure`, `图`, `Table`, `Eq.`, or formula image evidence.
4. For each referenced paper slug, read the raw bundle indexes:
   - `figure-index.json`
   - `formula-index.json`
   - `table-index.json` if present
   - `asset-normalization-record.json`
5. Produce an audit grouped as:
   - `auto_repairable`: old image path maps exactly to a normalized figure path.
   - `needs_review`: figure label is ambiguous, image is unmapped, or formal page wording claims more than the source index supports.
   - `missing_source_index`: raw bundle has not been normalized yet.
   - `broken_path`: formal page points to an image that does not exist in the raw bundle.

Do not write formal pages during audit.

## Repair

Repair only after the audit is reviewed or the user explicitly approves the listed patch set.

1. Create a pre-repair snapshot under `_epi/meta/formal-page-snapshots/<timestamp>-pre-figure-repair/` with a hash manifest for every formal page that will change.
2. Patch only the lines that carry figure/formula/table evidence:
   - image `src` paths
   - Evidence figure card source lines
   - original figure labels
   - Chinese captions when the source caption locator changed
   - provenance entries that cite figure/formula evidence
3. Do not rewrite unrelated paragraphs, frontmatter, tags, aliases, or page routing.
4. Preserve Obsidian math delimiters. Do not use fenced `math`, `tex`, or `latex` code blocks.
5. If a formula screenshot is referenced but MinerU Markdown or `formula-index.json` contains complete LaTeX, replace the screenshot evidence with math and cite the MinerU Markdown locator and index entry. Use optional native TeX only as a cross-check when present.
6. If a formula screenshot lacks complete LaTeX, keep the evidence as `needs_formula_review` and do not claim the equation has been fully recovered.
7. Refresh sidecars only when reviewed artifact hashes changed:
   - `final-source-review.json`
   - `prw-record-request.json`
   - related Paper Source record request artifacts

## Verification

After repair:

1. Verify all patched image paths exist.
2. Verify no new Markdown image embeds point to hash-like MinerU image names unless the source index marks the image as `unmapped`.
3. Verify no fenced math blocks were introduced.
4. Run the Paper Wiki post-task check through `check-wiki.md`.
5. Run QMD update/embed when configured, or state why it was skipped.
6. Report the exact remaining Paper Source action if `record-wiki-ingest` is not ready.
