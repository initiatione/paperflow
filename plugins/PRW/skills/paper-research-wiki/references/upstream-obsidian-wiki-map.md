# Upstream Obsidian Wiki Map

This plugin adapts Ar9av/obsidian-wiki patterns without exposing every upstream skill.

Ar9av/obsidian-wiki is a design source, not a runtime source of truth. During normal PRW runs, do not fetch or search Ar9av/obsidian-wiki. Use the local PRW workflows, references, rules, and the target vault contract as the executable contract. Consult the upstream repository only when maintaining PRW, auditing drift, or deliberately upgrading the adapted rules.

- `wiki-ingest` pattern -> extract papers workflow
- `wiki-status` and `wiki-query` pattern -> check wiki workflow
- `wiki-update` pattern -> update wiki workflow
- `cross-linker` pattern -> relink/cross-link cleanup inside update wiki
- `tag-taxonomy` pattern -> tag and alias maintenance inside update wiki
- `wiki-lint` pattern -> pre-record quality gate
- provenance, staged writes, and source-first merge decisions -> internal references and rules

## Internalized Repair Patterns

PRW handles link repair locally. Check for broken wikilinks, ambiguous aliases, duplicate concept owners, forbidden internal links from formal pages into `_epi/` or other internal folders, stale redirects, fragmented tags, and relationship direction mistakes before and after maintenance writes.

QMD is optional. If available, use it to accelerate lookup and refresh discoverability with `qmd update` and `qmd embed` after wiki writes. If QMD is missing, stale, slow, or noisy, fallback to manifest, `.manifest.json`, `index.md`, `log.md`, `hot.md`, and direct file search; do not block on qmd query.

Every write-oriented workflow ends with a post-task check: rerun the PRW check workflow, summarize remaining link/provenance/QMD/index issues, and only then tell the user whether EPI `record-wiki-ingest` remains.
