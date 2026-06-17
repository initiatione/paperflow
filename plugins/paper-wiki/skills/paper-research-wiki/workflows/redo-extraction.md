# Redo Extraction

Use when the user asks Paper Wiki to 重做, 重新提取, 更详细提取, 批量重提取, redo, redo extraction, deep extraction, source-map-first, or source-map-grounded extraction. This is deliberate re-deposition: source reread -> compare existing pages -> graph-aware rewrite or staged patch -> post-task check -> Paper Source record readiness.

Targets may be a single paper (slug, title, DOI, arXiv id, selected page, or selected handoff) or a batch (slugs, ready handoffs, a run, or topic/status filter). If ambiguous, ask one short question; `默认` means use the ready paper or batch implied by the current Paper Source handoff.

If the paper is a survey/review, route `references/` writing through `../references/survey-page-anatomy.md`, not the method-paper spine. Surveys may spawn taxonomy `concepts/`, landscape `synthesis/`, and gap `opportunities/`; do not create `derivations/` from borrowed formulas or `experiments/` from second-hand results.

## Preflight

1. Read `../../../rules/wiki-writing-standard.md` and `../../paper-wiki-language/SKILL.md`.
2. Resolve the target vault; read `AGENTS.md`, `_meta/schema.md`, `_meta/taxonomy.md`, and `_meta/directory-structure.md` when present.
3. Locate `_paper_source/staging/papers/*/wiki-ingest-brief.json` as the only Paper Source-to-Paper Wiki handoff contract.
4. Check `paper-gate` or handoff status; stop if source artifacts are missing or human approval is the only unresolved gate.
5. Read existing formal pages named by prior `wiki-ingest-record.json`, `final-source-review.json`, page `sources:`, or search hits in `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.

## Source Reread And Plan

Source reread is mandatory; never redo from wiki text alone. For each selected paper reread metadata, MinerU Markdown, images, MinerU manifest, `figure-index.json`, `formula-index.json`, reading report, `wiki-ingest-brief.json`, and prior `final-source-review.json` when present.

MinerU Markdown is primary for formulas, notation, method context, and prose. Only fall back to the PDF, `formula-index.json`, `figure-index.json`, or image evidence when Markdown is missing, wrong, ambiguous, or insufficient. Non-empty `mineru/paper.tex` is only an optional cross-check; reader/critic outputs guide attention but do not replace source reread.

Before writing, classify each touched page as keep, deepen, split, merge, supersede, or delete-proposal. Preserve useful wikilinks, aliases, tags, relationships, support labels, and evidence addresses; surface contradictions and unsupported claims instead of silently deleting them. Prefer a staged patch when identity, lifecycle, claim deletion, or multiple page families are involved. Return selected papers, pages to change, source artifacts reread, risk level, direct-write vs staged patch, and one confirmation. `默认` applies the recommended safe staged plan.

## Graph-Aware Rewrite

Redo work that materially changes formal claims is a material rewrite and graph-aware rewrite. Treat dependent formal pages as one transaction, not isolated markdown edits.

- references/ pages are evidence source nodes; if one changes, inspect dependent `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.
- Find reverse dependencies through backlinks, outlinks, `relationships:`, `sources:`, manifest or `.manifest.json`, prior `final-source-review.json`, previous `wiki-ingest-record.json`, `index.md`, `log.md`, `hot.md`, and direct search.
- Update dependent formal pages when claim/evidence boundaries, formulas, figures/tables, evidence tiers, reusable mechanisms, synthesis conclusions, or opportunity wording change.
- Create new `derivations/` or `concepts/` pages when derived concepts would otherwise remain trapped in one reference page.
- Refresh manifest or `.manifest.json`, `_meta/reference-index.json` when `references/` pages changed, `final-source-review.json`, `index.md`, `log.md`, and `hot.md`; read previous `wiki-ingest-record.json` only as provenance and reverse-dependency evidence.
- This is the formal knowledge maintenance layer: maintain formal page content relationships, content relationship maintenance, claim staleness, split or merge pages, reverse dependencies, evidence-tier drift, derived concepts, derivations, and synthesis.

Report Paper Source record readiness. Paper Wiki records readiness; Paper Source writes or replaces `wiki-ingest-record.json` through `record-wiki-ingest`. If record-ready, write `_paper_source/staging/papers/<paper-slug>/paper-wiki-record-request.json` with `schema_version: paper-wiki-record-request-v1`, `automation_mode: ask`, final page hashes, `final-source-review.json` hash, and `record-wiki-ingest --from-paper-wiki-request ...`; Paper Wiki writes the request artifact; Paper Source consumes it. Do not write human approval; Paper Source owns human approval records and `record-wiki-ingest`.

## Depth And Close

Use requested depth where relevant: theory reconstruction, formula derivation, figure/table evidence, experimental setup, metrics, datasets, baselines, ablations, implementation caveats, limitations, assumptions, reusable concepts, cross-paper contradictions, and research gaps. For surveys, capture review type, coverage/PRISMA signals, taxonomy, per-branch landscape, evidence-tier distribution, and reading map to primary sources via `../references/survey-page-anatomy.md`.

After confirmation, apply `wiki-writing-standard.md` and `paper-wiki-language`; direct-write only when risk is low and the vault allows it, otherwise write staged patch files. Recompute `provenance:` and `base_confidence:` when source mix or claim mix changes, update `relationships:` only when direction/type are clear, and update or recreate `final-source-review.json`.

Run or report `qmd update` and `qmd embed` after confirmed writes or staged patches. QMD is optional: use it as lookup aid only after source reread/page comparison; if unavailable, stale, slow, or noisy, fallback to manifest, `.manifest.json`, `index.md`, `log.md`, `hot.md`, previous `wiki-ingest-record.json`, and direct file search; do not block on qmd query.

Run `workflows/check-wiki.md` after writing as the post-task check. Confirm changed pages, tracking files, `_meta/reference-index.json` freshness and changed-page presence, source-review hashes, broken wikilinks, orphan pages, staged patch state, provenance drift, QMD refresh status, and whether `record-wiki-ingest --from-paper-wiki-request _paper_source/staging/papers/<paper-slug>/paper-wiki-record-request.json` remains.
