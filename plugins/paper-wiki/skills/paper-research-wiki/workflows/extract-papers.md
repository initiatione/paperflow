# Extract Papers

Use this when the user asks to extract, process, or deposit Paper Source-collected papers. `epi` is only a legacy alias for Paper Source.

This workflow adapts Ar9av/obsidian-wiki `wiki-ingest`: do not summarize papers in isolation. Instead, distill and integrate source-grounded paper knowledge into the existing wiki graph.

Before planning or writing pages, read `../../../rules/wiki-writing-standard.md` and `../../paper-wiki-language/SKILL.md`; treat them as mandatory page-writing and language contracts. When writing or repairing `references/` pages, also read `../references/references-page-anatomy.md` — the binding section-by-section references contract.

Detect survey/review papers and route them differently. A paper is a survey/review when any hold: the `method/review` tag is present; the title/venue says review or survey; the body has a PRISMA flow or a taxonomy figure organizing many cited works; or its results are aggregated from cited studies ("no datasets were generated or analysed"). For such papers, write the `references/` page with the **survey map/hub spine** in `../references/survey-page-anatomy.md` (not the method spine), and route durable knowledge to existing families: taxonomy → `concepts/`, cross-method landscape → `synthesis/`, gaps → `opportunities/`. Do not spawn a `derivations/` page from a survey's borrowed illustrative formulas, and do not spawn an `experiments/` page — a survey runs no experiments of its own. A paper that proposes a method and also surveys the field stays a primary paper (method spine).

## Preflight

1. Resolve the target vault.
2. Check the Paper Source `wiki-setup` bootstrap: core `_paper_source` roots (`_paper_source/`, `_paper_source/raw/`, `_paper_source/staging/`, `_paper_source/meta/`, `_paper_source/policies/`), legacy `_epi` roots, `_meta/`, `.obsidian`, `.git`, and the seven formal page roots. If missing core vault structure blocks safe work, stop and point back to Paper Source `wiki-setup`; do not initialize or reset from Paper Wiki. Do not require `_paper_source/runs/`, `_paper_source/cache/`, `_paper_source/tmp/`, `_paper_source/tmp-manual-pdfs/`, `_paper_source/quarantine/`, or `_paper_source/evolution/`; Paper Source creates those on demand.
3. Read target vault `AGENTS.md`, `_meta/schema.md`, `_meta/taxonomy.md`, and `_meta/directory-structure.md` when present.
4. Locate `_paper_source/staging/papers/*/wiki-ingest-brief.json`; this is the canonical Paper Source-to-Paper Wiki handoff. Legacy `_epi/staging/papers/*/wiki-ingest-brief.json` remains readable.
5. Treat `_paper_source/staging/papers/*/wiki_deposition_task.json` and legacy `_epi/staging/papers/*/wiki_deposition_task.json` as compatibility artifacts only. Do not treat task-only legacy handoffs as ready; route them back to Paper Source to regenerate or repair `wiki-ingest-brief.json`.
6. Run a readiness preflight and group papers as ready, needs human approval, blocked, already recorded, or legacy-needs-brief-repair.
7. For ready papers, read source bundle artifacts before writing: metadata, MinerU Markdown, images, manifest, figure/formula indexes, reading report, and `wiki-ingest-brief.json`; use the PDF, indexes, and image evidence as fallback checks when MinerU Markdown is missing, wrong, ambiguous, or insufficient. If non-empty native `mineru/paper.tex` exists, use it only as an optional cross-check.

## Plan Wiki Updates

1. Read the target vault `manifest` or `.manifest.json` to avoid duplicate source ingestion.
2. Read `index.md` to understand current pages and summaries.
3. Read `log.md` and `hot.md` for recent activity and active threads.
4. Search for existing related pages before creating new pages.
5. Choose page families from `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.
6. Prefer merge/update when an existing page already covers the concept.

## Write Pages

1. Write staged or formal pages according to the target vault contract.
2. Apply the page template, merge-before-create rule, and body rules from `wiki-writing-standard.md`.
3. Apply `paper-wiki-language`: write natural Chinese research-wiki prose, avoid machine-translation headings, and keep terminology stable.
4. Preserve source support status and evidence addresses.
5. Frontmatter `sources:` must stay scan-friendly; the invariant is: frontmatter `sources:` must stay scan-friendly. `references/ pages` use exactly one short source label. For non-reference families, concepts/, derivations/, experiments/, synthesis/, reports/, and opportunities/ may use one or more short source labels for materially used papers. Put the full clickable PDF URI in `## 原文与证据入口` as a Markdown link displayed as `原论文 PDF`, pointing at `obsidian://open?vault=<vault>&file=_paper_source%2Fraw%2F<slug>%2Fpaper.pdf` (path `_paper_source/raw/<slug>/paper.pdf`, no `papers/` segment); put the full clickable PDF URI in `## 原文与证据入口`, not in properties. Do not write Markdown links, `[[...]]` wikilinks, `_paper_source/`, legacy `_epi/`, PDF paths, DOI/arXiv URLs, metadata paths, MinerU paths, or figure paths in frontmatter `sources`. Do not write `[[...]]` wikilinks to `_paper_source/` from frontmatter or formal-page body links.
6. Add Obsidian wikilinks from new pages only to existing formal pages in `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, or `opportunities/`; put internal evidence paths in URI, file URL, or code/plain text form.
7. Add `relationships:` frontmatter entries only when direction and type are clear.
8. Keep formula and figure claims tied to formula or figure evidence.
9. Write or update `final-source-review.json`.
10. Run `workflows/check-wiki.md` after writing as the post-task check.

## Tracking

Update the wiki tracking surface when the target vault contract expects it:

- update manifest / `.manifest.json` with source paths, hashes, and pages written
- update `index.md` for created or materially updated pages
- append a concise `log.md` entry
- refresh `hot.md` with the conceptual change, not a file list

Write `_paper_source/staging/papers/<paper-slug>/paper-wiki-record-request.json` when formal pages and `final-source-review.json` are ready for Paper Source record. The request must include `schema_version: paper-wiki-record-request-v1`, `automation_mode: ask`, final page relative paths and sha256 hashes, `final-source-review.json` path/hash, `human_approval.approved_by`, and the command `record-wiki-ingest --from-paper-wiki-request _paper_source/staging/papers/<paper-slug>/paper-wiki-record-request.json`. Paper Wiki writes the request artifact; Paper Source consumes it. Tell the user whether the current agent can continue with that Paper Source command or whether a safety gate still blocks it.

Stop when source artifacts are missing and point back to Paper Source `paper-gate`.

## QMD Compatibility

QMD is an optional accelerator after the source-first plan is built from the Markdown vault. Use QMD only to improve lookup and discoverability. After writing or staging pages, run or recommend `qmd update` and `qmd embed` when QMD is installed and the target vault allows it. If QMD is unavailable, stale, slow, or noisy, fallback to manifest, `.manifest.json`, `index.md`, `log.md`, `hot.md`, and direct file search; do not block on qmd query.

## Post-Task Check

Run `workflows/check-wiki.md` after writing. The post-task check must cover broken wikilinks, orphan pages, missing frontmatter, provenance drift, QMD refresh status, stale tracking files, staged review state, `final-source-review.json`, and whether Paper Source `record-wiki-ingest` remains.
