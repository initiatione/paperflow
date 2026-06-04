# Check Wiki

Use this when the user asks to detect or inspect the paper wiki library. Also run it as the preflight for vague EPI deposition requests.

This workflow adapts Ar9av/obsidian-wiki `wiki-status` and `wiki-lint`: report current state, delta, and the next useful action instead of dumping raw JSON.

Check:

- target vault contract files
- pending EPI handoffs
- staged pages
- missing `final-source-review.json`
- lint failures
- duplicate concept candidates
- provenance gaps
- stale tags or aliases
- relink and cross-link opportunities
- orphan pages
- broken wikilinks
- staged writes waiting for review
- stale core pages
- fragmented tag clusters

## Report Shape

Return:

1. Overview: target vault, pending EPI handoffs, ready papers, blocked papers, already recorded papers.
2. Wiki health: orphan pages, broken wikilinks, missing frontmatter, provenance gaps, stale pages, staged writes.
3. Paper-specific gaps: missing `final-source-review.json`, weak evidence addresses, formula/figure review gaps.
4. What to Do Next: a ranked list of no more than six actions.

## What to Do Next

Rank actions in this order:

1. Deposit ready EPI papers.
2. Ask for human approval when `paper-gate` says approval is the only blocker.
3. Repair missing source artifacts through EPI.
4. Review staged writes.
5. Fix broken wikilinks or orphan pages.
6. Run update/relink maintenance for stale tags, aliases, or fragmented clusters.

Do not output raw JSON unless the user asks.
