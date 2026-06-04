# PRW Wiki Writing Standard

This rule is mandatory for every PRW formal paper wiki write. It adapts Ar9av/obsidian-wiki `wiki-ingest`, `llm-wiki`, `wiki-lint`, `cross-linker`, `tag-taxonomy`, and `wiki-update` into the paper research wiki contract.

Formal page prose must also follow `../skills/paper-wiki-language/SKILL.md`. Read that skill before drafting, rewriting, or materially repairing formal pages.

## Core Rule

Do not summarize papers in isolation. PRW must distill and integrate paper knowledge into the existing wiki graph.

The default decision is merge before create:

1. Read target vault `AGENTS.md` and `_meta/*` contracts when present.
2. Read the wiki inventory from `manifest` or `.manifest.json`, `index.md`, `log.md`, and `hot.md`.
3. Search existing formal pages by title, aliases, tags, references, concepts, methods, datasets, and claims.
4. Update an existing page when it already owns the concept, method, experiment, dataset, or synthesis question.
5. Create a new page only when the knowledge has a distinct durable identity and belongs in an allowed formal page family.

## Page Families

Formal paper pages may be written only to:

- `references/`
- `concepts/`
- `derivations/`
- `experiments/`
- `synthesis/`
- `reports/`
- `opportunities/`

Never write formal graph pages under `_epi/`, `_raw/`, `_staging/`, `_runs/`, `_quarantine/`, `.obsidian/`, or source bundle folders. Staged writes may use the target vault staging contract, but staged pages must still obey the same page template and evidence rules.

## Page Template

Every new or materially rewritten formal page must use this page template shape:

```markdown
---
title: Page Title
category: references
page_family: references
tags: [paper, method]
aliases: [alternate name]
relationships:
  - target: "[[concepts/related-concept]]"
    type: uses
sources: [source-bundle-or-paper-id]
summary: One or two sentences under 200 characters.
provenance:
  extracted: 0.70
  inferred: 0.25
  ambiguous: 0.05
base_confidence: 0.65
lifecycle: draft
lifecycle_changed: 2026-06-04
tier: supporting
created: 2026-06-04T00:00:00Z
updated: 2026-06-04T00:00:00Z
---

# Page Title

One paragraph explaining the page's scope.

## Key Ideas

- Source-grounded claim.
- Synthesis or generalization. ^[inferred]
- Unclear or contested claim. ^[ambiguous]

## Open Questions

- Questions that require more source evidence.

## Sources

- Source paper, EPI bundle, figure, formula, table, or evidence address.
```

Required frontmatter fields:

- `title:`
- `category:`
- `page_family:`
- `tags:`
- `aliases:`
- `relationships:` when a typed relation is known
- `sources:`
- `summary:`
- `provenance:`
- `base_confidence:`
- `lifecycle:`
- `lifecycle_changed:`
- `tier:`
- `created:`
- `updated:`

Do not set `lifecycle: reviewed`, `verified`, or `source-reviewed` automatically. New agent-written pages start as `draft` or `review-needed` unless the target vault contract says otherwise.

## Body Rules

- Write durable knowledge, not per-paper abstracts.
- Prefer short paragraphs and compact bullets over copied source text.
- Write natural Chinese research-wiki prose. Do not leave machine-translated headings, literal English sentence order, or generic academic filler in formal pages.
- Put paper-specific identity, contribution, setup, limitations, and evidence into `references/`.
- Put reusable methods, concepts, formulas, mechanisms, datasets, metrics, or design patterns into the matching family.
- Put cross-paper comparison, contradictions, and research gaps into `synthesis/`, `reports/`, or `opportunities/`.
- Mark inferred claims with `^[inferred]`.
- Mark ambiguous or contested claims with `^[ambiguous]`.
- Keep unsupported claims out of factual prose. If they must be preserved, put them under `Open Questions`.

## Link And Relationship Rules

Every formal page should connect to the graph:

1. Add Obsidian wikilinks to relevant existing pages.
2. Prefer the first natural mention for inline links.
3. Use a `Related` section only when no natural body mention exists.
4. Write `relationships:` frontmatter only when the direction and type are clear.
5. Allowed relationship types are `extends`, `implements`, `contradicts`, `derived_from`, `uses`, `replaces`, and `related_to`.
6. Do not fabricate typed relationships. Use `related_to` or omit the entry when uncertain.

## Tracking Files

After creating or materially updating pages, update the tracking surface expected by the target vault:

- update `manifest` or `.manifest.json` with source ids, hashes, pages created, and pages updated
- update `index.md` entries and summaries
- append a parseable `log.md` operation entry
- refresh `hot.md` with the conceptual change, not a file list

If the vault stages writes, update `index.md`, `log.md`, and `hot.md` immediately while keeping formal page changes under the staging path required by the vault.

## Quality Gate

Before telling the user a wiki write is ready for EPI `record-wiki-ingest`, check for:

- orphan pages created by the write
- broken wikilinks
- missing required frontmatter
- stale or missing `summary:`
- invalid `relationships:` entries or relationship issues
- provenance drift or missing evidence addresses
- language-style drift against `paper-wiki-language`: machine-translation headings, stiff translated prose, terminology drift, or generic AI academic filler
- fragmented tags or aliases against the target taxonomy
- staged writes that still need human review
- missing `final-source-review.json`

Only after the formal pages and `final-source-review.json` pass this gate should PRW tell the user the remaining EPI recording step.
