# Redo Extraction

Use this when the user asks PRW to 重做, 重新提取, 更详细提取, 批量重提取, redo, redo extraction, or deep extraction for one paper or many papers.

This workflow is for deliberate re-deposition. It is stronger than ordinary update: PRW must re-read the source bundle, compare existing wiki pages, and produce a controlled rewrite or staged patch.

## Modes

- single paper: target one slug, title, DOI, arXiv id, selected page, or selected EPI handoff.
- batch: target a list of slugs, all ready handoffs, all papers in a run, or all papers matching a topic/status filter.

If the target is ambiguous, ask one short question. A reply of `默认` means redo the ready paper or batch PRW can identify from the current EPI handoff context.

## Preflight

1. Read `../../../rules/wiki-writing-standard.md`.
2. Read `../../paper-wiki-language/SKILL.md`; redo writing must fix language quality without changing evidence.
3. Resolve the target vault and read `AGENTS.md`, `_meta/schema.md`, `_meta/taxonomy.md`, and `_meta/directory-structure.md` when present.
4. Locate the relevant `_epi/staging/papers/*/wiki_deposition_task.json` and `wiki-ingest-brief.json`.
5. Check `paper-gate` status or handoff status. Stop if source artifacts are missing or if human approval is the only unresolved gate.
6. Read current formal pages named by previous `wiki-ingest-record.json`, `final-source-review.json`, page frontmatter `sources:`, or search hits in the seven page families.

## Source Reread

source reread is mandatory. Do not redo from existing wiki text alone.

For every selected paper, re-read:

- PDF
- metadata
- MinerU Markdown
- TeX
- images
- MinerU manifest
- reading report
- `wiki-ingest-brief.json`
- prior `final-source-review.json` when present

Reader or critic outputs may guide attention, but they do not replace the PDF, MinerU Markdown, TeX, images, or manifest.

## Compare Existing Pages

Before writing, compare existing pages against the source reread:

1. Identify which `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/` pages the paper already touched.
2. Mark each page as keep, deepen, split, merge, supersede, or delete-proposal.
3. Preserve useful existing wikilinks, aliases, tags, and relationships.
4. Surface contradictions and unsupported claims instead of silently deleting them.
5. Decide whether the redo should be a direct rewrite or a staged patch.

Use `staged patch` by default when the redo changes page identity, removes existing claims, changes lifecycle, or affects more than one formal page family.

## Deep Extraction Lenses

For deep extraction, inspect the paper through these lenses:

- theory reconstruction
- formula derivation
- figure and table evidence
- experimental setup, metrics, datasets, baselines, and ablations
- implementation details and reproducibility caveats
- limitations, failure modes, and assumptions
- reusable methods or concepts
- cross-paper contradictions, confirmations, and research gaps
- opportunities for follow-up experiments or literature review sections

## Write Plan

Return a concise plan before writing:

1. selected papers: single paper or batch
2. pages to rewrite, deepen, split, merge, or stage
3. source artifacts reread
4. risk level: low, medium, or high
5. confirmation question

Ask one confirmation before write-heavy redo. A reply of `默认` means apply the recommended safe staged plan.

## Write Pages

After confirmation:

1. Apply `wiki-writing-standard.md`.
2. Apply `paper-wiki-language` before and during the rewrite; do not leave machine-translation headings or outline-like Chinese prose in formal pages.
3. Write direct changes only when risk is low and the target vault allows direct writes.
4. Otherwise write staged patch files or staged replacement pages using the vault staging contract.
5. Keep source support labels and evidence addresses visible.
6. Recompute `provenance:` and `base_confidence:` when sources or claim mix materially change.
7. Update `relationships:` only when direction and type are clear.
8. Update or recreate `final-source-review.json` for every selected paper.

## Tracking And EPI Boundary

Update the target vault tracking surface after the redo:

- manifest or `.manifest.json`
- `index.md`
- `log.md`
- `hot.md`

PRW can prepare pages and source review, but do not write human approval. EPI owns human approval records and `record-wiki-ingest`.

After redo, tell the user which `record-wiki-ingest` command remains, or say that staged review must happen first.
