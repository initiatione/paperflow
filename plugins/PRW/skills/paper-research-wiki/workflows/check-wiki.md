# Check Wiki

Use this when the user asks to detect or inspect the paper wiki library. Also run it as the preflight for vague EPI deposition requests and as the post-task check after every PRW write, repair, relink, redo, or staged deposition.

This workflow adapts Ar9av/obsidian-wiki `wiki-status` and `wiki-lint`: report current state, delta, and the next useful action instead of dumping raw JSON.

Read `../../../rules/wiki-writing-standard.md` before reporting health. Use it as the checklist for whether PRW-written pages are standardized enough to record back into EPI.

Check:

- bootstrap contract from EPI `wiki-setup`: `_epi/`, `_meta/`, `.obsidian`, `.git`, and the seven formal page roots
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
- ambiguous aliases
- duplicate concept owners
- forbidden internal links from formal pages into `_epi/`, `_raw/`, `_staging/`, `_runs/`, `_quarantine/`, or `.obsidian/`
- relationship direction and relationship type mistakes
- staged writes waiting for review
- stale core pages
- fragmented tag clusters
- wiki-writing-standard.md compliance
- QMD status, including whether `qmd update` and `qmd embed` should be run
- QMD lookup reliability; do not block on qmd query, and fallback to manifest, `.manifest.json`, `index.md`, `log.md`, `hot.md`, and direct file search

## Check Levels

Use Quick + Targeted by default.

- Quick check: read manifest or `.manifest.json`, `index.md`, `log.md`, `hot.md`, pending EPI handoffs, recent changed pages, current staged pages, and whether the EPI `wiki-setup` bootstrap structure exists.
- Targeted check: scan only the current source, concept, tag, alias, page-family, backlink, outlink, and relationship neighborhood affected by the task.
- Full check: scan the whole formal wiki graph only when the user asks for a comprehensive audit or when Quick + Targeted finds systemic link/tag chaos.

## Report Shape

Return:

1. Overview: target vault, pending EPI handoffs, ready papers, blocked papers, already recorded papers.
2. Wiki health: orphan pages, broken wikilinks, ambiguous aliases, duplicate concept owners, forbidden internal links, missing frontmatter, relationship direction issues, provenance gaps, stale pages, staged writes.
3. Paper-specific gaps: missing `final-source-review.json`, weak evidence addresses, formula/figure review gaps, page template drift.
4. Bootstrap gaps: any missing vault structure that requires EPI `wiki-setup`; PRW should not initialize or reset the vault.
5. QMD compatibility: whether QMD was used, whether QMD was skipped, whether `qmd update` / `qmd embed` should run, and whether fallback to manifest and file search was used.
6. What to Do Next: a ranked list of no more than six actions.
7. Completion Report when this is a post-task check: pages created or updated, links/tags/aliases repaired, tracking files updated, QMD refreshed / skipped / failed with fallback, remaining risks, and next EPI/PRW action.

## What to Do Next

Rank actions in this order:

1. Run EPI `wiki-setup` when missing vault structure prevents safe paper wiki work.
2. Deposit ready EPI papers.
3. Ask for human approval when `paper-gate` says approval is the only blocker.
4. Repair missing source artifacts through EPI.
5. Review staged writes.
6. Fix broken wikilinks or orphan pages.
7. Run update/relink maintenance for stale tags, aliases, or fragmented clusters.

## QMD Compatibility

Use QMD only as an accelerator. If it is available and fast enough, use it to check retrieval freshness. After write-heavy tasks, recommend or run `qmd update` and `qmd embed` when the target vault contract allows it. If QMD is unavailable, slow, stale, or noisy, fallback to manifest, `.manifest.json`, `index.md`, `log.md`, `hot.md`, and direct file search; do not block on qmd query.

## Post-Task Check

As a post-task check, re-read the changed page set, tracking files, and any touched EPI sidecars. Confirm broken wikilinks, ambiguous aliases, duplicate concept owners, forbidden internal links, relationship direction issues, frontmatter, provenance, QMD refresh status, and `final-source-review.json` before reporting completion.

## Completion Report

When reporting a completed PRW task, include:

- pages created or updated
- links/tags/aliases repaired
- tracking files updated
- QMD refreshed / skipped / failed with fallback
- remaining risks
- next EPI/PRW action

Do not output raw JSON unless the user asks.
