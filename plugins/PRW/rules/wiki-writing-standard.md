# PRW Wiki Writing Standard

This rule is mandatory for every PRW formal paper wiki write. It adapts Ar9av/obsidian-wiki `wiki-ingest`, `llm-wiki`, `wiki-lint`, `cross-linker`, `tag-taxonomy`, and `wiki-update` into the paper research wiki contract.

Formal page prose must also follow `../skills/paper-wiki-language/SKILL.md`. Read that skill before drafting, rewriting, or materially repairing formal pages.

A PRW task is not complete until formal pages, tracking files, graph links, taxonomy, provenance, language gate, QMD freshness, and EPI record readiness have been checked or explicitly reported as skipped with reason.

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
title: <full paper title>
category: references
page_family: references
tags: ["domain/<d>", "method/<m>", "task/<t>", "topic/<topic>", "evidence/<tier>"]
aliases: ["<ACRONYM>", "<full method name>", "<descriptive name>"]
relationships:
  - target: "[[concepts/related-concept]]"
    type: uses
sources: ["[<full paper title>](obsidian://open?vault=<vault>&file=_epi%2Fraw%2F<slug>%2Fpaper.pdf)"]
summary: "<year> <venue> <type>，提出 <ACRONYM>：<one-line mechanism>。"
provenance:
  extracted:
    - "<directly from source bundle: metadata, MinerU md/tex, images>"
  inferred:
    - "<cross-page or reuse inference>"
  ambiguous:
    - "<OCR noise, author future-work, data/code availability>"
base_confidence: 0.65
lifecycle: review-needed
lifecycle_changed: 2026-06-04
tier: supporting
created: 2026-06-04
updated: 2026-06-04
---

# <ACRONYM>：<one-sentence thesis that adds an angle beyond the title>

<opening paragraph: the problem the paper sets, and its core design idea, in curator voice>

## 证据钩子
## 原文与证据入口
## 问题设定
## 核心机制
## 实验设置与证据边界
## 局限与未覆盖问题
## Provenance
```

The template above shows the `references/` shape. For the full section-by-section references contract — body skeleton, depth/precision rules (mechanism-contrast, graph integration), stance vocabulary, provenance schema, and a self-check — follow `../skills/paper-research-wiki/references/references-page-anatomy.md`. The other families (`concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, `opportunities/`) keep the required frontmatter fields but use family-specific source cardinality and body structure per `../skills/paper-wiki-language/SKILL.md`.

`tags:` uses five facets: `domain/`, `method/` (one or more), `task/`, `topic/` (optional), and a required `evidence/` tier (`simulation`, `hardware-in-the-loop`, `pool-trial`, `sea-trial`, or `real-data-driven-simulation`). The `evidence/` facet is what prevents a simulation paper from being cited as field-proven.

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

`sources:` contains clickable original-paper PDF links only. `references/ pages` use exactly one clickable original-paper PDF link. Canonical form: a Markdown link displayed with the paper title, pointing at `obsidian://open?vault=<vault>&file=_epi%2Fraw%2F<slug>%2Fpaper.pdf` — this is what the reviewed exemplar pages use and what renders clickable in the Obsidian properties panel. The path is `_epi/raw/<slug>/paper.pdf`, with no `papers/` segment. The legacy wikilink form `"[[_epi/raw/<slug>/paper.pdf|<slug>]]"` remains accepted for EPI-generated pages. `concepts/, derivations/, experiments/, synthesis/, reports/, and opportunities/` use one or more clickable original-paper PDF links for the papers the page materially uses. Do not use plain path text, an alias such as `原论文 PDF`, or metadata/MinerU/DOI/arXiv entries in frontmatter `sources`; put those in the body evidence section or the Provenance section.

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

## QMD Compatibility

QMD is a secondary retrieval/indexing layer, not the source of truth. Prefer the Markdown vault, target vault contract, manifest or `.manifest.json`, `index.md`, `log.md`, `hot.md`, and direct file search when deciding what exists or what should be changed.

After PRW writes, repairs, relinks, or stages formal pages, refresh QMD when it is installed and in scope with `qmd update` and `qmd embed`. If QMD is unavailable, stale, slow, or returns noisy results, fallback to manifest, index files, and direct search, and do not block on qmd query.

## Link Repair Gate

When repairing link chaos, check broken wikilinks, orphan pages, ambiguous aliases, duplicate concept owners, forbidden internal links, stale redirects, fragmented tag clusters, and relationship direction problems. Prefer canonical page owners and aliases over mass rewriting. Do not hide unsupported claims merely to make the graph cleaner.

## Quality Gate

Before telling the user a wiki write is ready for EPI `record-wiki-ingest`, run a post-task check for:

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
- QMD refresh status when QMD is installed and in scope
- whether the next EPI/PRW action is explicit

Only after the formal pages and `final-source-review.json` pass this gate should PRW tell the user the remaining EPI recording step.

## Completion Report

Do not end with only "done". Report pages created or updated, links/tags/aliases repaired, tracking files updated, QMD refreshed / skipped / failed with fallback, remaining risks, and the next EPI/PRW action.
