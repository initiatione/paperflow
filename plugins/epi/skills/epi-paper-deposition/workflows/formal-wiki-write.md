# Formal Wiki Write

Use this workflow when `wiki_deposition_task.json` is ready but the normal PRW entrypoint cannot be used directly. For user-facing formal paper wiki work, prefer `$paper-research-wiki`; this file is the EPI compatibility adapter runbook.

## Load Inputs

Read the required EPI source bundle and target vault contract before writing:

- `_epi/staging/papers/<slug>/wiki_deposition_task.json`
- `_epi/staging/papers/<slug>/wiki-ingest-brief.json`
- `_epi/staging/papers/<slug>/briefs/reading-report.md`
- `_epi/raw/papers/<slug>/metadata.json`
- `_epi/raw/papers/<slug>/paper.pdf`
- `_epi/raw/papers/<slug>/mineru/<slug>.md`
- `_epi/raw/papers/<slug>/mineru/paper.tex`
- `_epi/raw/papers/<slug>/mineru/images/*`
- `_epi/raw/papers/<slug>/mineru/mineru-manifest.json`
- target vault `AGENTS.md` and `_meta/*` contract files

Reader and critic files reduce reading cost when present. They are evidence aids, not source authority.

## Use Wiki Skill Stack

Use the PRW and obsidian-wiki layer explicitly:

If the `prw` plugin package (`plugins/PRW`) is available, it is the plugin-level paper wiki assistant. Invoke `$paper-research-wiki` with natural actions such as `提取这些论文`, `检测 wiki 库`, `更新 wiki 库`, or `重link`; its internal workflows handle source-first deposition, provenance, lint, staged review, taxonomy, and relinking.

- `llm-wiki` for source-first knowledge compilation.
- `wiki-context-pack` before writing, so related pages are read first.
- `wiki-ingest` for staged page creation and merge decisions.
- `wiki-lint` before record or stage commit.
- `wiki-stage-commit` for human-reviewed promotion.
- `wiki-status` and `wiki-query` for existing knowledge and staged pages.
- `wiki-provenance` for support labels, evidence addresses, and final-source-review closure.
- `tag-taxonomy` for tags and aliases.

After first staged pages exist, `wiki-synthesize`, `wiki-dedup`, and `cross-linker` may improve graph quality.

Do not initialize, reset, or repair vault structure in this workflow. If the target vault is missing `_epi/`, `_meta/`, `.obsidian`, or the formal page roots, switch to EPI `wiki-setup` first.

## Page Families

Choose final page families under the target vault contract:

- `references/`: single-paper evidence pages.
- `concepts/`: reusable concepts, variables, assumptions, method variants, and conditions of use.
- `derivations/`: equations, variable definitions, derivation chain, assumptions, and cross-paper differences.
- `experiments/`: platforms, settings, baselines, metrics, environments, and reproducibility risks.
- `synthesis/`: cross-paper matrices, complementarity, contradictions, and evidence strength.
- `reports/`: low-burden Chinese reading entrypoints.
- `opportunities/`: research gaps linked to paper limitations and verifiable experiments.

Do not create generic `entities/`, `skills/`, `journal/`, or `projects/` pages for formal EPI deposition unless the target vault contract explicitly routes a secondary copy there.

## Frontmatter

Every formal page must include:

```yaml
---
title:
category:
page_family:
tags:
aliases:
sources:
summary:
provenance:
  extracted:
  inferred:
  ambiguous:
base_confidence:
lifecycle:
lifecycle_changed:
tier:
created:
updated:
---
```

Initial `lifecycle` is `draft` or `review-needed`; do not mark pages `source-reviewed` or `verified` until source reread, formula/figure review, `wiki-lint`, and human stage review have passed.

Frontmatter `sources` must contain only Obsidian wikilinks to original paper PDFs, each displayed as the paper slug: `"[[_epi/raw/papers/<slug>/paper.pdf|<slug>]]"`. Put metadata, MinerU Markdown/TeX, DOI/arXiv URLs, figure paths, and other evidence details in the page body or Provenance section instead of frontmatter `sources`.

## Quality Gates

Before `record-wiki-ingest` or `wiki-stage-commit`, check:

- Required frontmatter fields are present and non-empty where applicable.
- Frontmatter `sources` is PDF-only and every PDF link is displayed as the paper slug.
- Formal pages use Obsidian wikilinks for internal knowledge.
- `_epi/` and other internal roots must not enter the formal graph as pages.
- Do not use fenced formula blocks such as ` ```math`, ` ```tex`, or ` ```latex`; use `$...$` or `$$...$$`.
- `derivations/` pages include variable definitions and a derivation chain.
- `references/` pages include model or method, formulas, experiments, metrics, and limitations.
- `synthesis/` pages include a cross-paper comparison matrix.
- `concepts/` pages are reusable concept pages, not one paper retitled as a concept.

If lint fails, repair staged pages before recording ingest completion.
