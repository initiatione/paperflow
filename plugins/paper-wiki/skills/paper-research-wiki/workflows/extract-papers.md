# Extract Papers

Use when the user asks to extract, process, or deposit Paper Source-collected papers.

This workflow adapts Ar9av/obsidian-wiki `wiki-ingest`: Do not summarize papers in isolation; distill and integrate source-grounded paper knowledge into the existing wiki graph.

Before planning or writing, read `../../../rules/wiki-writing-standard.md`, `../../paper-wiki-language/SKILL.md`, and for `references/` pages `../references/references-page-anatomy.md`. Survey/review papers use `../references/survey-page-anatomy.md`: taxonomy -> `concepts/`, landscape -> `synthesis/`, gaps -> `opportunities/`; do not spawn `derivations/` from borrowed formulas or `experiments/` from second-hand results.

## Preflight

1. Resolve the target vault and check Paper Source `wiki-setup` bootstrap: core `_paper_source` roots, `_meta/`, `.obsidian`, `.git`, and seven formal roots. If missing core vault structure blocks safe work, stop and point to Paper Source `wiki-setup`; Paper Wiki does not initialize or reset. On-demand `_paper_source/runs|cache|tmp|tmp-manual-pdfs|quarantine|evolution` are not bootstrap requirements.
2. Read target `AGENTS.md`, `_meta/schema.md`, `_meta/taxonomy.md`, and `_meta/directory-structure.md` when present.
3. Locate `_paper_source/staging/papers/*/wiki-ingest-brief.json` as the only Paper Source-to-Paper Wiki handoff contract.
4. Treat Paper Source handoffs as paper-level deduplicated before they reach Paper Wiki; do graph-level merge-before-create against existing formal pages instead of paper deduplication.
5. Group papers as ready, automation-approved ready, needs human approval, blocked-source-artifacts, or graph-conflict. Ordinary approval-waiting handoff stops before formal page writes until Paper Source approval exists. Explicit Codex automation can continue only when Paper Source `wiki-agent-trigger.json` carries `automation_handoff` and `approved_by=codex-automation:<task-id>`.
6. For ready papers, read metadata, MinerU Markdown, images, manifest, figure/formula indexes, reading report, and `wiki-ingest-brief.json`; use PDF, indexes, and image evidence only as fallback when MinerU Markdown is missing, wrong, ambiguous, or insufficient. Non-empty native `mineru/paper.tex` is optional cross-check only.

## Plan

Read manifest or `.manifest.json`, `index.md`, `log.md`, and `hot.md`; search existing related pages before creating new pages; choose among `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`; prefer merge/update when an existing page already covers the concept.

## Write Pages

1. Write staged or formal pages according to the target vault contract, applying `wiki-writing-standard.md`, merge-before-create, and `paper-wiki-language`.
2. Preserve support status, evidence addresses, formula/figure grounding, and `relationships:` only when direction/type are clear.
3. Frontmatter `sources:` must be title-display Markdown links to canonical source PDFs. `references/ pages` use exactly one source PDF link: `[<paper title>](obsidian://open?vault=<vault>&file=_paper_source%2Fraw%2F<slug>%2Fpaper.pdf)`. Non-reference families use one or more title-display source PDF links for materially used papers.
4. Use `_paper_source/raw/<slug>/paper.pdf`, no `papers/` segment. In `## 原文与证据入口`, use the same canonical PDF URI with the paper title as clickable text, not `原论文 PDF`.
5. Do not write `[[...]]` wikilinks, plain/relative PDF paths, DOI/arXiv URLs, GitHub URLs, metadata paths, MinerU paths, or figure paths in frontmatter `sources`. Do not write `[[...]]` wikilinks to `_paper_source/` from frontmatter or formal-page body links.
6. Link only to existing formal pages; keep internal evidence paths as URI, file URL, code, or plain text.
7. Write or update `final-source-review.json`.
8. Run `workflows/check-wiki.md` after writing as the post-task check.

## Tracking

When the vault contract expects it, update manifest / `.manifest.json`, `index.md`, `log.md`, and `hot.md` with source paths, hashes, pages written, and conceptual change.

Write `_paper_source/staging/papers/<paper-slug>/paper-wiki-record-request.json` when formal pages and `final-source-review.json` are ready for Paper Source record. Include `schema_version: paper-wiki-record-request-v1`, `automation_mode: ask`, final page paths/hashes, `final-source-review.json` path/hash, `human_approval.approved_by`, and `record-wiki-ingest --from-paper-wiki-request _paper_source/staging/papers/<paper-slug>/paper-wiki-record-request.json`; Paper Wiki writes the request artifact; Paper Source consumes it. Stop when source artifacts are missing and point back to Paper Source `paper-gate`. Paper Wiki does not write `human-approval.json`, does not write `wiki-agent-trigger.json`, and does not write or replace `wiki-ingest-record.json`.

## QMD Compatibility

QMD is optional. Use it only after the source-first Markdown plan; after writes or staged pages, run or recommend `qmd update` and `qmd embed` when installed and allowed. If unavailable, stale, slow, or noisy, fallback to manifest, `.manifest.json`, `index.md`, `log.md`, `hot.md`, and direct file search; do not block on qmd query.

## Post-Task Check

Run `workflows/check-wiki.md` after writing. Cover broken wikilinks, orphan pages, missing frontmatter, provenance drift, QMD refresh status, stale tracking files, staged review state, `final-source-review.json`, and whether Paper Source `record-wiki-ingest` remains.
