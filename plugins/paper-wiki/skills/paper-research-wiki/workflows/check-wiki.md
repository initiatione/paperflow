# Check Wiki

Use when the user asks to detect or inspect the Paper Wiki library. Also run it as preflight for vague deposition requests and as the post-task check after every write, repair, relink, redo, or staged deposition.

This adapts Ar9av/obsidian-wiki `wiki-status` and `wiki-lint`: report state, delta, and next action instead of raw JSON. Read `../../../rules/wiki-writing-standard.md` before reporting health.

## Scope

Check the target vault contract, pending Paper Source handoffs, staged pages, source-review sidecars, graph health, and QMD compatibility.

- Bootstrap: core `_paper_source` roots (`_paper_source/`, `_paper_source/raw/`, `_paper_source/staging/`, `_paper_source/meta/`, `_paper_source/policies/`), `_meta/`, `.obsidian`, `.git`, and seven formal page roots. Paper Source `runs`, `cache`, `tmp`, `tmp-manual-pdfs`, `quarantine`, and `evolution` are on-demand, not bootstrap requirements.
- Handoffs: pending Paper Source handoffs using `_paper_source/staging/papers/*/wiki-ingest-brief.json` as canonical; legacy `_epi/.../wiki-ingest-brief.json` is fallback; task-only `wiki_deposition_task.json` means brief repair is needed.
- Formal graph: orphan pages, broken wikilinks, ambiguous aliases, duplicate concept owners, duplicate concept candidates, forbidden internal links from formal pages into `_paper_source/`, legacy `_epi/`, `_raw/`, `_staging/`, `_runs/`, `_quarantine/`, or `.obsidian/`, plus relationship direction and relationship type mistakes.
- Provenance: missing `final-source-review.json`, sidecar hashes in `final-source-review.json` and previous `wiki-ingest-record.json`, provenance gaps, weak evidence addresses, formula/figure review gaps, page template drift, stale tags/aliases, fragmented tag clusters, stale core pages, and staged writes waiting for review.
- QMD: status of QMD, whether `qmd update` and `qmd embed` should run, lookup reliability, fallback to manifest, `.manifest.json`, `index.md`, `log.md`, `hot.md`, and direct file search; do not block on qmd query.

## Check Levels

Use Quick + Targeted by default.

- Quick check: read manifest or `.manifest.json`, `index.md`, `log.md`, `hot.md`, pending handoffs, recent changed pages, staged pages, and bootstrap structure.
- Targeted check: scan only the current source, concept, tag, alias, page-family, backlink, outlink, and relationship neighborhood.
- Full check: scan the whole formal graph only on explicit audit requests or when Quick + Targeted finds systemic link/tag chaos.

## Report Shape

Return:

1. Overview: target vault, pending Paper Source handoffs, ready papers, blocked papers, already recorded papers.
2. Wiki health: orphan pages, broken wikilinks, ambiguous aliases, duplicate concept owners, forbidden internal links, missing frontmatter, relationship direction issues, provenance gaps, stale pages, staged writes.
3. Paper-specific gaps: missing `final-source-review.json`, weak evidence addresses, formula/figure review gaps, template drift.
4. Bootstrap gaps: missing vault structure that requires Paper Source `wiki-setup`; Paper Wiki should not initialize or reset the vault.
5. QMD compatibility: used, skipped, `qmd update` / `qmd embed` needed, or fallback used.
6. What to Do Next: no more than six ranked actions.
7. Completion Report when post-task: pages created or updated, links/tags/aliases repaired, tracking files updated, QMD refreshed / skipped / failed with fallback, remaining risks, and next Paper Source/Paper Wiki action.

## What to Do Next

Rank actions in this order: run Paper Source `wiki-setup` for blocking bootstrap gaps; deposit ready Paper Source papers; ask for human approval when `paper-gate` says that is the only blocker; repair missing source artifacts through Paper Source; review staged writes; fix broken wikilinks or orphan pages; run update/relink maintenance for stale tags, aliases, or fragmented clusters.

## Post-Task Check

As a post-task check, re-read changed pages and their reverse dependencies, tracking files, and touched Paper Source sidecars. Confirm broken wikilinks, ambiguous aliases, duplicate concept owners, forbidden internal links, relationship direction issues, frontmatter, provenance, sidecar hashes, QMD refresh status, and `final-source-review.json` before reporting completion.

Do not output raw JSON unless the user asks.
