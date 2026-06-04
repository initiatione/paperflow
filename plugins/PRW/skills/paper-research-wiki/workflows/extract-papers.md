# Extract Papers

Use this when the user asks to extract, process, or deposit EPI-collected papers.

This workflow adapts Ar9av/obsidian-wiki `wiki-ingest`: do not summarize papers in isolation. Instead, distill and integrate source-grounded paper knowledge into the existing wiki graph.

## Preflight

1. Resolve the target vault.
2. Read target vault `AGENTS.md`, `_meta/schema.md`, `_meta/taxonomy.md`, and `_meta/directory-structure.md` when present.
3. Locate `_epi/staging/papers/*/wiki_deposition_task.json`.
4. Run a readiness preflight and group papers as ready, needs human approval, blocked, or already recorded.
5. For ready papers, read source bundle artifacts before writing: PDF, metadata, MinerU Markdown, TeX, images, manifest, reading report, and `wiki-ingest-brief.json`.

## Plan Wiki Updates

1. Read the target vault `manifest` or `.manifest.json` to avoid duplicate source ingestion.
2. Read `index.md` to understand current pages and summaries.
3. Read `log.md` and `hot.md` for recent activity and active threads.
4. Search for existing related pages before creating new pages.
5. Choose page families from `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.
6. Prefer merge/update when an existing page already covers the concept.

## Write Pages

1. Write staged or formal pages according to the target vault contract.
2. Preserve source support status and evidence addresses.
3. Add Obsidian wikilinks from new pages to existing related pages.
4. Add `relationships:` frontmatter entries only when direction and type are clear.
5. Keep formula and figure claims tied to formula or figure evidence.
6. Write or update `final-source-review.json`.

## Tracking

Update the wiki tracking surface when the target vault contract expects it:

- update manifest / `.manifest.json` with source paths, hashes, and pages written
- update `index.md` for created or materially updated pages
- append a concise `log.md` entry
- refresh `hot.md` with the conceptual change, not a file list

Tell the user which EPI `record-wiki-ingest` command remains.

Stop when source artifacts are missing and point back to EPI `paper-gate`.
