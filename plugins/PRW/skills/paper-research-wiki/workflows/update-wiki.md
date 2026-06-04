# Update Wiki

Use this when the user asks to update, repair, continue, or relink the paper wiki library.

This workflow adapts Ar9av/obsidian-wiki `wiki-update`, `cross-linker`, `wiki-lint`, and `tag-taxonomy` for paper wiki maintenance.

1. Run the check workflow first.
2. Continue safe pending deposition for ready EPI papers.
3. Repair staged pages with lint or provenance gaps.
4. Refresh links, tags, aliases, and duplicate-page decisions.
5. Run relink/cross-link cleanup only after preserving evidence addresses.
6. Stop before destructive reset or ambiguous merge.
7. Preserve EPI boundaries for human approval and `record-wiki-ingest`.

## Relink And Maintenance

Use these internal patterns:

- cross-linker: find missing wikilinks, orphan pages, and bidirectional paper-concept links.
- tag-taxonomy: normalize tags and aliases against the target vault taxonomy.
- wiki-lint: check broken wikilinks, missing frontmatter, stale pages, provenance drift, and fragmented tag clusters.
- staged review: keep staged writes separate until human review when the vault contract requires it.

For missing wikilinks, add links conservatively: first natural mention inline, then a `Related` section if no natural mention exists.

For aliases and tag fixes, preserve canonical paper terminology and do not erase source-specific terms that the paper itself uses.

Ask one confirmation question before any write-heavy relink, tag normalization, staged repair, or page merge. A reply of `默认` means apply the recommended safe next step.
