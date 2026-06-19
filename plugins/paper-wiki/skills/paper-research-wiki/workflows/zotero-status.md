# Zotero Status And Dry Run

Use when the user asks for Paper Wiki Zotero status, Zotero sync dry-run, Zotero-only library items, or repair recommendations before apply.

This workflow is read-only by default. It scans formal `references/*.md` pages, reads existing nested `zotero:` metadata, calls the official Zotero helper only through the Paper Wiki adapter read commands, and reports the current sync health or future apply plan. It does not write formal pages, `_meta/reference-index.json`, `references.bib`, Zotero items, Paper Source sidecars, or sync report files unless the user explicitly requests a persisted diagnostic output.

## Modes

- Status: summarize linked/imported/unlinked/conflict/unavailable states, validate existing `zotero.item_key` links when Zotero read paths are available, and recommend repair actions.
- Dry-run: include status plus proposed future actions such as `link_existing`, `ready_for_import`, `needs_metadata_supplementation`, `review_conflict`, and `wait_for_zotero`.

## Matching Rules

Match priority is DOI exact, then arXiv base ID exact, then normalized title + year + first author. DOI/arXiv matches must be validated through a safe official-helper read path such as single-item BibTeX export. Title-only or low-confidence matches are review/conflict candidates, not automatic links.

One wiki page matching multiple Zotero items reports `conflict_multiple_zotero_items`. Multiple wiki pages matching one Zotero item reports `conflict_multiple_wiki_pages`.

Missing DOI/arXiv pages are `needs_metadata_supplementation`; metadata search, LLM validation, write-back, snapshots, imports, and `references.bib` refresh belong to the later apply workflow.

## Zotero-Only Output

Zotero-only means a top-level bibliographic Zotero item exists in the user's whole local Zotero library but does not match a formal Paper Wiki reference page. Do not read child attachments, local file paths, or attachment full text by default.

Default session output is a readable summary plus the top 20 actionable Zotero-only items with title, creators/authors, year, Zotero item key, identity/status, and recommended next action. Full Zotero-only output requires an explicit expand/export or write-report request.

## Warning Gates

Helper and Zotero availability problems remain visible warnings in session output and structured payloads:

- `zotero_plugin_missing`
- `zotero_helper_incompatible`
- `zotero_desktop_unavailable`
- `local_api_disabled`
- `connector_unavailable`
- `selected_target_mismatch`
- `zotero_timeout`
- `zotero_invalid_json`

For status/dry-run, selected target mismatch is a future-apply blocker, not a blocker for read-only local page scanning. Tell the user to select the fixed `Paper Wiki` collection in Zotero before apply.

## Report Shape

Return human-readable session output first. Raw JSON is only for explicit machine-readable requests.

The internal plan schema is `paper-wiki-zotero-dry-run-v1` and includes mode, vault, target collection, helper status, summary counts, item outcomes, Zotero-only shown/truncated state, gates, and `writes_performed=false`.

Persisted diagnostics require an explicit path or write-report request. A persisted dry-run diagnostic is not an apply report and must not update `_meta/zotero-sync/index.json`.
