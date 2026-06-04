# Extract Papers

Use this when the user asks to extract, process, or deposit EPI-collected papers.

This workflow adapts Ar9av/obsidian-wiki `wiki-ingest`: do not summarize papers in isolation. Instead, distill and integrate source-grounded paper knowledge into the existing wiki graph.

Before planning or writing pages, read `../../../rules/wiki-writing-standard.md` and `../../paper-wiki-language/SKILL.md`; treat them as mandatory page-writing and language contracts.

## Preflight

1. Resolve the target vault.
2. Check the EPI `wiki-setup` bootstrap: `_epi/`, `_meta/`, `.obsidian`, `.git`, and the seven formal page roots. If missing vault structure blocks safe work, stop and point back to EPI `wiki-setup`; do not initialize or reset from PRW.
3. Read target vault `AGENTS.md`, `_meta/schema.md`, `_meta/taxonomy.md`, and `_meta/directory-structure.md` when present.
4. Locate `_epi/staging/papers/*/wiki_deposition_task.json`.
5. Run a readiness preflight and group papers as ready, needs human approval, blocked, or already recorded.
6. For ready papers, read source bundle artifacts before writing: PDF, metadata, MinerU Markdown, TeX, images, manifest, reading report, and `wiki-ingest-brief.json`.

## Plan Wiki Updates

1. Read the target vault `manifest` or `.manifest.json` to avoid duplicate source ingestion.
2. Read `index.md` to understand current pages and summaries.
3. Read `log.md` and `hot.md` for recent activity and active threads.
4. Search for existing related pages before creating new pages.
5. Choose page families from `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.
6. Prefer merge/update when an existing page already covers the concept.

## Write Pages

1. Write staged or formal pages according to the target vault contract.
2. Apply the page template, merge-before-create rule, and body rules from `wiki-writing-standard.md`.
3. Apply `paper-wiki-language`: write natural Chinese research-wiki prose, avoid machine-translation headings, and keep terminology stable.
4. Preserve source support status and evidence addresses.
5. Put only Obsidian wikilinks to original paper PDFs in frontmatter `sources`, each displayed as the paper slug: `"[[_epi/raw/papers/<slug>/paper.pdf|<slug>]]"`, not plain path text, a Markdown link, an alias such as `原论文 PDF`, or metadata/MinerU/DOI/arXiv entries.
6. Add Obsidian wikilinks from new pages to existing related pages.
7. Add `relationships:` frontmatter entries only when direction and type are clear.
8. Keep formula and figure claims tied to formula or figure evidence.
9. Write or update `final-source-review.json`.
10. Run `workflows/check-wiki.md` after writing as the post-task check.

## Tracking

Update the wiki tracking surface when the target vault contract expects it:

- update manifest / `.manifest.json` with source paths, hashes, and pages written
- update `index.md` for created or materially updated pages
- append a concise `log.md` entry
- refresh `hot.md` with the conceptual change, not a file list

Tell the user which EPI `record-wiki-ingest` command remains.

Stop when source artifacts are missing and point back to EPI `paper-gate`.

## QMD Compatibility

QMD is an optional accelerator after the source-first plan is built from the Markdown vault. Use QMD only to improve lookup and discoverability. After writing or staging pages, run or recommend `qmd update` and `qmd embed` when QMD is installed and the target vault allows it. If QMD is unavailable, stale, slow, or noisy, fallback to manifest, `.manifest.json`, `index.md`, `log.md`, `hot.md`, and direct file search; do not block on qmd query.

## Post-Task Check

Run `workflows/check-wiki.md` after writing. The post-task check must cover broken wikilinks, orphan pages, missing frontmatter, provenance drift, QMD refresh status, stale tracking files, staged review state, `final-source-review.json`, and whether EPI `record-wiki-ingest` remains.
