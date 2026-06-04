# Update Wiki

Use this when the user asks to update, repair, continue, or relink the paper wiki library.

This workflow adapts Ar9av/obsidian-wiki `wiki-update`, `cross-linker`, `wiki-lint`, and `tag-taxonomy` for paper wiki maintenance.

Read `../../../rules/wiki-writing-standard.md` first. For repairs that touch formal page prose, also read `../../paper-wiki-language/SKILL.md`. Repairs must move pages toward those standards, not merely make tests pass.

1. Run the check workflow first.
2. Continue safe pending deposition for ready EPI papers.
3. Repair staged pages with lint or provenance gaps.
4. Repair page template, required frontmatter, source/provenance, tracking-file drift, and language-style drift against `wiki-writing-standard.md` and `paper-wiki-language`.
5. Refresh links, tags, aliases, and duplicate-page decisions.
6. Run relink/cross-link cleanup only after preserving evidence addresses.
7. Stop before destructive reset or ambiguous merge.
8. Preserve EPI boundaries for human approval and `record-wiki-ingest`.
9. Run `workflows/check-wiki.md` after writing as the post-task check.

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

After confirmed maintenance writes, run the post-task check. Run `workflows/check-wiki.md` after writing and report broken wikilinks, ambiguous aliases, duplicate concept owners, forbidden internal links, relationship direction issues, QMD refresh status, stale tracking files, and remaining EPI `record-wiki-ingest` work.
