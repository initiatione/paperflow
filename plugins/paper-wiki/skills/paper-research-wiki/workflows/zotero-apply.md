# Zotero Apply

Use when the user explicitly asks Paper Wiki to apply an approved Zotero dry-run plan, link formal reference pages to existing Zotero items, import wiki-only papers into Zotero, or refresh wiki-scoped `references.bib`.

This workflow performs writes only after one-run approval for the displayed current plan. Approval must be bound to the plan hash or equivalent immutable plan identity and must not become persistent authorization.

## Write Boundary

Paper Wiki may write:

- nested top-frontmatter `zotero:` metadata on formal `references/*.md` pages;
- allowed bibliographic identity fields (`doi`, `arxiv_id`, `year`, `venue`, `url`, `authors`) when accepted by metadata validation;
- single-page snapshots under `_paper_source/meta/formal-page-snapshots/<run-id>-pre-zotero-sync/` before overwriting existing non-empty bibliographic fields;
- `_meta/reference-index.json`;
- root `references.bib`, composed only from linked/imported Paper Wiki item-level BibTeX records;
- `_meta/zotero-sync/runs/<run-id>.json` and `_meta/zotero-sync/index.json`.

Paper Wiki must not write Paper Source `human-approval.json`, `wiki-agent-trigger.json`, `wiki-ingest-record.json`, or `zotero-record.json`, and must not create, switch, rename, or delete Zotero collections/items.

## Gates

- No approval -> no writes.
- Plan hash mismatch -> no writes and ask for a fresh approval.
- Zotero selected target mismatch -> stop imports and tell the user to select the fixed `Paper Wiki` collection in Zotero.
- Title-only or low-confidence matches -> conflict/review, no auto-link or import.
- Missing DOI/arXiv after supplementation or rejected validation -> skip, no import.

## Apply Order

1. Regenerate the current dry-run/apply plan and summarize write categories/counts.
2. Ask for explicit one-run approval for that plan.
3. Recheck helper status and selected target before imports.
4. Link existing validated DOI/arXiv/high-confidence Zotero matches.
5. Supplement missing bibliographic identity through configured retrieval/search and structured validation.
6. Snapshot affected pages before overwriting existing non-empty bibliographic fields.
7. Import accepted wiki-only papers through the official Zotero helper with write approval.
8. Verify imported item keys through post-import helper reads.
9. Write nested `zotero:` metadata and accepted bibliographic updates.
10. Refresh wiki-scoped `references.bib`, `_meta/reference-index.json`, and sync reports.
11. Run the Paper Wiki post-task check and report QMD skipped/refreshed status.

## Report Shape

Return a readable completion summary first: linked/imported/skipped/conflict/failed counts, selected target status, changed pages, snapshots, `references.bib`, reference-index refresh, sync report path, post-task check status, remaining risks, and marketplace/install-cache caveat when relevant. Raw JSON is only for explicit machine-readable requests.

