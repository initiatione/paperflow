# Check Wiki

Use when the user asks to detect or inspect the Paper Wiki library. Also run it as preflight for vague deposition requests and as the post-task check after every write, repair, relink, redo, or staged deposition.

This adapts Ar9av/obsidian-wiki `wiki-status` and `wiki-lint`: report state, delta, and next action instead of raw JSON. Read `../../../rules/wiki-writing-standard.md` before reporting health.

## Scope

Check the target vault contract, pending Paper Source handoffs, staged pages, source-review sidecars, `_meta/reference-index.json`, graph health, and QMD compatibility.

- Bootstrap: core `_paper_source` roots (`_paper_source/`, `_paper_source/raw/`, `_paper_source/staging/`, `_paper_source/meta/`, `_paper_source/policies/`), `_meta/`, `.obsidian`, `.git`, and seven formal page roots. Paper Source `runs`, `cache`, `tmp`, `tmp-manual-pdfs`, `quarantine`, and `evolution` are on-demand, not bootstrap requirements.
- Handoffs: pending Paper Source handoffs using `_paper_source/staging/papers/*/wiki-ingest-brief.json` as the only Paper Source-to-Paper Wiki handoff contract. Paper Source owns paper-level deduplication before handoff; Paper Wiki checks graph-level integration risks.
- Formal graph content: orphan pages, broken wikilinks, ambiguous aliases, duplicate concept owners, duplicate concept candidates, forbidden internal links from formal pages into `_paper_source/`, `_raw/`, `_staging/`, `_runs/`, `_quarantine/`, or `.obsidian/`, plus relationship direction and relationship type mistakes.
- Obsidian graph display: inspect `.obsidian/graph.json` and `.obsidian/app.json` separately from content links. Healthy display config has `graph.json` global `search` set to `""` and `app.json` `userIgnoreFilters` hiding `_paper_source/`, target-vault retired internal roots, `_meta/`, `.claude/`, `AGENTS.md`, `hot.md`, and `log.md`. Treat old `path:/^index\\.md$/ OR ...` graph search filters as drift because they can collapse the graph to only `index`. Ignore live UI-only keys such as `close` unless they are the user's explicit display preference.
- Provenance: missing `final-source-review.json`, sidecar hashes in `final-source-review.json` and previous `wiki-ingest-record.json`, provenance gaps, weak evidence addresses, formula/figure review gaps, page template drift, stale tags/aliases, fragmented tag clusters, stale core pages, and staged writes waiting for review.
- Reference index: `_meta/reference-index.json` exists, uses `paper-research-reference-index-v1`, includes changed `references/` pages by page/source_id/DOI/arXiv/title dedupe keys, and was refreshed after the current write. This file is the canonical Paper Source dedupe backlog.
- QMD: status of QMD, whether `qmd update` and `qmd embed` should run, lookup reliability, fallback to manifest, `.manifest.json`, `index.md`, `log.md`, `hot.md`, and direct file search; do not block on qmd query.

## Check Levels

Use Quick + Targeted by default.

- Quick check: read manifest or `.manifest.json`, `index.md`, `log.md`, `hot.md`, pending handoffs, recent changed pages, staged pages, and bootstrap structure.
- Targeted check: scan only the current source, concept, tag, alias, page-family, backlink, outlink, and relationship neighborhood.
- Full check: scan the whole formal graph only on explicit audit requests or when Quick + Targeted finds systemic link/tag chaos, or when display repair still leaves the Obsidian graph inconsistent with the Markdown link scan.

## Fast Graph Triage

When the user says the relationship graph is wrong, first decide which layer failed:

1. Display/config drift: `graph.json.search` is non-empty, old path-regex filters are present, required `app.json.userIgnoreFilters` are missing, or Obsidian still shows only `index` while the Markdown scan finds many formal nodes/edges and zero broken wikilinks.
2. Content graph drift: formal-page wikilinks are broken, missing, forbidden, ambiguous, orphaned, or relationship frontmatter conflicts with page links.
3. Runtime/cache drift: files are correct but the open Obsidian Graph tab still shows stale state. Report "close/reopen Graph tab or reload Obsidian" after confirming display config and Markdown link scan are healthy.

For a quick Markdown scan, count visible formal Markdown nodes under the seven formal roots plus `index.md`, count `[[wikilink]]` edges, and resolve targets by full relative path and basename without `.md`. Do not classify `graph.json.close=true` as a graph failure.

## Report Shape

Return:

1. Overview: target vault, pending Paper Source handoffs, ready papers, blocked-source-artifacts, needs-human-approval items, and graph-conflict items.
2. Wiki health: graph display config, visible formal node/edge counts when checked, orphan pages, broken wikilinks, ambiguous aliases, duplicate concept owners, forbidden internal links, missing frontmatter, relationship direction issues, provenance gaps, stale pages, staged writes.
3. Paper-specific gaps: missing `final-source-review.json`, weak evidence addresses, formula/figure review gaps, template drift.
4. Bootstrap gaps: missing vault structure that requires Paper Source `wiki-setup`; Paper Wiki should not initialize or reset the vault.
5. QMD compatibility: used, skipped, `qmd update` / `qmd embed` needed, or fallback used.
6. What to Do Next: no more than six ranked actions.
7. Completion Report when post-task: pages created or updated, links/tags/aliases repaired, tracking files updated, `_meta/reference-index.json` refreshed and verified, QMD refreshed / skipped / failed with fallback, remaining risks, and next Paper Source/Paper Wiki action.

## What to Do Next

Rank actions in this order: run Paper Source `wiki-setup` for blocking bootstrap gaps; repair Obsidian graph display drift when it hides healthy formal content; deposit ready Paper Source papers; ask for human approval when `paper-gate` says that is the only blocker; repair missing source artifacts through Paper Source; review staged writes; fix broken wikilinks or orphan pages; run update/relink maintenance for stale tags, aliases, or fragmented clusters.

## Post-Task Check

As a post-task check, re-read changed pages and their reverse dependencies, tracking files, `_meta/reference-index.json`, touched Paper Source sidecars, and graph display config when `.obsidian` changed or the user reported a graph issue. Confirm `graph.json.search == ""`, required `app.json.userIgnoreFilters`, broken wikilinks, ambiguous aliases, duplicate concept owners, forbidden internal links, relationship direction issues, frontmatter, provenance, sidecar hashes, reference-index freshness, QMD refresh status, and `final-source-review.json` before reporting completion.

Do not output raw JSON unless the user asks.
