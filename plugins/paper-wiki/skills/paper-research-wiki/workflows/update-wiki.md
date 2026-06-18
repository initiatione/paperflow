# Update Wiki

Use when the user asks to update, repair, continue, relink, 重link, 重写某页, 重写页面, rewrite formal page, or rewrite page. This workflow adapts Ar9av/obsidian-wiki `wiki-update`, `cross-linker`, `wiki-lint`, and `tag-taxonomy` for Paper Wiki.

Read `../../../rules/wiki-writing-standard.md` first. For repairs touching formal prose, also read `../../paper-wiki-language/SKILL.md`. Run check first, repair in small batches, preserve evidence addresses, and Run `workflows/check-wiki.md` after writing as the post-task check.

Default order: continue ready Paper Source deposition, repair staged pages, fix page template/frontmatter/source/provenance/tracking drift, refresh links/tags/aliases/duplicate-page decisions, then stop before destructive reset or ambiguous merge. Paper Source owns human approval records and `record-wiki-ingest`.

## Obsidian Graph Visibility Repair

Use this lightweight path when the user reports "关系图谱出错", "图谱只剩 index", "graph only index", or another display-level graph failure and no formal page claims need rewriting.

1. Run `workflows/check-wiki.md` first and separate display/config drift from content graph drift.
2. If `.obsidian/graph.json` exists, set the global `search` value to `""` and keep unrelated visual preferences. Remove old formal-root regex filters such as `path:/^index\\.md$/ OR path:/^references\\\\// ...`; they are known to drift and can hide all nodes except `index`.
3. If `.obsidian/app.json` exists, merge `userIgnoreFilters` so `_paper_source/`, target-vault retired internal roots, `_meta/`, `.claude/`, `AGENTS.md`, `hot.md`, and `log.md` stay hidden. Preserve user-added ignore filters and unrelated app preferences.
4. If `.obsidian/` is missing, report a bootstrap gap and route to Paper Source `wiki-setup`; Paper Wiki does not initialize or reset vault structure.
5. Run a Markdown formal graph scan after config repair: visible formal Markdown node count, wikilink edge count, broken visible wikilinks, forbidden internal wikilinks, and orphan pages when relevant.
6. If files are healthy but Obsidian still shows only `index`, tell the user to close/reopen the Graph tab or reload Obsidian; live UI keys such as `close` are not a content failure.
7. Do not take a formal-page snapshot, refresh `final-source-review.json`, or create `paper-wiki-record-request.json` for display-only config repair. Escalate to Link Repair Triage only when the Markdown scan shows content graph drift.

## Frontmatter-Only Metadata Repair

Use this lightweight path only when metadata changes do not alter claims, formulas, figure/table evidence, evidence tier, relationships, semantic aliases, lifecycle, or body prose.

1. Confirm the formal page and source paper identity are unchanged.
2. Verify against Paper Source artifacts such as `_paper_source/raw/<slug>/code-verification.json`, metadata, or prior source review; otherwise do one targeted repository/DOI/arXiv check and report whether the code was run locally.
3. Add a verified `github:` property only when supported. Preserve `sources:` as title-display Markdown links to the canonical source PDFs; repository links belong in `github:` or body evidence.
4. do not add GitHub, DOI, arXiv, README, metadata, MinerU paths, figure paths, plain/relative PDF paths, internal wikilinks, or non-PDF URLs to frontmatter `sources:`.
5. Do not automatically run the full graph-aware rewrite path, dependent-page rewrite, `final-source-review.json` refresh, or `paper-wiki-record-request.json` creation. Escalate to Graph-Aware Rewrite only if the metadata changes a claim, evidence boundary, relationship, lifecycle, or downstream synthesis.
6. Still run a targeted post-task check for frontmatter validity, changed paths, source PDF link preservation, and next Paper Source/Paper Wiki action.

## Graph-Aware Rewrite

Use for material rewrite work. A graph-aware rewrite treats the target page and dependent formal pages as one transaction.

1. Verify the pre-rewrite snapshot exists.
2. Read the target page, `relationships:`, `sources:`, outlinks, backlinks, manifest or `.manifest.json`, previous `final-source-review.json`, previous `wiki-ingest-record.json`, `index.md`, `log.md`, and `hot.md`.
3. Build reverse dependencies: pages that cite, link to, derive from, summarize, compare, or list the target page.
4. references/ pages are evidence source nodes; if one changes, inspect dependent `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.
5. Update dependent pages when these triggers apply: Claim/evidence boundary changes; Formula or figure/table evidence changes; Evidence-tier changes; Relationship or reusable-knowledge changes; Hash/provenance drift.
6. Create a new `derivations/` or `concepts/` node when reusable knowledge would otherwise stay trapped in one reference page.
7. Refresh manifest or `.manifest.json`, `_meta/reference-index.json` when `references/` pages changed, `final-source-review.json`, `index.md`, `log.md`, and `hot.md`; read previous `wiki-ingest-record.json` only as provenance and reverse-dependency evidence.
8. Report Paper Source record readiness. Paper Wiki records readiness; Paper Source writes or replaces `wiki-ingest-record.json` through `record-wiki-ingest`. If pages are record-ready, write `_paper_source/staging/papers/<paper-slug>/paper-wiki-record-request.json` with `schema_version: paper-wiki-record-request-v1`, `automation_mode: ask`, final page hashes, `final-source-review.json` hash, and `record-wiki-ingest --from-paper-wiki-request ...`; Paper Wiki writes the request artifact; Paper Source consumes it.
9. Run or report `qmd update` and `qmd embed`; confirm `_paper_source/` remains outside the formal graph/index.

Graph-aware updates also operate as the formal knowledge maintenance layer: maintain formal page content relationships, content relationship maintenance, claim staleness, split or merge pages, reverse dependencies, evidence-tier drift, derived concepts, derivations, and synthesis.

## Link Repair Triage

When the wiki has link chaos, Scan formal pages in the seven allowed page families; build a canonical page map and alias map from titles, aliases, tags, `sources:`, `relationships:`, English/Chinese names, abbreviations, DOI/arXiv IDs, method names, paper terms, and spelling variants; identify missing wikilinks, broken wikilinks, orphan pages, ambiguous aliases, duplicate pages, duplicate concept owners, forbidden internal links, stale redirects, relationship drift, and relationship direction/type mistakes; generate a repair plan separating low-risk additions from merge, split, rename, or canonical slug changes; repair in small batches while preserving support labels, formulas, figure references, and page-family boundaries; use a staging patch and ask one confirmation for high-risk operations; after each batch, rerun the post-task check. Do not use link repair to compensate for a bad Obsidian graph search filter; fix graph visibility config first, then repair content links only if the Markdown scan is unhealthy.

Use QMD only after reading the Markdown vault inventory. If installed and responsive, use it to accelerate lookup, then refresh after writes with `qmd update` and `qmd embed`. If QMD is missing, stale, slow, or noisy, fallback to manifest, `.manifest.json`, `index.md`, `log.md`, `hot.md`, and direct file search; do not block on qmd query.

After confirmed maintenance writes, report graph display config status when relevant, broken wikilinks, ambiguous aliases, duplicate concept owners, forbidden internal links, relationship direction issues, `_meta/reference-index.json` refresh/verification status, QMD refresh status, stale tracking files, and remaining Paper Source `record-wiki-ingest` work.
