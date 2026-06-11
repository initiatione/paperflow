# Update Wiki

Use this when the user asks to update, repair, continue, or relink the paper wiki library.

This workflow adapts Ar9av/obsidian-wiki `wiki-update`, `cross-linker`, `wiki-lint`, and `tag-taxonomy` for paper wiki maintenance.

Read `../../../rules/wiki-writing-standard.md` first. For repairs that touch formal page prose, also read `../../paper-wiki-language/SKILL.md`. Repairs must move pages toward those standards, not merely make tests pass.

1. Run the check workflow first.
2. Continue safe pending deposition for ready Paper Source papers.
3. Repair staged pages with lint or provenance gaps.
4. Repair page template, required frontmatter, source/provenance, tracking-file drift, and language-style drift against `wiki-writing-standard.md` and `paper-wiki-language`.
5. Refresh links, tags, aliases, and duplicate-page decisions.
6. Run relink/cross-link cleanup only after preserving evidence addresses.
7. Stop before destructive reset or ambiguous merge.
8. Preserve Paper Source boundaries for human approval and `record-wiki-ingest`.
9. Run `workflows/check-wiki.md` after writing as the post-task check.

## Frontmatter-Only Metadata Repair

Use this lightweight path when the user asks only to add or repair formal page metadata that does not change claims, formulas, figure/table evidence, evidence tier, relationships, aliases with semantic impact, lifecycle, or page body prose. Typical examples are adding a verified `github:` property for a code-bearing paper, normalizing a non-semantic property value, or exposing an already-verified repository link in the page properties.

1. Confirm the target page already exists and the source paper identity is unchanged.
2. Verify the metadata against an existing Paper Source artifact when available, such as `_paper_source/raw/<slug>/code-verification.json`, metadata, or prior source review. If no source artifact exists, perform one targeted repository/DOI/arXiv check and record the verification boundary in the completion report.
3. Keep `sources:` as scan-friendly short source labels. Put the full clickable PDF URI in the body `## 原文与证据入口`. Put repository links in `github:` or the page body evidence section; do not add GitHub, DOI, arXiv, README, metadata, MinerU paths, PDF paths, or Markdown links to frontmatter `sources:`.
4. Do not automatically run the full graph-aware rewrite path, dependent-page rewrite, `final-source-review.json` refresh, or `paper-wiki-record-request.json` creation for a metadata-only repair. Escalate to Graph-Aware Rewrite only if the metadata changes a claim, evidence boundary, relationship, lifecycle, or downstream synthesis.
5. Still run a targeted post-task check for frontmatter validity, changed file paths, source PDF link preservation, and the next Paper Source/Paper Wiki action.

## Graph-Aware Rewrite

Use this path when the user asks to 重写某页, 重写页面, rewrite formal page, rewrite page, or when an update is a material rewrite of a formal page. A graph-aware rewrite treats the target page and its dependent formal pages as one transaction.

1. Verify the required pre-rewrite snapshot exists before editing formal pages.
2. Read the target page, its frontmatter `relationships:`, `sources:`, outgoing wikilinks, backlinks, manifest or `.manifest.json` entries, previous `final-source-review.json`, previous `wiki-ingest-record.json`, `index.md`, `log.md`, and `hot.md`.
3. Build the reverse dependencies: pages that cite, link to, derive from, summarize, compare, or list the target page.
4. Treat references/ pages are evidence source nodes. If a `references/` page changes, inspect dependent `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/` pages.
5. Update dependent formal pages when any trigger applies:
   - Claim/evidence boundary changes.
   - Formula or figure/table evidence changes.
   - Evidence-tier changes, such as simulation, pool-trial, lake/field-like experiment, or sea-trial wording.
   - Relationship or reusable-knowledge changes, including new formulas, mechanisms, metrics, datasets, or distinctions.
   - Hash/provenance drift after markdown edits.
6. Create a new `derivations/` or `concepts/` node when reusable knowledge would otherwise remain trapped inside one reference page.
7. Refresh manifest or `.manifest.json`, `final-source-review.json`, `index.md`, `log.md`, and `hot.md` in the same run. Read previous `wiki-ingest-record.json` only as provenance and reverse-dependency evidence.
8. Report Paper Source record readiness. Paper Wiki records readiness; Paper Source writes or replaces `wiki-ingest-record.json` through `record-wiki-ingest`. If the update leaves pages record-ready, write `_paper_source/staging/papers/<paper-slug>/paper-wiki-record-request.json` with `schema_version: paper-wiki-record-request-v1`, `automation_mode: ask`, current final page hashes, `final-source-review.json` hash, and `record-wiki-ingest --from-paper-wiki-request ...`; Paper Wiki writes the request artifact; Paper Source consumes it. Legacy `_epi/.../prw-record-request.json` remains accepted only for existing artifacts.
9. Run or report `qmd update` and `qmd embed`; confirm `_paper_source/` and legacy `_epi/` remain outside the formal graph/index when the vault contract requires that boundary.

## Relink And Maintenance

Use these internal patterns:

- cross-linker: find missing wikilinks, orphan pages, and bidirectional paper-concept links.
- tag-taxonomy: normalize tags and aliases against the target vault taxonomy.
- wiki-lint: check broken wikilinks, missing frontmatter, stale pages, provenance drift, and fragmented tag clusters.
- staged review: keep staged writes separate until human review when the vault contract requires it.

For missing wikilinks, add links conservatively: first natural mention inline, then a `Related` section if no natural mention exists.

For aliases and tag fixes, preserve canonical paper terminology and do not erase source-specific terms that the paper itself uses.

## Link Repair Triage

When the wiki has link chaos, triage before editing:

1. Scan formal pages in the seven allowed page families.
2. Build a canonical page map from page titles, aliases, tags, `sources:`, and `relationships:`.
3. Build an alias map from English titles, Chinese names, abbreviations, DOI/arXiv IDs, method names, paper terms, and known spelling variants.
4. Identify broken wikilinks, orphan pages, ambiguous aliases, duplicate pages, duplicate concept owners, forbidden internal links, stale redirects, relationship drift, and relationship direction or relationship type mistakes.
5. Generate a repair plan that separates low-risk link additions from high-risk merge, split, rename, or canonical slug changes.
6. Repair in small batches and preserve evidence addresses, support labels, formulas, figure references, and page-family boundaries.
7. Use a staging patch and ask confirmation for high-risk operations such as merging two concept pages, renaming a canonical slug, or batch replacing links.
8. After each batch, rerun the post-task check before continuing.

## QMD Compatibility

QMD is optional. Use QMD only after reading the Markdown vault inventory. If QMD is installed and responsive, use it to accelerate lookup, then refresh after writes with `qmd update` and `qmd embed`. If QMD is missing, stale, slow, or noisy, fallback to manifest, `.manifest.json`, `index.md`, `log.md`, `hot.md`, and direct file search; do not block on qmd query.

Ask one confirmation question before any write-heavy relink, tag normalization, staged repair, or page merge. A reply of `默认` means apply the recommended safe next step.

After confirmed maintenance writes, run the post-task check. Run `workflows/check-wiki.md` after writing and report broken wikilinks, ambiguous aliases, duplicate concept owners, forbidden internal links, relationship direction issues, QMD refresh status, stale tracking files, and remaining Paper Source `record-wiki-ingest` work.
